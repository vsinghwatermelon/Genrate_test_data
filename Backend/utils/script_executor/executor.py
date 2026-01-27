"""
Selenium Script Executor

Main execution logic for running user Selenium scripts with tracking.
"""

import os
import sys
import importlib.util
import logging
import tempfile
import json
import re
import shutil
import zipfile
from typing import Dict, Any, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By

from utils.selenium_utils import create_chrome_driver
from utils.selenium_tracker import SeleniumActionTracker
from utils.locator_parser import LocatorParser
from .tracked_elements import TrackedWebElement, WebDriverProxy
from .patches import apply_robustness_patches

logger = logging.getLogger(__name__)

class SeleniumScriptExecutor:
    """Executes user-provided Selenium scripts with action tracking"""

    
    @staticmethod
    def _apply_robustness_patches(folder_path, search_bases, locators_dict=None):
        """
        Dynamically find and patch SeleniumHelper class in the payload
        to prevent common crashes and improve tab switching.
        """
        import importlib.util
        import sys
        import types
        
        # Search recursively for any selenium_helper.py
        helper_files = []
        for root, dirs, files in os.walk(folder_path):
            if "selenium_helper.py" in files:
                helper_files.append(os.path.join(root, "selenium_helper.py"))

        for helper_path in list(set(helper_files)):
            try:
                # Potential names depend on which search base we are relative to
                potential_names = set()
                for base in search_bases:
                    try:
                        rel = os.path.relpath(helper_path, base)
                        if not rel.startswith('..'):
                            mod_name = rel.replace(".py", "").replace(os.sep, ".")
                            potential_names.add(mod_name)
                    except:
                        pass
                
                # Also include suffixes of the longest name to be safe
                if potential_names:
                    longest_name = max(potential_names, key=len)
                    parts = longest_name.split('.')
                    for i in range(len(parts)):
                        potential_names.add(".".join(parts[i:]))

                # Import and Patch
                spec = importlib.util.spec_from_file_location("robust_patch_mod", helper_path)
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    # Add parent dirs to path temporarily for internal imports
                    orig_path = sys.path.copy()
                    sys.path.insert(0, os.path.dirname(helper_path))
                    sys.path.insert(0, os.path.dirname(os.path.dirname(helper_path)))
                    try:
                        spec.loader.exec_module(mod)
                        if hasattr(mod, 'SeleniumHelper'):
                            cls = mod.SeleniumHelper
                            patch_helper_class(cls, locators_dict)
                            
                            # Inject into sys.modules
                            helper_dir = os.path.dirname(os.path.abspath(helper_path))
                            for name in potential_names:
                                parts = name.split('.')
                                for i in range(len(parts)):
                                    curr_name = ".".join(parts[:i+1])
                                    if curr_name not in sys.modules:
                                        if i == len(parts) - 1:
                                            sys.modules[curr_name] = mod
                                        else:
                                            m = types.ModuleType(curr_name)
                                            subdir = helper_dir
                                            for _ in range(max(0, len(parts) - 2 - i)):
                                                subdir = os.path.dirname(subdir)
                                            m.__path__ = [subdir] if os.path.isdir(subdir) else []
                                            sys.modules[curr_name] = m
                                    if i > 0:
                                        parent_name = ".".join(parts[:i])
                                        child_name = parts[i]
                                        if hasattr(sys.modules[parent_name], '__dict__'):
                                            setattr(sys.modules[parent_name], child_name, sys.modules[curr_name])
                                logger.info(f"Injected patched helper into sys.modules: {name}")
                    finally:
                        sys.path = orig_path
            except Exception as e:
                logger.error(f"Failed to patch helper at {helper_path}: {e}")

    @staticmethod
    def _patch_helper_class(cls, locators_dict=None):
        """Apply fuzzy tab matching and descriptive error patches to a class"""
        
        # Inject locators if provided
        if locators_dict:
            if not hasattr(cls, 'locators') or not cls.locators:
                cls.locators = locators_dict
                logger.info(f"Injected {len(locators_dict)} locators into {cls.__name__} class")
            else:
                # Merge if it already exists but is a dict
                if isinstance(cls.locators, dict):
                    cls.locators.update(locators_dict)
                    logger.info(f"Merged {len(locators_dict)} locators into {cls.__name__}.locators")
        
        # Patch switch_tab with retry logic
        orig_switch_tab = getattr(cls, 'switch_tab', None)
        if orig_switch_tab and not hasattr(orig_switch_tab, '_is_patched'):
            def robust_switch_tab(self, tab_title):
                import time
                print(f"[PATCH] switch_tab called for: '{tab_title}'")
                
                # Retry loop (up to 3 times with 1.5s sleep)
                for attempt in range(4):
                    try:
                        # Try original first
                        res = orig_switch_tab(self, tab_title)
                        if res: return True
                    except:
                        pass
                    
                    # Fuzzy match: Try to find any handle that matches
                    if attempt == 0: print(f"[PATCH] Attempting fuzzy matching for: '{tab_title}'")
                    try:
                        handles = self.driver.window_handles
                        
                        # If only one handle, wait a bit for a new one
                        if len(handles) < 2 and attempt < 2:
                            time.sleep(1.5)
                            handles = self.driver.window_handles

                        matched = False
                        available_windows = []
                        for handle in handles:
                            try:
                                self.driver.switch_to.window(handle)
                                title = self.driver.title
                                url = self.driver.current_url
                                available_windows.append(f"'{title}' ({url})")
                                
                                # 1. Exact/Substring Match
                                if (tab_title.lower() in title.lower() or 
                                    title.lower() in tab_title.lower() or
                                    tab_title.lower() in url.lower() or
                                    url.lower() in tab_title.lower()):
                                    print(f"[PATCH] SUCCESS: Fuzzy matched tab handle: '{title}' (URL: {url})")
                                    return True
                                
                                # 2. Hyper-lenient Match: Extract keywords from query and check for hits
                                # (e.g. 'app.turtlemint.com' vs 'app.turtlemintinsurance.com')
                                # We look for significant chunks (length > 5)
                                query_parts = [p for p in re.split(r'[^a-zA-Z0-9]', tab_title.lower()) if len(p) > 5]
                                if query_parts and any(p in url.lower() or p in title.lower() for p in query_parts):
                                    print(f"[PATCH] SUCCESS: Hyper-lenient match for '{tab_title}': '{title}' (URL: {url})")
                                    return True
                            except: continue
                        
                        if attempt == 3: # Last attempt
                             print(f"[PATCH] FAILED: No tab matched globally. Available tabs: {available_windows}")
                    except Exception as e:
                        logger.debug(f"Fuzzy tab switch failed: {e}")
                    
                    if attempt < 3:
                        time.sleep(1.5)
                
                print(f"[PATCH] FAILED: No tab matched title or URL for '{tab_title}' after 4 attempts")
                return False
            
            robust_switch_tab._is_patched = True
            cls.switch_tab = robust_switch_tab

        # Patch hover
        orig_hover = getattr(cls, 'hover', None)
        if orig_hover and not hasattr(orig_hover, '_is_patched'):
            def robust_hover(self, locator_id):
                print(f"[PATCH] hover called for: '{locator_id}'")
                try:
                    # Elements are usually found via wait_for_element in these helpers
                    element = self.wait_for_element(locator_id)
                    res = orig_hover(self, locator_id)
                    if hasattr(self.driver, '_tracker'):
                        self.driver._tracker.track_hover(element, locator_id)
                    return res
                except Exception as e:
                    print(f"[PATCH] Hover failed for {locator_id}: {e}")
                    raise
            robust_hover._is_patched = True
            cls.hover = robust_hover

        # Patch is_verify
        orig_verify = getattr(cls, 'is_verify', None)
        if orig_verify and not hasattr(orig_verify, '_is_patched'):
            def robust_verify(self, locator_id, text='', **kwargs):
                print(f"[PATCH] is_verify called for: '{locator_id}' with text='{text}'")
                try:
                    element = self.wait_for_element(locator_id)
                    res = orig_verify(self, locator_id, text=text, **kwargs)
                    if hasattr(self.driver, '_tracker'):
                        # Assuming verify logic is successful if it doesn't raise
                        self.driver._tracker.track_verification(element, locator_id, text, element.text, True)
                    return res
                except Exception as e:
                    if hasattr(self.driver, '_tracker'):
                        # Try to get element for context even if verification fails
                        try:
                            el = self.wait_for_element(locator_id, timeout=1)
                            self.driver._tracker.track_verification(el, locator_id, text, el.text, False)
                        except: pass
                    print(f"[PATCH] Verification failed for {locator_id}: {e}")
                    raise
            robust_verify._is_patched = True
            cls.is_verify = robust_verify

        # Patch get_text
        orig_get_text = getattr(cls, 'get_text', None)
        if orig_get_text and not hasattr(orig_get_text, '_is_patched'):
            def robust_get_text(self, locator_id):
                print(f"[PATCH] get_text called for: '{locator_id}'")
                try:
                    element = self.wait_for_element(locator_id)
                    text = orig_get_text(self, locator_id)
                    if hasattr(self.driver, '_tracker'):
                        self.driver._tracker.track_get_text(element, locator_id, text)
                    return text
                except Exception as e:
                    print(f"[PATCH] get_text failed for {locator_id}: {e}")
                    raise
            robust_get_text._is_patched = True
            cls.get_text = robust_get_text

        # Patch wait_for_element
        orig_wait = getattr(cls, 'wait_for_element', None)
        if orig_wait and not hasattr(orig_wait, '_is_patched'):
            def robust_wait(self, locator_id, timeout=None):
                # print(f"[PATCH] wait_for_element called for: {locator_id}")
                element = orig_wait(self, locator_id, timeout) if timeout is not None else orig_wait(self, locator_id)
                if element is None:
                    # Check if locator exists at all
                    if hasattr(self, 'get_locator_info'):
                        loc_info = self.get_locator_info(locator_id)
                        if not loc_info:
                            raise Exception(f"CRITICAL: Locator ID '{locator_id}' NOT FOUND in any loaded locator config files.")
                    
                    raise Exception(f"CRITICAL: Element not found on page for '{locator_id}' using any provided identifier paths within timeout.")
                return element
            
            robust_wait._is_patched = True
            cls.wait_for_element = robust_wait

    @staticmethod
    def _convert_to_selenium_format(locators: Dict[str, Any]) -> Dict[str, list]:
        """
        Convert potentially raw locators to a list of (By.X, value) tuples.
        """
        selenium_locators = {}
        for key, value in locators.items():
            if isinstance(value, dict):
                # If it's already a dict with by:value, convert it
                paths = []
                for by_str, locator_val in value.items():
                    by_type = None
                    b_u = by_str.upper().replace(' ', '_')
                    if hasattr(By, b_u):
                        by_type = getattr(By, b_u)
                    elif b_u == 'CSS':
                        by_type = By.CSS_SELECTOR
                    
                    if by_type:
                        if isinstance(locator_val, list):
                            for v in locator_val: paths.append((by_type, v))
                        else:
                            paths.append((by_type, locator_val))
                selenium_locators[key] = paths
            else:
                # Fallback or already converted
                selenium_locators[key] = value
        return selenium_locators
    
    @staticmethod
    def setup_driver(headless: bool = True, use_wire: bool = False) -> webdriver.Chrome:
        """
        Setup Chrome WebDriver with options.
        This method is now simplified to instantiate SeleniumHelper and return its driver.
        
        Args:
            headless: Whether to run browser in headless mode
            use_wire: Whether to use selenium-wire for request interception
            
        Returns:
            Configured Chrome WebDriver instance
        """
        try:
            driver = create_chrome_driver(headless=headless, use_wire=use_wire)
            
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
                """
                Generate dynamic test data based on field name.
                No hardcoded values - creates contextual placeholders.
                """
                k = str(key).lower()
                if 'email' in k:
                    return f"user_{key}@example.com"
                elif 'phone' in k or 'mobile' in k:
                    return "1234567890"
                elif 'name' in k:
                    return f"Test_{key}"
                elif 'date' in k or 'dob' in k:
                    return "01/01/2000"
                elif 'pin' in k or 'zip' in k or 'postal' in k:
                    return "000000"
                elif 'city' in k:
                    return "TestCity"
                elif 'state' in k:
                    return "TestState"
                elif 'age' in k:
                    return "25"
                else:
                    return default or f'test_{key}'
            
            # Attach custom methods to driver instance
            driver.get_test_data_value = get_test_data_value
            
            return driver
        except Exception as e:
            logger.error(f"Failed to setup WebDriver: {str(e)}")
            raise
    
    @staticmethod
    def execute_script_with_tracking(
        script_path: str,
        locator_files: list,
        folder_path: str,
        headless: bool = True,
        use_wire: bool = False
    ) -> Dict[str, Any]:
        """
        Execute a Selenium script and track all actions
        
        Args:
            script_path: Path to the main Selenium script
            locator_files: List of paths to locator configuration files
            folder_path: Path to the folder containing the script
            headless: Whether to run browser in headless mode
            use_wire: Whether to use selenium-wire for request interception
            
        Returns:
            Dictionary with tracked actions and results
        """
        driver = None
        tracker = SeleniumActionTracker()
        original_sys_path = sys.path.copy()
        script_dir = None
        folder_path_to_clean = folder_path
        
        try:
            print("\n" + "="*80)
            print("EXECUTING SELENIUM SCRIPT WITH ACTION TRACKING")
            print("="*80)
            
            # Step 1: Parse locators from all potential sources in the payload
            print(f"\n[STEP 1] Scanning for locators across all files...")
            locators_dict = {}
            
            # We recursively scan the folder_path for any .py or .json files
            # to ensure we don't miss any locator definitions
            potential_sources = []
            for root, dirs, files in os.walk(folder_path):
                for f in files:
                    if f.endswith(('.py', '.json')) and not f.startswith('__'):
                        potential_sources.append(os.path.join(root, f))
            
            print(f"  → Found {len(potential_sources)} potential locator sources.")
            
            for source_file in potential_sources:
                try:
                    # Skip the main script file itself if we want, or include it
                    # (including it is safer for inline locators)
                    parsed_locators = LocatorParser.parse_file(source_file)
                    if parsed_locators:
                        selenium_locators = SeleniumScriptExecutor._convert_to_selenium_format(parsed_locators)
                        locators_dict.update(selenium_locators)
                        # Only print if we actually found something significant
                        if len(selenium_locators) > 0:
                            print(f"  ✓ Found {len(selenium_locators)} locators in {os.path.basename(source_file)}")
                except: continue
            
            print(f"[STEP 1] ✓ Total unique locators loaded: {len(locators_dict)}")
            
            # Step 2: Setup WebDriver
            print(f"\n[STEP 2] Setting up Chrome WebDriver (headless={headless}, wire={use_wire})...")
            driver = SeleniumScriptExecutor.setup_driver(headless=headless, use_wire=use_wire)
            print("[STEP 2] ✓ WebDriver ready")
            
            # Step 3: Load script
            print(f"\n[STEP 3] Loading script: {os.path.basename(script_path)}")
            with open(script_path, 'r', encoding='utf-8-sig', errors='replace') as f:
                script_content = f.read()
            
            # Step 4: Execute script with injected tracker
            print(f"\n[STEP 4] Executing script with action tracking...")
            print("-"*80)
            
            # Prepare execution environment
            script_dir = os.path.dirname(script_path)
            
            # Handle Module Isolation and Path Priority
            # First, clean up sys.modules to remove any conflicting 'config' or 'utils' modules
            # that might have been loaded by the Backend itself.
            conflicting_modules = ['config', 'utils', 'selenium_helper', 'locators_config', 'keys_config']
            original_modules = {}
            for mod_name in conflicting_modules:
                if mod_name in sys.modules:
                    original_modules[mod_name] = sys.modules.pop(mod_name)
                    logger.debug(f"Temporarily removed {mod_name} from sys.modules")
            
            # Build new sys.path with user's folders at the VERY BEGINNING
            # We want to ensure that 'import config' finds the user's config folder/file.
            backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            filtered_paths = [p for p in original_sys_path if not p.startswith(backend_path)]
            
            # Priority: 1. Script folder, 2. Root folder of payload
            # AND 3. Parent directories of all locator files found (to support nested 'config' packages)
            locator_parent_dirs = list(set([os.path.dirname(os.path.dirname(f)) for f in locator_files]))
            search_bases = [script_dir, folder_path] + locator_parent_dirs
            
            # Ensure __init__.py exists in all subdirectories to support dotted imports
            for root, dirs, files in os.walk(folder_path):
                for d in dirs:
                    init_file = os.path.join(root, d, "__init__.py")
                    if not os.path.exists(init_file):
                        try:
                            with open(init_file, 'w') as f:
                                pass
                            logger.debug(f"Created missing __init__.py in {os.path.join(root, d)}")
                        except Exception as e:
                            logger.debug(f"Failed to create __init__.py in {os.path.join(root, d)}: {e}")

            sys.path = search_bases + filtered_paths
            
            # Wrap driver with proxy for active_element tracking
            proxy_driver = WebDriverProxy(driver, tracker)
            
            # Global Monkey-patching to intercept all webdriver creations
            import selenium.webdriver
            import selenium.webdriver.chrome.webdriver as chrome_mod
            import selenium.webdriver.remote.webdriver as remote_mod
            
            orig_chrome = selenium.webdriver.Chrome
            orig_remote = selenium.webdriver.Remote
            orig_chrome_mod = chrome_mod.WebDriver
            orig_remote_mod = remote_mod.WebDriver
            
            # Function to return our proxy driver instead of a new one
            def mock_driver_factory(*a, **k):
                print(f"[DEBUG] Mock driver factory called! Returning proxy driver.")
                return proxy_driver
            
            selenium.webdriver.Chrome = mock_driver_factory
            selenium.webdriver.Remote = mock_driver_factory
            chrome_mod.WebDriver = mock_driver_factory
            remote_mod.WebDriver = mock_driver_factory
            
            # Create base namespace for script execution
            exec_namespace = {
                'driver': proxy_driver,
                '__file__': script_path,
                '__name__': '__main__',
                'undefined': None,
                'args': {}, 
            }
            
            # Add common selenium components to namespace for convenience
            try:
                from selenium.webdriver.common.by import By
                from selenium.webdriver.support.ui import WebDriverWait
                from selenium.webdriver.support import expected_conditions as EC
                from selenium.webdriver.common.keys import Keys
                from selenium.webdriver.common.action_chains import ActionChains
                from selenium.webdriver.support.ui import Select
                from selenium.common.exceptions import (
                    NoSuchElementException, TimeoutException, StaleElementReferenceException,
                    ElementClickInterceptedException, ElementNotInteractableException, WebDriverException
                )
                
                exec_namespace.update({
                    'By': By, 'WebDriverWait': WebDriverWait, 'EC': EC, 'Keys': Keys,
                    'ActionChains': ActionChains, 'Select': Select,
                    'NoSuchElementException': NoSuchElementException, 'TimeoutException': TimeoutException,
                    'StaleElementReferenceException': StaleElementReferenceException,
                    'ElementClickInterceptedException': ElementClickInterceptedException,
                    'ElementNotInteractableException': ElementNotInteractableException,
                    'WebDriverException': WebDriverException,
                })
            except ImportError:
                pass
            
            
            # Step 5: Execute the script
            try:
                # Link tracker with namespace for expression resolution
                setattr(tracker, '_exec_namespace', exec_namespace)
                
                # Apply robustness patches to any SeleniumHelper classes in the payload
                apply_robustness_patches(folder_path, search_bases, locators_dict)
                
                # We use exec with the prepared namespace and isolated sys.modules
                exec(script_content, exec_namespace)
                print("-"*80)
                print("[STEP 5] ✓ Script execution completed")
            except Exception as script_error:
                logger.error(f"Error during script execution: {str(script_error)}")
                print(f"[STEP 5] ⚠️  Script execution encountered an error: {str(script_error)}")
                import traceback
                traceback.print_exc()
            
            # Step 5.5: Collect API calls if using selenium-wire
            if use_wire:
                real_driver = getattr(driver, '_driver', driver)
                print(f"\n[STEP 5.5] Processing intercepted API calls (Fetch/XHR)...")
                print(f"  → Driver type: {type(real_driver).__name__}")
                
                if hasattr(real_driver, 'requests'):
                    all_requests = real_driver.requests
                    print(f"  → Total requests in storage: {len(all_requests)}")
                    
                    for request in all_requests:
                        if request.response:
                            content_type = request.response.headers.get('Content-Type', '').lower()
                            fetch_mode = request.headers.get('Sec-Fetch-Mode', '')
                            xhr = request.headers.get('X-Requested-With', '')
                            
                            # BROAD DYNAMIC FILTERING: Capture common API patterns
                            should_capture = False
                            
                            # 1. X-Requested-With (Standard for AJAX)
                            if request.headers.get('X-Requested-With', '').lower() == 'xmlhttprequest':
                                should_capture = True
                                
                            # 2. Sec-Fetch-Dest (empty usually implies fetch/XHR)
                            elif request.headers.get('Sec-Fetch-Dest', '').lower() == 'empty':
                                should_capture = True
                                
                            # 3. Common API content types in RESPONSE
                            elif any(t in content_type for t in ['application/json', 'application/xml', 'text/xml', 'application/x-javascript']):
                                should_capture = True
                            
                            # 4. Request Method (POST/PUT/PATCH/DELETE are usually API calls)
                            elif request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
                                should_capture = True
                            
                            # 5. URL patterns (common API indicators)
                            elif any(p in request.url.lower() for p in ['/api/', 'v1/', 'v2/', 'graphql', '.json']):
                                should_capture = True

                            if should_capture:
                                 # Capture response body if available
                                 response_body = None
                                 try:
                                     if request.response and request.response.body:
                                         response_body = request.response.body
                                 except:
                                     pass
                                 
                                 tracker.track_api_call(
                                     url=request.url,
                                     method=request.method,
                                     payload=request.body,
                                     headers=dict(request.headers),
                                     response_code=request.response.status_code,
                                     response_body=response_body
                                 )
                    
                    print(f"[STEP 5.5] ✓ Processed {len(tracker.api_calls)} API calls")
                else:
                     print(f"[WARN] use_wire=True but driver has no 'requests' attribute. Selenium-wire might not be active.")

            # Step 6: Restore original modules to sys.modules
            for mod_name, mod_obj in original_modules.items():
                sys.modules[mod_name] = mod_obj
                logger.debug(f"Restored {mod_name} to sys.modules")
            
            # Step 7: Generate summary
            print("\n[STEP 7] Generating action summary...")
            # Capture final screenshot
            tracker.capture_screenshot(driver, label="Final State")
            tracker.print_summary()
            summary = tracker.get_summary()
            print("[STEP 7] ✓ Summary generated")
            
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
            # Restore original selenium components if they were patched
            try:
                import selenium.webdriver
                import selenium.webdriver.chrome.webdriver as chrome_mod
                import selenium.webdriver.remote.webdriver as remote_mod
                if 'orig_chrome' in locals(): selenium.webdriver.Chrome = orig_chrome
                if 'orig_remote' in locals(): selenium.webdriver.Remote = orig_remote
                if 'orig_chrome_mod' in locals(): chrome_mod.WebDriver = orig_chrome_mod
                if 'orig_remote_mod' in locals(): remote_mod.WebDriver = orig_remote_mod
            except:
                pass

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
                if script_dir and script_dir in sys.path:
                    sys.path.remove(script_dir)
    
    @staticmethod
    def execute_from_zip(
        zip_path: str,
        headless: bool = True,
        use_wire: bool = False
    ) -> Dict[str, Any]:
        """
        Extract zip file and execute the Selenium script inside
        
        Args:
            zip_path: Path to zip file containing Selenium script
            headless: Whether to run browser in headless mode
            use_wire: Whether to use selenium-wire for request interception
            
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
                headless=headless,
                use_wire=use_wire
            )
