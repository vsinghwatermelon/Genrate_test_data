import logging
import os
from typing import Optional

def get_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """
    Get a standardized logger instance.
    
    Args:
        name: Name for the logger
        level: Optional logging level
        
    Returns:
        logging.Logger instance
    """
    logger = logging.getLogger(name)
    
    # Set level from environment or default to INFO
    if level is None:
        debug_mode = os.getenv("DEBUG_LOGGING", "false").lower() == "true"
        logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)
    else:
        logger.setLevel(level)
        
    # Add handler if not present
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
    return logger

def safe_print(text: str) -> None:
    """Safe console printing (shim for backward compatibility)."""
    try:
        print(text)
    except Exception:
        pass
