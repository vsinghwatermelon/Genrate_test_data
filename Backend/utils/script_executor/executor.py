"""
Selenium Script Executor

Orchestrates the execution of user-provided Selenium scripts while tracking all interactions.
Handles driver setup, locator parsing, script environment preparation, and API call interception.
"""

import os
import sys
import logging
import tempfile
import time
import zipfile
from typing import Dict, Any

from selenium import webdriver
from selenium.webdriver.common.by import By

from utils.selenium_utils import create_chrome_driver
from utils.selenium_tracker import SeleniumActionTracker
from utils.locator_parser import LocatorParser, ScriptAnalyzer
from .tracked_elements import WebDriverProxy
from .patches import apply_robustness_patches

logger = logging.getLogger(__name__)


class SeleniumScriptExecutor:
    """
    Main executor for running Selenium scripts with comprehensive action tracking.
    
    This class provides methods to:
    - Set up Chrome WebDriver with optional API interception
    - Parse and load element locators from various sources
    - Execute scripts in an isolated environment
    - Track user interactions (clicks, inputs, API calls)
    - Generate detailed execution summaries
    """

    # ============================================================================
    # SECTION 1: Driver Setup & Configuration
    # ============================================================================
    
    @staticmethod
    def setup_driver(headless: bool = True, use_wire: bool = False) -> webdriver.Chrome:
        """
        Create and configure a Chrome WebDriver instance.
        
        Sets up a WebDriver with optional selenium-wire for API interception,
        adds helper methods for test data generation, and applies fixes for
        common script compatibility issues.
        
        Args:
            headless: Run browser without visible window
            use_wire: Enable selenium-wire for intercepting network requests
            
        Returns:
            Configured Chrome WebDriver ready for script execution
        """
        try:
            driver = create_chrome_driver(headless=headless, use_wire=use_wire)
            
            # Fix scripts that pass strings to implicitly_wait instead of integers
            original_wait = driver.implicitly_wait
            def safe_implicitly_wait(time_to_wait):
                if isinstance(time_to_wait, str):
                    try:
                        time_to_wait = int(time_to_wait)
                    except ValueError:
                        time_to_wait = 10  # Sensible default
                return original_wait(time_to_wait)
            
            driver.implicitly_wait = safe_implicitly_wait
            
            # Add test data generation helper to driver
            def get_test_data_value(key, default=None):
                """
                Generate contextual test data based on field name.
                Creates reasonable placeholder values instead of hardcoded data.
                """
                field_name = str(key).lower()
                
                # Email fields
                if 'email' in field_name:
                    return f"user_{key}@example.com"
                    
                # Phone/mobile fields
                if 'phone' in field_name or 'mobile' in field_name:
                    return "1234567890"
                    
                # Name fields
                if 'name' in field_name:
                    return f"Test_{key}"
                    
                # Date fields
                if 'date' in field_name or 'dob' in field_name:
                    return "01/01/2000"
                    
                # Location fields
                if 'pin' in field_name or 'zip' in field_name or 'postal' in field_name:
                    return "000000"
                if 'city' in field_name:
                    return "TestCity"
                if 'state' in field_name:
                    return "TestState"
                    
                # Age field
                if 'age' in field_name:
                    return "25"
                    
                # Default fallback
                return default or f'test_{key}'
            
            driver.get_test_data_value = get_test_data_value
            
            return driver
            
        except Exception as e:
            logger.error(f"Failed to setup WebDriver: {str(e)}")
            raise

    # ============================================================================
    # SECTION 2: Locator Processing
    # ============================================================================
    
    @staticmethod
    def _convert_to_selenium_format(locators: Dict[str, Any]) -> Dict[str, list]:
        """
        Transform raw locator definitions into Selenium-compatible format.
        
        Converts dictionary-based locator definitions (e.g., {"css": ".btn"})
        into tuples of (By.CSS_SELECTOR, ".btn") that Selenium understands.
        
        Args:
            locators: Raw locator definitions from config files
            
        Returns:
            Dict mapping locator IDs to lists of (By type, value) tuples
        """
        selenium_locators = {}
        
        for locator_id, locator_value in locators.items():
            if not isinstance(locator_value, dict):
                # Already in correct format or unsupported  
                selenium_locators[locator_id] = locator_value
                continue
            
            # Convert each locator strategy to (By type, value) tuple
            paths = []
            seen = set()
            for strategy, value in locator_value.items():
                # Normalize strategy name (e.g., "CSS" -> "CSS_SELECTOR")
                normalized = strategy.upper().replace(' ', '_')
                by_type = getattr(By, normalized, None) if hasattr(By, normalized) else None
                
                # Special case for CSS
                if normalized == 'CSS':
                    by_type = By.CSS_SELECTOR
                
                if by_type:
                    # Support both single values and lists
                    values = value if isinstance(value, list) else [value]
                    for v in values:
                        pair = (by_type, str(v))
                        if pair not in seen:
                            paths.append(pair)
                            seen.add(pair)
            
            selenium_locators[locator_id] = paths
        
        return selenium_locators

    @staticmethod
    def _load_locators_from_folder(folder_path: str) -> Dict[str, list]:
        """
        Recursively scan folder for locator definitions in Python and JSON files.
        
        Searches through all files in the folder and extracts locator configurations
        from Python files (e.g., locators_config.py) and JSON files.
        
        Args:
            folder_path: Root directory to search for locator files
            
        Returns:
            Dictionary of all unique locators found, converted to Selenium format
        """
        print(f"\n[LOCATORS] Scanning for locator definitions...")
        locators_dict = {}
        
        # Find all potential locator source files
        potential_sources = []
        for root, _, files in os.walk(folder_path):
            for filename in files:
                if filename.endswith(('.py', '.json')) and not filename.startswith('__'):
                    potential_sources.append(os.path.join(root, filename))
        
        print(f"[LOCATORS] Found {len(potential_sources)} potential source files")
        
        # Parse each file and collect locators
        for source_file in potential_sources:
            try:
                parsed = LocatorParser.parse_file(source_file)
                if parsed:
                    # Flatten: if parsed is {'locators': {...}}, we want the contents
                    to_merge = {}
                    for k, v in parsed.items():
                        if isinstance(v, dict) and any(ik in str(v.keys()) for ik in ['xpath', 'css', 'id']):
                            # It's a single locator definition
                            to_merge[k] = v
                        elif isinstance(v, dict):
                            # It's a dictionary of locators (like 'locators = { ... }')
                            to_merge.update(v)
                        else:
                            # Scalar value, probably a constant
                            to_merge[k] = v
                    
                    converted = SeleniumScriptExecutor._convert_to_selenium_format(to_merge)
                    locators_dict.update(converted)
                    
                    if converted:
                        print(f"[LOCATORS]   ✓ {len(converted)} locators from {os.path.basename(source_file)}")
            except Exception as e:
                logger.debug(f"Skipping locator source {source_file}: {e}")
                continue
        
        print(f"[LOCATORS] ✓ Loaded {len(locators_dict)} unique locators total\n")
        return locators_dict

    # ============================================================================
    # SECTION 3: Environment Preparation
    # ============================================================================
    
    @staticmethod
    def _prepare_execution_environment(folder_path: str, script_dir: str, locator_files: list):
        """
        Set up Python import paths and module isolation for script execution.
        
        Ensures the user's script can import its own modules (config, utils, etc.)
        without conflicts with the backend's modules. Creates missing __init__.py
        files to support package imports.
        
        Args:
            folder_path: Root folder of the uploaded script
            script_dir: Directory containing the main script file  
            locator_files: List of locator file paths (for determining search paths)
            
        Returns:
            tuple: (search_bases, original_modules, original_sys_path)
        """
        # Remove backend modules that might conflict with user's imports
        conflicting_modules = ['config', 'utils', 'selenium_helper', 'locators_config', 'keys_config']
        original_modules = {}
        
        for module_name in conflicting_modules:
            if module_name in sys.modules:
                original_modules[module_name] = sys.modules.pop(module_name)
                logger.debug(f"Temporarily removed {module_name} from sys.modules")
        
        # Build import search paths prioritizing user's code
        backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        original_sys_path = sys.path.copy()
        filtered_paths = [p for p in original_sys_path if not p.startswith(backend_path)]
        
        # Priority order: script folder, payload root, locator parent dirs
        locator_parent_dirs = list(set([os.path.dirname(os.path.dirname(f)) for f in locator_files]))
        search_bases = [script_dir, folder_path] + locator_parent_dirs
        
        # Create __init__.py files for package imports
        for root, dirs, _ in os.walk(folder_path):
            for directory in dirs:
                init_file = os.path.join(root, directory, "__init__.py")
                if not os.path.exists(init_file):
                    try:
                        with open(init_file, 'w') as f:
                            pass
                        logger.debug(f"Created __init__.py in {os.path.join(root, directory)}")
                    except Exception as e:
                        logger.debug(f"Could not create __init__.py: {e}")
        
        sys.path = search_bases + filtered_paths
        
        return search_bases, original_modules, original_sys_path

    @staticmethod
    def _create_execution_namespace(proxy_driver, script_path):
        """
        Build the namespace (global variables) for script execution.
        
        Provides the driver and common Selenium imports so user scripts
        don't need to manually import them.
        
        Args:
            proxy_driver: Wrapped WebDriver with tracking capabilities
            script_path: Path to the script being executed
            
        Returns:
            Dictionary containing driver and Selenium utilities
        """
        namespace = {
            'driver': proxy_driver,
            '__file__': script_path,
            '__name__': '__main__',
            'undefined': None,  # Some scripts check for undefined values
            'args': {},  # Empty args dict for scripts expecting command-line args
        }
        
        # Add common Selenium imports for convenience
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
            
            namespace.update({
                'By': By,
                'WebDriverWait': WebDriverWait,
                'EC': EC,
                'Keys': Keys,
                'ActionChains': ActionChains,
                'Select': Select,
                'NoSuchElementException': NoSuchElementException,
                'TimeoutException': TimeoutException,
                'StaleElementReferenceException': StaleElementReferenceException,
                'ElementClickInterceptedException': ElementClickInterceptedException,
                'ElementNotInteractableException': ElementNotInteractableException,
                'WebDriverException': WebDriverException,
            })
        except ImportError:
            # Older Selenium versions might not have all these
            pass
        
        return namespace

    @staticmethod
    def _setup_driver_interception(driver, tracker):
        """
        Monkey-patch Selenium's WebDriver constructors.
        
        This ensures that if the user script tries to create its own driver
        (e.g., driver = webdriver.Chrome()), it gets our tracked proxy driver
        instead of creating an untracked new instance.
        
        Args:
            driver: The real WebDriver instance to wrap
            tracker: Action tracker for recording interactions
            
        Returns:
            tuple: (proxy_driver, original_constructors_dict)
        """
        from selenium import webdriver as wd
        import selenium.webdriver.chrome.webdriver as chrome_mod
        import selenium.webdriver.remote.webdriver as remote_mod
        
        # Save original constructors
        originals = {
            'selenium_chrome': wd.Chrome,
            'selenium_remote': wd.Remote,
            'chrome_webdriver': chrome_mod.WebDriver,
            'remote_webdriver': remote_mod.WebDriver,
        }
        
        # Create proxy driver
        proxy_driver = WebDriverProxy(driver, tracker)
        
        # Replace constructors with factory returning our proxy
        def mock_factory(*args, **kwargs):
            logger.debug("Script tried to create new driver - returning tracked proxy instead")
            return proxy_driver
        
        wd.Chrome = mock_factory
        wd.Remote = mock_factory
        chrome_mod.WebDriver = mock_factory
        remote_mod.WebDriver = mock_factory
        
        return proxy_driver, originals

    @staticmethod
    def _restore_driver_constructors(originals):
        """
        Restore original Selenium WebDriver constructors after script execution.
        
        Args:
            originals: Dictionary of original constructor functions
        """
        try:
            from selenium import webdriver as wd
            import selenium.webdriver.chrome.webdriver as chrome_mod
            import selenium.webdriver.remote.webdriver as remote_mod
            
            wd.Chrome = originals.get('selenium_chrome', wd.Chrome)
            wd.Remote = originals.get('selenium_remote', wd.Remote)
            chrome_mod.WebDriver = originals.get('chrome_webdriver', chrome_mod.WebDriver)
            remote_mod.WebDriver = originals.get('remote_webdriver', remote_mod.WebDriver)
        except Exception:
            pass

    # ============================================================================
    # SECTION 4: API Call Collection
    # ============================================================================
    
    @staticmethod
    def _collect_api_calls(driver, tracker):
        """
        Extract and filter API calls from selenium-wire's request log.
        
        Only captures APIs that were triggered by user clicks (within 3 seconds).
        Filters out page loads, assets, and other non-API traffic.
        
        Args:
            driver: selenium-wire enabled WebDriver
            tracker: Action tracker containing click timestamps
            
        Returns:
            tuple: (captured_count, skipped_count)
        """
        print(f"\n[API COLLECTION] Processing intercepted network requests...")
        
        real_driver = getattr(driver, '_driver', driver)
        
        if not hasattr(real_driver, 'requests'):
            print(f"[API COLLECTION] ⚠️  selenium-wire not active - driver missing 'requests' attribute")
            return 0, 0
        
        all_requests = real_driver.requests
        print(f"[API COLLECTION] Total requests captured: {len(all_requests)}")
        print(f"[API COLLECTION] Click events tracked: {len(tracker.clicked_elements)}")
        
        # Can't associate APIs without click events
        if not tracker.clicked_elements:
            print(f"[API COLLECTION] ⚠️  No clicks detected - skipping API capture")
            return 0, 0
        
        captured_count = 0
        skipped_count = 0
        
        for request in all_requests:
            if not request.response:
                continue
            
            # Identify API requests using multiple signals
            is_api = False
            content_type = request.response.headers.get('Content-Type', '').lower()
            
            # Check for API indicators
            if request.headers.get('X-Requested-With', '').lower() == 'xmlhttprequest':
                is_api = True
            elif request.headers.get('Sec-Fetch-Dest', '').lower() == 'empty':
                is_api = True
            elif any(t in content_type for t in ['application/json', 'application/xml', 'text/xml']):
                is_api = True
            elif request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
                is_api = True
            elif any(pattern in request.url.lower() for pattern in ['/api/', 'v1/', 'v2/', 'graphql', '.json']):
                is_api = True
            
            if not is_api:
                continue
            
            # Get API timestamp (prioritize internal capturing timestamp)
            try:
                api_timestamp = request.date.timestamp()
            except Exception:
                api_timestamp = time.time()
                # Fallback to response Date header if available
                try:
                    if request.response.headers.get('Date'):
                        from email.utils import parsedate_to_datetime
                        api_timestamp = parsedate_to_datetime(request.response.headers['Date']).timestamp()
                except Exception:
                    pass
            
            # Find which click triggered this API
            associated_click = tracker.find_associated_click(api_timestamp)
            
            if associated_click:
                # Extract response body if available
                response_body = None
                try:
                    if request.response.body:
                        response_body = request.response.body
                except Exception:
                    pass
                
                # Record this API call with click association
                tracker.track_api_call(
                    url=request.url,
                    method=request.method,
                    payload=request.body,
                    headers=dict(request.headers),
                    response_code=request.response.status_code,
                    response_body=response_body,
                    triggered_by=associated_click["locator"],
                    time_after_click=associated_click["time_after_click"],
                    trigger_details=associated_click
                )
                captured_count += 1
            else:
                skipped_count += 1
        
        print(f"[API COLLECTION] ✓ Captured {captured_count} click-triggered APIs")
        print(f"[API COLLECTION] → Skipped {skipped_count} non-click-triggered requests\n")
        
        return captured_count, skipped_count

    # ============================================================================
    # SECTION 5: Script Execution
    # ============================================================================
    
    @staticmethod
    def execute_script_with_tracking(
        script_path: str,
        locator_files: list,
        folder_path: str,
        headless: bool = True,
        use_wire: bool = False
    ) -> Dict[str, Any]:
        """
        Execute a Selenium script and track all user interactions.
        
        This is the main entry point for script execution. It:
        1. Loads element locators from config files
        2. Sets up Chrome WebDriver with optional API interception
        3. Prepares an isolated execution environment
        4. Runs the user's script while tracking all actions
        5. Collects API calls triggered by clicks
        6. Generates a comprehensive summary
        
        Args:
            script_path: Full path to the main Selenium script file
            locator_files: List of paths to locator configuration files
            folder_path: Root directory of the uploaded script folder
            headless: Whether to run browser in headless mode (no GUI)
            use_wire: Whether to use selenium-wire for API interception
            
        Returns:
            Dictionary containing:
                - success: True if execution completed, False if error
                - tracked_actions: Summary of all recorded interactions
                - script_path: Name of the executed script
                - locators_loaded: Count of locators found
                - error: Error message if success=False
        """
        driver = None
        original_sys_path = None
        script_dir = None
        
        try:
            print("\n" + "="*80)
            print("SELENIUM SCRIPT EXECUTION WITH ACTION TRACKING")
            print("="*80)
            
            # Load all locator definitions from the uploaded folder
            locators_dict = SeleniumScriptExecutor._load_locators_from_folder(folder_path)
            
            # Initialize tracker with discovered locators
            tracker = SeleniumActionTracker(all_locators=locators_dict)
            
            # Create Chrome WebDriver
            print(f"[DRIVER SETUP] Initializing Chrome (headless={headless}, API interception={use_wire})...")
            driver = SeleniumScriptExecutor.setup_driver(headless=headless, use_wire=use_wire)
            print("[DRIVER SETUP] ✓ WebDriver ready\n")
            
            # Load the script content
            print(f"[SCRIPT] Loading {os.path.basename(script_path)}...")
            with open(script_path, 'r', encoding='utf-8-sig', errors='replace') as f:
                script_content = f.read()
            print("[SCRIPT] ✓ Script loaded\n")
            
            # Prepare isolated execution environment
            print("[ENVIRONMENT] Setting up import paths and module isolation...")
            script_dir = os.path.dirname(script_path)
            search_bases, original_modules, original_sys_path = \
                SeleniumScriptExecutor._prepare_execution_environment(folder_path, script_dir, locator_files)
            print("[ENVIRONMENT] ✓ Environment ready\n")
            
            # Set up driver interception and tracking
            proxy_driver, original_constructors = \
                SeleniumScriptExecutor._setup_driver_interception(driver, tracker)
            
            # Attach merged locators to the driver for patch visibility
            proxy_driver._locators = locators_dict
            driver._locators = locators_dict # Original driver too
            
            # Create script execution namespace
            exec_namespace = SeleniumScriptExecutor._create_execution_namespace(proxy_driver, script_path)
            
            # Execute the script
            print("[EXECUTION] Running script with tracking enabled...")
            print("-" * 80)
            
            try:
                # Link tracker to namespace for expression resolution
                setattr(tracker, '_exec_namespace', exec_namespace)
                
                # Apply robustness patches to SeleniumHelper classes
                apply_robustness_patches(folder_path, search_bases, locators_dict)
                
                # Run the script
                exec(script_content, exec_namespace)
                
                print("-" * 80)
                print("[EXECUTION] ✓ Script completed successfully\n")
                
            except Exception as script_error:
                logger.error(f"Script execution error: {str(script_error)}")
                print(f"[EXECUTION] ⚠️  Script encountered an error: {str(script_error)}\n")
                import traceback
                traceback.print_exc()
            
            # Collect API calls if selenium-wire is enabled
            if use_wire:
                SeleniumScriptExecutor._collect_api_calls(driver, tracker)
            
            # Universal Page Inventory scan (track all elements)
            print("[SUMMARY] Capturing full page inventory...")
            tracker.track_page_inventory(driver)
            
            # Restore original modules
            for module_name, module_obj in original_modules.items():
                sys.modules[module_name] = module_obj
            
            # Generate execution summary
            print("[SUMMARY] Generating action tracking report...")
            tracker.capture_screenshot(driver, label="Final State")
            tracker.print_summary()
            summary = tracker.get_summary()
            print("[SUMMARY] ✓ Report generated\n")
            
            print("=" * 80)
            print("EXECUTION COMPLETED")
            print("=" * 80 + "\n")
            
            return {
                "success": True,
                "tracked_actions": summary,
                "script_path": os.path.basename(script_path),
                "locators_loaded": len(locators_dict)
            }
            
        except Exception as e:
            logger.error(f"Execution failed: {str(e)}")
            import traceback
            traceback.print_exc()
            
            return {
                "success": False,
                "error": str(e),
                "tracked_actions": tracker.get_summary() if tracker else None
            }
            
        finally:
            # Restore Selenium constructors
            if 'original_constructors' in locals():
                SeleniumScriptExecutor._restore_driver_constructors(original_constructors)
            
            # Close browser
            if driver:
                try:
                    driver.quit()
                    logger.info("WebDriver closed")
                except Exception as e:
                    logger.error(f"Error closing WebDriver: {str(e)}")
            
            # Restore Python path
            if original_sys_path:
                sys.path = original_sys_path

    # ============================================================================
    # SECTION 6: ZIP File Handling
    # ============================================================================
    
    @staticmethod
    def execute_from_zip(
        zip_path: str,
        headless: bool = True,
        use_wire: bool = False
    ) -> Dict[str, Any]:
        """
        Extract and execute a Selenium script from a ZIP file.
        
        Convenience method that handles ZIP extraction, script identification,
        and execution in one call. The ZIP file is extracted to a temporary
        directory that's cleaned up automatically after execution.
        
        Args:
            zip_path: Path to ZIP file containing the Selenium script
            headless: Whether to run browser in headless mode
            use_wire: Whether to use selenium-wire for API interception
            
        Returns:
            Same dictionary as execute_script_with_tracking()
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            print(f"\n[ZIP] Extracting to temporary directory: {tmpdir}")
            
            # Extract ZIP contents
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(tmpdir)
            print(f"[ZIP] ✓ Extraction complete\n")
            
            # Find the main script and locator files
            main_script, locator_files = ScriptAnalyzer.identify_script_files(tmpdir)
            
            if not main_script:
                return {
                    "success": False,
                    "error": "No Selenium script found in ZIP file"
                }
            
            # Execute the script
            return SeleniumScriptExecutor.execute_script_with_tracking(
                script_path=main_script,
                locator_files=locator_files,
                folder_path=tmpdir,
                headless=headless,
                use_wire=use_wire
            )
