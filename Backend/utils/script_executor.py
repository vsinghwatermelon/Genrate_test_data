"""
Selenium Script Executor - Backward Compatibility Wrapper

IMPORTANT: This file maintains backward compatibility after the modular refactor.

The 894-line script_executor.py has been split into a package:
- utils/script_executor/constants.py (reserved for future use)
- utils/script_executor/tracked_elements.py (element wrappers)
- utils/script_executor/patches.py (robustness patches)
- utils/script_executor/executor.py (main execution logic)

All existing imports continue to work without any changes required.
"""

# Import from the new modular package
from utils.script_executor import (
    SeleniumScriptExecutor,
    TrackedWebElement,
    WebDriverProxy
)

# Ensure backward compatibility for any code that imports from this module
__all__ = [
    'SeleniumScriptExecutor',
    'TrackedWebElement', 
    'WebDriverProxy'
]
