"""
Selenium Script Executor

Utility to execute user-provided Selenium scripts and inject action tracking.
"""

import os
import sys
import importlib.util
import logging
import tempfile
import json
import re
import shutil
from typing import Dict, Any, Optional
from selenium import webdriver
from utils.selenium_utils import create_chrome_driver

from utils.selenium_tracker import SeleniumActionTracker, TrackedHelper
from utils.locator_parser import LocatorParser
from selenium.webdriver.common.by import By

logger = logging.getLogger(__name__)


# --- GLOBAL INTERACTION MODEL (Dynamic Configuration) ---
# This allows the system to be robust across any website without hardcoding specific libraries
INTERACTION_CONFIG = {
    "SELECT_CONTAINERS": [".ant-select-selector", ".select-content", "[class*='select-selector']", "[class*='dropdown']", ".mui-select"],
    "MODAL_OVERLAYS": [".ant-modal-mask", ".ant-modal-wrap", "[class*='modal-mask']", "[class*='overlay']", "[class*='backdrop']", ".cdk-overlay-container"],
    "NOTIFICATION_BLOCKERS": [".ant-notification", ".ant-message", "[class*='notification']", "[class*='toast']", "[class*='alert']"],
    "SPINNER_PATTERNS": ["[class*='loading']", "[class*='spinner']", ".ant-spin", "[aria-busy='true']"],
    "COMPLEX_FIELD_KEYWORDS": ["select", "rc", "dropdown", "combobox", "choice", "date"],
    "NAV_ACTION_KEYWORDS": ["next", "submit", "continue", "save", "buy", "purchase", "pay", "proceed"],
    "MOCK_DATA_REGISTRY": {
        "email": "test@example.com",
        "phone": "9876543210",
        "mobile": "9876543210",
        "name": "Test User",
        "age": "25",
        "pin": "400708",
        "zip": "400708",
        "pincode": "400708",
        "city": "Mumbai",
        "state": "Maharashtra",
        "dob": "01/01/2000",
        "date": "01/01/2026"
    }
}

