"""
Locator Parser Module

Dynamically parses locator configuration files in various formats
(Python dict, JSON, YAML, etc.) and extracts XPath/CSS selectors.
"""

import re
import json
import ast
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path


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
            exec_context = {}
            exec(content, {}, exec_context)
            
            # Look for common locator variable names
            for var_name in ['locators', 'LOCATORS', 'elements', 'ELEMENTS', 'selectors', 'SELECTORS']:
                if var_name in exec_context:
                    return exec_context[var_name]
        except Exception as e:
            print(f"[WARNING] exec() failed: {e}, trying AST parsing...")
        
        # Fallback to AST parsing
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            var_name = target.id.lower()
                            if 'locator' in var_name or 'element' in var_name or 'selector' in var_name:
                                try:
                                    return ast.literal_eval(node.value)
                                except:
                                    pass
        except Exception as e:
            print(f"[WARNING] AST parsing failed: {e}")
        
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
                if 'locator' in fname_lower or 'config' in fname_lower:
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


# Import os for the identify_script_files method
import os
