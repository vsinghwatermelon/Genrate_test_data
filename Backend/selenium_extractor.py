"""
Selenium Script Value Extractor

Extracts values from driver.enter_text() and other Selenium commands
to provide cleaner input for the LLM parser.
"""

import re
from typing import List, Dict, Tuple
import os
import requests
import uuid
import time
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


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



def download_html_from_script(script_text: str, output_dir: str = "downloaded_pages") -> List[str]:
    """
    Extract URLs from driver.go_to() calls and download HTML using Selenium.
    
    Args:
        script_text: Selenium script content
        output_dir: Directory to save downloaded HTML files
        
    Returns:
        List of paths to downloaded files
    """
    downloaded_files = []
    
    # Create directory if it doesn't exist
    if not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
        except OSError as e:
            print(f"Error creating directory {output_dir}: {e}")
            return []
    
    # Patterns to match driver.go_to('url') or driver.get('url')
    url_patterns = [
        r"driver\.go_to\s*\(\s*['\"]([^'\"]+)['\"]\s*\)",
        r"driver\.get\s*\(\s*['\"]([^'\"]+)['\"]\s*\)"
    ]
    
    urls_to_download = set()
    
    for pattern in url_patterns:
        matches = re.finditer(pattern, script_text)
        for match in matches:
            urls_to_download.add(match.group(1))
            
    if not urls_to_download:
        return []

    # Initialize Headless Chrome
    print("Initializing Selenium WebDriver for HTML extraction...")
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        for url in urls_to_download:
            try:
                # Ensure URL has schema
                target_url = url
                if not target_url.startswith(('http://', 'https://')):
                    target_url = 'https://' + target_url
                    
                print(f"Downloading HTML from: {target_url} (using Headless Chrome)")
                
                driver.get(target_url)
                
                # Wait for SPA to render (simple sleep)
                time.sleep(8)
                
                # Expand Shadow DOM to make it visible to BS4
                print(" Expanding Shadow DOM for extraction...")
                full_html = driver.execute_script("""
                    function getDeepHTML(node) {
                        if (!node) return "";
                        if (node.nodeType === 3) return node.nodeValue;
                        if (node.nodeType === 1) {
                            let tagName = node.tagName.toLowerCase();
                            let attrs = "";
                            try {
                                for (let attr of node.attributes) {
                                    attrs += ` ${attr.name}="${attr.value}"`;
                                }
                            } catch(e) {}
                            
                            let childrenHTML = "";
                            if (node.shadowRoot) {
                                Array.from(node.shadowRoot.childNodes).forEach(c => childrenHTML += getDeepHTML(c));
                            }
                            Array.from(node.childNodes).forEach(c => childrenHTML += getDeepHTML(c));
                            
                            const voidElements = ['area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'];
                            if (voidElements.includes(tagName)) return `<${tagName}${attrs}>`;
                            return `<${tagName}${attrs}>${childrenHTML}</${tagName}>`;
                        }
                        return "";
                    }
                    return getDeepHTML(document.body);
                """)
                
                # FALLBACK: Explicitly find inputs via Selenium in case JS extraction missed them or failed
                # We append these as a "Safety Net" div at the bottom of the HTML
                print(" Running Selenium Direct Fallback...")
                fallback_html = '<div id="selenium-fallback-data" style="display:none">'
                try:
                    from selenium.webdriver.common.by import By
                    
                    # Find inputs
                    inputs = driver.find_elements(By.TAG_NAME, "input")
                    for inp in inputs:
                        try:
                            t = inp.get_attribute("type") or "text"
                            n = inp.get_attribute("name") or "N/A"
                            i = inp.get_attribute("id") or "N/A"
                            p = inp.get_attribute("placeholder") or "N/A"
                            # Try to get label from parent text if simplified
                            l = "N/A" # Complex to get logic here, stick to attributes
                            fallback_html += f'<input name="{n}" id="{i}" type="{t}" placeholder="{p}" data-source="fallback" />'
                        except: pass
                        
                    # Find selects
                    selects = driver.find_elements(By.TAG_NAME, "select")
                    for sel in selects:
                        try:
                            n = sel.get_attribute("name") or "N/A"
                            i = sel.get_attribute("id") or "N/A"
                            fallback_html += f'<select name="{n}" id="{i}" data-source="fallback">'
                            # Try to get options
                            opts = sel.find_elements(By.TAG_NAME, "option")
                            for o in opts[:10]:
                                ot = o.text
                                fallback_html += f'<option>{ot}</option>'
                            fallback_html += '</select>'
                        except: pass
                        
                    # Find textareas
                    textareas = driver.find_elements(By.TAG_NAME, "textarea")
                    for ta in textareas:
                        try:
                            n = ta.get_attribute("name") or "N/A"
                            i = ta.get_attribute("id") or "N/A"
                            p = ta.get_attribute("placeholder") or "N/A"
                            fallback_html += f'<textarea name="{n}" id="{i}" placeholder="{p}" data-source="fallback"></textarea>'
                        except: pass
                        
                except Exception as e:
                    print(f"Fallback extraction failed: {e}")
                
                fallback_html += '</div>'
                
                if not full_html or len(full_html) < 50:
                    page_source = driver.page_source + fallback_html
                else:
                    page_source = f"<body>{full_html}</body>" + fallback_html
                
                # Generate unique filename
                filename = f"page_{uuid.uuid4().hex[:8]}.html"
                filepath = os.path.join(output_dir, filename)
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(page_source)
                
                downloaded_files.append(filepath)
                print(f"Saved HTML to: {filepath}")
                    
            except Exception as e:
                print(f"Error downloading {url}: {str(e)}")
        
        driver.quit()
        
    except Exception as e:
        print(f"Failed to initialize/run Selenium driver: {e}")
        # Fallback to requests if selenium fails? 
        # For now, just report error as SPA sites need JS.
            
    return downloaded_files


