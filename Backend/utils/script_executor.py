"""
Selenium Script Executor

Utility to execute user-provided Selenium scripts and inject action tracking.
"""

import os
import sys
import importlib.util
import logging
import tempfile
import shutil
from typing import Dict, Any, Optional
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from utils.selenium_tracker import SeleniumActionTracker, TrackedHelper
from utils.locator_parser import LocatorParser
from selenium.webdriver.common.by import By

logger = logging.getLogger(__name__)


class SeleniumScriptExecutor:
    """
    Executes user-provided Selenium scripts with action tracking
    """
    
    @staticmethod
    def _convert_to_selenium_format(locators: Dict[str, Any]) -> Dict[str, tuple]:
        """
        Convert parsed locators to Selenium (By.X, "value") format.
        
        Args:
            locators: Dictionary from LocatorParser.parse_file()
                     Format can be:
                     1. Already in Selenium format: {'locator_key': (By.ID, 'value')}
                     2. Tuple format: {'locator_key': ('id', 'value')}
                     3. Dict format: {'locator_key': {'type': 'id', 'value': 'username'}}
        
        Returns:
            Dictionary with Selenium (By.X, "value") tuples
        """
        selenium_locators = {}
        
        for key, value in locators.items():
            try:
                # Case 1: Already a tuple (By.X, "value") or ('type', 'value')
                if isinstance(value, tuple) and len(value) == 2:
                    by_type, locator_value = value
                    
                    # Check if it's already a By object (from selenium.webdriver.common.by)
                    if hasattr(by_type, '__name__') and by_type.__name__ in ['ID', 'NAME', 'CLASS_NAME', 'TAG_NAME', 'CSS_SELECTOR', 'XPATH', 'LINK_TEXT', 'PARTIAL_LINK_TEXT']:
                        # Already in correct format
                        selenium_locators[key] = (by_type, locator_value)
                    elif isinstance(by_type, str):
                        # Convert string type to By.X
                        by_type = by_type.upper()
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
                            'PARTIAL_LINK_TEXT': By.PARTIAL_LINK_TEXT,
                        }
                        by_obj = by_mapping.get(by_type, By.CSS_SELECTOR)
                        selenium_locators[key] = (by_obj, locator_value)
                    else:
                        # Unknown format, try to use as-is
                        selenium_locators[key] = (by_type, locator_value)
                
                # Case 2: Dictionary format
                elif isinstance(value, dict):
                    # Check if it's a nested format like: {'xpath': [...], 'css selector': [...]}
                    if any(k.lower() in ['xpath', 'css', 'css selector', 'css_selector', 'id', 'name'] for k in value.keys()):
                        # Pick the first available selector type with values
                        # Priority: CSS > XPath > ID > Name
                        selector_priority = [
                            ('css selector', By.CSS_SELECTOR),
                            ('css_selector', By.CSS_SELECTOR),
                            ('css', By.CSS_SELECTOR),
                            ('id', By.ID),
                            ('name', By.NAME),
                            ('xpath', By.XPATH),
                            ('class name', By.CLASS_NAME),
                            ('class_name', By.CLASS_NAME),
                        ]
                        
                        for selector_key, by_type in selector_priority:
                            if selector_key in value:
                                selectors = value[selector_key]
                                # Get first non-empty selector from list
                                if isinstance(selectors, list) and selectors:
                                    locator_value = selectors[0]
                                    selenium_locators[key] = (by_type, locator_value)
                                    break
                                elif isinstance(selectors, str) and selectors:
                                    selenium_locators[key] = (by_type, selectors)
                                    break
                    else:
                        # Simple dict format: {'type': 'id', 'value': 'username'}
                        locator_type = value.get('type', value.get('by', 'css'))
                        locator_value = value.get('value', value.get('selector', ''))
                        
                        if locator_value:
                            locator_type = locator_type.upper()
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
                                'PARTIAL_LINK_TEXT': By.PARTIAL_LINK_TEXT,
                            }
                            by_type = by_mapping.get(locator_type, By.CSS_SELECTOR)
                            selenium_locators[key] = (by_type, locator_value)
                
                # Case 3: Simple string (assume it's a CSS selector)
                elif isinstance(value, str):
                    selenium_locators[key] = (By.CSS_SELECTOR, value)
                else:
                    logger.warning(f"Unknown locator format for {key}: {type(value).__name__} - {value}")
                    
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
        chrome_options = Options()
        if headless:
            chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        
        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Add custom methods to driver that scripts might expect
            def get_test_data_value(key, default=None):
                """Mock method for test data retrieval"""
                print(f"[INFO] get_test_data_value called with key: {key}")
                # Return some sensible defaults based on common key patterns
                if 'email' in key.lower():
                    return 'test@example.com'
                elif 'phone' in key.lower() or 'mobile' in key.lower():
                    return '9876543210'
                elif 'name' in key.lower():
                    return 'Test User'
                elif 'age' in key.lower():
                    return '30'
                elif 'address' in key.lower():
                    return 'Test Address'
                elif 'pin' in key.lower() or 'zip' in key.lower():
                    return '400001'
                return default or 'test_value'
            
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
                                print(f"[TRACKER] {helper_class_name} instance created with tracking enabled")
                                
                                # CRITICAL: Attach get_test_data_value to the helper's driver instance
                                # The helper might have its own driver or might have modified the one passed
                                if hasattr(self, 'driver') and self.driver:
                                    def get_test_data_value(key, default=None):
                                        """Mock method for test data retrieval"""
                                        print(f"[INFO] get_test_data_value called with key: {key}")
                                        if 'email' in key.lower():
                                            return 'test@example.com'
                                        elif 'phone' in key.lower() or 'mobile' in key.lower():
                                            return '9876543210'
                                        elif 'name' in key.lower():
                                            return 'Test User'
                                        elif 'age' in key.lower():
                                            return '30'
                                        elif 'address' in key.lower():
                                            return 'Test Address'
                                        elif 'pin' in key.lower() or 'zip' in key.lower():
                                            return '400001'
                                        return default or 'test_value'
                                    
                                    self.driver.get_test_data_value = get_test_data_value
                                    print(f"[TRACKER] ✓ Attached get_test_data_value to helper's driver")
                            
                            def click(self, locator_key, *args, **kwargs):
                                print(f"[TRACKER] Intercepted click for: {locator_key}")
                                
                                # Track the attempt BEFORE calling the action
                                # Try to get element details, but track even if we can't find it
                                try:
                                    if locator_key in locators_dict:
                                        by_type, value = locators_dict[locator_key]
                                        try:
                                            element = self.driver.find_element(by_type, value)
                                            self._tracker.track_click(element, locator_key, f"Click via helper")
                                            print(f"[TRACKER] ✓ Tracked click attempt: {locator_key}")
                                        except:
                                            # Element not found, but still track the locator attempt
                                            self._tracker.clicked_elements.append({
                                                'action': 'click',
                                                'locator': locator_key,
                                                'tag_name': 'unknown',
                                                'text': '',
                                                'description': 'Click attempt (element not found)',
                                                'attributes': {}
                                            })
                                            self._tracker.actions_log.append(self._tracker.clicked_elements[-1])
                                            print(f"[TRACKER] ✓ Tracked click attempt (element not found): {locator_key}")
                                except Exception as track_err:
                                    print(f"[TRACKER] ⚠ Could not track click: {track_err}")
                                
                                # Now execute the actual click (may fail, but we've already tracked it)
                                result = super().click(locator_key, *args, **kwargs)
                                return result
                            
                            def send_keys(self, locator_key, text, *args, **kwargs):
                                print(f"[TRACKER] Intercepted send_keys for: {locator_key}")
                                
                                # Track the attempt BEFORE calling the action
                                # Try to get element details, but track even if we can't find it
                                try:
                                    if locator_key in locators_dict:
                                        by_type, value = locators_dict[locator_key]
                                        try:
                                            element = self.driver.find_element(by_type, value)
                                            self._tracker.track_field_input(element, locator_key, text, f"Input via helper")
                                            print(f"[TRACKER] ✓ Tracked input attempt: {locator_key}")
                                        except:
                                            # Element not found, but still track the locator attempt
                                            self._tracker.filled_fields.append({
                                                'action': 'input',
                                                'locator': locator_key,
                                                'tag_name': 'unknown',
                                                'value': text,
                                                'description': 'Input attempt (element not found)',
                                                'attributes': {}
                                            })
                                            self._tracker.actions_log.append(self._tracker.filled_fields[-1])
                                            print(f"[TRACKER] ✓ Tracked input attempt (element not found): {locator_key}")
                                except Exception as track_err:
                                    print(f"[TRACKER] ⚠ Could not track input: {track_err}")
                                
                                # Now execute the actual input (may fail, but we've already tracked it)
                                result = super().send_keys(locator_key, text, *args, **kwargs)
                                return result
                        
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
