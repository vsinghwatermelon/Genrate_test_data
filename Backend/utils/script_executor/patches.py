"""
Robustness Patches for SeleniumHelper Classes

This module dynamically discovers and patches user-provided SeleniumHelper classes
to add better error handling, fuzzy tab matching, and interaction tracking.

The patches prevent common script failures while maintaining full compatibility with
the original helper class interface.
"""

import os
import re
import sys
import time
import types
import logging
import importlib.util

logger = logging.getLogger(__name__)


# ============================================================================
# SECTION 1: Module Discovery & Loading
# ============================================================================

def apply_robustness_patches(folder_path, search_bases, locators_dict=None):
    """
    Find all SeleniumHelper classes in the uploaded script and apply patches.
    
    This scans the folder for selenium_helper.py files, loads them dynamically,
    and applies stability patches to prevent crashes from tab switching failures,
    missing elements, and locator errors.
    
    Args:
        folder_path: Root directory of uploaded script
        search_bases: List of directories to search for helpers
        locators_dict: Locator definitions to inject into helper classes
    """
    # Find all selenium_helper.py files recursively
    helper_files = []
    for root, _, files in os.walk(folder_path):
        if "selenium_helper.py" in files:
            helper_files.append(os.path.join(root, "selenium_helper.py"))
    
    # Process each unique helper file found
    for helper_path in set(helper_files):
        try:
            _load_and_patch_helper(helper_path, search_bases, locators_dict)
        except Exception as e:
            logger.error(f"Failed to patch helper at {helper_path}: {e}")


def _load_and_patch_helper(helper_path, search_bases, locators_dict):
    """
    Load a selenium_helper.py file and patch its SeleniumHelper class.
    
    Handles module naming, import path setup, and module injection into sys.modules
    so the user's script can import the patched version.
    """
    # Generate all possible module names this helper could be imported as
    potential_names = _generate_module_names(helper_path, search_bases)
    
    # Load the module
    spec = importlib.util.spec_from_file_location("robust_patch_mod", helper_path)
    if not (spec and spec.loader):
        return
    
    module = importlib.util.module_from_spec(spec)
    
    # Temporarily add helper's directories to import path
    orig_path = sys.path.copy()
    sys.path.insert(0, os.path.dirname(helper_path))
    sys.path.insert(0, os.path.dirname(os.path.dirname(helper_path)))
    
    try:
        spec.loader.exec_module(module)
        
        # Find and patch the SeleniumHelper class
        if hasattr(module, 'SeleniumHelper'):
            helper_class = module.SeleniumHelper
            patch_helper_class(helper_class, locators_dict)
            
            # Inject patched module into sys.modules for all possible import names
            _inject_into_sys_modules(module, potential_names, helper_path)
    finally:
        sys.path = orig_path


def _generate_module_names(helper_path, search_bases):
    """
    Generate all possible module import names for a helper file.
    
    For example, if helper is at 'folder/config/selenium_helper.py', it could be
    imported as 'config.selenium_helper' or just 'selenium_helper' depending on
    where the script's working directory is.
    """
    names = set()
    
    # Try to create module name relative to each search base
    for base in search_bases:
        try:
            rel_path = os.path.relpath(helper_path, base)
            if not rel_path.startswith('..'):
                # Convert path to module name (remove .py, replace / with .)
                mod_name = rel_path.replace(".py", "").replace(os.sep, ".")
                names.add(mod_name)
        except Exception:
            pass
    
    # Also include all suffixes of the longest name
    # e.g., 'a.b.selenium_helper' -> also add 'b.selenium_helper' and 'selenium_helper'
    if names:
        longest = max(names, key=len)
        parts = longest.split('.')
        for i in range(len(parts)):
            names.add(".".join(parts[i:]))
    
    return names


