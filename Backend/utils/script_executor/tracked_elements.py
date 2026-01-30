"""
Tracked Web Elements

Wrapper classes that intercept Selenium WebDriver and WebElement operations
to record user interactions (clicks, inputs, hovers) for test data generation.

This module provides two main classes:
- TrackedWebElement: Wraps individual elements to track interactions
- WebDriverProxy: Wraps the driver to intercept element finding and script execution
"""

import inspect
import re
import logging
from selenium.webdriver.common.by import By

logger = logging.getLogger(__name__)


# ============================================================================
# SECTION 1: TrackedWebElement - Element-Level Tracking
# ============================================================================

class TrackedWebElement:
    """
    Wrapper for Selenium WebElement that records clicks and inputs.
    
    When a script clicks or types into an element, this class:
    1. Records the interaction in the tracker
    2. Forwards the action to the real element
    3. Resolves dynamic values from args.get() expressions
    """
    
    def __init__(self, element, tracker, locator=""):
        """
        Create a tracked element wrapper.
        
        Args:
            element: The real Selenium WebElement
            tracker: SeleniumActionTracker instance
            locator: Human-readable locator string (e.g., "css=.login-btn")
        """
        self._element = element
        self._tracker = tracker
        self._locator = locator or "unknown"
    
    def find_element(self, by=By.ID, value=None):
        """Find a child element and wrap it for tracking."""
        element = self._element.find_element(by, value)
        locator = f"{self._locator} -> {by}={value}"
        return TrackedWebElement(element, self._tracker, locator)
    
    def find_elements(self, by=By.ID, value=None):
        """Find multiple child elements and wrap each one."""
        elements = self._element.find_elements(by, value)
        locator = f"{self._locator} -> {by}={value}"
        return [TrackedWebElement(el, self._tracker, locator) for el in elements]

    def __getattr__(self, name):
        """Forward all other attribute access to the real element, wrapping finding methods."""
        if self._element is None:
            raise AttributeError(
                f"TrackedWebElement has no underlying element for '{self._locator}', "
                f"cannot access '{name}'"
            )
        
        attr = getattr(self._element, name)
        
        # Intercept and wrap child finding methods to maintain tracking chain
        if (name.startswith("find_element") or name.startswith("find_elements")) and callable(attr):
            def wrapper(*args, **kwargs):
                res = attr(*args, **kwargs)
                if isinstance(res, list):
                    return [TrackedWebElement(el, self._tracker, f"{self._locator}.{name}({args})") for el in res]
                else:
                    return TrackedWebElement(res, self._tracker, f"{self._locator}.{name}({args})")
            return wrapper
            
        return attr
    
    def click(self, *args, **kwargs):
        """Track click action and forward to real element with JS fallback."""
        if self._element is None:
            raise AttributeError(f"Cannot click None element for {self._locator}")
            
        self._tracker.track_click(self._element, self._locator)
        
        try:
            return self._element.click(*args, **kwargs)
        except Exception as e:
            logger.warning(f"Standard click failed for {self._locator}: {e}. Trying JS fallback.")
            try:
                driver = self._element.parent
                driver.execute_script("arguments[0].click();", self._element)
                return True
            except Exception as js_err:
                logger.error(f"JS fallback click also failed for {self._locator}: {js_err}")
                raise e
    
    def send_keys(self, *args, **kwargs):
        """
        Track input and send keys with smart value resolution.
        
        This method resolves expressions like args.get('username', 'default')
        into actual values from the script's args dictionary.
        """
        if self._element is None:
            raise AttributeError(f"Cannot send_keys to None element for {self._locator}")

        # Resolve any expressions in the arguments
        resolved_args = []
        for arg in args:
            if isinstance(arg, str) and ("args.get" in arg or "get_test_data_value" in arg):
                resolved_args.append(self._resolve_expression(arg))
            else:
                resolved_args.append(arg)
        
        # Track the input
        value_str = " ".join(str(a) for a in resolved_args)
        self._tracker.track_field_input(self._element, self._locator, value_str)
        
        return self._element.send_keys(*resolved_args, **kwargs)
    
    def _resolve_expression(self, expression):
        """
        Resolve a string expression into a value.
        
        Handles:
        - args.get('key', 'default') patterns
        - Nested args dictionaries
        - Fallback to generated test data
        """
        # Try to parse args.get('key', 'default') pattern
        match = re.search(r"args\.get\(['\"]([^'\"]+)['\"]\s*,\s*([^)]+)\)", expression)
        if match:
            key, default_raw = match.groups()
            default = default_raw.strip().strip("'").strip('"')
            
            # Get the args dictionary from caller's context
            caller_args = self._find_args_in_stack()
            
            # Look for the key in args
            value = caller_args.get(key)
            
            # If not found or empty, search nested dictionaries
            if not value or not str(value).strip():
                value = self._search_nested_args(caller_args, key)
            
            # Still nothing? Generate test data
            if not value or not str(value).strip():
                value = self._generate_test_value(key, default)
            
            return str(value) if value is not None else default
        
        # Couldn't parse as args.get(), try to evaluate it
        try:
            # Safely use the tracker's namespace if available
            exec_namespace = getattr(self._tracker, '_exec_namespace', {}).copy()
            result = eval(expression, exec_namespace)
            return str(result) if result is not None else expression
        except Exception:
            return expression
    
    def _find_args_in_stack(self):
        """Search call stack for an 'args' dictionary."""
        frame = inspect.currentframe()
        try:
            while frame:
                if 'args' in frame.f_locals and isinstance(frame.f_locals['args'], dict):
                    return frame.f_locals['args'].copy()
                frame = frame.f_back
        finally:
            del frame
        return {}
    
    def _search_nested_args(self, args_dict, key):
        """Search for a key in nested dictionaries within args."""
        key_lower = key.lower()
        
        for arg_key, arg_value in args_dict.items():
            if isinstance(arg_value, dict):
                # Direct key match
                if key in arg_value:
                    return arg_value[key]
                
                # Case-insensitive match
                for sub_key, sub_value in arg_value.items():
                    if sub_key.lower() == key_lower:
                        return sub_value
        
        return None
    
    def _generate_test_value(self, key, default):
        """
        Generate contextual test data based on field name.
        
        Creates reasonable placeholders instead of using hardcoded values.
        """
        key_lower = key.lower()
        
        # Email fields
        if 'email' in key_lower:
            return f"user_{key}@example.com"
        
        # Phone/mobile fields
        if 'phone' in key_lower or 'mobile' in key_lower:
            return "1234567890"
        
        # Name fields
        if 'name' in key_lower:
            return f"Test_{key}"
        
        # Date fields
        if 'date' in key_lower or 'dob' in key_lower:
            return "01/01/2000"
        
        # Location fields
        if any(word in key_lower for word in ['pin', 'zip', 'postal']):
            return "000000"
        if 'city' in key_lower:
            return "TestCity"
        if 'state' in key_lower:
            return "TestState"
        
        # Age field
        if 'age' in key_lower:
            return "25"
        
        # Default fallback
        return default or f'test_{key}'
    
    def __repr__(self):
        return f"TrackedWebElement({self._locator})"


