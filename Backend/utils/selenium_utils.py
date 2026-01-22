"""
Selenium Utilities Module

Common utilities for Selenium WebDriver setup and management.
"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


def create_chrome_driver(headless: bool = True, additional_options: list = None, use_wire: bool = False) -> webdriver.Chrome:
    """
    Create a Chrome WebDriver instance with common configuration.

    Args:
        headless: Run browser in headless mode
        additional_options: Additional Chrome options to add
        use_wire: Whether to use selenium-wire for request interception

    Returns:
        Configured Chrome WebDriver instance
    """
    chrome_options = Options()

    if headless:
        chrome_options.add_argument("--headless")

    # Common options for stability
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-plugins")
    
    if headless:
        chrome_options.add_argument("--disable-images")  # Speed up loading in headless
    
    # JavaScript should ALMOST ALWAYS be enabled for modern apps
    # chrome_options.add_argument("--disable-javascript")  <- WRONG: Removed

    # Add any additional options
    if additional_options:
        for option in additional_options:
            chrome_options.add_argument(option)

    # Create service with ChromeDriverManager
    service = Service(ChromeDriverManager().install())

    # Create and return driver
    if use_wire:
        try:
            from seleniumwire import webdriver as wire_webdriver
            print(f"[DEBUG] create_chrome_driver: Initializing selenium-wire Chrome driver...")
            return wire_webdriver.Chrome(service=service, options=chrome_options)
        except ImportError as e:
            print(f"[ERROR] create_chrome_driver: Failed to import seleniumwire: {e}")
            raise ImportError("User requested 'use_wire' but selenium-wire could not be imported. Please ensure it is installed.")
            
    return webdriver.Chrome(service=service, options=chrome_options)