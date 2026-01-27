"""
Tracked Web Elements  

Wrapper classes for Selenium WebDriver and WebElement that inject action tracking.
"""

import inspect
import re
import logging
from selenium.webdriver.common.by import By

logger = logging.getLogger(__name__)


class TrackedWebElement:
    """Wrapper for WebElement that tracks click and send_keys."""
    
    def __init__(self, element, tracker, locator=""):
        self._element = element
        self._tracker = tracker
        self._locator = locator or "unknown"
    
    def __getattr__(self, name):
        if self._element is None:
            raise AttributeError(f"TrackedWebElement has no underlying element for '{self._locator}', cannot access '{name}'")
        return getattr(self._element, name)
    
    def click(self, *args, **kwargs):
        self._tracker.track_click(self._element, self._locator)
        if self._element is None:
            raise AttributeError(f"Cannot click None element for {self._locator}")
        return self._element.click(*args, **kwargs)
    
    def _resolve_mock_value(self, key, default=None):
        """
        Generate dynamic placeholder based on key name.
        No hardcoded test data - generates contextual placeholders.
        """
        k = str(key).lower()
        # Generate contextual placeholder based on field name
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

    def send_keys(self, *args, **kwargs):
        """Send keys with smart value resolution from args.get() calls."""
        new_args = []
        exec_ns = getattr(self._tracker, '_exec_namespace', {}).copy()
        
        # Try to find 'args' in the stack
        caller_args = {}
        curr_frame = inspect.currentframe()
        try:
            while curr_frame:
                if 'args' in curr_frame.f_locals and isinstance(curr_frame.f_locals['args'], dict):
                    caller_args.update(curr_frame.f_locals['args'])
                    break
                curr_frame = curr_frame.f_back
        finally:
            del curr_frame

        if caller_args:
            if 'args' not in exec_ns:
                exec_ns['args'] = {}
            exec_ns['args'].update(caller_args)
        
        for arg in args:
            if isinstance(arg, str) and ("args.get" in arg or "get_test_data_value" in arg):
                # Try regex for common args.get('key', 'default') pattern
                match = re.search(r"args\.get\(['\"]([^'\"]+)['\"]\s*,\s*([^)]+)\)", arg)
                if match:
                    key, default_raw = match.groups()
                    default = default_raw.strip().strip("'").strip('"')
                    resolved = caller_args.get(key)
                    lower_key = key.lower()
                    
                    # Look for better alternatives for sensitive fields
                    if 'pass' in lower_key or 'user' in lower_key or 'email' in lower_key:
                        alternatives = []
                        for k, v in caller_args.items():
                            if k == key: continue
                            kl = k.lower()
                            if ('pass' in kl and 'pass' in lower_key) or \
                               (('user' in kl or 'email' in kl or 'login' in kl) and \
                                ('user' in lower_key or 'email' in lower_key)):
                                alternatives.append({k: v})
                        
                        if alternatives and len(alternatives) == 1:
                            # Use the alternative
                            alt_key = list(alternatives[0].keys())[0]
                            alt_val = alternatives[0][alt_key]
                            if alt_val and str(alt_val).strip():
                                resolved = alt_val
                        elif not resolved or not str(resolved).strip():
                            # Try finding in nested structures
                            for k, v in caller_args.items():
                                if isinstance(v, dict):
                                    if key in v:
                                        resolved = v[key]
                                        break
                                    for sub_k, sub_v in v.items():
                                        if sub_k.lower() == lower_key:
                                            resolved = sub_v
                                            break
                    
                    if not resolved or not str(resolved).strip():
                        # Try mock registry
                        resolved = self._resolve_mock_value(key, default)
                    
                    new_args.append(str(resolved) if resolved is not None else default)
                else:
                    # Couldn't parse, try to evaluate it
                    try:
                        exec_ns_copy = exec_ns.copy()
                        result = eval(arg, exec_ns_copy)
                        new_args.append(str(result) if result is not None else arg)
                    except:
                        new_args.append(arg)
            else:
                new_args.append(arg)
        
        # Track and send
        value_str = " ".join(str(a) for a in new_args)
        self._tracker.track_field_input(self._element, self._locator, value_str)
        if self._element is None:
            raise AttributeError(f"Cannot send_keys to None element for {self._locator}")
        return self._element.send_keys(*new_args, **kwargs)
    
    def __repr__(self):
        return f"TrackedWebElement({self._locator})"

class WebDriverProxy:
    """Proxy for WebDriver that intercepts find_element and switch_to for tracking."""
    
    def __init__(self, driver, tracker):
        self._driver = driver
        self._tracker = tracker
        self._is_wrapped = True
        
        # Wrap switch_to
        class WrappedSwitchTo:
            def __init__(self, st, tr):
                self._st = st
                self._tr = tr
            def __getattr__(self, name):
                return getattr(self._st, name)
        
        self.switch_to = WrappedSwitchTo(driver.switch_to, tracker)
        
        # Attach tracker to the underlying driver so patches can find it
        if not hasattr(self._driver, '_tracker'):
            self._driver._tracker = tracker
    
    def find_element(self, by=By.ID, value=None):
        """Find element and wrap it for tracking."""
        element = self._driver.find_element(by, value)
        locator = f"{by}={value}"
        return TrackedWebElement(element, self._tracker, locator)
    
    def find_elements(self, by=By.ID, value=None):
        """Find elements and wrap them."""
        elements = self._driver.find_elements(by, value)
        locator = f"{by}={value}"
        return [TrackedWebElement(el, self._tracker, locator) for el in elements]
    
    def _unwrap_args(self, *args):
        """Unwrap TrackedWebElement to raw WebElement for script execution."""
        unwrapped = []
        for arg in args:
            # Better check for TrackedWebElement using duck typing
            if hasattr(arg, '_element') and hasattr(arg, '_tracker'):
                unwrapped.append(arg._element)
            elif isinstance(arg, list):
                unwrapped.append([self._unwrap_args(a)[0] if (hasattr(a, '_element') and hasattr(a, '_tracker')) else a for a in arg])
            elif isinstance(arg, dict):
                unwrapped.append({k: (v._element if (hasattr(v, '_element') and hasattr(v, '_tracker')) else v) for k, v in arg.items()})
            else:
                unwrapped.append(arg)
        return unwrapped

    def execute_script(self, script, *args):
        """Execute script with tracking."""
        return self._driver.execute_script(script, *self._unwrap_args(*args))
    
    def execute_async_script(self, script, *args):
        """Execute async script."""
        return self._driver.execute_async_script(script, *self._unwrap_args(*args))
    
    def __getattr__(self, name):
        """Delegate all other attributes to wrapped driver."""
        return getattr(self._driver, name)
    
    def __repr__(self):
        return f"WebDriverProxy({self._driver})"
    
    def quit(self):
        """
        Soft quit. We don't actually quit here because the main executor 
        needs to collect logs and screenshots after the script finishes.
        """
        logger.info("Script called driver.quit() - ignoring to keep driver alive for tracking")
        print("[DEBUG] Script called driver.quit() - ignoring to keep driver alive for tracking")
        return None
    
    def close(self):
        """Soft close."""
        logger.info("Script called driver.close() - ignoring to keep driver alive for tracking")
        print("[DEBUG] Script called driver.close() - ignoring to keep driver alive for tracking")
        return None
