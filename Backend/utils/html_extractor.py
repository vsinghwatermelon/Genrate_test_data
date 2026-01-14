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

from utils.field_extractor import (
    extract_field_info,
    is_visible_field,
    normalize_field_name
)

logger = logging.getLogger(__name__)


class HTMLFieldExtractor:
    """Extract form fields from HTML documents with Selenium automation support."""
    
    def __init__(self, headless: bool = True, wait_time: int = 5):
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
        
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        logger.info("Selenium WebDriver initialized")
    
    def cleanup_driver(self):
        """Clean up Selenium WebDriver."""
        if self.driver:
            self.driver.quit()
            self.driver = None
            logger.info("Selenium WebDriver closed")
    
    def navigate_to_url(self, url: str) -> str:
        """Navigate to URL and return page source."""
        self.setup_driver()
        logger.info(f"Navigating to {url}")
        self.driver.get(url)
        
        # Wait for page to load completely
        try:
            WebDriverWait(self.driver, 15).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
        except:
            pass  # Continue even if timeout
        
        time.sleep(self.wait_time)
        return self.driver.page_source
    
    def execute_action(self, action: Dict[str, Any], locators: Dict[str, Any]) -> bool:
        """
        Execute a single action using locator information.
        
        Args:
            action: Action dict with 'type', 'locator', and optional params
            locators: Normalized locator data
        
        Returns:
            True if action succeeded, False otherwise
        """
        if not self.driver:
            return False
        
        action_type = action.get('type')
        locator_key = action.get('locator')
        locator_info = locators.get(locator_key, {})
        
        if not locator_info:
            logger.debug(f"No locator info found for {locator_key}")
            return False
        
        # Try different locator strategies
        element = self._find_element(locator_info)
        if not element:
            logger.debug(f"Element not found for {locator_key}")
            return False
        
        try:
            if action_type == 'click':
                # Scroll element into view
                self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
                time.sleep(0.5)  # Wait for scroll
                
                # Wait for element to be clickable
                wait = WebDriverWait(self.driver, 5)
                element = wait.until(EC.element_to_be_clickable(element))
                
                element.click()
                logger.info(f"Clicked element: {locator_key}")
                time.sleep(2)  # Wait for navigation
                return True
            
            elif action_type == 'send_keys':
                # Scroll element into view
                self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
                time.sleep(0.5)
                
                value = action.get('value', '')
                element.clear()
                element.send_keys(value)
                logger.info(f"Sent keys to {locator_key}: {value}")
                return True
            
            elif action_type == 'select':
                from selenium.webdriver.support.select import Select
                select = Select(element)
                option = action.get('option', '')
                select.select_by_visible_text(option)
                logger.info(f"Selected option in {locator_key}: {option}")
                return True
            
            elif action_type == 'wait':
                logger.info(f"Waiting for element: {locator_key}")
                return True
        
        except Exception as e:
            # Extract clean error message
            error_str = str(e)
            error_type = type(e).__name__
            
            # Handle Selenium error format: "Message: error_text\nStacktrace:..."
            if 'Message:' in error_str:
                parts = error_str.split('\nStacktrace:')[0].split('Message:', 1)
                if len(parts) > 1 and parts[1].strip():
                    error_msg = parts[1].strip()
                else:
                    # Message is empty, use error type
                    error_msg = error_type
            else:
                error_msg = error_str.split('\n')[0] if '\n' in error_str else error_str
            
            # Fallback to exception type if message is empty or just whitespace
            if not error_msg or not error_msg.strip():
                error_msg = error_type
            
            # Truncate if too long but show meaningful part
            if len(error_msg) > 150:
                error_msg = error_msg[:150] + '...'
            
            logger.debug(f"Failed to execute {action_type} on {locator_key}: {error_msg}")
            print(f"[STEP 6] ⚠ Action failed ({action_type} on {locator_key}): {error_msg}")
            import sys
            sys.stdout.flush()
            return False
        
        return False
    
    def _find_element(self, locator_info: Dict[str, List[str]], wait_time: int = 3):
        """Try to find element using multiple locator strategies with fast wait time."""
        wait = WebDriverWait(self.driver, wait_time)
        
        # Try CSS selectors
        for css_sel in locator_info.get('css', []):
            try:
                element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, css_sel)))
                return element
            except:
                continue
        
        # Try XPath
        for xpath in locator_info.get('xpath', []):
            try:
                element = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
                return element
            except:
                continue
        
        # Try ID
        for elem_id in locator_info.get('id', []):
            try:
                element = wait.until(EC.presence_of_element_located((By.ID, elem_id)))
                return element
            except:
                continue
        
        # Try name
        for name in locator_info.get('name', []):
            try:
                element = wait.until(EC.presence_of_element_located((By.NAME, name)))
                return element
            except:
                continue
        
        return None
    
    def extract_fields_from_html(self, html_content: str) -> List[Dict[str, Any]]:
        """
        Extract all visible form fields from HTML content.
        
        Args:
            html_content: HTML document content
        
        Returns:
            List of extracted field dictionaries
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        fields = []
        
        # Extract input fields
        for input_elem in soup.find_all('input'):
            if is_visible_field(input_elem):
                field_info = extract_field_info(input_elem, soup)
                if field_info.get('name') or field_info.get('id'):
                    fields.append(field_info)
        
        # Extract select fields
        for select_elem in soup.find_all('select'):
            if is_visible_field(select_elem):
                field_info = extract_field_info(select_elem, soup)
                if field_info.get('name') or field_info.get('id'):
                    fields.append(field_info)
        
        # Extract textarea fields
        for textarea_elem in soup.find_all('textarea'):
            if is_visible_field(textarea_elem):
                field_info = extract_field_info(textarea_elem, soup)
                if field_info.get('name') or field_info.get('id'):
                    fields.append(field_info)
        
        # Extract combobox fields (role="combobox")
        for elem in soup.find_all(attrs={"role": "combobox"}):
            field_info = extract_field_info(elem, soup)
            if field_info.get('name') or field_info.get('id') or field_info.get('aria-label'):
                fields.append(field_info)
        
        logger.info(f"Extracted {len(fields)} fields from HTML")
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
        max_pages: int = 10
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Navigate through pages and extract HTML from each step.
        
        Args:
            url: Starting URL
            actions: List of actions to execute
            locators: Normalized locator data
            max_pages: Maximum number of pages to capture
        
        Returns:
            Tuple of (page_sources, all_extracted_fields)
        """
        page_sources = []
        all_fields = []
        successful_actions = 0
        failed_actions = 0
        
        # Navigate to initial page
        page_source = self.navigate_to_url(url)
        page_sources.append(page_source)
        
        # Extract fields from first page
        fields = self.extract_fields_from_html(page_source)
        all_fields.extend(fields)
        logger.info(f"Page 1: Extracted {len(fields)} fields")
        
        # Execute actions and capture subsequent pages
        pages_captured = 1
        last_url = self.driver.current_url if self.driver else url
        
        print(f"[STEP 6] Executing {len(actions)} actions...")
        import sys
        sys.stdout.flush()
        
        consecutive_failures = 0
        max_consecutive_failures = 5  # Stop trying actions after 5 consecutive failures
        
        for i, action in enumerate(actions, 1):
            if pages_captured >= max_pages:
                logger.info(f"Reached max pages limit: {max_pages}")
                break
            
            # Early exit if too many consecutive failures
            if consecutive_failures >= max_consecutive_failures:
                print(f"[STEP 6] ⚠ Stopping action execution after {consecutive_failures} consecutive failures")
                sys.stdout.flush()
                break
            
            # Show progress
            action_type = action.get('type', 'unknown')
            locator_key = action.get('locator', 'unknown')
            print(f"[STEP 6] Action {i}/{len(actions)}: {action_type} on {locator_key}...")
            sys.stdout.flush()
            
            # Execute action
            success = self.execute_action(action, locators)
            
            if success:
                successful_actions += 1
                consecutive_failures = 0  # Reset on success
            else:
                failed_actions += 1
                consecutive_failures += 1
                continue
            
            # Check if page changed
            current_url = self.driver.current_url if self.driver else url
            time.sleep(1)  # Wait for page to stabilize
            
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
                    logger.info(f"Page {pages_captured}: Extracted {len(fields)} fields")
                    
                    last_url = current_url
        
        print(f"[STEP 6] Action execution complete: {successful_actions} successful, {failed_actions} failed")
        logger.info(f"Total pages captured: {len(page_sources)}")
        logger.info(f"Total fields extracted: {len(all_fields)}")
        logger.info(f"Actions: {successful_actions} successful, {failed_actions} failed")
        import sys
        sys.stdout.flush()
        
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