# ============================================================================
# SECTION 2: WebDriverProxy - Driver-Level Interception
# ============================================================================

class WebDriverProxy:
    """
    Proxy for Selenium WebDriver that wraps found elements for tracking.
    
    When a script finds an element (driver.find_element(...)), this class:
    1. Forwards the request to the real driver
    2. Wraps the returned element in TrackedWebElement
    3. Ensures switch_to is also tracked
    """
    
    def __init__(self, driver, tracker):
        """
        Create a driver proxy.
        
        Args:
            driver: The real Selenium WebDriver instance
            tracker: SeleniumActionTracker instance
        """
        self._driver = driver
        self._tracker = tracker
        self._is_wrapped = True
        
        # Wrap the switch_to object
        self.switch_to = self._create_switch_to_wrapper(driver.switch_to, tracker)
        
        # Attach tracker to underlying driver so patches can access it
        if not hasattr(self._driver, '_tracker'):
            self._driver._tracker = tracker
    
    @staticmethod
    def _create_switch_to_wrapper(switch_to, tracker):
        """Create a wrapper for driver.switch_to that passes through all calls."""
        class WrappedSwitchTo:
            def __init__(self, st, tr):
                self._st = st
                self._tr = tr
            
            def __getattr__(self, name):
                return getattr(self._st, name)
        
        return WrappedSwitchTo(switch_to, tracker)
    
    def find_element(self, by=By.ID, value=None):
        """
        Find an element and wrap it for tracking.
        
        Args:
            by: Selenium By type (By.ID, By.CSS_SELECTOR, etc.)
            value: Locator value
            
        Returns:
            TrackedWebElement wrapping the found element
        """
        element = self._driver.find_element(by, value)
        locator = f"{by}={value}"
        return TrackedWebElement(element, self._tracker, locator)
    
    def find_elements(self, by=By.ID, value=None):
        """Find multiple elements and wrap each one."""
        elements = self._driver.find_elements(by, value)
        locator = f"{by}={value}"
        return [TrackedWebElement(el, self._tracker, locator) for el in elements]
    
    def execute_script(self, script, *args):
        """
        Execute JavaScript with tracking support.
        
        Unwraps TrackedWebElement arguments into real elements before
        passing to the driver.
        """
        unwrapped_args = self._unwrap_elements(args)
        return self._driver.execute_script(script, *unwrapped_args)
    
    def execute_async_script(self, script, *args):
        """Execute async JavaScript with element unwrapping."""
        unwrapped_args = self._unwrap_elements(args)
        return self._driver.execute_async_script(script, *unwrapped_args)
    
    def _unwrap_elements(self, args):
        """
        Recursively unwrap TrackedWebElement to raw WebElement.
        
        JavaScript execution needs real elements, not our wrappers.
        """
        unwrapped = []
        
        for arg in args:
            # Check if it's a TrackedWebElement (using duck typing)
            if hasattr(arg, '_element') and hasattr(arg, '_tracker'):
                unwrapped.append(arg._element)
            
            # Unwrap lists
            elif isinstance(arg, list):
                unwrapped.append([
                    self._unwrap_single(item) for item in arg
                ])
            
            # Unwrap dictionaries
            elif isinstance(arg, dict):
                unwrapped.append({
                    key: self._unwrap_single(value) 
                    for key, value in arg.items()
                })
            
            # Pass through everything else
            else:
                unwrapped.append(arg)
        
        return unwrapped
    
    def _unwrap_single(self, item):
        """Unwrap a single item if it's a TrackedWebElement."""
        if hasattr(item, '_element') and hasattr(item, '_tracker'):
            return item._element
        return item
    
    def quit(self):
        """
        Soft quit - doesn't actually close the browser.
        
        Scripts often call driver.quit() at the end, but we need the browser
        to stay open so we can capture screenshots and collect logs.
        """
        logger.info("Script called driver.quit() - ignoring to preserve session")
        print("[DEBUG] Script called driver.quit() - ignoring to keep driver alive")
        return None
    
    def close(self):
        """Soft close - doesn't close the current tab."""
        logger.info("Script called driver.close() - ignoring to preserve session")
        print("[DEBUG] Script called driver.close() - ignoring to keep driver alive")
        return None
    
    def __getattr__(self, name):
        """Forward all other attribute access to the real driver, wrapping finding methods."""
        attr = getattr(self._driver, name)
        
        # Intercept and wrap all finding methods (including old find_element_by_id style)
        if (name.startswith("find_element") or name.startswith("find_elements")) and callable(attr):
            def wrapper(*args, **kwargs):
                res = attr(*args, **kwargs)
                if isinstance(res, list):
                    return [TrackedWebElement(el, self._tracker, f"driver.{name}({args})") for el in res]
                else:
                    return TrackedWebElement(res, self._tracker, f"driver.{name}({args})")
            return wrapper
            
        return attr
    
    def __repr__(self):
        return f"WebDriverProxy({self._driver})"


