"""
Field Extraction Utilities

Provides reusable functions for extracting and normalizing form field data
from HTML elements with automatic type detection and label extraction.
"""

import re
from typing import Dict, List, Optional, Any
from bs4 import BeautifulSoup, Tag


def to_snake_case(name: str) -> Optional[str]:
    """Convert a string to snake_case format."""
    if not name:
        return None
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    s2 = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1)
    return s2.replace('-', '_').replace(' ', '_').lower()


def normalize_field_name(field: Dict[str, Any]) -> str:
    """Extract and normalize field name from various possible sources."""
    # Prioritize label for better field names, then fall back to other attributes
    name = (
        field.get('label') or
        field.get('placeholder') or
        field.get('aria-label') or
        field.get('name') or 
        field.get('id') or 
        ''
    )
    # Clean up common suffixes that aren't helpful
    if name:
        # Remove common input field suffixes and prefixes
        name = re.sub(r'^(input|select|field)[-_]', '', name, flags=re.IGNORECASE)
        name = re.sub(r'[-_](input|select|field|id)$', '', name, flags=re.IGNORECASE)
    return to_snake_case(name) if name else 'unknown_field'


def detect_field_type(field: Dict[str, Any]) -> str:
    """
    Detect field type from HTML attributes and context.
    
    Supports: email, phone, number, date, checkbox, radio, select, combobox, textarea, string
    """
    input_type = (field.get('type') or '').lower()
    tag = (field.get('tag') or '').lower()
    role = (field.get('role') or '').lower()
    name = (field.get('name') or field.get('id') or '').lower()
    placeholder = (field.get('placeholder') or '').lower()
    
    # Type-based detection
    if input_type == 'email' or 'email' in name or 'email' in placeholder:
        return 'email'
    
    if input_type in ['tel', 'phone'] or 'mobile' in name or 'phone' in name:
        return 'phone'
    
    if input_type == 'number' or 'amount' in name or 'income' in name:
        return 'number'
    
    if input_type == 'date' or input_type == 'datetime-local' or 'date' in name or 'dob' in name:
        return 'date'
    
    if input_type == 'checkbox':
        return 'checkbox'
    
    if input_type == 'radio':
        return 'radio'
    
    # Tag-based detection
    if tag == 'select' or input_type == 'select':
        return 'select'
    
    if tag == 'textarea':
        return 'textarea'
    
    # Role-based detection
    if 'combobox' in role or 'combobox' in input_type:
        return 'combobox'
    
    # Default to string for text inputs
    return 'string'


def extract_element_label(element: Tag, soup: BeautifulSoup) -> Optional[str]:
    """
    Extract label for a form element using multiple strategies.
    
    Strategies:
    1. Direct <label> with matching 'for' attribute
    2. Parent <label> element
    3. aria-label attribute
    4. placeholder attribute
    5. Nearby text content
    6. Associated legend (for fieldsets)
    """
    if not element:
        return None
    
    element_id = element.get('id')
    element_name = element.get('name')
    
    # Strategy 1: Direct label with 'for' attribute
    if element_id:
        label = soup.find('label', {'for': element_id})
        if label:
            text = label.get_text(strip=True)
            if text:
                return text.replace('*', '').strip()
    
    # Strategy 2: Parent label
    parent_label = element.find_parent('label')
    if parent_label:
        # Extract only the label text, not nested input values
        text = parent_label.get_text(strip=True)
        if text:
            return text.replace('*', '').strip()
    
    # Strategy 3: aria-label
    aria_label = element.get('aria-label')
    if aria_label:
        return aria_label.strip()
    
    # Strategy 4: aria-labelledby
    aria_labelledby = element.get('aria-labelledby')
    if aria_labelledby:
        label_elem = soup.find(id=aria_labelledby)
        if label_elem:
            text = label_elem.get_text(strip=True)
            if text:
                return text.replace('*', '').strip()
    
    # Strategy 5: placeholder
    placeholder = element.get('placeholder')
    if placeholder:
        return placeholder.strip()
    
    # Strategy 6: title attribute
    title = element.get('title')
    if title:
        return title.strip()
    
    # Strategy 7: Nearby text (previous sibling or parent)
    if element.previous_sibling:
        if isinstance(element.previous_sibling, str):
            text = element.previous_sibling.strip()
            if text:
                return text.replace('*', '').strip()
    
    # Strategy 8: Associated legend (for radio/checkbox groups)
    fieldset = element.find_parent('fieldset')
    if fieldset:
        legend = fieldset.find('legend')
        if legend:
            text = legend.get_text(strip=True)
            if text:
                return text.replace('*', '').strip()
    
    return None


def extract_select_options(element: Tag) -> List[Dict[str, str]]:
    """Extract options from a select element or combobox."""
    options = []
    
    if element.name == 'select':
        for option in element.find_all('option'):
            value = option.get('value', '')
            label = option.get_text(strip=True)
            if label or value:
                options.append({
                    'value': value,
                    'label': label or value
                })
    
    return options