def extract_fields_from_html(file_path: str) -> str:
    """
    Parse HTML file to extract form fields using BeautifulSoup.
    
    Args:
        file_path: Path to the HTML file
        
    Returns:
        String description of extracted fields
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'html.parser')
            
        extracted_info = []
        
        def get_label(element):
            """Helper to find label text for an element."""
            # 1. Try 'for' attribute matching ID
            el_id = element.get('id')
            if el_id:
                label = soup.find('label', attrs={'for': el_id})
                if label:
                    return label.get_text(strip=True)
            
            # 2. Try parent label
            parent_label = element.find_parent('label')
            if parent_label:
                return parent_label.get_text(strip=True)
                
            # 3. Try aria-label
            aria_label = element.get('aria-label')
            if aria_label:
                return aria_label
                
            # 4. Try nearby text (siblings) - highly effective for Radio/Checkbox
            # Check next sibling
            next_sib = element.find_next_sibling()
            if next_sib and next_sib.name in ['span', 'div', 'label', 'p']:
                text = next_sib.get_text(strip=True)
                if text: return text
            
            # Check previous sibling (sometimes label is before)
            prev_sib = element.find_previous_sibling()
            if prev_sib and prev_sib.name in ['span', 'div', 'label', 'p']:
                text = prev_sib.get_text(strip=True)
                if text: return text
                
            # Check parent's text if the element is inside a lightweight wrapper
            parent = element.parent
            if parent:
                parent_text = parent.get_text(strip=True)
                # Avoid returning the whole huge page text if parent is body/html
                if len(parent_text) < 100: 
                    return parent_text
            
            return "N/A"
        
        def clean_text(text):
            if not text: return "N/A"
            return " ".join(text.split())
        
        # 1. Input fields
        inputs = soup.find_all('input')
        for inp in inputs:
            type_attr = inp.get('type', 'text')
            name_attr = inp.get('name', 'N/A')
            id_attr = inp.get('id', 'N/A')
            placeholder = inp.get('placeholder', 'N/A')
            label = clean_text(get_label(inp))
            
            # Skip hidden or submit types
            if type_attr not in ['hidden', 'submit', 'button', 'image', 'reset']:
                extracted_info.append(f"Input Field - Label: {label}, Name: {name_attr}, ID: {id_attr}, Type: {type_attr}, Placeholder: {clean_text(placeholder)}")
                
        # 2. Select fields (Dropdowns)
        selects = soup.find_all('select')
        for sel in selects:
            name_attr = sel.get('name', 'N/A')
            id_attr = sel.get('id', 'N/A')
            label = clean_text(get_label(sel))
            
            options = [opt.get_text(strip=True) for opt in sel.find_all('option')]
            if len(options) > 10:
                options_str = ", ".join(options[:10]) + "..."
            else:
                options_str = ", ".join(options)
                
            extracted_info.append(f"Dropdown Field - Label: {label}, Name: {name_attr}, ID: {id_attr}, Options: [{options_str}]")
            
        # 3. Textareas
        textareas = soup.find_all('textarea')
        for ta in textareas:
            name_attr = ta.get('name', 'N/A')
            id_attr = ta.get('id', 'N/A')
            placeholder = ta.get('placeholder', 'N/A')
            label = clean_text(get_label(ta))
            extracted_info.append(f"Textarea Field - Label: {label}, Name: {name_attr}, ID: {id_attr}, Placeholder: {clean_text(placeholder)}")
            
        return "\n".join(extracted_info)
        
    except Exception as e:
        print(f"Error parsing HTML {file_path}: {e}")
        return ""


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

    # Extract and download HTML from driver.go_to calls
    downloaded_files = download_html_from_script(script_text)
    html_context = ""
    html_fields_found = False
    if downloaded_files:
        print(f"Downloaded {len(downloaded_files)} pages to downloaded_pages/")
        html_context = "\n\nExtracted HTML Page Details:\n"
        for file_path in downloaded_files:
            fields_str = extract_fields_from_html(file_path)
            if fields_str:
                html_fields_found = True
                print(f"--- Extracted Fields from {os.path.basename(file_path)} ---")
                print(fields_str)
                print("---------------------------------------------------------")
                html_context += f"\n--- Fields from downloaded page ({os.path.basename(file_path)}) ---\n"
                html_context += fields_str
                html_context += "\n"
            else:
                print(f"Warning: No fields extracted from {os.path.basename(file_path)}")
            # Clean up: delete the downloaded file
            try:
                os.remove(file_path)
                print(f"Deleted temporary file: {file_path}")
            except OSError as e:
                print(f"Error removing file {file_path}: {e}")

    # Extract additional context
    context = extract_other_selenium_commands(script_text)

    # If we have extracted values, enhance the formatted text with context
    if extracted_values and (context['labels'] or context['tabs']):
        formatted_text += "\nAdditional context:\n"
        if context['labels']:
            formatted_text += f"\nLabels found: {', '.join(context['labels'])}\n"
        if context['tabs']:
            formatted_text += f"Tab sections: {', '.join(context['tabs'])}\n"

    # Only append HTML context if fields were found
    if html_fields_found:
        formatted_text += html_context

    return formatted_text