# ============================================================================
# SECTION 3: ActionChains Tracking
# ============================================================================

class TrackedActionChains:
    """
    Wrapper for Selenium ActionChains that records complex interactions.
    
    Ensures that hover, drag-and-drop, and multi-step interactions are
    captured in the tracker even when they don't use direct element methods.
    """
    
    def __init__(self, action_chains, tracker):
        self._ac = action_chains
        self._tracker = tracker
    
    def click(self, on_element=None):
        if on_element and hasattr(on_element, '_element'):
            self._tracker.track_click(on_element._element, on_element._locator, "ActionChains.click")
            return TrackedActionChains(self._ac.click(on_element._element), self._tracker)
        return TrackedActionChains(self._ac.click(on_element), self._tracker)
    
    def move_to_element(self, to_element):
        if hasattr(to_element, '_element'):
            self._tracker.track_hover(to_element._element, to_element._locator, "ActionChains.hover")
            return TrackedActionChains(self._ac.move_to_element(to_element._element), self._tracker)
        return TrackedActionChains(self._ac.move_to_element(to_element), self._tracker)
    
    def send_keys_to_element(self, element, *keys_to_send):
        if hasattr(element, '_element'):
            val = "".join(str(k) for k in keys_to_send)
            self._tracker.track_field_input(element._element, element._locator, val, "ActionChains.input")
            return TrackedActionChains(self._ac.send_keys_to_element(element._element, *keys_to_send), self._tracker)
        return TrackedActionChains(self._ac.send_keys_to_element(element, *keys_to_send), self._tracker)

    def __getattr__(self, name):
        """Forward all other calls and wrap the result if it's the ActionChains instance (for chaining)."""
        attr = getattr(self._ac, name)
        if callable(attr):
            def wrapper(*args, **kwargs):
                # Unwrap elements for the real Selenium call
                unwrapped_args = []
                for arg in args:
                    if hasattr(arg, '_element'): unwrapped_args.append(arg._element)
                    else: unwrapped_args.append(arg)
                
                unwrapped_kwargs = {}
                for k, v in kwargs.items():
                    if hasattr(v, '_element'): unwrapped_kwargs[k] = v._element
                    else: unwrapped_kwargs[k] = v
                
                res = attr(*unwrapped_args, **unwrapped_kwargs)
                # If it returns self (which ActionChains does for chaining), return the wrapper
                if res is self._ac:
                    return self
                return res
            return wrapper
        return attr