def _inject_into_sys_modules(module, module_names, helper_path):
    """
    Add the patched module to sys.modules under all possible import names.
    
    This ensures that when the user's script does 'import selenium_helper' or
    'from config import selenium_helper', they get the patched version.
    """
    helper_dir = os.path.dirname(os.path.abspath(helper_path))
    
    for full_name in module_names:
        parts = full_name.split('.')
        
        # Create parent package modules if they don't exist
        for i in range(len(parts)):
            current_name = ".".join(parts[:i+1])
            
            if current_name not in sys.modules:
                if i == len(parts) - 1:
                    # This is the actual module
                    sys.modules[current_name] = module
                else:
                    # This is a parent package
                    parent_module = types.ModuleType(current_name)
                    
                    # Calculate package directory
                    package_dir = helper_dir
                    for _ in range(max(0, len(parts) - 2 - i)):
                        package_dir = os.path.dirname(package_dir)
                    
                    parent_module.__path__ = [package_dir] if os.path.isdir(package_dir) else []
                    sys.modules[current_name] = parent_module
            
            # Link child to parent
            if i > 0:
                parent_name = ".".join(parts[:i])
                child_name = parts[i]
                parent_mod = sys.modules.get(parent_name)
                if parent_mod and hasattr(parent_mod, '__dict__'):
                    setattr(parent_mod, child_name, sys.modules[current_name])
        
        logger.info(f"Injected patched helper into sys.modules as '{full_name}'")


# ============================================================================
# SECTION 2: Main Patching Function
# ============================================================================

def patch_helper_class(cls, locators_dict=None):
    """
    Apply all robustness patches to a SeleniumHelper class.
    
    This is the main entry point that coordinates all the individual patches.
    Patches are applied idempotently (won't double-patch if called multiple times).
    
    Args:
        cls: The SeleniumHelper class to patch
        locators_dict: Locator definitions to inject
    """
    # Inject locators into the class if provided
    if locators_dict:
        _inject_locators(cls, locators_dict)
    
    # Apply tab switching patch with fuzzy matching
    _patch_switch_tab(cls)
    
    # Apply element interaction patches
    _patch_click(cls)
    _patch_send_keys(cls)
    _patch_hover(cls)
    _patch_verify(cls)
    _patch_get_text(cls)
    _patch_wait_for_element(cls)
    
    # Inject Selenium exceptions into helper's module to prevent NameErrors
    _inject_selenium_exceptions(cls)


def _inject_locators(cls, locators_dict):
    """
    Add locator definitions to the helper class.
    
    If the class doesn't have locators, adds them. If it already has some,
    merges the new ones with existing ones.
    """
    if not hasattr(cls, 'locators') or not cls.locators:
        cls.locators = locators_dict
        logger.info(f"Injected {len(locators_dict)} locators into {cls.__name__}")
    elif isinstance(cls.locators, dict):
        cls.locators.update(locators_dict)
        logger.info(f"Merged {len(locators_dict)} locators into {cls.__name__}.locators")


def _inject_selenium_exceptions(cls):
    """
    Add Selenium exception classes to the helper's module.
    
    User scripts often reference exceptions like NoSuchElementException without
    importing them. This prevents NameError by adding them to the module namespace.
    """
    try:
        from selenium.common.exceptions import (
            NoSuchElementException, TimeoutException, StaleElementReferenceException,
            ElementClickInterceptedException, ElementNotInteractableException, WebDriverException
        )
        
        module = sys.modules.get(cls.__module__)
        if not module:
            return
        
        exceptions = {
            'NoSuchElementException': NoSuchElementException,
            'TimeoutException': TimeoutException,
            'StaleElementReferenceException': StaleElementReferenceException,
            'ElementClickInterceptedException': ElementClickInterceptedException,
            'ElementNotInteractableException': ElementNotInteractableException,
            'WebDriverException': WebDriverException
        }
        
        for name, exception_class in exceptions.items():
            if not hasattr(module, name):
                setattr(module, name, exception_class)
    except ImportError:
        pass


# ============================================================================
# SECTION 3: Tab Switching Patches
# ============================================================================

