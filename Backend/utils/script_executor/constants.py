"""
Script Executor Constants

Configuration constants for the script executor module.
"""

# API Call Association
API_CAPTURE_WINDOW_SECONDS = 5.0  # Time window after click to capture APIs

# Browser Configuration
DEFAULT_IMPLICIT_WAIT_SECONDS = 10  # Default wait time for element finding
DEFAULT_PAGE_LOAD_TIMEOUT_SECONDS = 30  # Max time to wait for page loads

# Retry Configuration
TAB_SWITCH_MAX_ATTEMPTS = 4  # Number of retries for tab switching
TAB_SWITCH_WAIT_SECONDS = 1.5  # Wait between tab switch attempts
