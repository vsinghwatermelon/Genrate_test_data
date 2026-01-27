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
    _patch_select(cls)
    _patch_hover(cls)
    _patch_verify(cls)
    _patch_get_text(cls)
    _patch_wait_for_element(cls)
    
    # Catch any dynamic variants (click_if_present, click_and_wait, etc.)
    _patch_dynamic_variants(cls)
    
    # Inject Selenium exceptions into helper's module to prevent NameErrors
    _inject_selenium_exceptions(cls)


def _patch_dynamic_variants(cls):
    """
    Dynamically discover and patch all interaction helper methods.
    Catches variations like click_if_present, click_and_wait, input_text, etc.
    """
    prefixes = ['click_', 'input_', 'send_keys_', 'hover_', 'verify_', 'get_text_', 'select_']
    
    for name in dir(cls):
        # Only patch methods with interaction prefixes that haven't been patched yet
        if any(name.startswith(p) for p in prefixes) and not name.startswith('_'):
            original = getattr(cls, name)
            if not callable(original) or hasattr(original, '_is_patched'):
                continue
            
            # Skip standard methods we already patch
            if name in ['click', 'send_keys', 'select', 'hover', 'is_verify', 'get_text']:
                continue
                
            def make_wrapper(orig_name, orig_func):
                base_type = next((p[:-1] for p in prefixes if orig_name.startswith(p)), "action")
                
                def robust_dynamic(self, locator_id, *args, **kwargs):
                    """Dynamic variant wrapper with tracking."""
                    print(f"[{orig_name.upper()}] {locator_id}")
                    try:
                        # Check element existence (non-blocking wait)
                        element = self.wait_for_element(locator_id, timeout=0.1)
                        if element is None:
                            print(f"[{orig_name.upper()}] ✗ Skipped: Element '{locator_id}' not found")
                            tracker = getattr(self.driver, '_tracker', None)
                            if tracker:
                                tracker.track_skip(locator_id, base_type, reason=f"Helper '{orig_name}' called but element missing")
                            return None
                        
                        # Call the original custom method
                        return orig_func(self, locator_id, *args, **kwargs)
                    except Exception as e:
                        # Only log if it's not a standard Selenium error we handle in wait
                        print(f"[{orig_name.upper()}] ✗ Error: {e}")
                        raise
                
                robust_dynamic._is_patched = True
                return robust_dynamic
                
            setattr(cls, name, make_wrapper(name, original))
            logger.info(f"Dynamically patched auxiliary interaction method: {cls.__name__}.{name}")


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
    Add Selenium exception classes to the helper's module and builtins.
    
    User scripts often reference exceptions like NoSuchElementException without
    importing them. This prevents NameError by adding them to the module namespace
    and Python's builtins for global availability.
    """
    try:
        from selenium.common.exceptions import (
            NoSuchElementException, TimeoutException, StaleElementReferenceException,
            ElementClickInterceptedException, ElementNotInteractableException, WebDriverException
        )
        import builtins
        
        exceptions = {
            'NoSuchElementException': NoSuchElementException,
            'TimeoutException': TimeoutException,
            'StaleElementReferenceException': StaleElementReferenceException,
            'ElementClickInterceptedException': ElementClickInterceptedException,
            'ElementNotInteractableException': ElementNotInteractableException,
            'WebDriverException': WebDriverException
        }
        
        # 1. Inject into the helper class's module
        module = sys.modules.get(cls.__module__)
        if module:
            for name, exception_class in exceptions.items():
                if not hasattr(module, name):
                    setattr(module, name, exception_class)
        
        # 2. Inject into Python's builtins for absolute global availability
        for name, exception_class in exceptions.items():
            if not hasattr(builtins, name):
                setattr(builtins, name, exception_class)
                
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
        """Switch tab with fuzzy matching and auto-correction."""
        print(f"[TAB SWITCH] Looking for: '{tab_title}'")
        
        # 1. Fuzzy match against all open handles
        handles = self.driver.window_handles
        for handle in handles:
            try:
                self.driver.switch_to.window(handle)
                if tab_title.lower() in self.driver.title.lower() or \
                   tab_title.lower() in self.driver.current_url.lower():
                    print(f"[TAB SWITCH] ✓ Matched: '{self.driver.title}'")
                    return True
            except Exception:
                continue
        
        # 2. Auto-correction: If only 1 tab exists, just use it
        if len(handles) == 1:
            try:
                self.driver.switch_to.window(handles[0])
                print(f"[TAB SWITCH] ⚠️ Titles mismatched but only 1 tab exists. Auto-switched to: '{self.driver.title}'")
                return True
            except Exception:
                pass
            
        # 3. Aggressive retry loop for dynamic titles
        for attempt in range(1, 4):
            print(f"[TAB SWITCH] Attempt {attempt}: Fuzzy matching...")
            time.sleep(1.5)
            # Re-check updated handles
            for handle in self.driver.window_handles:
                try:
                    self.driver.switch_to.window(handle)
                    if tab_title.lower() in self.driver.title.lower():
                        print(f"[TAB SWITCH] ✓ Matched: '{self.driver.title}'")
                        return True
                except Exception:
                    continue
        
        print(f"[TAB SWITCH] ✗ Failed after 4 attempts for '{tab_title}'")
        return False
    
    robust_switch_tab._is_patched = True
    cls.switch_tab = robust_switch_tab


# ============================================================================
# SECTION 4: Element Interaction Patches
# ============================================================================

def _patch_select(cls):
    """Add tracking and robustness to select (dropdown) method."""
    original = getattr(cls, 'select', None)
    if not original or hasattr(original, '_is_patched'):
        return
    
    def robust_select(self, locator_id, value):
        """Select with tracking."""
        print(f"[SELECT] {locator_id} = '{value}'")
        try:
            element = self.wait_for_element(locator_id)
            if element is None:
                print(f"[SELECT] ✗ Skipped: Element '{locator_id}' not found")
                tracker = getattr(self.driver, '_tracker', None)
                if tracker: tracker.track_skip(locator_id, "select")
                return None
                
            result = original(self, locator_id, value)
            
            # Track as input
            tracker = getattr(self.driver, '_tracker', None)
            if tracker:
                tracker.track_field_input(element, locator_id, value)
            
            return result
        except Exception as e:
            print(f"[SELECT] ✗ Failed for '{locator_id}': {e}")
            raise
            
    robust_select._is_patched = True
    cls.select = robust_select


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
            # Check if element exists before calling original
            element = self.wait_for_element(locator_id, timeout=0.1)
            if element is None:
                print(f"[CLICK] ✗ Skipped: Element '{locator_id}' not found")
                tracker = getattr(self.driver, '_tracker', None)
                if tracker: tracker.track_skip(locator_id, "click")
                return None
            
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
            element = self.wait_for_element(locator_id, timeout=0.1)
            if element is None:
                print(f"[INPUT] ✗ Skipped: Element '{locator_id}' not found")
                tracker = getattr(self.driver, '_tracker', None)
                if tracker: tracker.track_skip(locator_id, "input")
                return None
                
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
            if element is None:
                print(f"[HOVER] ✗ Skipped: Element '{locator_id}' not found")
                tracker = getattr(self.driver, '_tracker', None)
                if tracker: tracker.track_skip(locator_id, "hover")
                return None
                
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
            if element is None:
                print(f"[VERIFY] ✗ Failed: Element '{locator_id}' not found")
                # Track failed verification even if element missing
                tracker = getattr(self.driver, '_tracker', None)
                if tracker:
                    tracker.track_verification(None, locator_id, text, "ELEMENT NOT FOUND", False)
                return False

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
        """Wait with descriptive error messages and exception safety."""
        # Call original wait
        try:
            element = original(self, locator_id, timeout) if timeout is not None else original(self, locator_id)
        except Exception as e:
            # Silence selenium errors
            element = None
        
        if element is None:
            # Multi-layer locator lookup
            locator_info = None
            
            # 1. Try instance methods
            if hasattr(self, 'get_locator_info'):
                locator_info = self.get_locator_info(locator_id)
            
            # 2. Try instance/class dictionary fallback
            if not locator_info:
                locs = getattr(self, 'locators', {}) or getattr(self.__class__, 'locators', {})
                if isinstance(locs, dict):
                    locator_info = locs.get(locator_id)
                
            # 3. Try global driver fallback (injected by executor.py)
            if not locator_info and hasattr(self, 'driver'):
                locator_info = getattr(self.driver, '_locators', {}).get(locator_id)
            elif not locator_info and hasattr(self, '_driver'): # Proxy style
                locator_info = getattr(self._driver, '_locators', {}).get(locator_id)
                
            if not locator_info:
                print(f"[WAIT] ⚠️ Warning: Locator '{locator_id}' not found in any config files!")
            else:
                print(f"[WAIT] ⚠️ Warning: Element '{locator_id}' not found on page within timeout.")
                
            return None # Return None to support 'if element:' logic in user scripts
        
        return element
    
    robust_wait._is_patched = True
    cls.wait_for_element = robust_wait