def _patch_switch_tab(cls):
    """
    Add fuzzy tab matching to switch_tab method.
    
    Many scripts fail because tab titles don't match exactly. This patch:
    - Retries tab switching with exponential backoff
    - Uses fuzzy matching (substring, URL matching)
    - Waits for new tabs to appear before giving up
    """
    original = getattr(cls, 'switch_tab', None)
    if not original or hasattr(original, '_is_patched'):
        return
    
    def robust_switch_tab(self, tab_title):
        """Switch to tab with fuzzy matching and retries."""
        print(f"[TAB SWITCH] Looking for: '{tab_title}'")
        
        for attempt in range(4):  # 4 attempts with increasing wait
            # First try: use original method
            if attempt == 0:
                try:
                    result = original(self, tab_title)
                    if result:
                        return True
                except Exception:
                    pass
            
            # Fuzzy matching attempts
            print(f"[TAB SWITCH] Attempt {attempt + 1}: Fuzzy matching...")
            
            try:
                handles = self.driver.window_handles
                
                # Wait for new tabs to appear (common when clicking links)
                if len(handles) < 2 and attempt < 2:
                    time.sleep(1.5)
                    handles = self.driver.window_handles
                
                available_tabs = []
                
                for handle in handles:
                    try:
                        self.driver.switch_to.window(handle)
                        title = self.driver.title
                        url = self.driver.current_url
                        available_tabs.append(f"'{title}' ({url})")
                        
                        # Match 1: Exact or substring match (case-insensitive)
                        if (tab_title.lower() in title.lower() or 
                            title.lower() in tab_title.lower() or
                            tab_title.lower() in url.lower() or
                            url.lower() in tab_title.lower()):
                            print(f"[TAB SWITCH] ✓ Matched: '{title}'")
                            return True
                        
                        # Match 2: Keyword matching (for partial domains)
                        # e.g., 'app.turtlemint.com' matches 'app.turtlemintinsurance.com'
                        keywords = [p for p in re.split(r'[^a-zA-Z0-9]', tab_title.lower()) if len(p) > 5]
                        if keywords and any(kw in url.lower() or k in title.lower() for kw in keywords):
                            print(f"[TAB SWITCH] ✓ Keyword match: '{title}'")
                            return True
                    except Exception:
                        continue
                
                # Show available tabs on final attempt
                if attempt == 3:
                    print(f"[TAB SWITCH] ✗ No match found")
                    print(f"[TAB SWITCH] Available tabs: {available_tabs}")
            except Exception as e:
                logger.debug(f"Tab switch attempt failed: {e}")
            
            # Wait before next attempt (exponential backoff)
            if attempt < 3:
                time.sleep(1.5)
        
        print(f"[TAB SWITCH] ✗ Failed after 4 attempts for '{tab_title}'")
        return False
    
    robust_switch_tab._is_patched = True
    cls.switch_tab = robust_switch_tab


# ============================================================================
# SECTION 4: Element Interaction Patches
# ============================================================================

def _patch_click(cls):
    """
    Add logging to click method.
    
    The actual tracking is done by TrackedWebElement, but this adds
    logging output for debugging.
    """
    original = getattr(cls, 'click', None)
    if not original or hasattr(original, '_is_patched'):
        return
    
    def robust_click(self, locator_id, *args, **kwargs):
        """Click with logging."""
        print(f"[CLICK] {locator_id}")
        try:
            return original(self, locator_id, *args, **kwargs)
        except Exception as e:
            print(f"[CLICK] ✗ Failed for '{locator_id}': {e}")
            raise
    
    robust_click._is_patched = True
    cls.click = robust_click


