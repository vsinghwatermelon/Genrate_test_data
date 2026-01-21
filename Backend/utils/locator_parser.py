"""
Locator Parser Module

Dynamically parses locator configuration files in various formats
(Python dict, JSON, YAML, etc.) and extracts XPath/CSS selectors.
"""

import re
import json
import ast
import os
import uuid
import time
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from bs4 import BeautifulSoup

from utils.selenium_utils import create_chrome_driver
from llm_factory import LLMFactory, BaseLLM
from prompts import SeleniumParserPrompts
from utils.json_utils import JSONCleaner, JSONExtractor, NDJSONParser
from utils.console import safe_print


class LocatorParser:
    """Parse locator configurations from various file formats."""
    
    @staticmethod
    def parse_python_file(file_path: str) -> Dict[str, Any]:
        """
        Parse a Python file containing locator definitions.
        
        Supports:
        - Dictionary assignments: locators = {...}
        - Class attributes
        - Module-level constants
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Try safe execution first
        try:
            # Add common automation imports to context to help exec() succeed
            from selenium.webdriver.common.by import By
            from selenium.webdriver.common.keys import Keys
            import os, json, sys, re
            
            exec_context = {
                "By": By,
                "Keys": Keys,
                "os": os,
                "json": json,
                "sys": sys,
                "re": re,
                "__builtins__": __builtins__
            }
            exec(content, exec_context, exec_context)
            
            # 1. Look for common locator variable names
            for var_name in ['locators', 'LOCATORS', 'elements', 'ELEMENTS', 'selectors', 'SELECTORS']:
                if var_name in exec_context and isinstance(exec_context[var_name], dict):
                    return exec_context[var_name]
            
            # 2. If no standard variable found, collect everything that looks like a locator
            # (starts with locator_ or ends with _locator, etc.)
            collected = {}
            keywords = ['locator', 'element', 'selector', 'btn', 'input', 'field', 'key', 'id', 'xpath', 'css', 'item', 'link', 'txt']
            
            def collect_from_obj(obj, prefix=""):
                for name in dir(obj):
                    if name.startswith('__'): continue
                    try:
                        val = getattr(obj, name)
                        name_lower = name.lower()
                        full_name = f"{prefix}.{name}" if prefix else name
                        
                        if any(k in name_lower for k in keywords):
                            if isinstance(val, (dict, list, tuple, str)):
                                collected[full_name] = val
                        elif isinstance(val, dict) and len(val) > 2:
                            collected[full_name] = val
                    except: continue

            for name, val in exec_context.items():
                if name.startswith('__'): continue
                
                # NEW: Look into any dictionary or list for locator signatures
                # We collect ANYTHING that looks like it contains a selector, regardless of variable name
                val_str = str(val).lower()
                is_locator_pattern = any(k in val_str for k in ['xpath', 'cssselector', '//', './', '[id=', '[name=', 'css='])
                name_lower = name.lower()
                
                if isinstance(val, (dict, list, tuple)):
                    if is_locator_pattern:
                        collected[name] = val
                    elif any(k in name_lower for k in keywords):
                        collected[name] = val
                    elif isinstance(val, dict) and len(val) > 1:
                        # Even if no pattern, if it's in a class and has a dict, it's likely a config
                        if prefix: collected[name] = val
                
                elif isinstance(val, str) and (val.startswith('//') or val.startswith('./')):
                    collected[name] = val

                # If it's a class, look inside
                if isinstance(val, type):
                    collect_from_obj(val, name)
            
            if collected:
                return collected

        except Exception as e:
            print(f"[WARNING] exec() failed: {e}, trying AST parsing...")
        
        # Fallback to AST parsing
        try:
            tree = ast.parse(content)
            collected = {}
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            var_name = target.id
                            if var_name.startswith('__'): continue
                            
                            # If it's one of the main variables, return its value immediately if it's a dict
                            if var_name.lower() in ['locators', 'elements', 'selectors']:
                                try:
                                    return ast.literal_eval(node.value)
                                except:
                                    pass
                            
                            # Otherwise collect it
                            keywords = ['locator', 'element', 'selector', 'btn', 'input', 'field', 'key', 'id', 'xpath', 'css', 'item']
                            name_lower = var_name.lower()
                            
                            try:
                                val = ast.literal_eval(node.value)
                                val_str = str(val).lower()
                                is_locator_pattern = any(k in val_str for k in ['xpath', 'cssselector', '//', './'])
                                
                                if is_locator_pattern or any(k in name_lower for k in keywords):
                                    collected[var_name] = val
                                elif isinstance(val, (dict, list)) and len(val) > 0:
                                    # Collect any non-empty dict/list just in case
                                    collected[var_name] = val
                            except:
                                pass
            if collected:
                # NEW: Try to normalize the structure so it's always mapping to something useful
                # (handled by caller like SeleniumScriptExecutor._convert_to_selenium_format, 
                # but let's be as clean as possible)
                return collected
        except Exception as e:
            print(f"[WARNING] AST parsing failed: {e}")
        
        return {}
        
        return {}
    
    @staticmethod
    def parse_json_file(file_path: str) -> Dict[str, Any]:
        """Parse a JSON file containing locator definitions."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[ERROR] Failed to parse JSON file {file_path}: {e}")
            return {}
    
    @staticmethod
    def detect_format(file_path: str) -> str:
        """Detect the format of a locator file."""
        path = Path(file_path)
        extension = path.suffix.lower()
        
        if extension == '.py':
            return 'python'
        elif extension == '.json':
            return 'json'
        elif extension in ['.yaml', '.yml']:
            return 'yaml'
        else:
            return 'unknown'
    
    @staticmethod
    def parse_file(file_path: str) -> Dict[str, Any]:
        """Automatically detect format and parse locator file."""
        file_format = LocatorParser.detect_format(file_path)
        
        if file_format == 'python':
            return LocatorParser.parse_python_file(file_path)
        elif file_format == 'json':
            return LocatorParser.parse_json_file(file_path)
        else:
            print(f"[WARNING] Unsupported file format: {file_format}")
            return {}
    
    @staticmethod
    def normalize_locator_data(locators: Dict[str, Any]) -> Dict[str, Dict[str, List[str]]]:
        """
        Normalize locator data to a standard format.
        
        Output format:
        {
            'locator_key': {
                'css': ['selector1', 'selector2'],
                'xpath': ['xpath1', 'xpath2'],
                'id': ['id1'],
                'name': ['name1']
            }
        }
        """
        normalized = {}
        
        for key, value in locators.items():
            if not isinstance(value, dict):
                continue
            
            normalized_entry = {
                'css': [],
                'xpath': [],
                'id': [],
                'name': [],
                'class': []
            }
            
            # Handle various key naming conventions
            for locator_type, selectors in value.items():
                locator_type_lower = locator_type.lower().replace(' ', '').replace('_', '')
                
                # Normalize to list
                if not isinstance(selectors, list):
                    selectors = [selectors]
                
                # Flatten nested lists
                flat_selectors = []
                for sel in selectors:
                    if isinstance(sel, list):
                        flat_selectors.extend(sel)
                    else:
                        flat_selectors.append(sel)
                
                # Categorize by type
                if 'css' in locator_type_lower or 'cssselector' in locator_type_lower:
                    normalized_entry['css'].extend(flat_selectors)
                elif 'xpath' in locator_type_lower:
                    normalized_entry['xpath'].extend(flat_selectors)
                elif 'id' in locator_type_lower:
                    normalized_entry['id'].extend(flat_selectors)
                elif 'name' in locator_type_lower:
                    normalized_entry['name'].extend(flat_selectors)
                elif 'class' in locator_type_lower:
                    normalized_entry['class'].extend(flat_selectors)
            
            normalized[key] = normalized_entry
        
        return normalized


