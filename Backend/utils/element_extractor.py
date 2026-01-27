"""
Selenium Element Information Extractor

A specialized utility suite for extracting rich metadata from Selenium WebElements.
Utilizes optimized JavaScript execution for performance and stale-element resistance. 
Provides semantic analysis to determine field purpose and accessibility roles.
"""

import logging
from typing import Dict, Any, List, Optional
from selenium.webdriver.remote.webelement import WebElement

# Centralized Logic Import
from utils.field_extractor import detect_field_type

logger = logging.getLogger(__name__)

# Analysis Constraints
MAX_TEXT_CAPTURE = 200
MAX_HTML_CAPTURE = 1000
MAX_TRAVERSAL_DEPTH = 10
MAX_DROPDOWN_TRAVERSAL = 5


# ============================================================================
# SECTION 1: CORE INFORMATION EXTRACTION
# ============================================================================

def extract_basic_info(element: WebElement, locator: str, action: str, description: str = "") -> Dict[str, Any]:
    """
    Capture fundamental properties from a live WebElement.
    
    Includes the initiating action, technical locator, and basic window metadata.
    """
    try:
        tag_name = element.tag_name
        text = (element.text or "")[:MAX_TEXT_CAPTURE]

        info = {
            "action": action,
            "locator": locator,
            "tag_name": tag_name,
            "text": text,
            "description": description,
            "page_url": "",
            "page_title": ""
        }

        # Contextual window attributes
        try:
            info["page_url"] = element.parent.current_url
            info["page_title"] = element.parent.title
        except Exception:
            pass

        return info
    except Exception as e:
        logger.error(f"Basic extraction failed for {locator}: {e}")
        return {
            "action": action,
            "locator": locator,
            "tag_name": "unknown",
            "text": "",
            "description": description,
            "error": str(e)
        }


def extract_full_element_info(element: WebElement, locator: str, action: str, description: str = "") -> Dict[str, Any]:
    """
    Orchestrator function: Aggregates all technical and semantic metadata for an element.
    
    Standard Pipeline:
    1. Base properties capture.
    2. JavaScript-driven attribute collection.
    3. Accessibility and context analysis.
    4. DOM property snapshotting.
    5. Dropdown/Choice discovery.
    6. Semantic classification.
    """
    try:
        # Step 1: Initialize result with basic data
        info = extract_basic_info(element, locator, action, description)
        tag_name = info["tag_name"]

        # Step 2: Extract technical attributes via optimized JS
        info["attributes"] = _extract_attributes_optimized(element)

        # Step 3: Extract UI context (labels, headings)
        info["context"] = _extract_context_optimized(element)

        # Step 4: Capture raw DOM properties
        info["properties"] = _capture_dom_properties(element)

        # Step 5: Discover available choices (Select/Dropdowns)
        options = _extract_dropdown_options(element)
        if options:
            info["dropdown_options"] = options

        # Step 6: Semantic Classification
        info["semantic_type"] = _analyze_semantic_role(tag_name, info["attributes"], info["context"])
        
        # Step 7: Final Purpose Synthesis
        info["exact_purpose"] = _synthesize_purpose(info["semantic_type"], info["text"], info["attributes"], info["context"])
        info["role_description"] = f"A {info['semantic_type']} ({tag_name}) identified as: {info['exact_purpose']}"

        return info

    except Exception as e:
        logger.error(f"Full element analysis failed for {locator}: {e}", exc_info=True)
        return {
            "action": action,
            "locator": locator,
            "tag_name": "unknown",
            "text": "",
            "description": description,
            "error": str(e)
        }


# ============================================================================
# SECTION 2: JAVASCRIPT-POWERED DATA COLLECTION
# ============================================================================

def _extract_attributes_optimized(element: WebElement) -> Dict[str, str]:
    """Extract all relevant HTML attributes using a single atomic JS block."""
    try:
        return element.parent.execute_script("""
            var el = arguments[0];
            if (!el) return {};
            var attrs = {};
            var standard = [
                "id", "name", "class", "type", "value", "placeholder", "href",
                "alt", "title", "role", "required", "pattern", "maxlength", 
                "min", "max", "aria-label", "aria-required", "data-testid"
            ];
            for (var i = 0; i < standard.length; i++) {
                var v = el.getAttribute(standard[i]);
                if (v !== null && v !== "") attrs[standard[i]] = v;
            }
            // Capture all custom data attributes
            for (var i = 0; i < el.attributes.length; i++) {
                var a = el.attributes[i];
                if (a.name.startsWith('data-')) attrs[a.name] = a.value;
            }
            return attrs;
        """, element) or {}
    except Exception:
        return {}