def _patch_send_keys(cls):
    """Add logging to send_keys method."""
    original = getattr(cls, 'send_keys', None)
    if not original or hasattr(original, '_is_patched'):
        return
    
    def robust_send_keys(self, locator_id, text, *args, **kwargs):
        """Send keys with logging."""
        print(f"[INPUT] {locator_id} = '{text}'")
        try:
            return original(self, locator_id, text, *args, **kwargs)
        except Exception as e:
            print(f"[INPUT] ✗ Failed for '{locator_id}': {e}")
            raise
    
    robust_send_keys._is_patched = True
    cls.send_keys = robust_send_keys


def _patch_hover(cls):
    """Add tracking to hover method."""
    original = getattr(cls, 'hover', None)
    if not original or hasattr(original, '_is_patched'):
        return
    
    def robust_hover(self, locator_id):
        """Hover with tracking."""
        print(f"[HOVER] {locator_id}")
        try:
            element = self.wait_for_element(locator_id)
            result = original(self, locator_id)
            
            # Track hover action if tracker is available
            tracker = getattr(self.driver, '_tracker', None)
            if tracker:
                tracker.track_hover(element, locator_id)
            
            return result
        except Exception as e:
            print(f"[HOVER] ✗ Failed for '{locator_id}': {e}")
            raise
    
    robust_hover._is_patched = True
    cls.hover = robust_hover


def _patch_verify(cls):
    """Add tracking to is_verify method."""
    original = getattr(cls, 'is_verify', None)
    if not original or hasattr(original, '_is_patched'):
        return
    
    def robust_verify(self, locator_id, text='', **kwargs):
        """Verify with tracking."""
        print(f"[VERIFY] {locator_id} contains '{text}'")
        try:
            element = self.wait_for_element(locator_id)
            result = original(self, locator_id, text=text, **kwargs)
            
            tracker = getattr(self.driver, '_tracker', None)
            if tracker:
                tracker.track_verification(element, locator_id, text, element.text, True)
            
            return result
        except Exception as e:
            # Track failed verification
            tracker = getattr(self.driver, '_tracker', None)
            if tracker:
                try:
                    elem = self.wait_for_element(locator_id, timeout=1)
                    tracker.track_verification(elem, locator_id, text, elem.text, False)
                except Exception:
                    pass
            
            print(f"[VERIFY] ✗ Failed for '{locator_id}': {e}")
            raise
    
    robust_verify._is_patched = True
    cls.is_verify = robust_verify


def _patch_get_text(cls):
    """Add tracking to get_text method."""
    original = getattr(cls, 'get_text', None)
    if not original or hasattr(original, '_is_patched'):
        return
    
    def robust_get_text(self, locator_id):
        """Get text with tracking."""
        print(f"[GET TEXT] {locator_id}")
        try:
            element = self.wait_for_element(locator_id)
            text = original(self, locator_id)
            
            tracker = getattr(self.driver, '_tracker', None)
            if tracker:
                tracker.track_get_text(element, locator_id, text)
            
            return text
        except Exception as e:
            print(f"[GET TEXT] ✗ Failed for '{locator_id}': {e}")
            raise
    
    robust_get_text._is_patched = True
    cls.get_text = robust_get_text


def _patch_wait_for_element(cls):
    """Add better error messages to wait_for_element."""
    original = getattr(cls, 'wait_for_element', None)
    if not original or hasattr(original, '_is_patched'):
        return
    
    def robust_wait(self, locator_id, timeout=None):
        """Wait with descriptive error messages."""
        # Call original wait
        element = original(self, locator_id, timeout) if timeout is not None else original(self, locator_id)
        
        if element is None:
            # Check if locator exists in configuration
            if hasattr(self, 'get_locator_info'):
                locator_info = self.get_locator_info(locator_id)
                if not locator_info:
                    raise Exception(
                        f"CRITICAL: Locator '{locator_id}' not found in config files. "
                        f"Check your locators_config.py or keys_config.py"
                    )
            
            raise Exception(
                f"CRITICAL: Element '{locator_id}' not found on page within timeout. "
                f"The locator exists in config but element is not present on the page."
            )
        
        return element
    
    robust_wait._is_patched = True
    cls.wait_for_element = robust_wait
