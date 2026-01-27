"""
Field Extraction Logic Hub

Core utilities for analyzing, normalizing, and classifying form fields extracted
from HTML. This module serves as the central logic hub for the extraction suite,
providing the rules and heuristics for identifying field types, generating labels,
and synthesizing validation metadata.
"""

import re
import logging
from typing import Dict, List, Optional, Any
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)


# ============================================================================
# SECTION 1: STRING NORMALIZATION
# ============================================================================

def to_snake_case(name: str) -> Optional[str]:
    """
    Convert a string to snake_case format.
    
    Commonly used for generating clean field identifiers from raw labels or attributes.
    """
    if not name:
        return None
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    s2 = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1)
    return s2.replace('-', '_').replace(' ', '_').replace(':', '').lower()


def normalize_field_name(field: Dict[str, Any]) -> str:
    """
    Synthesize a clean identifier for a form field.
    
    Heuristic Priority:
    1. Human-readable label
    2. Placeholder text
    3. ARIA accessibility labels
    4. Technical name attribute
    5. HTML ID attribute
    """
    # Prefer descriptive UI text over technical attributes
    name = (
        field.get('label') or
        field.get('placeholder') or
        field.get('aria-label') or
        field.get('name') or 
        field.get('id') or 
        ''
    )
    
    if name:
        # Strip common clutter prefixes like "input_" or "txt_"
        name = re.sub(r'^(input|select|field|txt|id)[-_]', '', name, flags=re.IGNORECASE)
        # Strip common clutter suffixes
        name = re.sub(r'[-_](input|select|field|id|box|wrapper)$', '', name, flags=re.IGNORECASE)
        
    return to_snake_case(name) if name else 'unknown_field'


# ============================================================================
# SECTION 2: FIELD CLASSIFICATION
# ============================================================================

def detect_field_type(field: Dict[str, Any]) -> str:
    """
    Infer the semantic type of a field based on its attributes and context.
    
    Detects specific patterns for:
    - email, phone, number, date (Dynamic Data)
    - checkbox, radio, select (Choice Components)
    - textarea, combobox, string (Text Components)
    """
    input_type = (field.get('type') or '').lower()
    tag = (field.get('tag') or '').lower()
    role = (field.get('role') or '').lower()
    name = (field.get('name') or field.get('id') or '').lower()
    placeholder = (field.get('placeholder') or '').lower()
    
    # Priority 1: Direct Type Evidence
    if input_type == 'email' or 'email' in name or 'email' in placeholder:
        return 'email'
    
    if input_type in ['tel', 'phone'] or 'mobile' in name or 'phone' in name:
        return 'phone'
    
    if input_type == 'number' or any(kw in name for kw in ['amount', 'income', 'salary', 'price']):
        return 'number'
    
    if input_type in ['date', 'datetime-local'] or any(kw in name for kw in ['date', 'dob', 'birthday']):
        return 'date'
    
    if input_type == 'checkbox':
        return 'checkbox'
    
    if input_type == 'radio':
        return 'radio'
    
    # Priority 2: Tag-Based Inference
    if tag == 'select' or input_type == 'select' or 'select' in name:
        return 'select'
    
    if tag == 'textarea':
        return 'textarea'
    
    # Priority 3: Role and ARIA Inference
    if 'combobox' in role or 'combobox' in input_type:
        return 'combobox'
    
    return 'string'


# ============================================================================
# SECTION 3: HTML EXTRACTION LOGIC
# ============================================================================

def extract_element_label(element: Tag, soup: BeautifulSoup) -> Optional[str]:
    """
    Attempt to find the most accurate human-readable label for a field.
    
    Employs 8 strategies ranging from targeted <label for="..."> checks 
    to nearby text proximity analysis.
    """
    if not element:
        return None
    
    element_id = element.get('id')
    
    # Strategy 1: Explicit <label for="ID">
    if element_id:
        label = soup.find('label', {'for': element_id})
        if label:
            text = label.get_text(strip=True)
            if text:
                return _clean_label_text(text)
    
    # Strategy 2: Implicit parent <label>
    parent_label = element.find_parent('label')
    if parent_label:
        text = parent_label.get_text(strip=True)
        if text:
            return _clean_label_text(text)
    
    # Strategy 3: Standard ARIA Labeling
    for attr in ['aria-label', 'placeholder', 'title']:
        val = element.get(attr)
        if val:
            return val.strip()
    
    # Strategy 4: aria-labelledby reference
    aria_labelledby = element.get('aria-labelledby')
    if aria_labelledby:
        label_elem = soup.find(id=aria_labelledby)
        if label_elem:
            text = label_elem.get_text(strip=True)
            if text:
                return _clean_label_text(text)
    
    # Strategy 5: Text Proximity (Previous sibling)
    if element.previous_sibling and isinstance(element.previous_sibling, str):
        text = element.previous_sibling.strip()
        if text:
            return _clean_label_text(text)
    
    # Strategy 6: Fieldset Legend
    fieldset = element.find_parent('fieldset')
    if fieldset:
        legend = fieldset.find('legend')
        if legend:
            text = legend.get_text(strip=True)
            if text:
                return _clean_label_text(text)
    
    return None