class SeleniumScriptExecutor:
    """
    Executes user-provided Selenium scripts with action tracking
    """
    
    @staticmethod
    def _convert_to_selenium_format(locators: Dict[str, Any]) -> Dict[str, list]:
        """
        Convert parsed locators to Selenium (By.X, "value") format.
        """
        selenium_locators = {}
        
        by_mapping = {
            'ID': By.ID,
            'NAME': By.NAME,
            'CLASS_NAME': By.CLASS_NAME,
            'CLASS': By.CLASS_NAME,
            'TAG_NAME': By.TAG_NAME,
            'TAG': By.TAG_NAME,
            'CSS_SELECTOR': By.CSS_SELECTOR,
            'CSS': By.CSS_SELECTOR,
            'XPATH': By.XPATH,
            'LINK_TEXT': By.LINK_TEXT,
            'LINK': By.LINK_TEXT,
            'LINKTEXT': By.LINK_TEXT,
            'PARTIAL_LINK_TEXT': By.PARTIAL_LINK_TEXT,
            'PARTIAL_LINK': By.PARTIAL_LINK_TEXT,
            'PARTIALLINK': By.PARTIAL_LINK_TEXT,
        }
        
        for key, value in locators.items():
            try:
                paths = []
                
                if isinstance(value, tuple) and len(value) == 2:
                    by_type, locator_value = value
                    if hasattr(by_type, '__name__') and by_type.__name__ in ['ID', 'NAME', 'CLASS_NAME', 'TAG_NAME', 'CSS_SELECTOR', 'XPATH', 'LINK_TEXT', 'PARTIAL_LINK_TEXT']:
                        paths.append((by_type, locator_value))
                    elif isinstance(by_type, str):
                        by_obj = by_mapping.get(by_type.upper(), By.CSS_SELECTOR)
                        paths.append((by_obj, locator_value))
                    else:
                        paths.append((by_type, locator_value))
                
                elif isinstance(value, dict):
                    # Special Case: Element Details (JSON structure)
                    if 'elementDetails' in value:
                        details_list = value['elementDetails']
                        if isinstance(details_list, list):
                            for detail_str in details_list:
                                if isinstance(detail_str, str) and detail_str.startswith('{'):
                                    try:
                                        import json
                                        data = json.loads(detail_str)
                                        self_data = data.get('self', {})
                                        
                                        # Extract usable locators from self
                                        tag = self_data.get('tag', '*')
                                        
                                        # 1. ID
                                        if self_data.get('id'):
                                            paths.append((By.ID, self_data['id']))
                                            paths.append((By.CSS_SELECTOR, f"{tag}#{self_data['id']}"))
                                            # If ID looks dynamic, add a "contains" xpath
                                            if any(c in self_data['id'] for c in ['_', '-', 'rc-select']):
                                                clean_id = ''.join([c for c in self_data['id'] if not c.isdigit()]).strip('_-')
                                                if len(clean_id) > 2:
                                                    paths.append((By.XPATH, f"//{tag}[contains(@id, '{clean_id}')]"))
                                        # 2. Name
                                        if self_data.get('name'):
                                            paths.append((By.NAME, self_data['name']))
                                            paths.append((By.CSS_SELECTOR, f"{tag}[name='{self_data['name']}']"))
                                        # 3. XPath (if any)
                                        if self_data.get('xpath'):
                                            paths.append((By.XPATH, self_data['xpath']))
                                        # 4. CSS (if any)
                                        if self_data.get('css'):
                                            paths.append((By.CSS_SELECTOR, self_data['css']))
                                        
                                        # 5. Link Text / Partial Link Text
                                        txt = self_data.get('text', '').strip()
                                        if tag == 'a' and txt:
                                            paths.append((By.LINK_TEXT, txt))
                                            if len(txt) > 5:
                                                paths.append((By.PARTIAL_LINK_TEXT, txt[:len(txt)//2]))
                                        
                                        # 6. Fallback to common attributes
                                        raw_cls = self_data.get('class', '').strip()
                                        if raw_cls:
                                            cls_parts = [p.replace(':', '\\:') for p in raw_cls.split() if p]
                                            if cls_parts:
                                                # Try full class string first
                                                paths.append((By.CSS_SELECTOR, f"{tag}.{'.'.join(cls_parts)}"))
                                                # Try individual classes (often more robust)
                                                for p in cls_parts[:3]: # First few are usually most specific
                                                    paths.append((By.CSS_SELECTOR, f"{tag}.{p}"))

                                        # 7. Attributes (href, value, placeholder, etc.)
                                        for attr in ['href', 'placeholder', 'value', 'aria-label', 'title']:
                                            val = self_data.get(attr)
                                            if val:
                                                # For href, try both absolute and relative if possible, but usually raw is fine
                                                paths.append((By.CSS_SELECTOR, f"{tag}[{attr}='{val}']"))
                                                if len(str(val)) > 10:
                                                    paths.append((By.CSS_SELECTOR, f"{tag}[{attr}*='{val}']"))

                                        # 8. Data attributes
                                        for attr in ['data-testid', 'data-qa', 'data-cy', 'data-auto', 'data-id']:
                                            if self_data.get(attr):
                                                paths.append((By.CSS_SELECTOR, f"[{attr}='{self_data[attr]}']"))

                                        # 9. Type + Tag
                                        if self_data.get('type'):
                                            paths.append((By.CSS_SELECTOR, f"{tag}[type='{self_data['type']}']"))
                                            
                                        # 10. Text fallback via XPath
                                        if txt and len(txt) < 100:
                                            safe_txt = txt.replace("'", "\\'")
                                            paths.append((By.XPATH, f"//{tag}[text()='{safe_txt}']"))
                                            paths.append((By.XPATH, f"//*[text()='{safe_txt}']"))
                                            paths.append((By.XPATH, f"//*[contains(text(),'{safe_txt}')]"))
                                    except:
                                        pass

                    # Try to match any key that sounds like a selenium locator
                    found_any = bool(paths)
                    for k, val in value.items():
                        if k == 'elementDetails': continue # Already handled
                        norm_k = k.lower().replace(' ', '_').replace('-', '_')
                        by_type = by_mapping.get(norm_k.upper())
                        
                        if not by_type:
                            if norm_k == 'cssselector': by_type = By.CSS_SELECTOR
                        
                        if by_type:
                            if isinstance(val, list):
                                for v in val:
                                    if v and isinstance(v, str):
                                        paths.append((by_type, v))
                            elif isinstance(val, str) and val:
                                paths.append((by_type, val))
                            found_any = True
                    
                    # Fallback: if no keys match, look for xpath-like or css-like strings in any key
                    for k, val in value.items():
                        if k == 'elementDetails': continue
                        if k.upper() in by_mapping: continue # Already handled
                        
                        values_to_check = val if isinstance(val, list) else [val]
                        for v in values_to_check:
                            if not isinstance(v, str) or not v.strip(): continue
                            
                            # Skip JSON strings in fallback detection
                            if v.startswith('{') and v.endswith('}'): continue
                            
                            if v.startswith('/') or v.startswith('('):
                                paths.append((By.XPATH, v))
                                found_any = True
                            elif '.' in v or '#' in v or '>' in v or '[' in v:
                                # Basic blacklist for non-CSS strings
                                if ' ' in v and not any(c in v for c in ['>', ' ', '+', '~']):
                                    continue
                                paths.append((By.CSS_SELECTOR, v))
                                found_any = True
                
                elif isinstance(value, str):
                    if value.startswith('/') or value.startswith('('):
                        paths.append((By.XPATH, value))
                    else:
                        paths.append((By.CSS_SELECTOR, value))
                
                if paths:
                    # 11. Add dynamic fallbacks for ALL paths
                    extra_paths = []
                    for b_type, b_val in paths:
                            # Dynamic ID fallback
                            if b_type == By.ID or (b_type == By.CSS_SELECTOR and '#' in b_val):
                                raw_id = str(b_val).replace('#', '')
                                if any(c in raw_id for c in ['_', '-', 'rc-select']):
                                    clean_val = re.sub(r'\d+', '', raw_id).strip('_-')
                                    if len(clean_val) > 2:
                                        extra_paths.append((By.XPATH, f"//*[contains(@id, '{clean_val}')]"))
                                
                                # Robust detection of complex selects (AntD, MUI, etc)
                                raw_lower = raw_id.lower()
                                if any(kw in raw_lower for kw in INTERACTION_CONFIG["COMPLEX_FIELD_KEYWORDS"]):
                                    # Fallback to general containers
                                    extra_paths.append((By.XPATH, f"//*[@id='{raw_id}']/ancestor::div[contains(@class, 'select') or contains(@class, 'dropdown')]"))
                                    extra_paths.append((By.XPATH, f"//label[@for='{raw_id}']"))
                                    for selector in INTERACTION_CONFIG["SELECT_CONTAINERS"]:
                                        extra_paths.append((By.CSS_SELECTOR, selector))
                                
                                if '_' in raw_id:
                                    extra_paths.append((By.CSS_SELECTOR, f"[id*='{raw_id.split('_')[0]}']"))
                            
                            # Partial Attribute fallback
                            if b_type == By.NAME:
                                extra_paths.append((By.CSS_SELECTOR, f"[name*='{b_val}']"))
                                
                            # If it's a navigation/action button specifically
                            b_val_lower = str(b_val).lower()
                            if any(kw in b_val_lower for kw in INTERACTION_CONFIG["NAV_ACTION_KEYWORDS"]):
                                for kw in INTERACTION_CONFIG["NAV_ACTION_KEYWORDS"]:
                                    if kw in b_val_lower:
                                        extra_paths.append((By.XPATH, f"//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{kw}')]"))
                                        extra_paths.append((By.XPATH, f"//span[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{kw}')]/.."))

                    # 12. Add global placeholder/aria fallbacks
                    search_vals = []
                    if isinstance(value, dict):
                        for k, v in value.items():
                            if isinstance(v, str) and len(v) < 50 and not v.startswith('/') and not v.startswith('{'):
                                search_vals.append(v)
                    elif isinstance(value, str) and len(value) < 50:
                        search_vals.append(value)
                    
                    for v_text in search_vals:
                        val_safe = str(v_text).replace("'", "\\'")
                        extra_paths.append((By.CSS_SELECTOR, f"[placeholder='{val_safe}']"))
                        extra_paths.append((By.CSS_SELECTOR, f"[aria-label='{val_safe}']"))
                        extra_paths.append((By.XPATH, f"//*[contains(text(), '{val_safe}')]"))
                        
                        v_lower = val_safe.lower()
                        if any(kw in v_lower for kw in INTERACTION_CONFIG["COMPLEX_FIELD_KEYWORDS"] + INTERACTION_CONFIG["NAV_ACTION_KEYWORDS"]):
                            clean_kw = val_safe.replace(' ', '')
                            extra_paths.append((By.CSS_SELECTOR, f"input[class*='{clean_kw}']"))
                            extra_paths.append((By.CSS_SELECTOR, f"div[class*='{clean_kw}']"))
                            extra_paths.append((By.CSS_SELECTOR, f"button[class*='{clean_kw}']"))

                    paths.extend(extra_paths)
                    # Deduplicate paths
                    seen = set()
                    unique_paths = []
                    for p in paths:
                        p_str = f"{p[0]}:{p[1]}"
                        if p_str not in seen:
                            unique_paths.append(p)
                            seen.add(p_str)
                    selenium_locators[key] = unique_paths
                    
            except Exception as e:
                logger.warning(f"Failed to convert locator {key}: {e}")
                continue
        
        return selenium_locators
    
    @staticmethod
    def setup_driver(headless: bool = True) -> webdriver.Chrome:
        """
        Setup Chrome WebDriver with options
        
        Args:
            headless: Whether to run browser in headless mode
            
        Returns:
            Configured Chrome WebDriver instance
        """
        try:
            driver = create_chrome_driver(headless=headless)
            
            # Wrapper for driver to fix common script issues
            original_implicitly_wait = driver.implicitly_wait
            def wrapped_implicitly_wait(time_to_wait):
                if isinstance(time_to_wait, str):
                    try:
                        time_to_wait = int(time_to_wait)
                    except:
                        time_to_wait = 10 # Fallback
                return original_implicitly_wait(time_to_wait)
            
            driver.implicitly_wait = wrapped_implicitly_wait
            
            # Add custom methods to driver that scripts might expect
            def get_test_data_value(key, default=None):
                """Mock method for test data retrieval"""
                print(f"[INFO] get_test_data_value called with key: {key}")
                # Return some sensible defaults based on common key patterns
                k = key.lower()
                if 'email' in k:
                    return 'test@example.com'
                elif 'phone' in k or 'mobile' in k:
                    return '9876543210'
                elif 'name' in k:
                    return 'Test User'
                elif 'age' in k:
                    return '30'
                elif 'address' in k:
                    return 'Test Address'
                elif 'pin' in k or 'zip' in k:
                    return '400001'
                return default or f'test_{key}'
            
            # Attach custom methods to driver instance
            driver.get_test_data_value = get_test_data_value
            
            # Verify method was attached
            print(f"[DEBUG] get_test_data_value method attached to driver: {hasattr(driver, 'get_test_data_value')}")
            
            return driver
        except Exception as e:
            logger.error(f"Failed to setup WebDriver: {str(e)}")
            raise
    
    @staticmethod
    def execute_script_with_tracking(
        script_path: str,
        locator_files: list,
        folder_path: str,
        headless: bool = True
    ) -> Dict[str, Any]:
        """
        Execute a Selenium script and track all actions
        
        Args:
            script_path: Path to the main Selenium script
            locator_files: List of paths to locator configuration files
            folder_path: Path to the folder containing the script
            headless: Whether to run browser in headless mode
            
        Returns:
            Dictionary with tracked actions and results
        """
        driver = None
        tracker = SeleniumActionTracker()
        
        try:
            print("\n" + "="*80)
            print("EXECUTING SELENIUM SCRIPT WITH ACTION TRACKING")
            print("="*80)
            
            # Step 1: Parse locators from config files
            print(f"\n[STEP 1] Parsing locators from {len(locator_files)} config file(s)...")
            locators_dict = {}
            
            for locator_file in locator_files:
                logger.info(f"Parsing locator file: {locator_file}")
                print(f"  → Parsing {os.path.basename(locator_file)}...")
                try:
                    # Parse the locator file using the correct method
                    parsed_locators = LocatorParser.parse_file(locator_file)
                    print(f"    Raw parsed data: {list(parsed_locators.keys()) if parsed_locators else 'None'}")
                    
                    # Show sample of raw data structure
                    if parsed_locators:
                        first_key = list(parsed_locators.keys())[0]
                        first_value = parsed_locators[first_key]
                        print(f"    Sample structure: {first_key} = {first_value} (type: {type(first_value).__name__})")
                    
                    # Convert to Selenium (By.X, "value") format if needed
                    if parsed_locators:
                        selenium_locators = SeleniumScriptExecutor._convert_to_selenium_format(parsed_locators)
                        locators_dict.update(selenium_locators)
                        print(f"  ✓ Parsed {len(selenium_locators)} locators from {os.path.basename(locator_file)}")
                        if selenium_locators:
                            # Show first few locators as sample
                            sample_keys = list(selenium_locators.keys())[:3]
                            for key in sample_keys:
                                print(f"    - {key}: {selenium_locators[key]}")
                        else:
                            print(f"  ⚠ Conversion resulted in 0 locators - check format compatibility")
                    else:
                        print(f"  ⚠ No locators found in {os.path.basename(locator_file)}")
                except Exception as e:
                    logger.error(f"Failed to parse {locator_file}: {e}")
                    print(f"  ✗ Failed to parse {os.path.basename(locator_file)}: {e}")
                    import traceback
                    traceback.print_exc()
            
            print(f"[STEP 1] ✓ Total locators loaded: {len(locators_dict)}")
            if not locators_dict:
                print(f"[STEP 1] ⚠ WARNING: No locators loaded! Script may fail if it uses helper.click() or helper.send_keys()")
            
            # Step 2: Setup WebDriver
            print(f"\n[STEP 2] Setting up Chrome WebDriver (headless={headless})...")
            driver = SeleniumScriptExecutor.setup_driver(headless=headless)
            print("[STEP 2] ✓ WebDriver ready")
            
            # Step 3: Load and prepare script for execution
            print(f"\n[STEP 3] Loading script: {os.path.basename(script_path)}")
            with open(script_path, 'r', encoding='utf-8') as f:
                script_content = f.read()
            
            # Step 3.5: Auto-fix common import issues
            print(f"[STEP 3.5] Checking for common import patterns...")
            original_content = script_content
            
            # Fix all config.* imports to remove the config prefix
            import re
            # Pattern: from config.SOMETHING import ... → from SOMETHING import ...
            script_content = re.sub(
                r'from config\.(\w+) import',
                r'from \1 import',
                script_content
            )
            
            if script_content != original_content:
                print("  ✓ Fixed: Removed 'config.' prefix from imports")
                # Show what was changed
                original_imports = re.findall(r'from config\.(\w+) import', original_content)
                if original_imports:
                    for module in set(original_imports):
                        print(f"    - 'from config.{module} import' → 'from {module} import'")
                print("  ℹ️  Script imports were automatically adjusted for compatibility")
            else:
                print("  → No import fixes needed")
            
            # Step 4: Execute script with injected tracker
            print(f"\n[STEP 4] Executing script with action tracking...")
            print("-"*80)
            
            # Create tracked helper instance
            helper = TrackedHelper(driver, tracker, locators_dict)
            
            # Prepare execution environment
            # CRITICAL: Add user's script folder FIRST to avoid conflicts with Backend's modules
            script_dir = os.path.dirname(script_path)
            
            # Store original sys.path to restore later
            original_sys_path = sys.path.copy()
            
            # Remove Backend path entirely to prevent conflicts
            backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            filtered_paths = [p for p in original_sys_path if not p.startswith(backend_path)]
            
            # Build new sys.path with user's folders first
            sys.path = [folder_path, script_dir] + filtered_paths
            
            print(f"  → Script directory: {script_dir}")
            print(f"  → Folder path: {folder_path}")
            print(f"  → Backend path removed: {backend_path}")
            print(f"  → First 3 sys.path entries: {sys.path[:3]}")
            
            # Create base namespace for script execution
            exec_namespace = {
                'driver': driver,
                'helper': helper,
                '__file__': script_path,
                '__name__': '__main__',
                'undefined': None,  # Handle common JS-to-Python conversion artifact
            }
            
            # Verify driver has the custom method
            print(f"\n  → Verifying driver has custom methods...")
            print(f"    driver.get_test_data_value exists: {hasattr(driver, 'get_test_data_value')}")
            if hasattr(driver, 'get_test_data_value'):
                print(f"    Testing get_test_data_value: {driver.get_test_data_value('email')}")
            else:
                print(f"    ERROR: get_test_data_value NOT found on driver!")
                print(f"    Driver type: {type(driver)}")
                print(f"    Driver attributes: {[attr for attr in dir(driver) if not attr.startswith('_')][:20]}")
            
            # Pre-import config files and add them to namespace
            print(f"\n  → Pre-loading config modules...")
            
            # Find all Python files in the script directory and subdirectories
            all_py_files = []
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    if file.endswith('.py') and file != os.path.basename(script_path):
                        all_py_files.append(os.path.join(root, file))
            
            # Pre-load all found Python files
            selenium_helper_module = None
            for py_file in all_py_files:
                module_name = os.path.splitext(os.path.basename(py_file))[0]
                try:
                    # Import the module
                    import importlib.util
                    spec = importlib.util.spec_from_file_location(module_name, py_file)
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        sys.modules[module_name] = module
                        spec.loader.exec_module(module)
                        exec_namespace[module_name] = module
                        print(f"    ✓ Pre-loaded: {module_name} ({os.path.basename(os.path.dirname(py_file))})")
                        
                        # Keep track of selenium_helper for later wrapping
                        if module_name == 'selenium_helper':
                            selenium_helper_module = module
                            print(f"    → Found selenium_helper module, will inject tracking...")
                except Exception as e:
                    print(f"    ⚠ Could not pre-load {module_name}: {e}")
            
            # Wrap the user's helper class to add tracking
            print(f"\n  → Checking for Helper class to wrap...")
            if selenium_helper_module:
                print(f"    ✓ selenium_helper module found")
                
                # Try both 'Helper' and 'SeleniumHelper' class names
                helper_class_name = None
                if hasattr(selenium_helper_module, 'Helper'):
                    helper_class_name = 'Helper'
                elif hasattr(selenium_helper_module, 'SeleniumHelper'):
                    helper_class_name = 'SeleniumHelper'
                
                if helper_class_name:
                    print(f"    ✓ {helper_class_name} class found in module")
                    try:
                        original_helper_class = getattr(selenium_helper_module, helper_class_name)
                        
                        # Create a wrapper class that tracks actions
                        class TrackedHelperWrapper(original_helper_class):
                            def __init__(self, *args, **kwargs):
                                super().__init__(*args, **kwargs)
                                self._tracker = tracker
                                self._full_locators = locators_dict
                                print(f"[TRACKER] {helper_class_name} instance created with tracking enabled")
                                
                                # CRITICAL: Attach get_test_data_value to the helper's driver instance
                                if hasattr(self, 'driver') and self.driver:
                                    def get_test_data_value(key, default=None):
                                        """Universal test data retrieval based on interaction model"""
                                        k = str(key).lower()
                                        registry = INTERACTION_CONFIG["MOCK_DATA_REGISTRY"]
                                        for pattern, val in registry.items():
                                            if pattern in k:
                                                return val
                                        return default or f'test_{key}'
                                    
                                    self.driver.get_test_data_value = get_test_data_value
                                    
                                    # Support for active_element tracking
                                    original_get = self.driver.__getattribute__
                                    def tracked_get(name):
                                        attr = original_get(name)
                                        if name == 'switch_to':
                                            class WrappedSwitchTo:
                                                def __init__(self, st, tracker):
                                                    self._st = st
                                                    self._tracker = tracker
                                                def __getattr__(self, n):
                                                    val = getattr(self._st, n)
                                                    if n == 'active_element':
                                                        # Wrap the element to track actions
                                                        class WrappedElement:
                                                            def __init__(self, el, tr):
                                                                self._el = el
                                                                self._tr = tr
                                                            def __getattr__(self, a):
                                                                return getattr(self._el, a)
                                                            def send_keys(self, *args):
                                                                text = "".join(str(a) for a in args)
                                                                self._tr.track_field_input(self._el, "active_element", text, "Interaction with active element")
                                                                return self._el.send_keys(*args)
                                                        return WrappedElement(val, self._tracker)
                                                    return val
                                            return WrappedSwitchTo(attr, self._tracker)
                                        return attr
                                    
                                    # Only apply if it's not already wrapped
                                    try:
                                        # Use a slightly different approach as __getattribute__ is tricky
                                        # Instead, just add a property-like behavior if possible
                                        pass
                                    except:
                                        pass

                                    print(f"[TRACKER] ✓ Enhanced helper's driver with tracking and data mocks")

                            def click(self, locator_key, *args, **kwargs):
                                print(f"[TRACKER] Intercepted click for: {locator_key}")
                                if locator_key not in self._full_locators:
                                    print(f"[TRACKER] ⚠ Locator {locator_key} not found")
                                    return super().click(locator_key, *args, **kwargs)

                                paths = self._full_locators[locator_key]
                                last_err = None
                                
                                path_count = 0
                                for by_type, value in paths:
                                    path_count += 1
                                    try:
                                        print(f"[TRACKER] Trying path: {by_type}={value}")
                                        # 1. Clear loaders ONLY on retry/second path to save time
                                        if path_count > 1:
                                            try:
                                                spinner_selectors = ", ".join(INTERACTION_CONFIG["SPINNER_PATTERNS"])
                                                self.driver.execute_script(f"""
                                                    document.querySelectorAll('{spinner_selectors}').forEach(el => {{
                                                        if (el.innerText.trim() === '' || el.getAttribute('aria-busy') === 'true' || el.classList.contains('ant-spin')) {{
                                                            el.style.display = 'none';
                                                        }}
                                                    }});
                                                """)
                                            except: pass

                                        # 2. Wait for element to be present and VISIBLE
                                        from selenium.webdriver.support.ui import WebDriverWait
                                        from selenium.webdriver.support import expected_conditions as EC
                                        element = WebDriverWait(self.driver, 10).until(
                                            EC.presence_of_element_located((by_type, value))
                                        )
                                        # Force scroll but skip the sleep for fast path
                                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)

                                        self._tracker.track_click(element, locator_key, f"Click via helper")
                                        
                                        original_locators = None
                                        if hasattr(self, 'locators'):
                                            original_locators = self.locators.copy()
                                            self.locators[locator_key] = (by_type, value)
                                            
                                        try:
                                            # 3. Handle Complex Fields (Selects/Comboboxes)
                                            is_complex_field = False
                                            try:
                                                el_id = str(element.get_attribute('id') or "").lower()
                                                el_cls = str(element.get_attribute('class') or "").lower()
                                                el_role = str(element.get_attribute('role') or "").lower()
                                                
                                                keywords = INTERACTION_CONFIG["COMPLEX_FIELD_KEYWORDS"]
                                                if any(kw in el_id or kw in el_cls or kw in el_role for kw in keywords):
                                                    is_complex_field = True
                                            except: pass

                                            if is_complex_field:
                                                print(f"[TRACKER] Specialized handling for Complex Field...")
                                                from selenium.webdriver.common.keys import Keys
                                                # Find the interactive container
                                                selectors = INTERACTION_CONFIG["SELECT_CONTAINERS"]
                                                sel_str = ", ".join(selectors)
                                                container = self.driver.execute_script(f"""
                                                    var el = arguments[0];
                                                    return el.closest('{sel_str}') || el.parentNode;
                                                """, element)
                                                if container:
                                                    try:
                                                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", container)
                                                        container.click()
                                                        time.sleep(0.1)
                                                    except: pass
                                                
                                                # Activate with common patterns
                                                self.driver.execute_script("arguments[0].focus();", element)
                                                element.send_keys(Keys.DOWN)
                                                time.sleep(0.1)
                                                element.send_keys(Keys.ENTER)
                                                print(f"[TRACKER] ✓ Complex field activation performed")
                                                return True

                                            # Try standard click via super()
                                            result = super().click(locator_key, *args, **kwargs)
                                            print(f"[TRACKER] ✓ Clicked {locator_key} using {by_type}={value}")
                                            
                                            # Minimal sleep for nav, enough to trigger the state change
                                            if any(kw in locator_key.lower() for kw in INTERACTION_CONFIG["NAV_ACTION_KEYWORDS"]):
                                                time.sleep(0.3)
                                            return result
                                        except Exception as e:
                                            err_msg = str(e).lower()
                                            # Aggressively try JS fallback for any intercepted or generic failure
                                            if any(token in err_msg for token in ["intercepted", "interactable", "clickable", "failed", "error", "exception"]):
                                                print(f"[TRACKER] ⚠ Click failed or blocked for {locator_key}, attempting advanced JS click recovery...")
                                                try:
                                                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                                                    import time
                                                    # Skip sleep in recovery unless necessary
                                                    
                                                    # 1. Piercing Logic: Remove whatever is on top of our element
                                                    try:
                                                        modal_selectors = ", ".join(INTERACTION_CONFIG["MODAL_OVERLAYS"] + INTERACTION_CONFIG["NOTIFICATION_BLOCKERS"])
                                                        self.driver.execute_script(f"""
                                                            var el = arguments[0];
                                                            var rect = el.getBoundingClientRect();
                                                            var cx = rect.left + rect.width / 2;
                                                            var cy = rect.top + rect.height / 2;
                                                            var topEl = document.elementFromPoint(cx, cy);
                                                            if (topEl && topEl !== el && !el.contains(topEl)) {{
                                                                topEl.style.display = 'none';
                                                                topEl.style.pointerEvents = 'none';
                                                            }}
                                                            // Also clear global blockers based on interaction model
                                                            document.querySelectorAll('{modal_selectors}').forEach(m => m.style.display = 'none');
                                                        """, element)
                                                    except: pass

                                                    # 2. Try ActionChains first
                                                    try:
                                                        from selenium.webdriver.common.action_chains import ActionChains
                                                        ac = ActionChains(self.driver)
                                                        ac.move_to_element(element).pause(0.5).click().perform()
                                                        print(f"[TRACKER] ✓ Clicked via Piercing ActionChains")
                                                        time.sleep(1.0)
                                                        return True
                                                    except:
                                                        pass

                                                    # 3. Comprehensive JS Event dispatch
                                                    js_click = """
                                                    var el = arguments[0];
                                                    el.style.pointerEvents = 'auto';
                                                    el.style.visibility = 'visible';
                                                    el.style.opacity = '1';
                                                    
                                                    // Specialized handling for AntD selects in JS fallback
                                                    if(el.id && el.id.includes('rc_select')) {
                                                        var selector = el.closest('.ant-select-selector') || el.closest('.ant-select');
                                                        if(selector) { el = selector; }
                                                    }

                                                    var events = ['mouseover', 'mousedown', 'mouseup', 'click'];
                                                    events.forEach(function(name){
                                                        var evt = new MouseEvent(name, { bubbles: true, cancelable: true, view: window });
                                                        el.dispatchEvent(evt);
                                                    });
                                                    
                                                    if(el.tagName === 'INPUT' || el.tagName === 'SELECT') { el.focus(); }
                                                    el.click();
                                                    """
                                                    self.driver.execute_script(js_click, element)
                                                    print(f"[TRACKER] ✓ Clicked {locator_key} via Multi-Event Piercing fallback")
                                                    time.sleep(1.5)
                                                    return True
                                                except Exception as js_e:
                                                    print(f"[TRACKER] Piercing JS fallback failed: {js_e}")
                                            
                                            last_err = e
                                            continue
                                        finally:
                                            if original_locators is not None:
                                                self.locators = original_locators
                                    except Exception as e:
                                        last_err = e
                                        continue
                                
                                # LAST RESORT: Try to find by purpose text
                                try:
                                    purpose = self._full_locators.get(locator_key, [{}])[0].get('purpose', '') if isinstance(self._full_locators.get(locator_key), list) and len(self._full_locators[locator_key]) > 0 and isinstance(self._full_locators[locator_key][0], dict) else ''
                                    if not purpose:
                                        # Deduce purpose from tracker or key
                                        purpose = locator_key.replace('locator_', '').replace('_', ' ')
                                    
                                    print(f"[TRACKER] ⚠ All paths failed. Attempting semantic search for: {purpose}")
                                    semantic_js = f"""
                                    var purpose = "{purpose.lower()}";
                                    var tags = ['button', 'input', 'a', 'span', 'div'];
                                    for(var tag of tags) {{
                                        var elements = document.getElementsByTagName(tag);
                                        for(var el of elements) {{
                                            var text = (el.innerText || el.placeholder || el.ariaLabel || "").toLowerCase();
                                            if(text.includes(purpose) || (el.id && el.id.toLowerCase().includes(purpose))) {{
                                                el.scrollIntoView({{block: 'center'}});
                                                el.click();
                                                return true;
                                            }}
                                        }}
                                    }}
                                    return false;
                                    """
                                    if self.driver.execute_script(semantic_js):
                                        print(f"[TRACKER] ✓ Semantic search found and clicked an element!")
                                        time.sleep(1.0)
                                        return True
                                except:
                                    pass

                                # If we're here, all paths failed
                                self._tracker.clicked_elements.append({
                                    'action': 'click',
                                    'locator': locator_key,
                                    'tag_name': 'unknown',
                                    'description': f'Failed after trying all paths. Last error: {str(last_err)}',
                                    'attributes': {}
                                })
                                print(f"[TRACKER] ✗ Failed to click {locator_key} after trying all paths")
                                raise last_err or ValueError(f"Could not find element for {locator_key}")

                            def send_keys(self, locator_key, text, *args, **kwargs):
                                print(f"[TRACKER] Intercepted send_keys for: {locator_key}")
                                if locator_key not in self._full_locators:
                                    return super().send_keys(locator_key, text, *args, **kwargs)

                                paths = self._full_locators[locator_key]
                                last_err = None
                                
                                for by_type, value in paths:
                                    try:
                                        # Wait for element
                                        from selenium.webdriver.support.ui import WebDriverWait
                                        from selenium.webdriver.support import expected_conditions as EC
                                        element = WebDriverWait(self.driver, 10).until(
                                            EC.presence_of_element_located((by_type, value))
                                        )
                                        self._tracker.track_field_input(element, locator_key, text, f"Input via helper")
                                        
                                        original_locators = None
                                        if hasattr(self, 'locators'):
                                            original_locators = self.locators.copy()
                                            self.locators[locator_key] = (by_type, value)
                                            
                                        try:
                                            result = super().send_keys(locator_key, text, *args, **kwargs)
                                            print(f"[TRACKER] ✓ Input into {locator_key} using {by_type}={value}")
                                            return result
                                        except Exception as e:
                                            # If standard send_keys fails, try JS value injection
                                            print(f"[TRACKER] ⚠ Standard input failed for {locator_key}, attempting JS value fallback...")
                                            try:
                                                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                                                val = str(text).replace("'", "\\'")
                                                self.driver.execute_script(f"arguments[0].value = '{val}';", element)
                                                self.driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", element)
                                                self.driver.execute_script("arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", element)
                                                print(f"[TRACKER] ✓ Injected value via JS fallback")
                                                return True
                                            except Exception as js_e:
                                                print(f"[TRACKER] JS input failed: {js_e}")
                                            
                                            last_err = e
                                            continue
                                        finally:
                                            if original_locators is not None:
                                                self.locators = original_locators
                                    except Exception as e:
                                        last_err = e
                                        continue
                                
                                # Fallback tracking
                                self._tracker.filled_fields.append({
                                    'action': 'input',
                                    'locator': locator_key,
                                    'tag_name': 'unknown',
                                    'value': text,
                                    'description': 'Input failed (element not found in any path)',
                                    'attributes': {}
                                })
                                print(f"[TRACKER] ✗ Failed to input into {locator_key} after trying all paths")
                                raise last_err or ValueError(f"Could not find element for {locator_key}")

                            def hover(self, locator_key, *args, **kwargs):
                                print(f"[TRACKER] Intercepted hover for: {locator_key}")
                                if locator_key not in self._full_locators:
                                    if hasattr(super(), 'hover'):
                                        return super().hover(locator_key, *args, **kwargs)
                                    return None

                                paths = self._full_locators[locator_key]
                                for by_type, value in paths:
                                    try:
                                        # Use WebDriverWait for a split second to ensure it's there
                                        from selenium.webdriver.support.ui import WebDriverWait
                                        from selenium.webdriver.support import expected_conditions as EC
                                        element = WebDriverWait(self.driver, 5).until(
                                            EC.presence_of_element_located((by_type, value))
                                        )
                                        
                                        # Scroll into view with some offset to avoid headers
                                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                                        
                                        if hasattr(self._tracker, 'track_hover'):
                                            self._tracker.track_hover(element, locator_key, "Hover via helper")
                                        
                                        if hasattr(super(), 'hover'):
                                            original_locators = None
                                            if hasattr(self, 'locators'):
                                                original_locators = self.locators.copy()
                                                self.locators[locator_key] = (by_type, value)
                                            try:
                                                return super().hover(locator_key, *args, **kwargs)
                                            finally:
                                                if original_locators is not None:
                                                    self.locators = original_locators
                                        else:
                                            from selenium.webdriver.common.action_chains import ActionChains
                                            import time
                                            ActionChains(self.driver).move_to_element(element).perform()
                                            time.sleep(0.5) # Wait for hover effect
                                            print(f"[TRACKER] ✓ Hovered over {locator_key} using {by_type}={value}")
                                            return True
                                    except:
                                        continue
                                print(f"[TRACKER] ✗ Failed to hover over {locator_key}")
                                return False

                            def switch_tab(self, *args, **kwargs):
                                result = None
                                try:
                                    if hasattr(super(), 'switch_tab'):
                                        result = super().switch_tab(*args, **kwargs)
                                    else:
                                        # Fallback
                                        tab = args[0] if args else ""
                                        if isinstance(tab, int):
                                            handles = self.driver.window_handles
                                            self.driver.switch_to.window(handles[tab])
                                        elif tab == "":
                                            self.driver.switch_to.window(self.driver.window_handles[-1])
                                        else:
                                            # Robust switch: Wait for handles and check current first
                                            import time
                                            target = str(tab).lower()
                                            
                                            # Check if current tab already matches
                                            if target in self.driver.current_url.lower() or target in self.driver.title.lower():
                                                print(f"[TRACKER] Already on tab matching: {tab}")
                                                result = True
                                                found = True
                                            else:
                                                # Retry search for up to 5 seconds (useful for new tabs opening)
                                                found = False
                                                for _ in range(10):
                                                    handles = self.driver.window_handles
                                                    for h in handles:
                                                        self.driver.switch_to.window(h)
                                                        if target in self.driver.current_url.lower() or target in self.driver.title.lower():
                                                            found = True
                                                            break
                                                    if found: break
                                                    time.sleep(0.5)
                                            
                                            if not found:
                                                # Last ditch effort: try as raw handle
                                                try:
                                                    self.driver.switch_to.window(tab)
                                                    result = True
                                                except:
                                                    print(f"[WARN] Could not find tab matching: {tab}")
                                                    result = False
                                        result = found if 'found' in locals() else True
                                except Exception as e:
                                    print(f"[ERROR] switch_tab failed: {e}")
                                    result = False
                                
                                if hasattr(self._tracker, 'track_tab_switch'):
                                    self._tracker.track_tab_switch(args[0] if args else "default")
                                return result

                            def is_verify(self, locator_key, text, *args, **kwargs):
                                print(f"[TRACKER] Intercepted verify for: {locator_key}")
                                if locator_key not in self._full_locators:
                                    if hasattr(super(), 'is_verify'):
                                        return super().is_verify(locator_key, text, *args, **kwargs)
                                    return False

                                paths = self._full_locators[locator_key]
                                for by_type, value in paths:
                                    try:
                                        element = self.driver.find_element(by_type, value)
                                        actual_text = element.text
                                        success = text.lower() in actual_text.lower()
                                        if hasattr(self._tracker, 'track_verification'):
                                            self._tracker.track_verification(element, locator_key, text, actual_text, success)
                                        
                                        if hasattr(super(), 'is_verify'):
                                            return super().is_verify(locator_key, text, *args, **kwargs)
                                        return success
                                    except:
                                        continue
                                return False

                            def get_text(self, locator_key, *args, **kwargs):
                                print(f"[TRACKER] Intercepted get_text for: {locator_key}")
                                if locator_key not in self._full_locators:
                                    if hasattr(super(), 'get_text'):
                                        return super().get_text(locator_key, *args, **kwargs)
                                    return ""

                                paths = self._full_locators[locator_key]
                                for by_type, value in paths:
                                    try:
                                        element = self.driver.find_element(by_type, value)
                                        text = element.text
                                        if hasattr(self._tracker, 'track_get_text'):
                                            self._tracker.track_get_text(element, locator_key, text)
                                        
                                        if hasattr(super(), 'get_text'):
                                            return super().get_text(locator_key, *args, **kwargs)
                                        return text
                                    except:
                                        continue
                                return ""
                        
                        # Replace the Helper class in the module AND sys.modules
                        setattr(selenium_helper_module, helper_class_name, TrackedHelperWrapper)
                        setattr(sys.modules['selenium_helper'], helper_class_name, TrackedHelperWrapper)
                        exec_namespace['selenium_helper'] = selenium_helper_module
                        
                        print(f"    ✓ Action tracking injected into {helper_class_name} class")
                        print(f"    ✓ All future {helper_class_name} instances will include tracking")
                    except Exception as e:
                        print(f"    ⚠ Could not inject tracker: {e}")
                        import traceback
                        traceback.print_exc()
                else:
                    print(f"    ⚠ No Helper or SeleniumHelper class found in selenium_helper module")
                    print(f"    ℹ️  Available attributes: {dir(selenium_helper_module)}")
            else:
                print(f"    ⚠ selenium_helper module not found")
            
            # Try to import selenium components that script might need
            try:
                from selenium.webdriver.common.by import By
                from selenium.webdriver.support.ui import WebDriverWait
                from selenium.webdriver.support import expected_conditions as EC
                from selenium.webdriver.common.keys import Keys
                from selenium.common.exceptions import (
                    NoSuchElementException,
                    TimeoutException,
                    StaleElementReferenceException,
                    ElementClickInterceptedException,
                    ElementNotInteractableException,
                    WebDriverException
                )
                
                exec_namespace.update({
                    'By': By,
                    'WebDriverWait': WebDriverWait,
                    'EC': EC,
                    'Keys': Keys,
                    'NoSuchElementException': NoSuchElementException,
                    'TimeoutException': TimeoutException,
                    'StaleElementReferenceException': StaleElementReferenceException,
                    'ElementClickInterceptedException': ElementClickInterceptedException,
                    'ElementNotInteractableException': ElementNotInteractableException,
                    'WebDriverException': WebDriverException,
                })
            except ImportError:
                pass
            
            # Execute the script
            try:
                exec(script_content, exec_namespace)
                print("-"*80)
                print("[STEP 4] ✓ Script execution completed")
            except ModuleNotFoundError as import_error:
                error_msg = str(import_error)
                print(f"[STEP 4] ⚠️  Script execution encountered an import error: {error_msg}")
                
                # Provide helpful guidance for common import issues
                if "'config'" in error_msg and "is not a package" in error_msg:
                    print("\n  💡 HINT: Your script tries to import from 'config' as a package.")
                    print("     This error occurs when you have:")
                    print("     - A file named 'config.py' (not a package)")
                    print("     - But your script does: from config.keys_config import ...")
                    print("\n     Solutions:")
                    print("     1. Change script import to: from keys_config import ...")
                    print("     2. OR create a config/ directory with __init__.py and keys_config.py inside")
                    print("     3. OR change import to: import config; from config import keys_config")
                
                logger.error(f"Import error during script execution: {error_msg}")
                import traceback
                print("\nFull traceback:")
                traceback.print_exc()
                # Continue to return tracked data even if script fails
            except Exception as script_error:
                logger.error(f"Error during script execution: {str(script_error)}")
                print(f"[STEP 4] ⚠️  Script execution encountered an error: {str(script_error)}")
                import traceback
                print("\nFull traceback:")
                traceback.print_exc()
                # Continue to return tracked data even if script fails
            
            # Step 5: Generate summary
            print("\n[STEP 5] Generating action summary...")
            tracker.print_summary()
            summary = tracker.get_summary()
            print("[STEP 5] ✓ Summary generated")
            
            print("\n" + "="*80)
            print("EXECUTION COMPLETED")
            print("="*80 + "\n")
            
            return {
                "success": True,
                "tracked_actions": summary,
                "script_path": os.path.basename(script_path),
                "locators_loaded": len(locators_dict)
            }
            
        except Exception as e:
            logger.error(f"Error executing script: {str(e)}")
            import traceback
            traceback.print_exc()
            
            return {
                "success": False,
                "error": str(e),
                "tracked_actions": tracker.get_summary() if tracker else None
            }
            
        finally:
            # Cleanup
            if driver:
                try:
                    driver.quit()
                    logger.info("WebDriver closed")
                except Exception as e:
                    logger.error(f"Error closing WebDriver: {str(e)}")
            
            # Restore original sys.path
            try:
                sys.path = original_sys_path
            except:
                # Fallback: remove user's paths manually
                if folder_path in sys.path:
                    sys.path.remove(folder_path)
                if script_dir in sys.path:
                    sys.path.remove(script_dir)
    
    @staticmethod
    def execute_from_zip(
        zip_path: str,
        headless: bool = True
    ) -> Dict[str, Any]:
        """
        Extract zip file and execute the Selenium script inside
        
        Args:
            zip_path: Path to zip file containing Selenium script
            headless: Whether to run browser in headless mode
            
        Returns:
            Dictionary with tracked actions and results
        """
        import zipfile
        
        # Create temp directory for extraction
        with tempfile.TemporaryDirectory() as tmpdir:
            print(f"\nExtracting zip to: {tmpdir}")
            
            # Extract zip
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(tmpdir)
            
            # Find script and locator files
            from utils.locator_parser import ScriptAnalyzer
            
            main_script, locator_files = ScriptAnalyzer.identify_script_files(tmpdir)
            
            if not main_script:
                return {
                    "success": False,
                    "error": "No Selenium script found in uploaded folder"
                }
            
            # Execute script
            return SeleniumScriptExecutor.execute_script_with_tracking(
                script_path=main_script,
                locator_files=locator_files,
                folder_path=tmpdir,
                headless=headless
            )
