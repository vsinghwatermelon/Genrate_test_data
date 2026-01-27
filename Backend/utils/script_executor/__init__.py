"""
Script Executor Package

Provides tools for executing Selenium scripts with action tracking.

This package replaces the monolithic script_executor.py module.
"""

# Backward compatibility - export main class at package level
from .executor import SeleniumScriptExecutor
from .tracked_elements import TrackedWebElement, WebDriverProxy

__all__ = [
    'SeleniumScriptExecutor',
    'TrackedWebElement',
    'WebDriverProxy'
]
