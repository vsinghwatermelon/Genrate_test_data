"""
Script Executor Package

A comprehensive system for executing user-provided Selenium scripts while
tracking all interactions (clicks, inputs, API calls) for test data generation.

## Main Components

### SeleniumScriptExecutor
The main executor class that orchestrates script execution. It handles:
- Chrome WebDriver setup with optional selenium-wire for API interception
- Loading element locators from config files
- Creating an isolated execution environment
- Running scripts while tracking all user actions
- Generating detailed execution summaries

### TrackedWebElement & WebDriverProxy
Wrapper classes that intercept Selenium operations to record:
- Element clicks with timestamps
- Field inputs with resolved values
- Hover actions and verifications
- API calls triggered by interactions

### Robustness Patches
Automatic fixes for common script failures:
- Fuzzy tab matching (handles minor title differences)
- Better error messages for missing locators
- Retry logic for unstable operations

## Usage Example

```python
from modules.execution.engine import SeleniumScriptExecutor

# Execute a script from a ZIP file
result = SeleniumScriptExecutor.execute_from_zip(
    zip_path='/path/to/script.zip',
    headless=True,
    use_wire=True  # Enable API interception
)

# Check results
if result['success']:
    actions = result['tracked_actions']
    print(f"Clicks: {actions['summary']['total_clicks']}")
    print(f"APIs: {actions['summary']['total_api_calls']}")
else:
    print(f"Error: {result['error']}")
```

## Architecture

```
modules/execution/engine/
├── executor.py         # Main execution orchestration (6 sections)
├── patches.py          # SeleniumHelper class patches (4 sections)
├── tracked_elements.py # Element/driver wrappers (2 sections)
├── constants.py        # Configuration constants
└── __init__.py         # Package exports
```

## Public API

The package exports three main classes:
- `SeleniumScriptExecutor`: Main executor
- `TrackedWebElement`: Element wrapper
- `WebDriverProxy`: Driver wrapper
"""

from .executor import SeleniumScriptExecutor
from .tracked_elements import TrackedWebElement, WebDriverProxy

__all__ = [
    'SeleniumScriptExecutor',
    'TrackedWebElement',
    'WebDriverProxy'
]

__version__ = '2.0.0'
