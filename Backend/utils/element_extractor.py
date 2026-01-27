"""
Element Information Extractor

Extracts comprehensive information from Selenium WebElements including
attributes, context, dropdown options, and semantic analysis.

This module breaks down the massive 324-line _extract_element_info method
into focused, testable functions.
"""

import logging
from typing import Dict, Any, List, Optional
from selenium.webdriver.remote.webelement import WebElement

# Try to import detect_field_type
try:
    from .field_extractor import detect_field_type
except ImportError:
    try:
        from utils.field_extractor import detect_field_type
    except ImportError:
        def detect_field_type(info: Dict) -> str:
            return info.get('type', 'string')

logger = logging.getLogger(__name__)

# Constants
MAX_TEXT_LENGTH = 200
MAX_HTML_LENGTH = 1000
MAX_CONTEXT_DEPTH = 10
MAX_DROPDOWN_DEPTH = 5
MAX_OPTIONS_TO_DISPLAY = 10

def extract_basic_info(element: WebElement, locator: str, action: str, description: str = "") ->  Dict[str, Any]:
    """
    Extract basic information from a WebElement.

    Args:
        element: The WebElement to extract from
        locator: Locator string used to find the element
        action: Action type (click, input, etc.)
        description: Optional description

    Returns:
        Dictionary with basic element info
    """
    try:
        tag_name = element.tag_name
        text = element.text[:MAX_TEXT_LENGTH] if element.text else ""

        info = {
            "action": action,
            "locator": locator,
            "tag_name": tag_name,
            "text": text,
            "description": description,
            "page_url": "",
            "page_title": ""
        }

        # Extract window info
        try:
            info["page_url"] = element.parent.current_url
            info["page_title"] = element.parent.title
        except Exception:
            pass

        return info
    except Exception as e:
        logger.error(f"Error extracting basic info: {e}")
        return {
            "action": action,
            "locator": locator,
            "tag_name": "unknown",
            "text": "",
            "description": description,
            "error": str(e)
        }

def extract_attributes_via_js(element: WebElement) -> Dict[str, str]:
    """
    Extract HTML attributes from element using JavaScript.

    Uses a consolidated JS block for efficiency and stale-element resistance.

    Args:
        element: WebElement to extract attributes from

    Returns:
        Dictionary of attribute name/value pairs
    """
    try:
        driver = element.parent
        attributes = driver.execute_script("""
            var el = arguments[0];
            if (!el) return {};

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
                var val = el.getAttribute(common[i]);
                if (val !== null && val !== "") attrs[common[i]] = val;
            }

            // Also get all data-* attributes
            for (var i = 0; i < el.attributes.length; i++) {
                var attr = el.attributes[i];
                if (attr.name.startsWith('data-')) {
                    attrs[attr.name] = attr.value;
                }
            }

            return attrs;
        """, element)

        return attributes or {}
    except Exception as e:
        logger.warning(f"Could not extract attributes via JS: {e}")
        # Fallback to Selenium API
        try:
            attrs = {}
            for attr in ["id", "name", "class", "type", "placeholder"]:
                val = element.get_attribute(attr)
                if val:
                    attrs[attr] = val
            return attrs
        except Exception:
            return {}

def extract_context_via_js(element: WebElement) -> Dict[str, str]:
    """
    Extract contextual information (labels, headings, surrounding text).

    Args:
        element: WebElement to extract context from

    Returns:
        Dictionary with label, headings, form title, etc.
    """
    try:
        driver = element.parent
        context = driver.execute_script("""
            var el = arguments[0];
            if (!el) return {};

            var context = {
                label: '',
                surrounding_text: '',
                container_heading: '',
                form_title: '',
                semantic_purpose: ''
            };

            // 1. Better Label Search
            // a) Label for id
            if (el.id) {
                var l = document.querySelector('label[for="' + el.id + '"]');
                if (l) context.label = l.innerText || l.textContent;
            }
            // b) Parent label
            if (!context.label) {
                var p = el.parentElement;
                while (p && p !== document.body) {
                    if (p.tagName === 'LABEL') {
                        context.label = p.innerText || p.textContent;
                        break;
                    }
                    p = p.parentElement;
                }
            }
            // c) aria-label or placeholder
            if (!context.label) {
                context.label = el.getAttribute('aria-label') || el.getAttribute('placeholder') || '';
            }

            // 2. Headings & Form Context
            var up = el.parentElement;
            var depth = 0;
            while (up && up !== document.body && depth < """ + str(MAX_CONTEXT_DEPTH) + """) {
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
            var prev = el.previousElementSibling;
            if (prev && prev.innerText) {
                context.surrounding_text = prev.innerText.substring(0, """ + str(MAX_TEXT_LENGTH) + """);
            }

            return context;
        """, element)

        return context or {}
    except Exception as e:
        logger.warning(f"Could not extract context via JS: {e}")
        return {}

