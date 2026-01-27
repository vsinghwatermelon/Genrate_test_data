"""
Robustness Patches

Patches for SeleniumHelper classes to improve stability and error handling.
"""

import os
import re
import sys
import time
import types
import logging
import importlib.util

logger = logging.getLogger(__name__)


def apply_robustness_patches(folder_path, search_bases, locators_dict=None):
    """
    Dynamically find and patch SeleniumHelper class in the payload
    to prevent common crashes and improve tab switching.
    """
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


def patch_helper_class(cls, locators_dict=None):
    """Apply fuzzy tab matching and descriptive error patches to a class."""
    
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
            print(f"[PATCH] switch_tab called for: '{tab_title}'")
            for attempt in range(4):
                try:
                    res = orig_switch_tab(self, tab_title)
                    if res: return True
                except:
                    pass
                
                if attempt == 0: print(f"[PATCH] Attempting fuzzy matching for: '{tab_title}'")
                try:
                    handles = self.driver.window_handles
                    if len(handles) < 2 and attempt < 2:
                        time.sleep(1.5)
                        handles = self.driver.window_handles

                    available_windows = []
                    for handle in handles:
                        try:
                            self.driver.switch_to.window(handle)
                            title = self.driver.title
                            url = self.driver.current_url
                            available_windows.append(f"'{title}' ({url})")
                            
                            # Fuzzy matching
                            if (tab_title.lower() in title.lower() or 
                                title.lower() in tab_title.lower() or
                                tab_title.lower() in url.lower() or
                                url.lower() in tab_title.lower()):
                                print(f"[PATCH] SUCCESS: Fuzzy matched tab: '{title}'")
                                return True
                            
                            # Hyper-lenient match
                            query_parts = [p for p in re.split(r'[^a-zA-Z0-9]', tab_title.lower()) if len(p) > 5]
                            if query_parts and any(p in url.lower() or p in title.lower() for p in query_parts):
                                print(f"[PATCH] SUCCESS: Hyper-lenient match: '{title}'")
                                return True
                        except: continue
                    
                    if attempt == 3:
                        print(f"[PATCH] FAILED: No tab matched. Available: {available_windows}")
                except Exception as e:
                    logger.debug(f"Fuzzy tab switch failed: {e}")
                
                if attempt < 3:
                    time.sleep(1.5)
            
            print(f"[PATCH] FAILED: No tab matched '{tab_title}' after 4 attempts")
            return False
        
        robust_switch_tab._is_patched = True
        cls.switch_tab = robust_switch_tab

    # Patch common interaction methods
    _patch_click(cls)
    _patch_send_keys(cls)
    _patch_hover(cls)
    _patch_verify(cls)
    _patch_get_text(cls)
    _patch_wait_for_element(cls)
    
    # Inject common exceptions into the class's module to prevent NameErrors in scripts
    try:
        from selenium.common.exceptions import (
            NoSuchElementException, TimeoutException, StaleElementReferenceException,
            ElementClickInterceptedException, ElementNotInteractableException, WebDriverException
        )
        mod = sys.modules.get(cls.__module__)
        if mod:
            exceptions = {
                'NoSuchElementException': NoSuchElementException,
                'TimeoutException': TimeoutException,
                'StaleElementReferenceException': StaleElementReferenceException,
                'ElementClickInterceptedException': ElementClickInterceptedException,
                'ElementNotInteractableException': ElementNotInteractableException,
                'WebDriverException': WebDriverException
            }
            for name, exc in exceptions.items():
                if not hasattr(mod, name):
                    setattr(mod, name, exc)
    except ImportError:
        pass


def _patch_click(cls):
    """Patch click method."""
    orig_click = getattr(cls, 'click', None)
    if orig_click and not hasattr(orig_click, '_is_patched'):
        def robust_click(self, locator_id, *args, **kwargs):
            print(f"[PATCH] click called for: '{locator_id}'")
            try:
                # We don't call tracker.track_click here because 
                # the underlying element.click() in orig_click is already tracked
                # by TrackedWebElement.
                return orig_click(self, locator_id, *args, **kwargs)
            except Exception as e:
                print(f"[PATCH] Click failed for {locator_id}: {e}")
                raise
        robust_click._is_patched = True
        cls.click = robust_click


