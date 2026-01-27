"""
Selenium Script Executor - Backward Compatibility Wrapper

This module maintains backward compatibility by importing from the new modular package.
The actual implementation has been split into:
- utils/script_executor/constants.py - Mock data registry
- utils/script_executor/tracked_elements.py - Element wrappers  
- utils/script_executor/patches.py - Robustness patches
- utils/script_executor/executor.py - Main execution logic

All imports continue to work as before.
"""

# Import everything from the new package to maintain backward compatibility
from utils.script_executor import (
    SeleniumScriptExecutor,
    TrackedWebElement,
    WebDriverProxy,
    MOCK_DATA_REGISTRY
)

__all__ = [
    'SeleniumScriptExecutor',
    'TrackedWebElement',
    'WebDriverProxy',
    'MOCK_DATA_REGISTRY'
]
