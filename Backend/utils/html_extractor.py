"""
HTML Field Extractor Module

Extracts form fields from HTML using dynamic strategies with Selenium automation.
Supports multi-page navigation and comprehensive field discovery.
"""

from typing import Dict, List, Any, Optional, Tuple
from bs4 import BeautifulSoup
from lxml import html as lxml_html
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time
import logging

from utils.selenium_utils import create_chrome_driver
from utils.field_extractor import is_visible_field, extract_field_info, normalize_field_name

logger = logging.getLogger(__name__)

# Constants
DEFAULT_WAIT_TIME = 5  # Default page load wait (seconds)
DOCUMENT_READY_TIMEOUT = 15  # Timeout for document.readyState check
POST_LOAD_DELAY = 2  # Wait after page load for animations/scripts
SCROLL_DELAY = 0.5  # Delay after scrolling to element
HOVER_DELAY = 1.0  # Delay after hovering over element
PAGE_STABILIZE_DELAY = 1.0  # Wait for page to stabilize after action
IFRAME_WAIT_TIMEOUT = 2  # Shorter timeout for iframe searches
MAIN_DOC_WAIT_TIMEOUT = 10  # Timeout for main document element finding
DEFAULT_MAX_PAGES = 10  # Default maximum pages to capture
FIELD_SUMMARY_LIMIT = 5  # Number of fields to show in summaries

