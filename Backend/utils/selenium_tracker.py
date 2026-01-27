"""
Selenium Interaction Tracker

A high-fidelity monitoring agent that wraps Selenium actions to record clicks, 
form interactions, and intercepted API calls. Provides a structured narrative 
of the user flow for schema synthesis and test data generation.
"""

import time
import logging
import base64
from typing import Dict, Any, List, Optional
from datetime import datetime
from selenium.webdriver.remote.webelement import WebElement

# Centralized Logic Hub Imports
from utils.element_extractor import extract_full_element_info

logger = logging.getLogger(__name__)


# ============================================================================
# SECTION 1: INTERACTION TRACKER (KEEPS STATE)
# ============================================================================

class SeleniumActionTracker:
    """
    Stateful monitor that intercepts and records all Selenium-driven interactions.
    
    Acts as the source of truth for 'what happened' during a script execution,
    correlating UI interactions with resulting API side-effects.
    """

    def __init__(self, api_capture_window: float = 3.0, all_locators: Dict = None):
        """
        Initialize a tracking session.
        
        Args:
            api_capture_window: Seconds after a click to correlate API calls to that click.
            all_locators: Full dictionary of discovered locators from scanning.
        """
        self.all_locators = all_locators or {}
        self.clicked_elements: List[Dict[str, Any]] = [] # Internal use
        self.filled_fields: List[Dict[str, Any]] = []    # Internal use
        self.click_events: List[Dict[str, Any]] = []     # Data compatibility
        self.fill_events: List[Dict[str, Any]] = []      # Data compatibility
        self.action_log: List[Dict[str, Any]] = []
        self.api_calls: List[Dict[str, Any]] = []
        self.screenshots: List[Dict[str, str]] = []
        self.skipped_actions: List[Dict[str, Any]] = []
        self.page_inventory: List[Dict[str, Any]] = []
        
        self.start_time = datetime.now()
        self.api_window = api_capture_window


    def track_click(self, element: WebElement, locator: str, description: str = ""):
        """Record a successful click and analyze the target element."""
        timestamp = time.time()
        logger.info(f"[TRACKER] Intercepted CLICK on: {locator}")
        
        # Utilize centralized analysis suite
        info = extract_full_element_info(element, locator, "click", description)
        info['timestamp'] = timestamp
        
        self.clicked_elements.append(info)
        self.click_events.append(info)
        self.action_log.append({
            "type": "click",
            "locator": locator,
            "timestamp": timestamp,
            "details": info
        })


    def track_field_input(self, element: WebElement, locator: str, value: str, description: str = ""):
        """Record a field modification and analyze the interaction context."""
        timestamp = time.time()
        logger.info(f"[TRACKER] Intercepted INPUT on: {locator} -> '{value}'")
        
        info = extract_full_element_info(element, locator, "input", description)
        info['value_entered'] = value
        info['timestamp'] = timestamp
        
        self.filled_fields.append(info)
        self.fill_events.append(info)
        self.action_log.append({
            "type": "input",
            "locator": locator,
            "value": value,
            "timestamp": timestamp,
            "details": info
        })


    def track_api_call(self, url: str, method: str, payload: Any, headers: Dict, **kwargs):
        """Record an intercepted Fetch/XHR request."""
        call_info = {
            "url": url,
            "method": method,
            "payload": payload,
            "headers": headers,
            "timestamp": time.time(),
            **kwargs
        }
        
        # Only attempt to find trigger if not already provided via kwargs
        if 'triggered_by' not in call_info and 'triggered_by_click' not in call_info and 'trigger_details' not in call_info:
            trigger = self.find_associated_click(call_info['timestamp'])
            if trigger:
                # Add full semantic context for rich frontend display
                call_info['trigger_details'] = trigger
                
                # Use a specific priority for the grouping string
                group_id = trigger.get('exact_purpose') or trigger.get('locator')
                call_info['triggered_by'] = group_id
                call_info['triggered_by_click'] = group_id
                call_info['triggered_by_action'] = group_id
                call_info['time_after_click'] = trigger.get('time_after_click')
        else:
            # If trigger details were passed (likely from executor.py), ensure all keys exist
            details = call_info.get('trigger_details') or {}
            if details:
                # Add compatibility keys for grouping and display
                group_id = details.get('exact_purpose') or details.get('locator') or call_info.get('triggered_by')
                call_info['triggered_by'] = group_id
                call_info['triggered_by_click'] = group_id
                call_info['triggered_by_action'] = group_id
                if 'time_after_click' not in call_info and 'time_after_click' in details:
                    call_info['time_after_click'] = details['time_after_click']
            
        self.api_calls.append(call_info)
        logger.debug(f"[TRACKER] Intercepted API {method}: {url[:100]}")


    def track_hover(self, element: WebElement, locator: str, description: str = ""):
        """Record a mouse hover interaction."""
        info = extract_full_element_info(element, locator, "hover", description)
        self.action_log.append({
            "type": "hover",
            "locator": locator,
            "timestamp": time.time(),
            "details": info
        })


    def track_skip(self, locator: str, action_type: str, reason: str = "Element not found"):
        """Record an action that was skipped due to a missing element or other non-fatal issue."""
        timestamp = time.time()
        logger.warning(f"[TRACKER] Skipped {action_type.upper()} on: {locator} (Reason: {reason})")
        
        self.skipped_actions.append({
            "type": action_type,
            "locator": locator,
            "timestamp": timestamp,
            "reason": reason
        })
        
        # Also add to action log as a "skip" entry
        self.action_log.append({
            "type": f"skipped_{action_type}",
            "locator": locator,
            "timestamp": timestamp,
            "status": "skipped",
            "reason": reason
        })


    def track_verification(self, element: Optional[WebElement], locator: str, expected: str, actual: str, success: bool, description: str = ""):
        """Record a text verification or assertion."""
        timestamp = time.time()
        info = {}
        if element:
            try:
                info = extract_full_element_info(element, locator, "verify", description)
            except Exception:
                pass
        
        self.action_log.append({
            "type": "verify",
            "locator": locator,
            "expected": expected,
            "actual": actual,
            "success": success,
            "timestamp": timestamp,
            "details": info
        })
        
        logger.info(f"[TRACKER] Intercepted VERIFY on: {locator} ({'PASSED' if success else 'FAILED'})")


    def track_get_text(self, element: Optional[WebElement], locator: str, text: str, description: str = ""):
        """Record a text extraction action."""
        timestamp = time.time()
        info = {}
        if element:
            try:
                info = extract_full_element_info(element, locator, "get_text", description)
            except Exception:
                pass
                
        self.action_log.append({
            "type": "get_text",
            "locator": locator,
            "text": text,
            "timestamp": timestamp,
            "details": info
        })
        
        logger.info(f"[TRACKER] Intercepted GET_TEXT on: {locator} -> '{text[:50]}'")


    def track_page_inventory(self, driver):
        """
        Scans the current page for ALL interactive elements to create a complete inventory.
        This fulfills the "track all elements" requirement.
        """
        logger.info("[TRACKER] Starting Universal Page Inventory scan...")
        try:
            # Common interactive selectors
            selectors = [
                "button", "input", "a", "select", "textarea",
                "[onclick]", "[role='button']", "[role='link']", "[role='menuitem']"
            ]
            
            elements = driver.find_elements_by_css_selector(", ".join(selectors)) if hasattr(driver, 'find_elements_by_css_selector') else driver.find_elements("css selector", ", ".join(selectors))
            
            for i, element in enumerate(elements):
                try:
                    # Limit to visible elements to avoid noise
                    if not element.is_displayed():
                        continue
                        
                    # Extract full info for each element
                    info = extract_full_element_info(element, f"inventory_element_{i}", "inventory")
                    self.page_inventory.append(info)
                except Exception:
                    continue
                    
            logger.info(f"[TRACKER] ✓ Inventory scan complete. Captured {len(self.page_inventory)} elements.")
        except Exception as e:
            logger.warning(f"[TRACKER] ⚠️ Inventory scan failed: {e}")


    # ============================================================================
    # SECTION 2: STATE & CONTEXT CAPTURE
    # ============================================================================

    def capture_screenshot(self, driver, label: str = "state_capture"):
        """Snapshot the current visual state for debugging or reporting."""
        try:
            b64 = driver.get_screenshot_as_base64()
            self.screenshots.append({
                "label": label,
                "timestamp": time.time(),
                "data": b64
            })
        except Exception as e:
            logger.warning(f"Screenshot capture failed: {e}")


    def find_associated_click(self, api_timestamp: float) -> Optional[Dict]:
        """Heuristic: finds the UI action most likely to have triggered an API call."""
        if not self.clicked_elements:
            return None
            
        # Check clicks in reverse (most recent first)
        for click in reversed(self.clicked_elements):
            delta = api_timestamp - click['timestamp']
            if 0 <= delta <= self.api_window:
                # Add calculated delta for API coordination
                return {**click, 'time_after_click': delta}
        return None


    # ============================================================================
    # SECTION 3: SUMMARY & FINALIZATION
    # ============================================================================

    def get_summary(self) -> Dict[str, Any]:
        """Aggregate all tracked metadata into a single portable result set."""
        duration = (datetime.now() - self.start_time).total_seconds()
        
        # Define flat summary keys for both console and frontend legacy support
        summary = {
            "session_duration": f"{duration:.2f}s",
            "total_actions": len(self.action_log),
            "total_clicks": len(self.clicked_elements),
            "total_inputs": len(self.filled_fields),
            "total_api_calls": len(self.api_calls),
            "interaction_count": len(self.action_log),
            "click_count": len(self.clicked_elements),
            "fill_count": len(self.filled_fields),
            "api_count": len(self.api_calls)
        }

        return {
            "summary": summary,
            "session_duration": summary["session_duration"], # Flattened for console/legacy
            "all_locators": self.all_locators,
            "total_locators_found": len(self.all_locators),
            "click_events": self.click_events,
            "fill_events": self.fill_events,
            "api_calls": self.api_calls,
            "interactions": self.action_log,
            "action_log": self.action_log,
            "clicked_elements": self.clicked_elements,
            "filled_fields": self.filled_fields,
            "total_actions": summary["total_actions"], # Extra flattening
            "total_clicks": summary["total_clicks"],
            "total_inputs": summary["total_inputs"],
            "total_api_calls": summary["total_api_calls"],
            "skipped_actions": self.skipped_actions,
            "total_skips": len(self.skipped_actions),
            "page_inventory": self.page_inventory,
            "total_inventory_count": len(self.page_inventory),
            "screenshots": self.screenshots,
            "screenshots_count": len(self.screenshots)
        }

    def print_summary(self):
        """Output a professional log summary to the server console."""
        s = self.get_summary()
        logger.info("=" * 60)
        logger.info(f"TRACKING SESSION COMPLETE - {s['session_duration']}")
        logger.info("-" * 60)
        logger.info(f"Clicks: {len(s['click_events'])}")
        logger.info(f"Inputs: {len(s['fill_events'])}")
        logger.info(f"APIs:   {len(s['api_calls'])}")
        logger.info("=" * 60)


# ============================================================================
# SECTION 4: TRACKED HELPER (CODE WRAPPER)
# ============================================================================

# SESSION MONITORING COMPLETE
