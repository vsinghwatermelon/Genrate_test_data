"""
JSON Utilities Module

Provides robust JSON parsing, cleaning, and repair functions
for handling LLM responses that may have formatting issues.
"""

import json
import re
import gzip
import base64
from typing import Optional, List, Dict, Any, Union, Tuple, Set

# Constants
MAX_REPAIR_ATTEMPTS = 5  # Maximum number of repair attempts
MAX_JSON_LENGTH = 1000000  # Maximum JSON string length to process (1MB)
MAX_PREVIEW_LENGTH = 500  # Maximum length for error previews
DEFAULT_TIMEOUT = 30  # Default timeout for parsing operations
MAX_NESTING_DEPTH = 50  # Maximum nesting depth for JSON structures

class JSONCleaner:
    """Utility class for cleaning and repairing JSON responses from LLMs."""

    @staticmethod
    def remove_control_characters(text: str) -> str:
        """
        Remove control characters that break JSON parsing.
        Keeps printable characters, newlines, tabs, and carriage returns.
        """
        cleaned = []
        for char in text:
            code = ord(char)
            if code >= 32 or char in '\n\r\t':
                cleaned.append(char)
            else:
                cleaned.append(' ')
        return ''.join(cleaned)

    @staticmethod
    def remove_markdown_code_blocks(text: str) -> str:
        """Remove markdown code block markers."""
        # Remove ```json and ``` markers
        text = re.sub(r'^```json\s*\n?', '', text, flags=re.MULTILINE | re.IGNORECASE)
        text = re.sub(r'^```\s*\n?', '', text, flags=re.MULTILINE)
        text = re.sub(r'\n?```\s*$', '', text)
        return text

    @staticmethod
    def remove_comments(text: str) -> str:
        """Remove JavaScript-style comments from JSON."""
        # Remove single-line comments
        text = re.sub(r'//.*$', '', text, flags=re.MULTILINE)
        # Remove multi-line comments
        text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
        return text

    @staticmethod
    def fix_double_brackets(text: str) -> str:
        """Fix accidental double brackets."""
        text = re.sub(r'^\s*\[\s*\[', '[', text)
        text = re.sub(r'\]\s*\]\s*$', ']', text)
        return text

    @staticmethod
    def fix_trailing_commas(text: str) -> str:
        """Remove trailing commas before closing brackets."""
        text = re.sub(r',(\s*\])', r'\1', text)
        text = re.sub(r',(\s*\})', r'\1', text)
        return text

    @staticmethod
    def fix_escaped_quotes(text: str) -> str:
        """Fix incorrectly escaped quotes."""
        # JSON doesn't require escaping single quotes
        text = text.replace("\\'", "'")
        return text

    @staticmethod
    def remove_null_tokens(text: str) -> str:
        """Remove standalone null tokens that appear as array elements."""
        text = re.sub(r',\s*null\s*,', ',', text)
        text = re.sub(r',\s*null\s*\}', '}', text)
        text = re.sub(r'\{\s*null\s*,', '{', text)
        text = re.sub(r'\[\s*null\s*,', '[', text)
        text = re.sub(r',\s*null\s*\]', ']', text)
        return text

    @staticmethod
    def collapse_multiple_commas(text: str) -> str:
        """Collapse accidental multiple commas."""
        return re.sub(r',\s*,+', ',', text)

    @staticmethod
    def fix_python_literals(text: str) -> str:
        """Convert Python literals to JSON equivalents."""
        text = re.sub(r'\bTrue\b', 'true', text)
        text = re.sub(r'\bFalse\b', 'false', text)
        text = re.sub(r'\bNone\b', 'null', text)
        return text

    @staticmethod
    def fix_single_quotes(text: str) -> str:
        """
        Attempt to convert single-quoted strings to double-quoted.
        Only for simple key patterns to avoid breaking apostrophes.
        """
        text = re.sub(r"(?<=[{,\s])'([^']+?)'\s*:\s*", r'"\1": ', text)
        return text

    @staticmethod
    def remove_blank_lines(text: str) -> str:
        """Remove blank lines from JSON."""
        return '\n'.join(line for line in text.splitlines() if line.strip())

    @classmethod
    def clean(cls, text: str) -> str:
        """
        Apply all cleaning operations to a JSON string.

        Args:
            text: Raw JSON string from LLM

        Returns:
            Cleaned JSON string
        """
        if not text:
            return text

        # Apply all cleaning steps in order
        text = cls.remove_control_characters(text)
        text = cls.remove_markdown_code_blocks(text)
        text = cls.fix_double_brackets(text)
        text = cls.remove_comments(text)
        text = cls.fix_trailing_commas(text)
        text = cls.fix_escaped_quotes(text)
        text = cls.remove_null_tokens(text)
        text = cls.collapse_multiple_commas(text)
        text = cls.remove_blank_lines(text)

        return text

    @classmethod
    def repair(cls, text: str) -> str:
        """
        Apply aggressive repair operations for heavily malformed JSON.

        Args:
            text: Cleaned but still invalid JSON string

        Returns:
            Repaired JSON string
        """
        text = cls.fix_python_literals(text)
        text = cls.fix_single_quotes(text)
        text = cls.fix_missing_commas(text)
        text = cls.fix_unquoted_keys(text)
        text = cls.collapse_multiple_commas(text)
        text = cls.fix_trailing_commas(text)
        return text

    @staticmethod
    def fix_missing_commas(text: str) -> str:
        """
        Fix missing commas between JSON elements.
        Common LLM error: }\n{ instead of },\n{
        """
        # Fix missing comma between objects: } { -> }, {
        text = re.sub(r'\}\s*\{', '}, {', text)

        # Fix missing comma between objects in array: }\n  { -> },\n  {
        text = re.sub(r'\}(\s*\n\s*)\{', r'},\1{', text)

        # Fix missing comma after string value before next key: "value" "key" -> "value", "key"
        text = re.sub(r'(")\s*\n\s*(")', r'\1,\n\2', text)

        # Fix missing comma between array elements
        text = re.sub(r'\](\s*\n\s*)\[', r'],\1[', text)

        # Fix missing comma after number before next key
        text = re.sub(r'(\d)\s*\n\s*(")', r'\1,\n\2', text)

        # Fix missing comma after true/false/null before next key
        text = re.sub(r'(true|false|null)\s*\n\s*(")', r'\1,\n\2', text)

        return text

    @staticmethod
    def fix_unquoted_keys(text: str) -> str:
        """Fix unquoted keys in JSON objects."""
        # Match unquoted keys: { key: or , key:
        text = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', text)
        return text

    @classmethod
    def deep_repair(cls, text: str) -> str:
        """
        Perform deep repair on heavily malformed JSON.
        This is a last resort when standard repair fails.

        Args:
            text: Malformed JSON string

        Returns:
            Repaired JSON string
        """
        # First apply standard repairs
        text = cls.repair(text)

        # Try to extract individual objects and rebuild array
        objects = []
        current_obj = ""
        brace_count = 0
        in_string = False
        escape = False

        for char in text:
            if in_string:
                if escape:
                    escape = False
                elif char == '\\':
                    escape = True
                elif char == '"':
                    in_string = False
                current_obj += char
            else:
                if char == '"':
                    in_string = True
                    current_obj += char
                elif char == '{':
                    brace_count += 1
                    current_obj += char
                elif char == '}':
                    brace_count -= 1
                    current_obj += char
                    if brace_count == 0 and current_obj.strip():
                        # Try to parse this object
                        try:
                            obj = json.loads(current_obj)
                            objects.append(obj)
                        except json.JSONDecodeError:
                            pass
                        current_obj = ""
                elif brace_count > 0:
                    current_obj += char

        if objects:
            return json.dumps(objects)

        return text

