"""
HTML Field Extraction Engine

A robust navigation and extraction engine powered by Selenium and BeautifulSoup.
Handles multi-page form discovery, complex iframe traversals, and automated 
action sequences to reveal hidden or dynamic fields.
"""

import time
import logging
from typing import Dict, List, Any, Optional, Tuple
from bs4 import BeautifulSoup
from lxml import html as lxml_html
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from utils.selenium_utils import create_chrome_driver
from utils.field_extractor import is_visible_field, extract_field_info, normalize_field_name

logger = logging.getLogger(__name__)

# Execution Thresholds
DOCUMENT_READY_TIMEOUT = 15
ACTION_STABILIZE_DELAY = 1.0
IFRAME_SCAN_TIMEOUT = 2
DEFAULT_MAX_PAGES = 10


class HTMLFieldExtractor:
    """
    Orchestrates the navigation and field extraction pipeline.
    
    Supports headless browsing, automatic iframe discovery, and 
    stateful multi-page traversing via Selenium.
    """

    def __init__(self, headless: bool = True, wait_time: int = 5):
        """
        Initialize the extraction engine.
        
        Args:
            headless: Whether to run the browser without a UI.
            wait_time: Default duration to wait for page stability.
        """
        self.headless = headless
        self.wait_time = wait_time
        self.driver = None


    # ============================================================================
    # SECTION 1: LIFECYCLE MANAGEMENT
    # ============================================================================

    def setup_driver(self):
        """Initialize the underlying Selenium WebDriver with project-standard options."""
        if not self.driver:
            self.driver = create_chrome_driver(headless=self.headless)
            logger.info("Selenium engine successfully initialized.")

    def cleanup_driver(self):
        """Standard teardown of the browser instance."""
        if self.driver:
            self.driver.quit()
            self.driver = None
            logger.info("Selenium engine decommissioned.")

    def __enter__(self):
        """Active session entry point for use in 'with' blocks."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Auto-cleanup when exiting context."""
        self.cleanup_driver()


    # ============================================================================
    # SECTION 2: NAVIGATION & PAGE STABILITY
    # ============================================================================

    def navigate_to_url(self, url: str) -> str:
        """
        Navigate to a target URL and wait for the DOM to reach a stable state.
        
        Returns the raw HTML source of the fully loaded page.
        """
        self.setup_driver()
        logger.info(f"Navigating to mission target: {url}")
        self.driver.get(url)

        try:
            # Atomic check for document readiness
            WebDriverWait(self.driver, DOCUMENT_READY_TIMEOUT).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            time.sleep(1.0) # Grace period for post-load scripts
        except Exception as e:
            logger.warning(f"Navigation stability check timed out: {e}")

        return self.driver.page_source


    # ============================================================================
    # SECTION 3: ATOMIC ACTION EXECUTION
    # ============================================================================

    def execute_action(self, action: Dict[str, Any], locators: Dict[str, Any]) -> bool:
        """
        Execute a single targeted interaction on the page.
        
        Supports clicking (with force/JS fallback), text input, 
        selection, and hovering. Automatically handles iframe switching.
        """
        if not self.driver:
            return False

        action_type = action.get('type')
        locator_key = action.get('locator')
        locator_info = locators.get(locator_key, {})

        if not locator_info:
            logger.warning(f"Metadata missing for locator reference: {locator_key}")
            return False

        # Attempt to find the element across the main document and all iframes
        element = self._find_element_omnibus(locator_info)
        if not element:
            logger.warning(f"Action target not found in DOM: {locator_key}")
            return False

        try:
            if action_type == 'click':
                return self._perform_robust_click(element)

            elif action_type == 'send_keys':
                v = action.get('value', '')
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                try:
                    element.clear()
                    element.send_keys(v)
                except:
                    # Fallback to direct JS property injection if simulation fails
                    self.driver.execute_script("arguments[0].value = arguments[1];", element, v)
                    self.driver.execute_script("arguments[0].dispatchEvent(new Event('input', {bubbles:true}));", element)
                return True

            elif action_type == 'select':
                from selenium.webdriver.support.select import Select
                Select(element).select_by_visible_text(action.get('option', ''))
                return True

            elif action_type == 'hover':
                from selenium.webdriver.common.action_chains import ActionChains
                ActionChains(self.driver).move_to_element(element).perform()
                return True

        except Exception as e:
            logger.error(f"Action execution failure [{action_type}] on {locator_key}: {e}")
            return False

        return False


    def _find_element_omnibus(self, locator: Dict[str, List[str]], timeout: int = 10):
        """Search for an element using prioritized strategies across the entire page hierarchy."""
        strategies = [(By.CSS_SELECTOR, 'css'), (By.XPATH, 'xpath'), (By.ID, 'id'), (By.NAME, 'name')]
        
        # 1. Primary search: Main document
        self.driver.switch_to.default_content()
        for by, key in strategies:
            for selector in locator.get(key, []):
                try:
                    return WebDriverWait(self.driver, timeout).until(EC.presence_of_element_located((by, selector)))
                except: continue

        # 2. Secondary search: Recurse through all iframes
        try:
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            for iframe in iframes:
                try:
                    self.driver.switch_to.frame(iframe)
                    for by, key in strategies:
                        for selector in locator.get(key, []):
                            try:
                                return WebDriverWait(self.driver, IFRAME_SCAN_TIMEOUT).until(EC.presence_of_element_located((by, selector)))
                            except: continue
                    self.driver.switch_to.default_content()
                except:
                    self.driver.switch_to.default_content()
        except: pass

        return None


    def _perform_robust_click(self, element) -> bool:
        """Click with prioritized fallbacks for overlays and dynamic UI components."""
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            element.click()
            return True
        except:
            try:
                # JS 'Buster' Click: bypasses pointer-event blockers
                self.driver.execute_script("arguments[0].click();", element)
                return True
            except:
                return False


    # ============================================================================
    # SECTION 4: FIELD DISCOVERY PIPELINE
    # ============================================================================

    def extract_fields_from_html(self, html_content: str) -> List[Dict[str, Any]]:
        """
        Scan the target HTML for all actionable form fields.
        
        Automatically includes fields buried inside iframes if the browser 
        session is still active.
        """
        fields = self._scan_soup(BeautifulSoup(html_content, 'html.parser'))

        # Live iframe scanning
        if self.driver:
            try:
                for i, iframe in enumerate(self.driver.find_elements(By.TAG_NAME, "iframe")):
                    try:
                        self.driver.switch_to.frame(iframe)
                        iframe_fields = self._scan_soup(BeautifulSoup(self.driver.page_source, 'html.parser'))
                        for f in iframe_fields: f['iframe_context'] = f"iframe_{i}"
                        fields.extend(iframe_fields)
                        self.driver.switch_to.default_content()
                    except: self.driver.switch_to.default_content()
            except: pass

        return fields


    def _scan_soup(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Heuristic scan of a BeautifulSoup object for interactive form elements."""
        results = []
        tags = ['input', 'select', 'textarea']
        
        for element in soup.find_all(tags):
            if is_visible_field(element):
                info = extract_field_info(element, soup)
                if info.get('name') or info.get('id'):
                    results.append(info)

        # Include custom components marked with semantic ARIA roles
        for custom in soup.find_all(attrs={"role": "combobox"}):
            info = extract_field_info(custom, soup)
            if any(info.get(k) for k in ['name', 'id', 'aria-label']):
                results.append(info)

        return results


    def extract_fields_by_locators(self, html: str, locators: Dict, refs: List[str]) -> Dict[str, List[Dict]]:
        """Perform a targeted search for fields specifically mentioned in a script."""
        soup = BeautifulSoup(html, 'html.parser')
        tree = lxml_html.fromstring(html)
        results = {}

        for key in refs:
            meta = locators.get(key, {})
            matches = []

            # Try CSS prioritized matches
            for sel in meta.get('css', []):
                for node in soup.select(sel):
                    if is_visible_field(node):
                        matches.append({**extract_field_info(node, soup), 'locator_key': key})

            # Try XPath prioritized matches
            for path in meta.get('xpath', []):
                for node in tree.xpath(path):
                    node_html = lxml_html.tostring(node, encoding='unicode')
                    node_soup = BeautifulSoup(node_html, 'html.parser').find()
                    if node_soup and is_visible_field(node_soup):
                        matches.append({**extract_field_info(node_soup, soup), 'locator_key': key})

            if matches: results[key] = matches

        return results


    # ============================================================================
    # SECTION 5: ORCHESTRATION PIPELINE
    # ============================================================================

    def navigate_and_extract(self, url: str, actions: List, locators: Dict, max_pages: int = 10, log_callback=None) -> Tuple[List[str], List[Dict]]:
        """
        Execute the full end-to-end extraction sequence.
        
        Navigates to the root URL, then sequentially executes the script's 
        actions, capturing the resulting DOM states and harvesting fields 
        at every distinct step.
        """
        def _log(m):
            if log_callback: log_callback(m)
            logger.info(m)

        pages = []
        fields = []

        # Phase 1: Initial Landing
        _log(f"Initiating sequence on: {url}")
        landing_source = self.navigate_to_url(url)
        pages.append(landing_source)
        fields.extend(self.extract_fields_from_html(landing_source))

        # Phase 2: Action Progression
        for i, action in enumerate(actions, 1):
            if len(pages) >= max_pages: break
            
            act_type, loc_id = action.get('type', 'op'), action.get('locator', 'unknown')
            _log(f"Step {i}/{len(actions)}: {act_type} -> {loc_id}")

            if self.execute_action(action, locators):
                time.sleep(ACTION_STABILIZE_DELAY)
                current_source = self.driver.page_source
                
                # Capture the state if the DOM has meaningfully changed
                if current_source not in pages:
                    pages.append(current_source)
                    new_fields = self.extract_fields_from_html(current_source)
                    fields.extend(new_fields)
                    _log(f"State change detected. Discovered {len(new_fields)} new fields.")

        return pages, fields


    # ============================================================================
    # SECTION 6: POST-PROCESSING
    # ============================================================================

    def deduplicate_fields(self, fields: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Condense the extracted field list by merging duplicate observations.
        
        Prioritizes the earliest observation of a field but merges metadata 
        if subsequent observations are richer.
        """
        registry = {}

        for f in fields:
            key = normalize_field_name(f)
            if key not in registry:
                registry[key] = f
            else:
                # Merge logic: Prefer the record with more populated metadata attributes
                if self._score_metadata(f) > self._score_metadata(registry[key]):
                    registry[key] = f

        return list(registry.values())

    def _score_metadata(self, field: Dict) -> int:
        """Heuristic score to determine the richness of a field's metadata."""
        return sum(1 for v in field.values() if v and v not in [None, '', []])