class ScriptAnalyzer:
    """Analyze Selenium/automation scripts to extract metadata."""
    
    @staticmethod
    def extract_url(script_content: str) -> Optional[str]:
        """Extract the target URL from a Selenium script."""
        patterns = [
            # Selenium WebDriver patterns
            r'driver\.get\(["\']([^"\']+)["\']\)',  # driver.get("url")
            r'driver\.get\(\s*(["\'][^"\']+["\'])\s*\)',  # driver.get( "url" ) with spaces
            r'self\.driver\.get\(["\']([^"\']+)["\']\)',  # self.driver.get("url")
            
            # URL variable patterns
            r'url\s*=\s*["\']([^"\']+)["\']',  # url = "..."
            r'URL\s*=\s*["\']([^"\']+)["\']',  # URL = "..."
            r'base_url\s*=\s*["\']([^"\']+)["\']',  # base_url = "..."
            r'BASE_URL\s*=\s*["\']([^"\']+)["\']',  # BASE_URL = "..."
            
            # Other browser automation frameworks
            r'browser\.goto\(["\']([^"\']+)["\']\)',  # Playwright
            r'browser\.url\(["\']([^"\']+)["\']\)',  # WebdriverIO
            r'navigate\(["\']([^"\']+)["\']\)',  # Generic
            r'open\(["\']([^"\']+)["\']\)',  # Generic
            r'visit\(["\']([^"\']+)["\']\)',  # Capybara/Ruby
            
            # Look for http/https URLs anywhere in the script
            r'["\']?(https?://[^\s"\'<>]+)["\']?',  # Any http/https URL
        ]
        
        for pattern in patterns:
            match = re.search(pattern, script_content, re.MULTILINE | re.IGNORECASE)
            if match:
                url = match.group(1)
                # Validate it looks like a URL
                if url.startswith(('http://', 'https://', 'www.')):
                    return url
        
        return None
    
    @staticmethod
    def extract_locator_references(script_content: str) -> List[str]:
        """
        Extract all locator references from a script.
        
        Detects patterns like:
        - helper.click("locator_name")
        - find_element("locator_name")
        - locators["locator_name"]
        """
        locator_refs = set()
        
        patterns = [
            r'helper\.(?:click|send_keys|wait|hover)\(["\']([^"\']+)["\']\)',  # helper methods
            r'find_element\(["\']([^"\']+)["\']\)',  # find_element
            r'locators\[["\']([^"\']+)["\']\]',  # locators dict access
            r'get_element\(["\']([^"\']+)["\']\)',  # get_element
            r'wait_for\(["\']([^"\']+)["\']\)',  # wait_for
            r'interact_with\(["\']([^"\']+)["\']\)',  # interact_with
            r'(?:hover|move_to)\(["\']([^"\']+)["\']\)',  # hover/move_to
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, script_content)
            for match in matches:
                locator_refs.add(match.group(1))
        
        return sorted(list(locator_refs))
    
    @staticmethod
    def extract_actions(script_content: str) -> List[Dict[str, Any]]:
        """
        Extract actions from a Selenium script in order.
        
        Returns a list of actions with their type and parameters.
        """
        actions = []
        
        # Pattern for various action types
        action_patterns = [
            (r'helper\.click\(["\']([^"\']+)["\']\)', 'click'),
            (r'helper\.send_keys\(["\']([^"\']+)["\']\s*,\s*["\']?([^"\']+)["\']?\)', 'send_keys'),
            (r'helper\.wait\(["\']([^"\']+)["\']\)', 'wait'),
            (r'helper\.select\(["\']([^"\']+)["\']\s*,\s*["\']([^"\']+)["\']\)', 'select'),
            (r'helper\.hover\(["\']([^"\']+)["\']\)', 'hover'),
            (r'helper\.move_to\(["\']([^"\']+)["\']\)', 'hover'),
        ]
        
        # Process script line by line to maintain order
        for line_num, line in enumerate(script_content.split('\n'), 1):
            line = line.strip()
            
            for pattern, action_type in action_patterns:
                match = re.search(pattern, line)
                if match:
                    action_data = {
                        'type': action_type,
                        'locator': match.group(1),
                        'line': line_num
                    }
                    
                    # Add value for send_keys actions
                    if action_type == 'send_keys' and len(match.groups()) > 1:
                        action_data['value'] = match.group(2)
                    
                    # Add option for select actions
                    if action_type == 'select' and len(match.groups()) > 1:
                        action_data['option'] = match.group(2)
                    
                    actions.append(action_data)
                    break
        
        return actions
    
    @staticmethod
    def identify_script_files(directory: str) -> Tuple[Optional[str], List[str]]:
        """
        Identify main script and locator files in a directory.
        
        Returns: (main_script_path, locator_file_paths)
        """
        import logging
        logger = logging.getLogger(__name__)
        
        main_script = None
        locator_files = []
        best_score = 0
        
        logger.info(f"Scanning directory: {directory}")
        all_py_files = []
        script_candidates = []
        
        for root, dirs, files in os.walk(directory):
            for fname in files:
                full_path = os.path.join(root, fname)
                
                # Skip common non-script files
                if fname in ['__init__.py', 'conftest.py', '__pycache__']:
                    continue
                
                # Track all Python files for logging
                if fname.endswith('.py'):
                    all_py_files.append(fname)
                
                # Skip helper/utility files - these are not main test scripts
                fname_lower = fname.lower()
                if any(keyword in fname_lower for keyword in ['helper', 'util', 'base', 'common', 'fixture']):
                    # These are likely helper files, not main scripts
                    logger.info(f"  ⊗ Skipping helper file: {fname}")
                    continue
                
                # Identify locator config files
                if any(k in fname_lower for k in ['locator', 'config', 'keys', 'elements', 'selectors']):
                    if fname.endswith(('.py', '.json', '.yaml', '.yml')):
                        logger.info(f"  → Found locator config: {fname}")
                        locator_files.append(full_path)
                        continue
                
                # Identify main script files
                if fname.endswith('.py'):
                    try:
                        with open(full_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        # Check for Selenium/automation patterns
                        has_driver = 'driver.get(' in content or 'driver.' in content
                        has_helper = 'helper.' in content
                        has_browser = 'browser.' in content
                        has_url = 'http://' in content or 'https://' in content
                        has_selenium = 'selenium' in content.lower()
                        has_webdriver = 'webdriver' in content.lower()
                        
                        # Score the script based on automation indicators
                        score = 0
                        if has_driver: score += 3
                        if has_helper: score += 2
                        if has_browser: score += 2
                        if has_url: score += 1
                        if has_selenium: score += 1
                        if has_webdriver: score += 1
                        
                        # Bonus points for test/main script naming patterns
                        if any(keyword in fname_lower for keyword in ['test', 'main', 'run', 'script']):
                            score += 2
                        
                        # Bonus for files with common test patterns
                        if 'VA_RETRO' in fname or 'test_' in fname_lower:
                            score += 3
                        
                        # Consider it a candidate if score >= 2 or it's a large file with URLs
                        if score >= 2 or (has_url and len(content) > 500):
                            script_candidates.append((fname, score, full_path))
                            logger.info(f"  ★ Script candidate: {fname} (score: {score})")
                            
                            if not main_script:
                                main_script = full_path
                                best_score = score
                            else:
                                # Compare scores first, then size
                                if score > best_score:
                                    logger.info(f"  ↑ New best script: {fname} (score: {score} > {best_score})")
                                    main_script = full_path
                                    best_score = score
                                elif score == best_score:
                                    # Same score, prefer larger file
                                    with open(main_script, 'r', encoding='utf-8') as f:
                                        existing_content = f.read()
                                    
                                    if len(content) > len(existing_content):
                                        logger.info(f"  ↑ New best script (larger): {fname} ({len(content)} > {len(existing_content)} chars)")
                                        main_script = full_path
                    except Exception as e:
                        logger.warning(f"Could not read {fname}: {e}")
        
        logger.info(f"\nScript Selection Summary:")
        logger.info(f"  Python files found: {all_py_files}")
        logger.info(f"  Script candidates: {[(name, score) for name, score, _ in script_candidates]}")
        logger.info(f"  Selected script: {os.path.basename(main_script) if main_script else 'None'}")
        logger.info(f"  Locator files: {[os.path.basename(f) for f in locator_files]}")
        
        return main_script, locator_files


    @staticmethod
    def preprocess_selenium_script(script_text: str) -> str:
        """
        Main preprocessing function.
        Extracts values and formats them for the LLM parser.
        """
        def get_label(soup, element):
            """Helper to find label text for an element."""
            el_id = element.get('id')
            if el_id:
                label = soup.find('label', attrs={'for': el_id})
                if label:
                    return label.get_text(strip=True)
            parent_label = element.find_parent('label')
            if parent_label:
                return parent_label.get_text(strip=True)
            aria_label = element.get('aria-label')
            if aria_label:
                return aria_label
            next_sib = element.find_next_sibling()
            if next_sib and next_sib.name in ['span', 'div', 'label', 'p']:
                text = next_sib.get_text(strip=True)
                if text: return text
            prev_sib = element.find_previous_sibling()
            if prev_sib and prev_sib.name in ['span', 'div', 'label', 'p']:
                text = prev_sib.get_text(strip=True)
                if text: return text
            parent = element.parent
            if parent:
                parent_text = parent.get_text(strip=True)
                if len(parent_text) < 100: 
                    return parent_text
            return "N/A"

        def extract_fields_from_html(file_path: str) -> str:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    soup = BeautifulSoup(f, 'html.parser')
                extracted_info = []
                for inp in soup.find_all('input'):
                    type_attr = inp.get('type', 'text')
                    if type_attr not in ['hidden', 'submit', 'button', 'image', 'reset']:
                        label = " ".join((get_label(soup, inp) or "N/A").split())
                        extracted_info.append(f"Input Field - Label: {label}, Name: {inp.get('name', 'N/A')}, ID: {inp.get('id', 'N/A')}, Type: {type_attr}, Placeholder: {inp.get('placeholder', 'N/A')}")
                for sel in soup.find_all('select'):
                    label = " ".join((get_label(soup, sel) or "N/A").split())
                    options = [opt.get_text(strip=True) for opt in sel.find_all('option')]
                    options_str = ", ".join(options[:10]) + ("..." if len(options) > 10 else "")
                    extracted_info.append(f"Dropdown Field - Label: {label}, Name: {sel.get('name', 'N/A')}, ID: {sel.get('id', 'N/A')}, Options: [{options_str}]")
                for ta in soup.find_all('textarea'):
                    label = " ".join((get_label(soup, ta) or "N/A").split())
                    extracted_info.append(f"Textarea Field - Label: {label}, Name: {ta.get('name', 'N/A')}, ID: {ta.get('id', 'N/A')}, Placeholder: {ta.get('placeholder', 'N/A')}")
                return "\n".join(extracted_info)
            except Exception as e:
                print(f"Error parsing HTML {file_path}: {e}")
                return ""

        def download_html_from_script(script_text: str, output_dir: str = "downloaded_pages") -> List[str]:
            downloaded_files = []
            if not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
            url_patterns = [r"driver\.go_to\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", r"driver\.get\s*\(\s*['\"]([^'\"]+)['\"]\s*\)"]
            urls = set()
            for p in url_patterns:
                for m in re.finditer(p, script_text):
                    urls.add(m.group(1))
            if not urls: return []
            try:
                driver = create_chrome_driver(headless=True)
                for url in urls:
                    try:
                        target_url = url if url.startswith(('http://', 'https://')) else 'https://' + url
                        driver.get(target_url)
                        time.sleep(5)
                        full_html = driver.execute_script("return document.body.innerHTML;")
                        filename = f"page_{uuid.uuid4().hex[:8]}.html"
                        filepath = os.path.join(output_dir, filename)
                        with open(filepath, 'w', encoding='utf-8') as f:
                            f.write(full_html)
                        downloaded_files.append(filepath)
                    except Exception as e:
                        print(f"Error downloading {url}: {e}")
                driver.quit()
            except Exception as e:
                print(f"Driver failure: {e}")
            return downloaded_files

        field_related_lines = []
        patterns = ['driver.enter_text', 'driver.click', 'driver.select', 'args.get(']
        for line in script_text.splitlines():
            if any(p in line for p in patterns):
                field_related_lines.append(line.strip())

        formatted_text = "Relevant Selenium script lines:\n\n"
        for i, l in enumerate(field_related_lines, 1):
            formatted_text += f"{i}. {l}\n"

        downloaded = download_html_from_script(script_text)
        if downloaded:
            formatted_text += "\nExtracted HTML Page Details:\n"
            for f in downloaded:
                fields = extract_fields_from_html(f)
                if fields:
                    formatted_text += f"\n--- Fields from {os.path.basename(f)} ---\n{fields}\n"
                os.remove(f)
        return formatted_text

    @staticmethod
    def parse_selenium_script(script_text: str, provider: str = "ollama", model_name: Optional[str] = None) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """Parse a Selenium script or preprocessed text using LLM."""
        try:
            llm = LLMFactory.create_llm(provider=provider, model_name=model_name or "llama3:latest", temperature=0.0)
            prompt = SeleniumParserPrompts.create_parse_prompt(script_text or '')
            response = llm.invoke(prompt)
            
            # Internal parsing logic moved from selenium_llm_parser
            assembled = NDJSONParser.parse(response) or response
            json_str = JSONExtractor.extract_json(assembled, expect_array=True) or assembled.strip()
            json_str = JSONCleaner.clean(json_str)
            
            try:
                parsed = json.loads(json_str, strict=False)
            except:
                try:
                    parsed = json.loads(JSONCleaner.repair(json_str), strict=False)
                except Exception as e:
                    return [], f"JSON parse failed: {str(e)}"
            
            if not isinstance(parsed, list): parsed = [parsed]
            
            normalized = []
            for item in parsed:
                if isinstance(item, dict):
                    normalized.append({
                        'name': str(item.get('name', '')).strip(),
                        'type': str(item.get('type', 'string')),
                        'rules': str(item.get('rules', '') or ''),
                        'description': str(item.get('description', '') or ''),
                        'example': str(item.get('example', '') or '')
                    })
            return normalized, None
        except Exception as e:
            return [], f"LLM parsing failed: {str(e)}"