class HTMLFieldExtractor:
    """Extract form fields from HTML documents with Selenium automation support."""

    def __init__(self, headless: bool = True, wait_time: int = DEFAULT_WAIT_TIME):
        """
        Initialize HTML field extractor.

        Args:
            headless: Run browser in headless mode
            wait_time: Default wait time for page loads (seconds)
        """
        self.headless = headless
        self.wait_time = wait_time
        self.driver = None

    def setup_driver(self):
        """Set up Selenium WebDriver with Chrome."""
        if self.driver:
            return

        self.driver = create_chrome_driver(headless=self.headless)
        logger.info("Selenium WebDriver initialized")

    def cleanup_driver(self):
        """Clean up Selenium WebDriver."""
        if self.driver:
            self.driver.quit()
            self.driver = None
            logger.info("Selenium WebDriver closed")

    def navigate_to_url(self, url: str) -> str:
        """Navigate to URL and return page source with robust loading."""
        self.setup_driver()
        logger.info(f"Navigating to {url}")
        self.driver.get(url)

        # Wait for page to load completely with dynamic wait
        try:
            # First wait for document ready
            WebDriverWait(self.driver, DOCUMENT_READY_TIMEOUT).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            # Then wait for any initial animations/scripts
            time.sleep(POST_LOAD_DELAY)
        except Exception as e:
            logger.warning(f"Wait during navigation failed: {e}")

        return self.driver.page_source

    def execute_action(self, action: Dict[str, Any], locators: Dict[str, Any]) -> bool:
        """Execute a single Selenium action with robust finding and execution."""
        if not self.driver:
            logger.debug("No driver available for action execution")
            return False

        action_type = action.get('type')
        locator_key = action.get('locator')
        locator_info = locators.get(locator_key, {})

        logger.debug(f"Executing action: {action_type} on locator_key: {locator_key}")
        logger.debug(f"Locator info for {locator_key}: {locator_info}")

        if not locator_info:
            logger.warning(f"No locator info found for {locator_key}")
            return False

        # 1. FIND ELEMENT (Omni-Search logic handles iframes)
        element = self._find_element(locator_info)
        if not element:
            logger.warning(f"Element not found for {locator_key} (searched main document and all iframes)")
            return False

        try:
            if action_type == 'click':
                return self._force_click(element, locator_key)

            elif action_type == 'send_keys':
                self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
                time.sleep(0.5)
                value = action.get('value', '')
                try:
                    element.clear()
                    element.send_keys(value)
                except:
                    # Fallback for send_keys via JS if element is stubborn
                    self.driver.execute_script("arguments[0].value = arguments[1];", element, value)
                    self.driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", element)
                logger.info(f"Sent keys to {locator_key}: {value}")
                return True

            elif action_type == 'select':
                from selenium.webdriver.support.select import Select
                select_obj = Select(element)
                option = action.get('option', '')
                select_obj.select_by_visible_text(option)
                logger.info(f"Selected option in {locator_key}: {option}")
                return True

            elif action_type == 'hover':
                self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
                time.sleep(0.5)
                from selenium.webdriver.common.action_chains import ActionChains
                chains = ActionChains(self.driver)
                chains.move_to_element(element).perform()
                logger.info(f"Hovered over element: {locator_key}")
                time.sleep(HOVER_DELAY)
                return True

            elif action_type == 'wait':
                logger.info(f"Waiting for element: {locator_key}")
                return True

        except Exception as e:
            error_msg = str(e).split('\n')[0]
            logger.debug(f"Failed to execute {action_type} on {locator_key}: {error_msg}")
            print(f"[STEP 6] ⚠ Action failed ({action_type} on {locator_key}): {error_msg}")
            import sys
            sys.stdout.flush()
            return False

        return False

    def _find_element(self, locator_info: Dict[str, List[str]], wait_time: int = MAIN_DOC_WAIT_TIMEOUT):
        """Try to find element searching through main document and all iframes."""
        strategies = [
            (By.CSS_SELECTOR, locator_info.get('css', [])),
            (By.XPATH, locator_info.get('xpath', [])),
            (By.ID, locator_info.get('id', [])),
            (By.NAME, locator_info.get('name', []))
        ]

        logger.debug(f"Searching for element with locator_info: {locator_info}")

        # 1. Main document
        self.driver.switch_to.default_content()
        for by, selectors in strategies:
            for selector in selectors:
                try:
                    logger.debug(f"Trying {by} selector: '{selector}' in main document")
                    element = WebDriverWait(self.driver, wait_time).until(
                        EC.presence_of_element_located((by, selector))
                    )
                    logger.debug(f"Found element with {by} selector: '{selector}'")
                    return element
                except Exception as e:
                    logger.debug(f"Failed {by} selector '{selector}' in main document: {str(e)}")
                    continue

        # 2. Iframes
        try:
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            logger.debug(f"Found {len(iframes)} iframes to search")
            for i, iframe in enumerate(iframes):
                try:
                    logger.debug(f"Searching in iframe {i}")
                    self.driver.switch_to.frame(iframe)
                    for by, selectors in strategies:
                        for selector in selectors:
                            try:
                                logger.debug(f"Trying {by} selector: '{selector}' in iframe {i}")
                                element = WebDriverWait(self.driver, IFRAME_WAIT_TIMEOUT).until(
                                    EC.presence_of_element_located((by, selector))
                                )
                                logger.debug(f"Found element with {by} selector: '{selector}' in iframe {i}")
                                return element
                            except Exception as e:
                                logger.debug(f"Failed {by} selector '{selector}' in iframe {i}: {str(e)}")
                                continue
                    self.driver.switch_to.default_content()
                except Exception as e:
                    logger.debug(f"Error searching iframe {i}: {str(e)}")
                    self.driver.switch_to.default_content()
                    continue
        except Exception as e:
            logger.debug(f"Error getting iframes: {str(e)}")

        logger.debug(f"Element not found with any selector in locator_info: {locator_info}")
        return None

    def _force_click(self, element, locator_key: str):
        """Standard click falling back to Hover + JS 'Overlay Buster'."""
        try:
            # 1. Standard scroll and click
            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
            time.sleep(0.5)
            element.click()
            return True
        except:
            # 2. Hover Fallback: Some elements need a hover to become interactive/visible
            try:
                from selenium.webdriver.common.action_chains import ActionChains
                chains = ActionChains(self.driver)
                chains.move_to_element(element).perform()
                time.sleep(0.5)
                # Try clicking after hover
                element.click()
                return True
            except:
                # 3. JS Click (Overlay Buster)
                try:
                    self.driver.execute_script("arguments[0].click();", element)
                    return True
                except:
                    return False

    def extract_fields_from_html(self, html_content: str) -> List[Dict[str, Any]]:
        """
        Extract visible form fields from main document and all iframes.
        """
        all_found_fields = []

        # 1. Extract from the main page source (provided)
        soup = BeautifulSoup(html_content, 'html.parser')
        main_fields = self._extract_from_soup(soup)
        all_found_fields.extend(main_fields)

        # 2. Extract from iframes (live check via driver)
        if self.driver:
            try:
                iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
                for i, iframe in enumerate(iframes):
                    try:
                        self.driver.switch_to.frame(iframe)
                        iframe_soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                        iframe_fields = self._extract_from_soup(iframe_soup)
                        for f in iframe_fields:
                            f['source_iframe'] = f"iframe_{i}"
                        all_found_fields.extend(iframe_fields)
                        self.driver.switch_to.default_content()
                    except:
                        self.driver.switch_to.default_content()
                        continue
            except Exception as e:
                logger.warning(f"Failed to scan iframes for fields: {e}")

        logger.info(f"Extracted {len(all_found_fields)} fields from document (+iframes)")
        return all_found_fields

    def _extract_from_soup(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Internal helper for extracting from a soup object."""
        fields = []
        # Input fields
        for input_elem in soup.find_all('input'):
            if is_visible_field(input_elem):
                field_info = extract_field_info(input_elem, soup)
                if field_info.get('name') or field_info.get('id'):
                    fields.append(field_info)

        # Select fields
        for select_elem in soup.find_all('select'):
            if is_visible_field(select_elem):
                field_info = extract_field_info(select_elem, soup)
                if field_info.get('name') or field_info.get('id'):
                    fields.append(field_info)

        # Textarea fields
        for textarea_elem in soup.find_all('textarea'):
            if is_visible_field(textarea_elem):
                field_info = extract_field_info(textarea_elem, soup)
                if field_info.get('name') or field_info.get('id'):
                    fields.append(field_info)

        # Combobox fields
        for elem in soup.find_all(attrs={"role": "combobox"}):
            field_info = extract_field_info(elem, soup)
            if field_info.get('name') or field_info.get('id') or field_info.get('aria-label'):
                fields.append(field_info)

        return fields

    def extract_fields_by_locators(
        self,
        html_content: str,
        locators: Dict[str, Dict[str, List[str]]],
        locator_keys: List[str]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extract fields matching specific locators from HTML.

        Args:
            html_content: HTML document content
            locators: Normalized locator data
            locator_keys: List of locator keys to search for

        Returns:
            Dictionary mapping locator keys to matched fields
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        tree = lxml_html.fromstring(html_content)

        results = {}

        for locator_key in locator_keys:
            locator_info = locators.get(locator_key, {})
            if not locator_info:
                continue

            matches = []

            # Try CSS selectors
            for css_sel in locator_info.get('css', []):
                try:
                    elements = soup.select(css_sel)
                    for elem in elements:
                        if is_visible_field(elem):
                            field_info = extract_field_info(elem, soup)
                            field_info['locator_key'] = locator_key
                            field_info['matched_by'] = f'css: {css_sel}'
                            matches.append(field_info)
                except Exception as e:
                    logger.warning(f"CSS selector failed for {locator_key}: {e}")

            # Try XPath
            for xpath in locator_info.get('xpath', []):
                try:
                    elements = tree.xpath(xpath)
                    for elem in elements:
                        # Convert lxml element to BeautifulSoup
                        elem_html = lxml_html.tostring(elem, encoding='unicode')
                        elem_soup = BeautifulSoup(elem_html, 'html.parser')
                        main_elem = elem_soup.find()

                        if main_elem and is_visible_field(main_elem):
                            field_info = extract_field_info(main_elem, soup)
                            field_info['locator_key'] = locator_key
                            field_info['matched_by'] = f'xpath: {xpath}'
                            matches.append(field_info)
                except Exception as e:
                    logger.warning(f"XPath failed for {locator_key}: {e}")

            if matches:
                results[locator_key] = matches

        logger.info(f"Found matches for {len(results)}/{len(locator_keys)} locators")
        return results

    def navigate_and_extract(
        self,
        url: str,
        actions: List[Dict[str, Any]],
        locators: Dict[str, Any],
        max_pages: int = DEFAULT_MAX_PAGES,
        log_callback=None
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Navigate through pages and extract HTML from each step with logging.
        """
        def log(msg):
            if log_callback: log_callback(msg)
            logger.info(msg)
        page_sources = []
        all_fields = []
        successful_actions = 0
        failed_actions = 0

        # Navigate to initial page
        log(f"Navigating to initial URL: {url}")
        page_source = self.navigate_to_url(url)
        page_sources.append(page_source)

        # Extract fields from first page
        fields = self.extract_fields_from_html(page_source)
        all_fields.extend(fields)

        # Log specific field names for transparency
        field_names = [f.get('label') or f.get('placeholder') or f.get('name') or f.get('id') for f in fields]
        field_names = [name for name in field_names if name]
        field_summary = ", ".join(field_names[:5])
        if len(field_names) > FIELD_SUMMARY_LIMIT:
            field_summary += f" (+{len(field_names)-FIELD_SUMMARY_LIMIT} more)"

        log(f"Page 1 capture complete. Extracted {len(fields)} fields: [{field_summary}]")

        # Execute actions and capture subsequent pages
        pages_captured = 1
        last_url = self.driver.current_url if self.driver else url

        log(f"Executing {len(actions)} actions from script...")

        # Execute all actions regardless of consecutive failures
        for i, action in enumerate(actions, 1):
            # Check page limit
            if pages_captured >= max_pages:
                log(f"⚠ Reached max pages limit ({max_pages}). Stopping further actions to prevent infinite loops.")
                break

            # Show progress
            action_type = action.get('type', 'unknown')
            locator_key = action.get('locator', 'unknown')
            log(f"Action {i}/{len(actions)}: {action_type} on {locator_key}...")

            # Execute action
            success = self.execute_action(action, locators)

            if success:
                successful_actions += 1
            else:
                failed_actions += 1
                # Continue to next action even on failure
                continue

            # Check if page changed
            current_url = self.driver.current_url if self.driver else url
            time.sleep(PAGE_STABILIZE_DELAY)  # Wait for page to stabilize

            if current_url != last_url or action.get('type') == 'click':
                # Capture new page
                new_source = self.driver.page_source if self.driver else ""

                # Only add if content is different
                if new_source and new_source not in page_sources:
                    page_sources.append(new_source)
                    pages_captured += 1

                    # Extract fields
                    fields = self.extract_fields_from_html(new_source)
                    all_fields.extend(fields)

                    # Log specific field names for transparency
                    field_names = [f.get('label') or f.get('placeholder') or f.get('name') or f.get('id') for f in fields[:10]]
                    field_names = [name for name in field_names if name]
                    field_summary = ", ".join(field_names[:5])
                    if len(field_names) > FIELD_SUMMARY_LIMIT:
                        field_summary += f" (+{len(field_names)-FIELD_SUMMARY_LIMIT} more)"

                    log(f"Page {pages_captured} capture complete. Extracted {len(fields)} fields: [{field_summary}]")

                    last_url = current_url

        log(f"Action execution complete: {successful_actions} successful, {failed_actions} failed")

        return page_sources, all_fields

    def deduplicate_fields(self, fields: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Deduplicate fields based on name/id.

        Keeps the first occurrence with the most complete metadata.
        """
        seen = {}

        for field in fields:
            key = normalize_field_name(field)

            if key not in seen:
                seen[key] = field
            else:
                # Keep field with more metadata
                existing = seen[key]
                if self._count_metadata(field) > self._count_metadata(existing):
                    seen[key] = field

        return list(seen.values())

    @staticmethod
    def _count_metadata(field: Dict[str, Any]) -> int:
        """Count non-empty metadata fields."""
        count = 0
        for key, value in field.items():
            if value and value not in [None, '', []]:
                count += 1
        return count

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup driver."""
        self.cleanup_driver()