def _extract_context_optimized(element: WebElement) -> Dict[str, str]:
    """Capture surrounding labels and proximity text for semantic analysis."""
    try:
        return element.parent.execute_script("""
            var el = arguments[0];
            if (!el) return {};
            var ctx = { label: '', surrounding_text: '', container_heading: '', form_title: '' };

            // Find best matching label
            if (el.id) {
                var l = document.querySelector('label[for="' + el.id + '"]');
                if (l) ctx.label = l.innerText || l.textContent;
            }
            if (!ctx.label) {
                var p = el.parentElement;
                while (p && p !== document.body) {
                    if (p.tagName === 'LABEL') { ctx.label = p.innerText; break; }
                    p = p.parentElement;
                }
            }
            if (!ctx.label) ctx.label = el.getAttribute('aria-label') || el.getAttribute('placeholder') || '';

            // Map container hierarchy
            var up = el.parentElement;
            var d = 0;
            while (up && up !== document.body && d < 10) {
                var h = up.querySelectorAll('h1, h2, h3, h4, legend');
                if (h.length > 0 && !ctx.container_heading) ctx.container_heading = h[0].innerText;
                if (up.tagName === 'FORM' || up.classList.contains('form')) {
                    var fh = up.querySelector('h1, h2, .form-title');
                    if (fh) ctx.form_title = fh.innerText;
                }
                up = up.parentElement; d++;
            }
            return ctx;
        """, element) or {}
    except Exception:
        return {}


def _capture_dom_properties(element: WebElement) -> Dict[str, Any]:
    """Snapshot direct DOM state properties."""
    try:
        return element.parent.execute_script("""
            var el = arguments[0];
            var rect = el.getBoundingClientRect();
            return {
                tagName: el.tagName,
                outerHTML: el.outerHTML ? el.outerHTML.substring(0, 1000) : '',
                value: el.value || '',
                className: el.className,
                children: el.childElementCount || 0,
                dimensions: Math.round(rect.width) + "x" + Math.round(rect.height) + " px"
            };
        """, element) or {}
    except Exception:
        return {}


def _extract_dropdown_options(element: WebElement) -> List[Dict[str, Any]]:
    """Extract items from standard select or custom ARIA-based choice components."""
    try:
        return element.parent.execute_script("""
            var el = arguments[0];
            if (!el) return [];
            var opts = [];

            // Case A: Native Select
            if (el.tagName === 'SELECT') {
                for (var i = 0; i < el.options.length; i++) {
                    opts.push({ value: el.options[i].value, text: el.options[i].text });
                }
                return opts;
            }

            // Case B: Custom Dropdowns (React/MUI/etc)
            var role = (el.getAttribute('role') || '').toLowerCase();
            if (role === 'combobox' || role === 'listbox' || el.tagName === 'LI') {
                var c = el.getAttribute('aria-controls') || el.getAttribute('aria-owns');
                var target = c ? document.getElementById(c) : el.parentElement;
                if (target) {
                    var items = target.querySelectorAll('[role="option"], li, .option');
                    for (var i=0; i<items.length; i++) {
                        opts.push({ text: items[i].innerText.trim(), value: items[i].getAttribute('value') || '' });
                    }
                }
            }
            return opts;
        """, element) or []
    except Exception:
        return []


# ============================================================================
# SECTION 3: SEMANTIC ANALYSIS
# ============================================================================

def _analyze_semantic_role(tag_name: str, attributes: Dict, context: Dict) -> str:
    """Classify the field's role using consolidated suite logic."""
    role = detect_field_type({
        **attributes,
        "tag": tag_name,
        "label": context.get('label', ''),
        "id": attributes.get('id', ''),
        "name": attributes.get('name', '')
    })

    # Manual adjustments for specialized UI objects
    html_role = attributes.get('role', '').lower()
    if html_role in ['option', 'menuitem'] or tag_name == 'li':
        return "dropdown_option"
    if html_role == 'combobox' or 'select' in attributes.get('class', ''):
        return "select"

    return role


def _synthesize_purpose(semantic_type: str, text: str, attributes: Dict, context: Dict) -> str:
    """Define what the element *actually* does in user-facing language."""
    if context.get('label'):
        return context['label'].strip()
    
    if semantic_type == "dropdown_option":
        if context.get('container_heading'): return f"Choice for {context['container_heading']}"
        return f"Option: {text or 'Selectable Item'}"

    # Fallback cascade
    return (
        attributes.get('placeholder') or 
        attributes.get('aria-label') or 
        text or 
        attributes.get('name') or 
        "unlabeled input"
    )
