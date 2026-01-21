"""
Selenium Utilities Module

Common utilities for Selenium WebDriver setup and management.
"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


def create_chrome_driver(headless: bool = True, additional_options: list = None) -> webdriver.Chrome:
    """
    Create a Chrome WebDriver instance with common configuration.

    Args:
        headless: Run browser in headless mode
        additional_options: Additional Chrome options to add

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
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver