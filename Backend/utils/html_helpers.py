"""
HTML Helper Utilities

Helper functions for parsing HTML content and extracting form field information.
Extracted from locator_parser.py to eliminate nested functions.
"""

import os
import re
import uuid
import time
import logging
from typing import List, Optional
from bs4 import BeautifulSoup, Tag
from utils.selenium_utils import create_chrome_driver

logger = logging.getLogger(__name__)

# Constants
MAX_LABEL_TEXT_LENGTH = 100
MAX_OPTIONS_TO_DISPLAY = 10
DEFAULT_DOWNLOAD_DIR = "downloaded_pages"
PAGE_LOAD_WAIT_SECONDS = 5


def find_element_label(soup: BeautifulSoup, element: Tag) -> str:
    """
    Find label text for an HTML form element.
    
    Tries multiple strategies in order:
    1. Label with matching 'for' attribute
    2. Parent <label> element
    3. aria-label attribute
    4. Next/previous sibling text
    5. Parent element text
    
    Args:
        soup: BeautifulSoup object containing the element
        element: The form element (input, select, textarea, etc.)
        
    Returns:
        Label text or "N/A" if not found
        
    Example:
        >>> soup = BeautifulSoup('<label for="email">Email:</label><input id="email">', 'html.parser')
        >>> element = soup.find('input')
        >>> find_element_label(soup, element)
        'Email:'
    """
    # 1. Label with 'for' attribute
    el_id = element.get('id')
    if el_id:
        label = soup.find('label', attrs={'for': el_id})
        if label:
            return label.get_text(strip=True)
    
    # 2. Parent label element
    parent_label = element.find_parent('label')
    if parent_label:
        return parent_label.get_text(strip=True)
    
    # 3. aria-label attribute
    aria_label = element.get('aria-label')
    if aria_label:
        return aria_label
    
    # 4. Next sibling
    next_sib = element.find_next_sibling()
    if next_sib and next_sib.name in ['span', 'div', 'label', 'p']:
        text = next_sib.get_text(strip=True)
        if text:
            return text
    
    # 5. Previous sibling
    prev_sib = element.find_previous_sibling()
    if prev_sib and prev_sib.name in ['span', 'div', 'label', 'p']:
        text = prev_sib.get_text(strip=True)
        if text:
            return text
    
    # 6. Parent element text (short text only)
    parent = element.parent
    if parent:
        parent_text = parent.get_text(strip=True)
        if len(parent_text) < MAX_LABEL_TEXT_LENGTH:
            return parent_text
    
    return "N/A"


def extract_fields_from_html_file(file_path: str) -> str:
    """
    Extract form field information from an HTML file.
    
    Extracts information about:
    - Input fields (text, email, number, etc.)
    - Dropdowns/selects with options
    - Textareas
    
    Args:
        file_path: Path to HTML file
        
    Returns:
        Formatted string with field information, one field per line
        
    Example output:
        Input Field - Label: Email, Name: user_email, ID: email, Type: email, Placeholder: Enter email
        Dropdown Field - Label: Country, Name: country, ID: country_select, Options: [US, UK, Canada...]
        Textarea Field - Label: Comments, Name: comments, ID: comment_box, Placeholder: Enter comments
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'html.parser')
        
        extracted_info = []
        
        # Extract input fields
        for inp in soup.find_all('input'):
            type_attr = inp.get('type', 'text')
            # Skip non-data input types
            if type_attr not in ['hidden', 'submit', 'button', 'image', 'reset']:
                label = " ".join((find_element_label(soup, inp) or "N/A").split())
                extracted_info.append(
                    f"Input Field - Label: {label}, "
                    f"Name: {inp.get('name', 'N/A')}, "
                    f"ID: {inp.get('id', 'N/A')}, "
                    f"Type: {type_attr}, "
                    f"Placeholder: {inp.get('placeholder', 'N/A')}"
                )
        
        # Extract select/dropdown fields
        for sel in soup.find_all('select'):
            label = " ".join((find_element_label(soup, sel) or "N/A").split())
            options = [opt.get_text(strip=True) for opt in sel.find_all('option')]
            options_str = ", ".join(options[:MAX_OPTIONS_TO_DISPLAY])
            if len(options) > MAX_OPTIONS_TO_DISPLAY:
                options_str += "..."
            extracted_info.append(
                f"Dropdown Field - Label: {label}, "
                f"Name: {sel.get('name', 'N/A')}, "
                f"ID: {sel.get('id', 'N/A')}, "
                f"Options: [{options_str}]"
            )
        
        # Extract textarea fields
        for ta in soup.find_all('textarea'):
            label = " ".join((find_element_label(soup, ta) or "N/A").split())
            extracted_info.append(
                f"Textarea Field - Label: {label}, "
                f"Name: {ta.get('name', 'N/A')}, "
                f"ID: {ta.get('id', 'N/A')}, "
                f"Placeholder: {ta.get('placeholder', 'N/A')}"
            )
        
        return "\n".join(extracted_info)
    
    except Exception as e:
        logger.error(f"Error parsing HTML {file_path}: {e}")
        return ""


def download_html_from_selenium_script(
    script_text: str,
    output_dir: str = DEFAULT_DOWNLOAD_DIR
) -> List[str]:
    """
    Download HTML pages from URLs found in Selenium script.
    
    Extracts URLs from driver.get() and driver.go_to() calls,
    then downloads the HTML content using a headless browser.
    
    Args:
        script_text: Selenium script content
        output_dir: Directory to save downloaded HTML files
        
    Returns:
        List of file paths to downloaded HTML files
        
    Example:
        >>> script = 'driver.get("https://example.com")'
        >>> files = download_html_from_selenium_script(script)
        >>> len(files)
        1
    """
    downloaded_files = []
    
    # Create output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    
    # Extract URLs from script
    url_patterns = [
        r"driver\.go_to\s*\(\s*['\"]([^'\"]+)['\"]\s*\)",
        r"driver\.get\s*\(\s*['\"]([^'\"]+)['\"]\s*\)"
    ]
    
    urls = set()
    for pattern in url_patterns:
        for match in re.finditer(pattern, script_text):
            urls.add(match.group(1))
    
    if not urls:
        logger.info("No URLs found in script")
        return []
    
    logger.info(f"Found {len(urls)} unique URLs to download")
    
    # Download HTML for each URL
    driver = None
    try:
        driver = create_chrome_driver(headless=True)
        
        for url in urls:
            try:
                # Ensure URL has proper scheme
                target_url = url if url.startswith(('http://', 'https://')) else 'https://' + url
                logger.info(f"Downloading HTML from: {target_url}")
                
                driver.get(target_url)
                time.sleep(PAGE_LOAD_WAIT_SECONDS)  # Wait for page to load
                
                # Get full HTML content
                full_html = driver.execute_script("return document.body.innerHTML;")
                
                # Save to file
                filename = f"page_{uuid.uuid4().hex[:8]}.html"
                filepath = os.path.join(output_dir, filename)
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(full_html)
                
                downloaded_files.append(filepath)
                logger.info(f"Saved HTML to: {filename}")
                
            except Exception as e:
                logger.error(f"Error downloading {url}: {e}")
        
        return downloaded_files
    
    except Exception as e:
        logger.error(f"Driver initialization failure: {e}")
        return []
    
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
