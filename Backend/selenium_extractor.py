"""
Selenium Script Value Extractor

Extracts values from driver.enter_text() and other Selenium commands
to provide cleaner input for the LLM parser.
"""

import re
from typing import List, Dict, Tuple


def extract_selenium_values(script_text: str) -> Tuple[List[Dict[str, str]], str]:
    """
    Extract values from Selenium script commands.
    
    Looks for patterns like:
    - driver.enter_text('id', 'value', ...)
    - driver.enter_text("id", "value", ...)
    
    Returns:
        Tuple of (extracted_values, formatted_text)
        - extracted_values: List of dicts with 'element_id' and 'value'
        - formatted_text: Formatted text for LLM parser
    """
    
    extracted_values = []
    
    # Pattern to match driver.enter_text() calls
    # Matches: driver.enter_text('id', 'value', ...) or driver.enter_text("id", "value", ...)
    patterns = [
        # Single quotes
        r"driver\.enter_text\s*\(\s*'([^']*?)'\s*,\s*'([^']*?)'\s*[,\)]",
        # Double quotes
        r'driver\.enter_text\s*\(\s*"([^"]*?)"\s*,\s*"([^"]*?)"\s*[,\)]',
        # Mixed quotes (id in single, value in double)
        r"driver\.enter_text\s*\(\s*'([^']*?)'\s*,\s*\"([^\"]*?)\"\s*[,\)]",
        # Mixed quotes (id in double, value in single)
        r'driver\.enter_text\s*\(\s*"([^"]*?)"\s*,\s*\'([^\']*?)\'\s*[,\)]',
    ]
    
    for pattern in patterns:
        matches = re.finditer(pattern, script_text, re.MULTILINE)
        for match in matches:
            element_id = match.group(1)
            value = match.group(2)
            
            # Skip empty values
            if value.strip():
                extracted_values.append({
                    'element_id': element_id,
                    'value': value
                })
    
    # Remove duplicates while preserving order
    seen = set()
    unique_values = []
    for item in extracted_values:
        key = (item['element_id'], item['value'])
        if key not in seen:
            seen.add(key)
            unique_values.append(item)
    
    # Format the extracted values for LLM parser
    if unique_values:
        formatted_text = "Extracted form field values from Selenium script:\n\n"
        for i, item in enumerate(unique_values, 1):
            formatted_text += f"{i}. {item['value']}\n"
    else:
        # If no values extracted, return original script
        formatted_text = script_text
    
    return unique_values, formatted_text


def extract_other_selenium_commands(script_text: str) -> Dict[str, List[str]]:
    """
    Extract other useful context from Selenium script.
    
    Returns dict with:
    - 'labels': Text from get_text() calls
    - 'tabs': Tab switch targets
    - 'clicks': Click targets
    """
    
    context = {
        'labels': [],
        'tabs': [],
        'clicks': []
    }
    
    # Extract get_text (label) calls
    label_patterns = [
        r"driver\.get_text\s*\(\s*'([^']*?)'\s*\)",
        r'driver\.get_text\s*\(\s*"([^"]*?)"\s*\)',
    ]
    
    for pattern in label_patterns:
        matches = re.finditer(pattern, script_text)
        for match in matches:
            context['labels'].append(match.group(1))
    
    # Extract switch_Tab calls
    tab_patterns = [
        r"driver\.switch_Tab\s*\(\s*'([^']*?)'\s*\)",
        r'driver\.switch_Tab\s*\(\s*"([^"]*?)"\s*\)',
    ]
    
    for pattern in tab_patterns:
        matches = re.finditer(pattern, script_text)
        for match in matches:
            context['tabs'].append(match.group(1))
    
    # Extract click calls
    click_patterns = [
        r"driver\.click\s*\(\s*'([^']*?)'\s*\)",
        r'driver\.click\s*\(\s*"([^"]*?)"\s*\)',
    ]
    
    for pattern in click_patterns:
        matches = re.finditer(pattern, script_text)
        for match in matches:
            context['clicks'].append(match.group(1))
    
    return context


def preprocess_selenium_script(script_text: str) -> str:
    """
    Main preprocessing function.
    Extracts values and formats them for the LLM parser.
    
    Args:
        script_text: Raw Selenium script
        
    Returns:
        Formatted text optimized for LLM parsing
    """
    
    # Extract values from enter_text calls
    extracted_values, formatted_text = extract_selenium_values(script_text)
    
    # Extract additional context
    context = extract_other_selenium_commands(script_text)
    
    # If we have extracted values, enhance the formatted text with context
    if extracted_values and (context['labels'] or context['tabs']):
        formatted_text += "\nAdditional context:\n"
        
        if context['labels']:
            formatted_text += f"\nLabels found: {', '.join(context['labels'])}\n"
        
        if context['tabs']:
            formatted_text += f"Tab sections: {', '.join(context['tabs'])}\n"
    
    return formatted_text
