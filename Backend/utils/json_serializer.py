"""
JSON serialization utilities for non-standard types.

Handles complex data type conversions including:
- Bytes with gzip decompression
- UTF-8/Latin-1 decoding
- Base64 encoding for binary data
- Recursive structure handling
"""
import json
import gzip
import base64
import logging
from typing import Any, Union, Dict, List, Tuple, Set

logger = logging.getLogger(__name__)


def make_json_serializable(obj: Any) -> Any:
    """
    Convert non-JSON-serializable objects to JSON-compatible types.
    
    Handles complex nested structures and various data types:
    - bytes: Attempts gzip decompression, UTF-8 decoding, JSON parsing, or base64 encoding
    - dict: Recursively converts all values
    - list: Recursively converts all items
    - tuple: Converts to tuple of serializable items
    - set: Converts to list of serializable items
    
    Args:
        obj: Object to convert (can be any type)
        
    Returns:
        JSON-serializable version of the object
        
    Example:
        >>> data = {"key": b'{"nested": "json"}', "list": [1, 2, {3, 4}]}
        >>> serialized = make_json_serializable(data)
        >>> json.dumps(serialized)  # Now works!
    """
    if isinstance(obj, bytes):
        return _serialize_bytes(obj)
    elif isinstance(obj, dict):
        return {k: make_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [make_json_serializable(i) for i in obj]
    elif isinstance(obj, tuple):
        return tuple(make_json_serializable(i) for i in obj)
    elif isinstance(obj, set):
        return [make_json_serializable(i) for i in obj]
    else:
        return obj


def _serialize_bytes(data: bytes) -> Union[str, Dict, List]:
    """
    Serialize bytes to string using best available method.
    
    Attempts multiple strategies in order:
    1. Gzip decompression (if gzip magic bytes 0x1f 0x8b detected)
    2. UTF-8 decoding
    3. JSON parsing (if decoded string looks like JSON)
    4. Base64 encoding (fallback for binary data)
    
    Args:
        data: Bytes to serialize
        
    Returns:
        Serialized representation (string, dict, or list)
    """
    # Strategy 1: Check for gzip compression (magic bytes: 0x1f 0x8b)
    if len(data) > 2 and data[0:2] == b'\x1f\x8b':
        try:
            data = gzip.decompress(data)
            logger.debug(f"Decompressed gzip data ({len(data)} bytes)")
        except Exception as e:
            logger.warning(f"Failed to decompress gzip data: {e}")
            # Continue with original data
    
    # Strategy 2: Try UTF-8 decoding
    try:
        decoded = data.decode('utf-8')
        
        # Strategy 3: If it looks like JSON, parse it
        if decoded.strip().startswith(('{', '[')):
            try:
                parsed = json.loads(decoded)
                logger.debug("Successfully parsed bytes as JSON")
                return parsed
            except json.JSONDecodeError:
                logger.debug("Bytes look like JSON but failed to parse")
                # Return as string instead
        
        return decoded
        
    except UnicodeDecodeError:
        logger.debug(f"Binary data detected ({len(data)} bytes), using base64 encoding")
        
        # Strategy 4: Base64 encoding for binary data
        b64 = base64.b64encode(data).decode('ascii')
        
        # Truncate if too long for readability
        if len(b64) > 200:
            return f"[Binary: {len(data)} bytes, base64 preview: {b64[:200]}...]"
        
        return f"[Binary: {len(data)} bytes, base64: {b64}]"