def is_visible_field(element: Tag) -> bool:
    """Check if a form field is visible (not hidden)."""
    input_type = (element.get('type') or '').lower()
    style = (element.get('style') or '').lower()
    
    # Hidden input type
    if input_type == 'hidden':
        return False
    
    # Hidden via style
    if 'display:none' in style.replace(' ', '') or 'display: none' in style:
        return False
    
    if 'visibility:hidden' in style.replace(' ', '') or 'visibility: hidden' in style:
        return False
    
    # Hidden class names (common patterns)
    classes = element.get('class', [])
    if isinstance(classes, list):
        hidden_classes = ['hidden', 'hide', 'd-none', 'invisible']
        if any(hc in classes for hc in hidden_classes):
            return False
    
    return True


def extract_field_info(element: Tag, soup: BeautifulSoup) -> Dict[str, Any]:
    """
    Extract comprehensive field information from an HTML element.
    
    Returns a dictionary with field metadata including:
    - name, id, type, tag
    - label, placeholder
    - required, disabled, readonly
    - options (for select/combobox)
    - validation attributes
    """
    field_info = {
        'tag': element.name,
        'type': element.get('type', 'text'),
        'name': element.get('name'),
        'id': element.get('id'),
        'placeholder': element.get('placeholder'),
        'value': element.get('value'),
        'required': element.get('required') is not None,
        'disabled': element.get('disabled') is not None,
        'readonly': element.get('readonly') is not None,
        'role': element.get('role'),
        'aria-label': element.get('aria-label'),
    }
    
    # Extract label
    field_info['label'] = extract_element_label(element, soup)
    
    # Extract validation attributes
    field_info['pattern'] = element.get('pattern')
    field_info['min'] = element.get('min')
    field_info['max'] = element.get('max')
    field_info['minlength'] = element.get('minlength')
    field_info['maxlength'] = element.get('maxlength')
    field_info['step'] = element.get('step')
    
    # Extract options for select elements
    if element.name == 'select':
        field_info['options'] = extract_select_options(element)
    
    # Detect field type
    field_info['detected_type'] = detect_field_type(field_info)
    
    return field_info


def generate_validation_rules(field: Dict[str, Any]) -> str:
    """Generate human-readable validation rules from field metadata."""
    rules = []
    field_type = field.get('detected_type', field.get('type', 'string'))
    
    # Type-specific rules
    if field_type == 'email':
        rules.append('Must be a valid email address')
    elif field_type == 'phone':
        rules.append('Must be a valid phone number')
    elif field_type == 'number':
        if field.get('min'):
            rules.append(f"Minimum value: {field['min']}")
        if field.get('max'):
            rules.append(f"Maximum value: {field['max']}")
    elif field_type == 'date':
        rules.append('Must be a valid date (DD/MM/YYYY or YYYY-MM-DD)')
    
    # Required field
    if field.get('required'):
        rules.append('Required field')
    
    # Length constraints
    if field.get('minlength'):
        rules.append(f"Minimum length: {field['minlength']} characters")
    if field.get('maxlength'):
        rules.append(f"Maximum length: {field['maxlength']} characters")
    
    # Pattern validation
    if field.get('pattern'):
        rules.append(f"Must match pattern: {field['pattern']}")
    
    # Options for select/combobox
    if field_type in ['select', 'combobox', 'radio'] and field.get('options'):
        options_text = ', '.join([opt.get('label', '') for opt in field['options'][:5]])
        if len(field['options']) > 5:
            options_text += f", ... ({len(field['options'])} total options)"
        rules.append(f"Options: {options_text}")
    
    return ' | '.join(rules) if rules else 'Enter a valid value'


def generate_example_value(field: Dict[str, Any]) -> Any:
    """Generate a realistic example value based on field type."""
    field_type = field.get('detected_type', field.get('type', 'string'))
    name = (field.get('name') or field.get('id') or '').lower()
    
    # Check for existing value
    if field.get('value'):
        return field['value']
    
    # Type-specific examples
    if field_type == 'email':
        return 'john.doe@example.com'
    elif field_type == 'phone':
        return '9876543210'
    elif field_type == 'number':
        if 'age' in name:
            return 30
        elif 'amount' in name or 'income' in name:
            return 50000
        elif 'pincode' in name or 'zip' in name:
            return '400001'
        return 100
    elif field_type == 'date':
        return '01/01/1990'
    elif field_type == 'checkbox':
        return True
    elif field_type in ['select', 'combobox', 'radio']:
        options = field.get('options', [])
        if options:
            return options[0].get('label', 'Option 1')
        return 'Option 1'
    elif field_type == 'textarea':
        return 'Sample text content'
    else:
        # String field - context-aware examples
        if 'name' in name:
            return 'John Doe'
        elif 'address' in name:
            return '123 Main Street'
        elif 'city' in name:
            return 'Mumbai'
        elif 'state' in name:
            return 'Maharashtra'
        elif 'country' in name:
            return 'India'
        return 'sample_value'


def calculate_confidence(field: Dict[str, Any]) -> float:
    """Calculate confidence score for field extraction (0.0 to 1.0)."""
    confidence = 0.6  # Base confidence
    
    # Boost confidence based on available metadata
    if field.get('label'):
        confidence += 0.15
    if field.get('name') or field.get('id'):
        confidence += 0.10
    if field.get('type') and field['type'] != 'text':
        confidence += 0.10
    if field.get('required'):
        confidence += 0.05
    
    return min(confidence, 1.0)
