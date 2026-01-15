"""
Selenium Action Tracker

Utility to wrap Selenium actions and track clicked buttons and filled fields
during script execution. Logs all interactions to the console and returns
structured data about the interactions.
"""

import logging
from typing import List, Dict, Any
from selenium.webdriver.remote.webelement import WebElement
try:
    from .field_extractor import detect_field_type
except ImportError:
    try:
        from utils.field_extractor import detect_field_type
    except ImportError:
        def detect_field_type(info): return info.get('type', 'string')

logger = logging.getLogger(__name__)


class SeleniumActionTracker:
    """
    Wrapper class that tracks all clicks and field interactions
    during Selenium script execution.
    """
    
    def __init__(self):
        self.clicked_elements = []
        self.filled_fields = []
        self.actions_log = []
    
    def _extract_element_info(self, element: WebElement, locator: str, action: str, description: str = "") -> Dict[str, Any]:
        """
        Extract comprehensive information from a WebElement
        
        Args:
            element: The WebElement to extract info from
            locator: The locator string used to find the element
            action: The action type (click, input, etc.)
            description: Optional description
            
        Returns:
            Dictionary with comprehensive element information
        """
        try:
            # Basic info gathered while we still have the element
            tag_name = element.tag_name
            text = element.text[:200] if element.text else ""
            
            info = {
                "action": action,
                "locator": locator,
                "tag_name": tag_name,
                "text": text,
                "description": description,
            }
            
            # Use a consolidated JS block to extract EVERYTHING in one go
            # This is much faster and more resistant to stale element errors
            try:
                driver = element.parent
                all_data = driver.execute_script("""
                    var el = arguments[0];
                    if (!el) return null;
                    
                    function getAttributes(e) {
                        var attrs = {};
                        var common = [
                            "id", "name", "class", "type", "value", "placeholder", "href", 
                            "src", "alt", "title", "aria-label", "aria-describedby", "aria-required",
                            "role", "tabindex", "disabled", "readonly", "required", "maxlength",
                            "minlength", "pattern", "autocomplete", "autofocus", "checked",
                            "selected", "multiple", "accept", "min", "max", "step",
                            "for", "form", "data-testid", "data-qa", "data-cy"
                        ];
                        for (var i = 0; i < common.length; i++) {
                            var val = e.getAttribute(common[i]);
                            if (val !== null && val !== "") attrs[common[i]] = val;
                        }
                        // Also get all data-* attributes
                        for (var i = 0; i < e.attributes.length; i++) {
                            var attr = e.attributes[i];
                            if (attr.name.startsWith('data-')) attrs[attr.name] = attr.value;
                        }
                        return attrs;
                    }

                    function getContext(e) {
                        var context = {
                            label: '',
                            surrounding_text: '',
                            container_heading: '',
                            form_title: '',
                            semantic_purpose: ''
                        };

                        // 1. Better Label Search
                        // a) Label for id
                        if (e.id) {
                            var l = document.querySelector('label[for="' + e.id + '"]');
                            if (l) context.label = l.innerText || l.textContent;
                        }
                        // b) Parent label
                        if (!context.label) {
                            var p = e.parentElement;
                            while (p && p !== document.body) {
                                if (p.tagName === 'LABEL') {
                                    context.label = p.innerText || p.textContent;
                                    break;
                                }
                                p = p.parentElement;
                            }
                        }
                        // c) aria-label or placeholder
                        if (!context.label) context.label = e.getAttribute('aria-label') || e.getAttribute('placeholder') || '';

                        // 2. Headings & Form Context
                        var up = e.parentElement;
                        var depth = 0;
                        while (up && up !== document.body && depth < 10) {
                            // Check for headings in this container
                            var h = up.querySelectorAll('h1, h2, h3, h4, h5, h6, legend');
                            if (h.length > 0 && !context.container_heading) {
                                context.container_heading = h[0].innerText || h[0].textContent;
                            }
                            // Check for form title
                            if (up.tagName === 'FORM' || up.classList.contains('form')) {
                                var fh = up.querySelector('h1, h2, h3, .form-title');
                                if (fh) context.form_title = fh.innerText || fh.textContent;
                            }
                            up = up.parentElement;
                            depth++;
                        }

                        // 3. Nearby instructions/text
                        var prev = e.previousElementSibling;
                        if (prev && prev.innerText) context.surrounding_text = prev.innerText.substring(0, 200);

                        return context;
                    }

                    function getOptions(e) {
                        var options = [];
                        function pushOption(node) {
                            if (!node || node.nodeType !== 1) return;
                            var t = node.innerText || node.textContent || '';
                            if (!t.trim() && !node.getAttribute('value') && !node.id) return;
                            options.push({
                                text: t.trim(),
                                value: node.getAttribute('data-value') || node.getAttribute('value') || '',
                                id: node.id || '',
                                selected: node.getAttribute('aria-selected') === 'true' || 
                                          (node.classList && (node.classList.contains('selected') || node.classList.contains('is-selected'))) ||
                                          node.getAttribute('aria-checked') === 'true'
                            });
                        }

                        // 1. Native Select
                        if (e.tagName === 'SELECT') {
                            for (var i = 0; i < e.options.length; i++) {
                                options.push({
                                    value: e.options[i].value,
                                    text: e.options[i].text,
                                    selected: e.options[i].selected
                                });
                            }
                            return options;
                        }

                        // 2. Custom Dropdown Heuristics
                        var role = (e.getAttribute('role') || '').toLowerCase();
                        var cls = (e.className || '');
                        var id = (e.id || '');
                        var isOption = role === 'option' || role === 'menuitem' || 
                                      cls.indexOf('option') !== -1 || id.indexOf('option') !== -1 ||
                                      e.tagName === 'LI';
                        var isControl = role === 'combobox' || role === 'haspopup' || role === 'select' ||
                                       cls.indexOf('control') !== -1 || cls.indexOf('select') !== -1 ||
                                       cls.indexOf('dropdown') !== -1;

                        if (isOption || isControl) {
                            // A) Check aria-controls/owns (Standard ARIA)
                            var controls = e.getAttribute('aria-controls') || e.getAttribute('aria-owns');
                            if (controls) {
                                var menu = document.getElementById(controls);
                                if (menu) {
                                    var nodes = menu.querySelectorAll('[role="option"], [role="menuitem"], .option, li');
                                    for (var i=0; i<nodes.length; i++) pushOption(nodes[i]);
                                }
                            }

                            // B) Parent Container Search
                            if (options.length === 0) {
                                var p = e.parentElement;
                                var depth = 0;
                                while (p && p !== document.body && depth < 5) {
                                    var pr = (p.getAttribute('role') || '').toLowerCase();
                                    var pc = (p.className || '');
                                    if (pr.indexOf('listbox') !== -1 || pr.indexOf('menu') !== -1 || 
                                        pc.indexOf('listbox') !== -1 || pc.indexOf('menu') !== -1 ||
                                        pc.indexOf('dropdown') !== -1 ||
                                        p.querySelectorAll('[role="option"], .option').length > 1) {
                                        var nodes = p.querySelectorAll('[role="option"], [role="menuitem"], .option, li');
                                        for (var i=0; i<nodes.length; i++) pushOption(nodes[i]);
                                        break;
                                    }
                                    p = p.parentElement; depth++;
                                }
                            }

                            // C) React-Select prefix-based search
                            if (id.indexOf('react-select-') === 0) {
                                var prefix = id.split('-option')[0].split('-control')[0].split('-list')[0].split('-menu')[0];
                                if (prefix) {
                                    // Search for options or menus sharing this prefix
                                    var related = document.querySelectorAll('[id^="' + prefix + '"]');
                                    for (var i=0; i<related.length; i++) {
                                        var r = related[i];
                                        if (r.id.indexOf('-option') !== -1 || r.getAttribute('role') === 'option') {
                                            pushOption(r);
                                        } else if (r.id.indexOf('-menu') !== -1 || r.id.indexOf('-list') !== -1) {
                                            var sub = r.querySelectorAll('[role="option"], .option, li');
                                            for (var j=0; j<sub.length; j++) pushOption(sub[j]);
                                        }
                                    }
                                }
                            }

                            // D) Global Fallback for visible menus (useful for Portals)
                            if (options.length === 0) {
                                var globalMenus = document.querySelectorAll('[role="listbox"], [role="menu"], .select-options, .dropdown-menu');
                                for (var i=0; i<globalMenus.length; i++) {
                                    // Only consider if not explicitly hidden
                                    var style = window.getComputedStyle(globalMenus[i]);
                                    if (style.display !== 'none' && style.visibility !== 'hidden') {
                                        var nodes = globalMenus[i].querySelectorAll('[role="option"], .option, li');
                                        for (var j=0; j<nodes.length; j++) pushOption(nodes[j]);
                                        if (options.length > 0) break;
                                    }
                                }
                            }
                        }

                        // Deduplicate by text and value
                        var seen = {};
                        return options.filter(function(o) {
                            var k = (o.text || '') + '||' + (o.value || '') + '||' + (o.id || '');
                            if (seen[k]) return false;
                            seen[k] = true;
                            return true;
                        });
                    }

                    return {
                        attributes: getAttributes(el),
                        context: getContext(el),
                        properties: {
                            tagName: el.tagName,
                            outerHTML: el.outerHTML ? el.outerHTML.substring(0, 1000) : '',
                            value: el.value || '',
                            className: el.className
                        },
                        options: getOptions(el)
                    };
                """, element)
                
                if all_data:
                    info["attributes"] = all_data.get('attributes', {})
                    info["context"] = all_data.get('context', {})
                    info["properties"] = all_data.get('properties', {})
                    if all_data.get('options'):
                        info["dropdown_options"] = all_data['options']
                    
                    # Synthesize "Semantic Role" and "Exact Purpose"
                    attrs = info["attributes"]
                    ctx = info["context"]
                    
                    # Detect semantic type
                    raw_type = attrs.get('type', '')
                    role = attrs.get('role', '').lower()
                    
                    semantic_type = detect_field_type({
                        **attrs,
                        "tag": tag_name,
                        "label": ctx.get('label', ''),
                        "id": attrs.get('id', ''),
                        "name": attrs.get('name', '')
                    })
                    
                    # Special handling for Options/Buttons in a dropdown
                    if role == 'option' or 'option' in attrs.get('class', '') or tag_name == 'li':
                        semantic_type = "dropdown_option"
                    elif role == 'combobox' or 'select' in attrs.get('class', ''):
                        semantic_type = "select"

                    info["semantic_type"] = semantic_type
                    
                    # Determine Purpose
                    purpose = ""
                    # 1. Direct label or placeholder
                    if ctx.get('label'):
                        purpose = ctx['label'].strip()
                    elif attrs.get('placeholder'):
                        purpose = attrs['placeholder']
                    
                    # 2. For options: the text of the option is the value, but purpose is the question
                    if semantic_type == "dropdown_option":
                        # If we have a container heading, that's likely the question
                        if ctx.get('container_heading'):
                            purpose = f"Choice for '{ctx['container_heading']}'"
                        elif ctx.get('label'):
                             purpose = f"Choice for '{ctx['label']}'"
                        else:
                            purpose = f"Option: {info['text']}"
                    
                    # 3. Fallbacks
                    if not purpose:
                        if attrs.get('aria-label'):
                            purpose = attrs['aria-label']
                        elif ctx.get('container_heading'):
                            purpose = f"Input under {ctx['container_heading']}"
                        else:
                            purpose = info["text"] or attrs.get('name') or attrs.get('id') or "unknown field"

                    info["exact_purpose"] = purpose
                    info["role_description"] = f"A {semantic_type} ({tag_name}) used for {purpose}"
                    
            except Exception as e:
                logger.warning(f"Could not extract enhanced properties via JS: {str(e)}")
                # Falling back to basic attributes if JS fails
                info["attributes"] = {}
                for attr in ["id", "name", "class", "type", "placeholder"]:
                    val = element.get_attribute(attr)
                    if val: info["attributes"][attr] = val

            return info
            
        except Exception as e:
            logger.error(f"Error extracting element info: {str(e)}")
            return {
                "action": action,
                "locator": locator,
                "tag_name": "unknown",
                "text": "",
                "description": description,
                "error": str(e)
            }
        
    def track_click(self, element: WebElement, locator: str, description: str = ""):
        """
        Track a button/element click
        
        Args:
            element: The WebElement that was clicked
            locator: The locator string used to find the element
            description: Optional description of the element
        """
        try:
            # Get comprehensive element information
            element_info = self._extract_element_info(element, locator, "click", description)
            
            self.clicked_elements.append(element_info)
            self.actions_log.append(element_info)
            
            # Log to console
            logger.info(f"[CLICK] {locator} | Tag: {element_info.get('tag_name', 'unknown')} | Purpose: {element_info.get('exact_purpose', 'unknown')}")
            print(f"[CLICK] {locator} | Tag: {element_info.get('tag_name', 'unknown')} | Purpose: {element_info.get('exact_purpose', 'unknown')}")
            
        except Exception as e:
            logger.error(f"Error tracking click for {locator}: {str(e)}")
    
    def track_field_input(self, element: WebElement, locator: str, value: str, description: str = ""):
        """
        Track a field input/fill action
        
        Args:
            element: The WebElement that was filled
            locator: The locator string used to find the element
            value: The value that was entered
            description: Optional description of the field
        """
        try:
            # Get comprehensive element information
            field_info = self._extract_element_info(element, locator, "input", description)
            field_info["input_value"] = value
            
            self.filled_fields.append(field_info)
            self.actions_log.append(field_info)
            
            # Log to console (mask sensitive data)
            masked_value = "*" * len(value) if len(value) > 0 else ""
            logger.info(f"[INPUT] {locator} | Type: {field_info.get('semantic_type', 'unknown')} | Purpose: {field_info.get('exact_purpose', 'unknown')}")
            print(f"[INPUT] {locator} | Type: {field_info.get('semantic_type', 'unknown')} | Purpose: {field_info.get('exact_purpose', 'unknown')}")
            
        except Exception as e:
            logger.error(f"Error tracking input for {locator}: {str(e)}")
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of all tracked actions
        
        Returns:
            Dictionary with clicked elements, filled fields, and full action log
        """
        return {
            "clicked_elements": self.clicked_elements,
            "filled_fields": self.filled_fields,
            "actions_log": self.actions_log,
            "summary": {
                "total_clicks": len(self.clicked_elements),
                "total_inputs": len(self.filled_fields),
                "total_actions": len(self.actions_log)
            }
        }
    
    def print_summary(self):
        """Print a formatted summary to console"""
        print("\n" + "="*80)
        print("SELENIUM ACTION TRACKING SUMMARY")
        print("="*80)
        
        print(f"\nTotal Actions: {len(self.actions_log)}")
        print(f"  - Clicks: {len(self.clicked_elements)}")
        print(f"  - Field Inputs: {len(self.filled_fields)}")
        
        if self.clicked_elements:
            print("\n" + "-"*80)
            print("CLICKED ELEMENTS (COMPREHENSIVE DATA):")
            print("-"*80)
            for idx, elem in enumerate(self.clicked_elements, 1):
                print(f"\n{idx}. {elem['locator']}")
                print(f"   Tag: {elem.get('tag_name', 'unknown')}")
                
                # Show semantic information
                if elem.get('exact_purpose'):
                    print(f"   Purpose: {elem['exact_purpose']}")
                if elem.get('role_description'):
                    print(f"   Role: {elem['role_description']}")
                
                # Show text if available
                if elem.get('text'):
                    print(f"   Text: {elem['text']}")
                
                # Show all attributes
                if elem.get('attributes'):
                    print(f"   \n   HTML Attributes:")
                    for attr_name, attr_value in elem['attributes'].items():
                        if attr_value:  # Only show non-empty values
                            print(f"      {attr_name}: {attr_value}")
                
                # Show context
                if elem.get('context'):
                    print(f"   \n   Page Context:")
                    for k, v in elem['context'].items():
                        if v: print(f"      {k}: {v}")
                
                # Show dropdown options if available
                if elem.get('dropdown_options'):
                    print(f"   \n   Dropdown Options ({len(elem['dropdown_options'])} found):")
                    for opt in elem['dropdown_options'][:10]:
                        print(f"      - {opt.get('text', 'No Text')} (Value: {opt.get('value', 'None')})")
                    if len(elem['dropdown_options']) > 10:
                        print(f"      ... and {len(elem['dropdown_options']) - 10} more")
        
        if self.filled_fields:
            print("\n" + "-"*80)
            print("FILLED FIELDS (COMPREHENSIVE DATA):")
            print("-"*80)
            for idx, field in enumerate(self.filled_fields, 1):
                print(f"\n{idx}. {field['locator']}")
                print(f"   Tag: {field.get('tag_name', 'unknown')}")
                print(f"   Semantic Type: {field.get('semantic_type', 'unknown')}")
                
                if field.get('exact_purpose'):
                    print(f"   Purpose: {field['exact_purpose']}")
                
                print(f"   Input Value: {'*' * len(str(field.get('input_value', '')))}")
                
                # Show all attributes
                if field.get('attributes'):
                    print(f"   \n   HTML Attributes:")
                    for attr_name, attr_value in field['attributes'].items():
                        if attr_value:
                            print(f"      {attr_name}: {attr_value}")
                
                # Show context
                if field.get('context'):
                    print(f"   \n   Page Context:")
                    for k, v in field['context'].items():
                        if v: print(f"      {k}: {v}")
                
                # Show dropdown options if available
                if field.get('dropdown_options'):
                    print(f"   \n   Dropdown Options ({len(field['dropdown_options'])} found):")
                    for opt in field['dropdown_options'][:10]:
                        print(f"      - {opt.get('text', 'No Text')} (Value: {opt.get('value', 'None')})")
                    if len(field['dropdown_options']) > 10:
                        print(f"      ... and {len(field['dropdown_options']) - 10} more")
        
        print("\n" + "="*80 + "\n")


class TrackedHelper:
    """
    Drop-in replacement for Selenium helper class that tracks all actions.
    Can be used to replace the original helper in user scripts.
    """
    
    def __init__(self, driver, tracker: SeleniumActionTracker, locators_dict: Dict[str, tuple]):
        """
        Initialize tracked helper
        
        Args:
            driver: Selenium WebDriver instance
            tracker: SeleniumActionTracker instance to log actions
            locators_dict: Dictionary mapping locator names to (By.X, "value") tuples
        """
        self.driver = driver
        self.tracker = tracker
        self.locators = locators_dict
    
    def click(self, locator_key: str, description: str = ""):
        """
        Click an element and track the action
        
        Args:
            locator_key: Key from locators dictionary
            description: Optional description of the action
        """
        if locator_key not in self.locators:
            logger.error(f"Locator '{locator_key}' not found in locators dictionary")
            return
        
        by_type, value = self.locators[locator_key]
        element = self.driver.find_element(by_type, value)
        element.click()
        
        self.tracker.track_click(element, locator_key, description)
    
    def send_keys(self, locator_key: str, text: str, description: str = ""):
        """
        Send keys to an element and track the action
        
        Args:
            locator_key: Key from locators dictionary
            text: Text to send to the element
            description: Optional description of the field
        """
        if locator_key not in self.locators:
            logger.error(f"Locator '{locator_key}' not found in locators dictionary")
            return
        
        by_type, value = self.locators[locator_key]
        element = self.driver.find_element(by_type, value)
        element.send_keys(text)
        
        self.tracker.track_field_input(element, locator_key, text, description)
    
    def find_element(self, locator_key: str):
        """
        Find an element using locator key
        
        Args:
            locator_key: Key from locators dictionary
            
        Returns:
            WebElement instance
        """
        if locator_key not in self.locators:
            raise ValueError(f"Locator '{locator_key}' not found in locators dictionary")
        
        by_type, value = self.locators[locator_key]
        return self.driver.find_element(by_type, value)
