"""Minimal Ollama wrapper used by TestDataGenerator.

Provides an `OllamaLLM` class with a simple `invoke(prompt: str) -> str`
method that posts to a local Ollama HTTP server (default `http://127.0.0.1:11434`).

The implementation is defensive: it handles JSON and streaming NDJSON responses
from Ollama and returns the concatenated text content.
"""
import logging
import json
try:
    import requests
except Exception:  # pragma: no cover
    requests = None
from typing import Optional, List, Dict, Any

from utils.logger import get_logger

# Constants
DEFAULT_OLLAMA_MODEL = "llama3:latest"
DEFAULT_OLLAMA_HOST = "http://127.0.0.1:11434"
DEFAULT_INVOKE_TIMEOUT = 300.0
DEFAULT_POST_TIMEOUT = 11300.0
MAX_SNIPPET_LENGTH = 1000

logger = get_logger(__name__)

class OllamaError(Exception):
    """Exception raised for errors in the Ollama LLM wrapper."""
    pass

class OllamaLLM:
    """
    Minimal Ollama wrapper providing a simple invoke interface.
    
    Handles both non-streamed JSON and streamed NDJSON responses
    from local Ollama instances.
    """
    
    def __init__(
        self, 
        model: str = DEFAULT_OLLAMA_MODEL, 
        temperature: float = 0.7, 
        host: str = DEFAULT_OLLAMA_HOST
    ):
        """
        Initialize the Ollama LLM client.
        
        Args:
            model: Name of the model to use
            temperature: Sampling temperature
            host: Ollama server base URL
        """
        self.model = model
        self.temperature = temperature
        self.host = host.rstrip('/')
        logger.info(f"OllamaLLM initialized with model={model}, host={host}")

    def _post_generate(self, prompt: str, timeout: float = DEFAULT_POST_TIMEOUT) -> requests.Response:
        """
        Send a POST request to Ollama's generation endpoint.
        
        Args:
            prompt: Thinking/generation prompt
            timeout: Request timeout in seconds
            
        Returns:
            requests.Response object
        """
        url = f"{self.host}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "temperature": float(self.temperature)
        }

        if requests is None:
            raise OllamaError(
                "Python package 'requests' is required for OllamaLLM. "
                "Install it: 'pip install requests'"
            )

        try:
            # Use stream=True to support NDJSON/streaming responses
            return requests.post(url, json=payload, stream=True, timeout=timeout)
        except Exception as e:
            logger.error(f"Ollama connection failure at {url}: {e}")
            raise OllamaError(f"Failed to connect to Ollama at {url}: {e}")

    def _extract_strings_from_object(self, obj: Any) -> List[str]:
        """
        Recursively extract all string values from a JSON-like object.
        
        Args:
            obj: Scalar, dict, or list to extract strings from
            
        Returns:
            List of extracted strings
        """
        if isinstance(obj, str):
            return [obj]
        if isinstance(obj, dict):
            parts = []
            for v in obj.values():
                parts.extend(self._extract_strings_from_object(v))
            return parts
        if isinstance(obj, list):
            parts = []
            for v in obj:
                parts.extend(self._extract_strings_from_object(v))
            return parts
        return []

    def _find_first_json_array(self, text: str) -> Optional[str]:
        """
        Find the first balanced JSON array in a string.
        
        Handles brackets inside strings and escaped characters.
        
        Args:
            text: Text to search in
            
        Returns:
            The first balanced JSON array string, or None if not found
        """
        start_idx = None
        in_string = False
        is_escaped = False
        bracket_depth = 0
        
        for i, char in enumerate(text):
            if start_idx is None:
                if char == '[':
                    start_idx = i
                    bracket_depth = 1
            else:
                if is_escaped:
                    is_escaped = False
                    continue
                if char == '\\':
                    is_escaped = True
                    continue
                if char == '"':
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if char == '[':
                    bracket_depth += 1
                elif char == ']':
                    bracket_depth -= 1
                    if bracket_depth == 0:
                        return text[start_idx:i+1]
        return None

    def _process_json_line(self, line: str, text_parts: List[str]) -> bool:
        """
        Process a single line of potential JSON from Ollama.
        
        Args:
            line: The line to process
            text_parts: List to append extracted text to
            
        Returns:
            True if JSON was successfully processed, False otherwise
        """
        try:
            obj = json.loads(line)
        except Exception:
            # Not a JSON object, might be a text chunk
            text_parts.append(line)
            return False

        # Known text fields in Ollama and other common LLM responses
        for key in ('token', 'text', 'content', 'output', 'response'):
            val = obj.get(key)
            if isinstance(val, str):
                text_parts.append(val)
                return True
        
        # Fallback: extract any strings found in the object
        strings = self._extract_strings_from_object(obj)
        if strings:
            text_parts.append(''.join(strings))
            return True
            
        return False

    def invoke(self, prompt: str, timeout: Optional[float] = None) -> str:
        """
        Send prompt to Ollama and return the aggregated response text.
        
        Args:
            prompt: Prompt to send
            timeout: Request timeout in seconds
            
        Returns:
            Aggregated response text
        """
        invoke_timeout = timeout or DEFAULT_INVOKE_TIMEOUT
        resp = self._post_generate(prompt, timeout=invoke_timeout)

        if resp.status_code != 200:
            error_content = resp.text
            try:
                error_content = resp.json()
            except Exception:
                pass
            logger.error(f"Ollama error: status={resp.status_code}, content={error_content}")
            raise OllamaError(f"Ollama returned status {resp.status_code}: {error_content}")

        text_parts = []
        
        # Attempt to process response text as multi-line JSON/NDJSON if already available
        full_text = getattr(resp, 'text', '')
        if full_text:
            for line in full_text.splitlines():
                clean_line = line.strip()
                if clean_line:
                    self._process_json_line(clean_line, text_parts)

        # If no parts could be extracted from static text, try streaming
        if not text_parts:
            try:
                for raw_line in resp.iter_lines(decode_unicode=True):
                    if raw_line:
                        self._process_json_line(raw_line.strip(), text_parts)
            except Exception as e:
                logger.warning(f"Error during streaming response processing: {e}")
                # Fallback to whatever text we got if any
                if full_text:
                    return full_text
                raise OllamaError(f"Failed to read response: {e}")

        result = ''.join(text_parts).strip()
        
        if not result:
            snippet = (full_text or '')[:500]
            logger.error(f"Empty response from Ollama. Snippet: {snippet!r}")
            raise OllamaError(
                f"Empty response from Ollama. Check server logs. Snippet: {snippet!r}"
            )

        # Post-process: Ollama often embeds JSON arrays inside the text response
        try:
            json_array = self._find_first_json_array(result)
            if json_array:
                return json_array
        except Exception as e:
            logger.debug(f"Failed to extract JSON array from result: {e}")

        return result


if __name__ == '__main__':
    # Quick smoke test when run directly
    client = OllamaLLM()
    try:
        print(client.invoke("Say hello"))
    except Exception as e:
        print("OllamaLLM error:", e)