class JSONExtractor:
    """Utility class for extracting JSON from mixed text responses."""

    @staticmethod
    def extract_first_array(text: str) -> Optional[str]:
        """
        Extract the first balanced JSON array from text.
        Handles quoted strings and escapes properly.

        Args:
            text: Text potentially containing a JSON array

        Returns:
            The extracted JSON array string, or None if not found
        """
        if not text:
            return None

        start = text.find('[')
        if start == -1:
            return None

        i = start
        depth = 0
        in_str = False
        escape = False

        while i < len(text):
            ch = text[i]
            if in_str:
                if escape:
                    escape = False
                elif ch == '\\':
                    escape = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == '[':
                    depth += 1
                elif ch == ']':
                    depth -= 1
                    if depth == 0:
                        return text[start:i + 1]
            i += 1

        return None

    @staticmethod
    def extract_first_object(text: str) -> Optional[str]:
        """
        Extract the first balanced JSON object from text.

        Args:
            text: Text potentially containing a JSON object

        Returns:
            The extracted JSON object string, or None if not found
        """
        if not text:
            return None

        start = text.find('{')
        if start == -1:
            return None

        i = start
        depth = 0
        in_str = False
        escape = False

        while i < len(text):
            ch = text[i]
            if in_str:
                if escape:
                    escape = False
                elif ch == '\\':
                    escape = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        return text[start:i + 1]
            i += 1

        return None

    @staticmethod
    def fix_truncated_array(text: str) -> str:
        """
        Attempt to fix a truncated JSON array.

        Args:
            text: Potentially truncated JSON array

        Returns:
            Fixed JSON array
        """
        if not text:
            return text

        # Find array start
        start = text.find('[')
        if start == -1:
            return text

        incomplete = text[start:]

        # Check if we have more opens than closes
        open_braces = incomplete.count('{') - incomplete.count('}')
        open_brackets = incomplete.count('[') - incomplete.count(']')

        if open_braces > 0 or open_brackets > 0:
            # Truncate at last complete object
            last_complete = incomplete.rfind('},')
            if last_complete > 0:
                incomplete = incomplete[:last_complete + 1]
            elif incomplete.rfind('}') > incomplete.rfind('{'):
                pass  # Already ends at a complete object
            else:
                # Remove incomplete object
                last_brace = incomplete.rfind('{')
                if last_brace > 0:
                    incomplete = incomplete[:last_brace].rstrip(',').rstrip()

            # Ensure proper closing
            if not incomplete.rstrip().endswith(']'):
                incomplete = incomplete.rstrip(',').rstrip() + '\n]'

        return incomplete

    @classmethod
    def extract_json(cls, text: str, expect_array: bool = True) -> Optional[str]:
        """
        Extract JSON from text, with fallback to regex if balanced extraction fails.

        Args:
            text: Text containing JSON
            expect_array: Whether to expect an array (vs object)

        Returns:
            Extracted JSON string
        """
        if expect_array:
            result = cls.extract_first_array(text)
            if not result:
                # Fallback to regex
                match = re.search(r'\[.*\]', text, re.DOTALL)
                if match:
                    result = match.group(0)
                else:
                    # Try to fix truncated array
                    result = cls.fix_truncated_array(text)
        else:
            result = cls.extract_first_object(text)
            if not result:
                match = re.search(r'\{.*\}', text, re.DOTALL)
                if match:
                    result = match.group(0)

        return result