def extract_dropdown_options_via_js(element: WebElement) -> List[Dict[str, Any]]:
    """
    Extract dropdown/select options from element.

    Handles:
    - Native <select> elements
    - Custom dropdowns (React-Select, Material-UI, etc.)
    - ARIA-based dropdowns

    Args:
        element: WebElement (select or dropdown trigger)

    Returns:
        List of option dictionaries with text, value, selected status
    """
    try:
        driver = element.parent
        options = driver.execute_script("""
            var el = arguments[0];
            if (!el) return [];

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
                              (node.classList && (node.classList.contains('selected') ||
                               node.classList.contains('is-selected'))) ||
                              node.getAttribute('aria-checked') === 'true'
                });
            }

            // 1. Native Select
            if (el.tagName === 'SELECT') {
                for (var i = 0; i < el.options.length; i++) {
                    options.push({
                        value: el.options[i].value,
                        text: el.options[i].text,
                        selected: el.options[i].selected
                    });
                }
                return options;
            }

            // 2. Custom Dropdown Heuristics
            var role = (el.getAttribute('role') || '').toLowerCase();
            var cls = (el.className || '');
            var id = (el.id || '');
            var isOption = role === 'option' || role === 'menuitem' ||
                          cls.indexOf('option') !== -1 || id.indexOf('option') !== -1 ||
                          el.tagName === 'LI';
            var isControl = role === 'combobox' || role === 'haspopup' || role === 'select' ||
                           cls.indexOf('control') !== -1 || cls.indexOf('select') !== -1 ||
                           cls.indexOf('dropdown') !== -1;

            if (isOption || isControl) {
                // A) Check aria-controls/owns (Standard ARIA)
                var controls = el.getAttribute('aria-controls') || el.getAttribute('aria-owns');
                if (controls) {
                    var menu = document.getElementById(controls);
                    if (menu) {
                        var nodes = menu.querySelectorAll('[role="option"], [role="menuitem"], .option, li');
                        for (var i=0; i<nodes.length; i++) pushOption(nodes[i]);
                    }
                }

                // B) Parent Container Search
                if (options.length === 0) {
                    var p = el.parentElement;
                    var depth = 0;
                    while (p && p !== document.body && depth < """ + str(MAX_DROPDOWN_DEPTH) + """) {
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
        """, element)

        return options or []
    except Exception as e:
        logger.warning(f"Could not extract dropdown options via JS: {e}")
        return []

def analyze_semantic_type(tag_name: str, attributes: Dict, context: Dict) -> str:
    """
    Determine semantic type of element using field_extractor.

    Args:
        tag_name: HTML tag name
        attributes: Element attributes
        context: Element context (labels, etc.)

    Returns:
        Semantic type string (email, phone, select, etc.)
    """
    try:
        semantic_type = detect_field_type({
            **attributes,
            "tag": tag_name,
            "label": context.get('label', ''),
            "id": attributes.get('id', ''),
            "name": attributes.get('name', '')
        })

        # Special handling for dropdown types
        role = attributes.get('role', '').lower()
        if role ==  'option' or 'option' in attributes.get('class', '') or tag_name == 'li':
            semantic_type = "dropdown_option"
        elif role == 'combobox' or 'select' in attributes.get('class', ''):
            semantic_type = "select"

        return semantic_type
    except Exception as e:
        logger.warning(f"Could not determine semantic type: {e}")
        return "string"

def determine_element_purpose(semantic_type: str, text: str, attributes: Dict, context: Dict) -> str:
    """
    Determine the exact purpose/label of the element.

    Args:
        semantic_type: Semantic type from analyze_semantic_type
        text: Element text content
        attributes: Element attributes
        context: Element context

    Returns:
        Human-readable purpose string
    """
    purpose = ""

    # 1. Direct label or placeholder
    if context.get('label'):
        purpose = context['label'].strip()
    elif attributes.get('placeholder'):
        purpose = attributes['placeholder']

    # 2. For dropdown options: context is more important
    if semantic_type == "dropdown_option":
        if context.get('container_heading'):
            purpose = f"Choice for '{context['container_heading']}'"
        elif context.get('label'):
            purpose = f"Choice for '{context['label']}'"
        else:
            purpose = f"Option: {text}"

    # 3. Fallbacks
    if not purpose:
        if attributes.get('aria-label'):
            purpose = attributes['aria-label']
        elif context.get('container_heading'):
            purpose = f"Input under {context['container_heading']}"
        else:
            purpose = text or attributes.get('name') or attributes.get('id') or "unknown field"

    return purpose

def extract_full_element_info(element: WebElement, locator: str, action: str, description: str = "") -> Dict[str, Any]:
    """
    Orchestrator function that extracts ALL element information.

    This replaces the massive 324-line _extract_element_info method.

    Args:
        element: WebElement to extract information from
        locator: Locator string used to find element
        action: Action type (click, input, hover, etc.)
        description: Optional description

    Returns:
        Comprehensive dictionary with all element information
    """
    try:
        # 1. Extract basic info
        info = extract_basic_info(element, locator, action, description)
        tag_name = info["tag_name"]

        # 2. Extract attributes
        info["attributes"] = extract_attributes_via_js(element)

        # 3. Extract context
        info["context"] = extract_context_via_js(element)

        # 4. Extract properties
        try:
            driver = element.parent
            properties = driver.execute_script("""
                var el = arguments[0];
                return {
                    tagName: el.tagName,
                    outerHTML: el.outerHTML ? el.outerHTML.substring(0, """ + str(MAX_HTML_LENGTH) + """) : '',
                    value: el.value || '',
                    className: el.className
                };
            """, element)
            info["properties"] = properties or {}
        except Exception:
            info["properties"] = {}

        # 5. Extract dropdown options if applicable
        options = extract_dropdown_options_via_js(element)
        if options:
            info["dropdown_options"] = options

        # 6. Analyze semantic type
        semantic_type = analyze_semantic_type(
            tag_name,
            info["attributes"],
            info["context"]
        )
        info["semantic_type"] = semantic_type

        # 7. Determine purpose
        purpose = determine_element_purpose(
            semantic_type,
            info["text"],
            info["attributes"],
            info["context"]
        )
        info["exact_purpose"] = purpose
        info["role_description"] = f"A {semantic_type} ({tag_name}) used for {purpose}"

        return info

    except Exception as e:
        logger.error(f"Error extracting full element info: {e}")
        return {
            "action": action,
            "locator": locator,
            "tag_name": "unknown",
            "text": "",
            "description": description,
            "error": str(e)
        }
