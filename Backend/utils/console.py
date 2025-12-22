"""
Console Utilities Module

Provides safe console output functions for cross-platform compatibility.
"""

import sys
from typing import Optional


def safe_print(text: str, end: str = '\n', file=None) -> None:
    """
    Print text safely to console, handling encoding issues.
    
    Falls back to replacement encoding if the default stdout encoding
    can't handle certain characters (common on Windows consoles).
    
    Args:
        text: Text to print
        end: Line ending (default: newline)
        file: Output file (default: stdout)
    """
    output = file or sys.stdout
    
    try:
        print(text, end=end, file=output)
    except UnicodeEncodeError:
        try:
            encoding = output.encoding or 'utf-8'
            encoded = text.encode(encoding, errors='replace').decode(encoding)
            print(encoded, end=end, file=output)
        except Exception:
            # Last resort: replace non-encodable chars with ?
            print(text.encode('ascii', errors='replace').decode('ascii'), end=end, file=output)
    except Exception:
        # Catch-all for any other printing issues
        try:
            print(repr(text), end=end, file=output)
        except Exception:
            pass  # Give up silently


def print_header(title: str, char: str = '=', width: int = 60) -> None:
    """Print a formatted header."""
    safe_print(char * width)
    safe_print(f"  {title}")
    safe_print(char * width)


def print_subheader(title: str, char: str = '-', width: int = 60) -> None:
    """Print a formatted subheader."""
    safe_print(char * width)
    safe_print(f"  {title}")
    safe_print(char * width)


def print_success(message: str) -> None:
    """Print a success message."""
    safe_print(f"✓ {message}")


def print_error(message: str) -> None:
    """Print an error message."""
    safe_print(f"✗ {message}")


def print_warning(message: str) -> None:
    """Print a warning message."""
    safe_print(f"⚠ {message}")


def print_info(message: str) -> None:
    """Print an info message."""
    safe_print(f"ℹ {message}")


def print_debug(message: str, enabled: bool = True) -> None:
    """Print a debug message if debugging is enabled."""
    if enabled:
        safe_print(f"[DEBUG] {message}")
