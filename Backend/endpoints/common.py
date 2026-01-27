"""
Common Utilities for All Endpoints

Centralizes repeated patterns across endpoint files to reduce code duplication
and ensure consistent behavior for common operations like file handling and
LLM initialization.
"""

import logging
import os
import tempfile
import zipfile
import json
from typing import Any, Dict, Optional
from fastapi import UploadFile, HTTPException

logger = logging.getLogger(__name__)

# Configuration Constants
MAX_UPLOAD_SIZE_MB = 100
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024


# ============================================================================
# FILE HANDLING
# ============================================================================

async def extract_zip_file(file: UploadFile, tmpdir: str) -> str:
    """
    Extract uploaded zip file to temporary directory with validation.
    
    Validates file size before extraction to prevent resource exhaustion.
    
    Args:
        file: Uploaded zip file from FastAPI
        tmpdir: Temporary directory path for extraction
        
    Returns:
        Path to the extracted zip file
        
    Raises:
        HTTPException: If file is too large (>100MB) or extraction fails
        
    Example:
        >>> tmpdir = tempfile.mkdtemp()
        >>> zip_path = await extract_zip_file(upload_file, tmpdir)
        >>> # Files are now extracted in tmpdir
    """
    zip_path = os.path.join(tmpdir, "upload.zip")
    
    # Read and validate file size
    file_bytes = await file.read()
    file_size_mb = len(file_bytes) / 1024 / 1024
    
    if len(file_bytes) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({file_size_mb:.2f}MB). Maximum allowed: {MAX_UPLOAD_SIZE_MB}MB"
        )
    
    logger.info(f"Extracting zip file ({file_size_mb:.2f}MB)...")
    
    try:
        # Write zip to disk
        with open(zip_path, "wb") as f:
            f.write(file_bytes)
        
        # Extract all contents
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(tmpdir)
        
        logger.info(f"Successfully extracted {file_size_mb:.2f}MB to {tmpdir}")
        return zip_path
        
    except zipfile.BadZipFile as e:
        logger.error(f"Invalid zip file: {e}")
        raise HTTPException(
            status_code=400,
            detail="Invalid zip file format"
        )
    except Exception as e:
        logger.error(f"Failed to extract zip file: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to extract zip file: {str(e)}"
        )


# ============================================================================
# LLM INTEGRATION
# ============================================================================

def get_llm_with_fallback(preferred_provider: str = "groq") -> Any:
    """
    Get LLM instance with automatic fallback to ollama.
    
    Centralizes LLM initialization pattern used across multiple endpoints.
    Tries the preferred provider first, automatically falls back to ollama
    if initialization fails (e.g., API key missing, service unreachable).
    
    Args:
        preferred_provider: Preferred LLM provider (default: "groq")
        
    Returns:
        LLM instance from LLMFactory
        
    Example:
        >>> llm = get_llm_with_fallback("groq")
        >>> response = llm.invoke("What is 2+2?")
    """
    try:
        from llm_factory import LLMFactory
        llm = LLMFactory.create_llm(provider=preferred_provider)
        logger.info(f"Using LLM provider: {preferred_provider}")
        return llm
    except Exception as e:
        logger.warning(
            f"Failed to initialize {preferred_provider} provider: {e}. "
            f"Falling back to ollama."
        )
        from llm_factory import LLMFactory
        return LLMFactory.create_llm(provider="ollama")


from utils.json_utils import parse_llm_json_response


# ============================================================================
# FORM DATA PARSING
# ============================================================================

def parse_form_bool(value: Any, default: bool = False) -> bool:
    """
    Safely parse boolean from form data.
    
    Handles various string representations of booleans that can come from
    HTML form submissions (checkboxes, radio buttons, etc.).
    
    Args:
        value: Form value (can be str, bool, None)
        default: Default value if parsing fails
        
    Returns:
        Parsed boolean value
        
    Example:
        >>> parse_form_bool("true")
        True
        >>> parse_form_bool("1")
        True
        >>> parse_form_bool(None, default=False)
        False
    """
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ('true', '1', 'yes', 'on')
    return default