def _clean_label_text(text: str) -> str:
    """Strip clutter from raw label text (e.g., required asterisks)."""
    return text.replace('*', '').strip()


def extract_select_options(element: Tag) -> List[Dict[str, str]]:
    """Record available options for selection-based components."""
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
    """Robust check to exclude hidden or decorative input elements."""
    input_type = (element.get('type') or '').lower()
    style = (element.get('style') or '').lower()
    
    if input_type == 'hidden':
        return False
    
    # Style-based hiding patterns
    hiding_patterns = ['display:none', 'visibility:hidden', 'opacity:0', 'height:0', 'width:0']
    clean_style = style.replace(' ', '')
    if any(p in clean_style for p in hiding_patterns):
        return False
    
    # Accessibility-based hiding
    if element.get('aria-hidden') == 'true':
        return False

    # Common CSS class-based hiding
    classes = element.get('class', [])
    hidden_classes = {'hidden', 'hide', 'd-none', 'invisible', 'sr-only', 'visually-hidden'}
    if isinstance(classes, list) and any(hc in classes for hc in hidden_classes):
        return False
    
    return True


# ============================================================================
# SECTION 4: SYNTHESIS & METADATA
# ============================================================================

def extract_field_info(element: Tag, soup: BeautifulSoup) -> Dict[str, Any]:
    """
    Construct a comprehensive metadata snapshot of a form field.
    
    Captures technical attributes, semantic classification, labels, 
    and surrounding UI context.
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
    }
    
    # Capture parent context (nearby text clues)
    parent = element.find_parent(['div', 'section', 'td', 'tr', 'li'])
    if parent:
        nearby = parent.get_text(separator=' ', strip=True)
        field_info['nearby_context'] = nearby[:200]
    
    field_info['label'] = extract_element_label(element, soup)
    
    # Store native HTML validation constraints
    for attr in ['pattern', 'min', 'max', 'minlength', 'maxlength', 'step']:
        field_info[attr] = element.get(attr)
    
    if element.name == 'select':
        field_info['options'] = extract_select_options(element)
    
    # Classify the final semantic type
    field_info['detected_type'] = detect_field_type(field_info)
    
    return field_info


def generate_validation_rules(field: Dict[str, Any]) -> str:
    """Translate raw HTML constraints into human-readable rule summaries."""
    rules = []
    field_type = field.get('detected_type', field.get('type', 'string'))
    
    # Semantic type rules
    type_rules = {
        'email': 'Must be a valid email address',
        'phone': 'Must be a valid phone number',
        'date': 'Must be a valid date format',
    }
    if field_type in type_rules:
        rules.append(type_rules[field_type])
    
    # Value constraints
    if field_type == 'number':
        if field.get('min'): rules.append(f"Min: {field['min']}")
        if field.get('max'): rules.append(f"Max: {field['max']}")
    
    # Mandatory status
    if field.get('required'):
        rules.append('Required field')
    
    # Length & Pattern
    if field.get('minlength'): rules.append(f"Min length: {field['minlength']}")
    if field.get('maxlength'): rules.append(f"Max length: {field['maxlength']}")
    if field.get('pattern'): rules.append(f"Pattern: {field['pattern']}")
    
    # Options summary
    if field.get('options'):
        opts = [o.get('label', '') for o in field['options'][:5]]
        text = f"Choices: {', '.join(opts)}"
        if len(field['options']) > 5:
            text += f" (+{len(field['options'])-5} more)"
        rules.append(text)
    
    return ' | '.join(rules) if rules else 'Enter valid input'


def generate_example_value(field: Dict[str, Any]) -> Any:
    """Produce a representative example value for documentation and testing."""
    field_type = field.get('detected_type', field.get('type', 'string'))
    name = (field.get('name') or field.get('id') or '').lower()
    
    if field.get('value'):
        return field['value']
    
    # Generic type examples
    standard_examples = {
        'email': 'john.doe@example.com',
        'phone': '1234567890',
        'date': '01/01/1990',
        'checkbox': True,
        'textarea': 'A descriptive block of text.',
    }
    
    if field_type in standard_examples:
        return standard_examples[field_type]
    
    if field_type == 'number':
        return 50000 if any(k in name for k in ['amount', 'salary']) else 25
    
    if field_type in ['select', 'radio', 'combobox']:
        options = field.get('options', [])
        return options[0].get('label', 'Sample Option') if options else 'Option 1'

    # Context-aware string examples
    name_clues = {
        'name': 'John Doe',
        'address': '123 Innovation Drive',
        'city': 'Mumbai',
        'state': 'Maharashtra',
        'country': 'India',
        'zip': '400001',
    }
    for clue, example in name_clues.items():
        if clue in name:
            return example
            
    return 'sample_value'


def calculate_confidence(field: Dict[str, Any]) -> float:
    """Grade the reliability of the extraction on a scale of 0.0 to 1.0."""
    score = 0.5  # Neutral starting point
    
    if field.get('label'): score += 0.2
    if field.get('name') or field.get('id'): score += 0.1
    if field.get('detected_type') not in ['string', 'text']: score += 0.1
    if field.get('required'): score += 0.1
    
    return min(score, 1.0)