class NDJSONParser:
    """Parser for Newline-Delimited JSON (Ollama streaming format)."""

    @staticmethod
    def parse(text: str) -> str:
        """
        Parse NDJSON stream and assemble response content.

        Ollama streams responses as multiple JSON objects, each with a 'response' field.
        This method assembles them into a single string.

        Args:
            text: NDJSON stream text

        Returns:
            Assembled response content
        """
        assembled = []

        if not text:
            return ''

        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue

            try:
                obj = json.loads(line)
                if isinstance(obj, dict) and 'response' in obj:
                    assembled.append(obj['response'])
            except (json.JSONDecodeError, ValueError):
                continue

        return ''.join(assembled)

def parse_llm_json_response(
    response: str,
    expect_array: bool = True
) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Parse JSON from an LLM response with comprehensive error handling.

    Args:
        response: Raw LLM response text
        expect_array: Whether to expect a JSON array (vs object)

    Returns:
        Parsed JSON data

    Raises:
        ValueError: If JSON cannot be parsed after all repair attempts
    """
    if not response:
        raise ValueError("Empty response from LLM")

    # Try to parse NDJSON (Ollama format)
    assembled = NDJSONParser.parse(response)
    source_text = assembled if assembled else response

    # Extract JSON
    json_str = JSONExtractor.extract_json(source_text, expect_array)
    if not json_str:
        json_str = source_text

    # Clean JSON
    json_str = JSONCleaner.clean(json_str)

    # Try to parse
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass

    # Try with repairs
    repaired = JSONCleaner.repair(json_str)
    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass

    # Try deep repair as last resort
    try:
        deep_repaired = JSONCleaner.deep_repair(json_str)
        return json.loads(deep_repaired)
    except json.JSONDecodeError as e:
        # Include context in error
        error_context = json_str[max(0, e.pos - 100):min(len(json_str), e.pos + 100)]
        raise ValueError(
            f"Failed to parse JSON: {e.msg} at position {e.pos}\n"
            f"Context: ...{error_context}..."
        )


def make_json_serializable(obj: Any) -> Any:
    """
    Convert non-JSON-serializable objects to JSON-compatible types.
    
    Handles complex nested structures and various data types:
    - bytes: Attempts gzip decompression, UTF-8 decoding, JSON parsing, or base64 encoding
    - dict: Recursively converts all values
    - list: Recursively converts all items
    - tuple: Converts to list of serializable items
    - set: Converts to list of serializable items
    
    Args:
        obj: Object to convert (can be any type)
        
    Returns:
        JSON-serializable version of the object
    """
    if isinstance(obj, bytes):
        return _serialize_bytes(obj)
    elif isinstance(obj, dict):
        return {k: make_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [make_json_serializable(i) for i in obj]
    elif isinstance(obj, (tuple, set)):
        return [make_json_serializable(i) for i in obj]
    else:
        return obj


def _serialize_bytes(data: bytes) -> Union[str, Dict, List]:
    """
    Serialize bytes to string using best available method.
    
    Attempts multiple strategies in order:
    1. Gzip decompression (if gzip magic bytes detected)
    2. UTF-8 decoding
    3. JSON parsing (if decoded string looks like JSON)
    4. Base64 encoding (fallback for binary data)
    """
    # Strategy 1: Check for gzip compression (magic bytes: 0x1f 0x8b)
    if len(data) > 2 and data[0:2] == b'\x1f\x8b':
        try:
            data = gzip.decompress(data)
        except Exception:
            pass
    
    # Strategy 2: Try UTF-8 decoding
    try:
        decoded = data.decode('utf-8')
        
        # Strategy 3: If it looks like JSON, parse it
        if decoded.strip().startswith(('{', '[')):
            try:
                return json.loads(decoded)
            except json.JSONDecodeError:
                pass
        
        return decoded
        
    except UnicodeDecodeError:
        # Strategy 4: Base64 encoding for binary data
        b64 = base64.b64encode(data).decode('ascii')
        
        # Truncate if too long for readability
        if len(b64) > 200:
            return f"[Binary: {len(data)} bytes, base64 preview: {b64[:200]}...]"
        
        return f"[Binary: {len(data)} bytes, base64: {b64}]"