def _patch_send_keys(cls):
    """Patch send_keys method."""
    orig_send_keys = getattr(cls, 'send_keys', None)
    if orig_send_keys and not hasattr(orig_send_keys, '_is_patched'):
        def robust_send_keys(self, locator_id, text, *args, **kwargs):
            print(f"[PATCH] send_keys called for: '{locator_id}' with text: '{text}'")
            try:
                # We don't call tracker.track_field_input here because 
                # element.send_keys(text) in orig_send_keys is already tracked
                # by TrackedWebElement.
                return orig_send_keys(self, locator_id, text, *args, **kwargs)
            except Exception as e:
                print(f"[PATCH] send_keys failed for {locator_id}: {e}")
                raise
        robust_send_keys._is_patched = True
        cls.send_keys = robust_send_keys


def _patch_hover(cls):
    """Patch hover method."""
    orig_hover = getattr(cls, 'hover', None)
    if orig_hover and not hasattr(orig_hover, '_is_patched'):
        def robust_hover(self, locator_id):
            print(f"[PATCH] hover called for: '{locator_id}'")
            try:
                element = self.wait_for_element(locator_id)
                res = orig_hover(self, locator_id)
                tracker = getattr(self.driver, '_tracker', None)
                if tracker:
                    tracker.track_hover(element, locator_id)
                return res
            except Exception as e:
                print(f"[PATCH] Hover failed for {locator_id}: {e}")
                raise
        robust_hover._is_patched = True
        cls.hover = robust_hover


def _patch_verify(cls):
    """Patch is_verify method."""
    orig_verify = getattr(cls, 'is_verify', None)
    if orig_verify and not hasattr(orig_verify, '_is_patched'):
        def robust_verify(self, locator_id, text='', **kwargs):
            print(f"[PATCH] is_verify called for: '{locator_id}'")
            try:
                element = self.wait_for_element(locator_id)
                res = orig_verify(self, locator_id, text=text, **kwargs)
                tracker = getattr(self.driver, '_tracker', None)
                if tracker:
                    tracker.track_verification(element, locator_id, text, element.text, True)
                return res
            except Exception as e:
                tracker = getattr(self.driver, '_tracker', None)
                if tracker:
                    try:
                        el = self.wait_for_element(locator_id, timeout=1)
                        tracker.track_verification(el, locator_id, text, el.text, False)
                    except: pass
                print(f"[PATCH] Verification failed for {locator_id}: {e}")
                raise
        robust_verify._is_patched = True
        cls.is_verify = robust_verify


def _patch_get_text(cls):
    """Patch get_text method."""
    orig_get_text = getattr(cls, 'get_text', None)
    if orig_get_text and not hasattr(orig_get_text, '_is_patched'):
        def robust_get_text(self, locator_id):
            print(f"[PATCH] get_text called for: '{locator_id}'")
            try:
                element = self.wait_for_element(locator_id)
                text = orig_get_text(self, locator_id)
                tracker = getattr(self.driver, '_tracker', None)
                if tracker:
                    tracker.track_get_text(element, locator_id, text)
                return text
            except Exception as e:
                print(f"[PATCH] get_text failed for {locator_id}: {e}")
                raise
        robust_get_text._is_patched = True
        cls.get_text = robust_get_text


def _patch_wait_for_element(cls):
    """Patch wait_for_element method."""
    orig_wait = getattr(cls, 'wait_for_element', None)
    if orig_wait and not hasattr(orig_wait, '_is_patched'):
        def robust_wait(self, locator_id, timeout=None):
            element = orig_wait(self, locator_id, timeout) if timeout is not None else orig_wait(self, locator_id)
            if element is None:
                if hasattr(self, 'get_locator_info'):
                    loc_info = self.get_locator_info(locator_id)
                    if not loc_info:
                        raise Exception(f"CRITICAL: Locator ID '{locator_id}' NOT FOUND in any loaded locator config files.")
                raise Exception(f"CRITICAL: Element not found on page for '{locator_id}' within timeout.")
            return element
        robust_wait._is_patched = True
        cls.wait_for_element = robust_wait
