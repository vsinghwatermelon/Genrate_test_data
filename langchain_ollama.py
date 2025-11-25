"""Minimal Ollama wrapper used by TestDataGenerator.

Provides an `OllamaLLM` class with a simple `invoke(prompt: str) -> str`
method that posts to a local Ollama HTTP server (default `http://127.0.0.1:11434`).

The implementation is defensive: it handles JSON and streaming NDJSON responses
from Ollama and returns the concatenated text content.
"""
from __future__ import annotations

import json
try:
    import requests
except Exception:  # pragma: no cover - helpful fallback message
    requests = None
from typing import Optional


class OllamaError(Exception):
    pass


class OllamaLLM:
    def __init__(self, model: str = "llama3:latest", temperature: float = 0.7, host: str = "http://127.0.0.1:11434"):
        self.model = model
        self.temperature = temperature
        self.host = host.rstrip('/')

    def _post_generate(self, prompt: str, timeout: Optional[float] = 11300.0):
        url = f"{self.host}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "temperature": float(self.temperature)
        }

        if requests is None:
            raise OllamaError(
                "Python package 'requests' is required for OllamaLLM. "
                "Install it in your virtualenv: 'pip install requests'"
            )

        try:
            # Use stream=True to support NDJSON/streaming responses from Ollama
            resp = requests.post(url, json=payload, stream=True, timeout=timeout)
        except Exception as e:
            raise OllamaError(f"Failed to connect to Ollama at {url}: {e}")

        if resp.status_code != 200:
            # Try to present helpful message
            content = None
            try:
                content = resp.json()
            except Exception:
                content = resp.text
            raise OllamaError(f"Ollama returned status {resp.status_code}: {content}")

        return resp

    def invoke(self, prompt: str, timeout: Optional[float] = None) -> str:
        """Send `prompt` to Ollama and return the aggregated text response.

        This attempts to handle both non-streamed JSON responses and streamed
        NDJSON responses produced by Ollama's `/api/generate`.
        """
        if timeout is None:
            timeout = 300.0
        resp = self._post_generate(prompt, timeout=timeout)

        # Debug: print raw response metadata + body snippet to help diagnose format issues
        try:
            status = getattr(resp, 'status_code', None)
            headers = getattr(resp, 'headers', {})
            # resp.text is safe to call even if stream=True
            full_text = resp.text if hasattr(resp, 'text') else ''
            snippet = (full_text or '')[:1000]
        except Exception:
            status = None
            headers = {}
            snippet = ''

        def _safe_print(s: str) -> None:
            try:
                print(s)
            except Exception:
                try:
                    print(s.encode('utf-8', errors='replace').decode('utf-8'))
                except Exception:
                    print(repr(s))

        _safe_print(f"[OLLAMA DEBUG] status={status} headers_keys={list(headers.keys())} body_snippet={snippet!r}")

        text_parts = []

        # If response content is already available as text (NDJSON or full body),
        # prefer parsing it first to collect streamed 'response' fields.
        raw_text = ''
        try:
            raw_text = resp.text or ''
        except Exception:
            raw_text = ''

        # Helper keys to look for inside JSON objects
        content_type = resp.headers.get('Content-Type', '')
        if raw_text:
            # Attempt to parse NDJSON lines or a single JSON body
            for raw_line in raw_text.splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    # Not a JSON object, treat as text chunk
                    text_parts.append(line)
                    continue

                for key in ('token', 'text', 'content', 'output', 'response'):
                    if key in obj:
                        val = obj.get(key)
                        if isinstance(val, str):
                            text_parts.append(val)
                            break
                else:
                    # extract any string values
                    def extract_strings(o):
                        if isinstance(o, str):
                            return [o]
                        if isinstance(o, dict):
                            s = []
                            for v in o.values():
                                s += extract_strings(v)
                            return s
                        if isinstance(o, list):
                            s = []
                            for v in o:
                                s += extract_strings(v)
                            return s
                        return []

                    strings = extract_strings(obj)
                    if strings:
                        text_parts.append(''.join(strings))

        # If we didn't get anything from raw_text, try streaming iteration
        if not text_parts:
            # Handle streaming/NDJSON: iterate lines and parse JSON objects
            try:
                for raw_line in resp.iter_lines(decode_unicode=True):
                    if not raw_line:
                        continue
                    line = raw_line.strip()
                    # Some streaming endpoints send plain text chunks
                    if line.startswith('{') and line.endswith('}'):
                        try:
                            obj = json.loads(line)
                        except Exception:
                            # Not a JSON object, treat as text
                            text_parts.append(line)
                            continue

                        # Look for common text fields
                        for key in ('token', 'text', 'content', 'output', 'response'):
                            if key in obj:
                                val = obj.get(key)
                                if isinstance(val, str):
                                    text_parts.append(val)
                                    break
                        else:
                            # obj may have a nested 'response' or 'choices'
                            def extract_strings(o):
                                if isinstance(o, str):
                                    return [o]
                                if isinstance(o, dict):
                                    s = []
                                    for v in o.values():
                                        s += extract_strings(v)
                                    return s
                                if isinstance(o, list):
                                    s = []
                                    for v in o:
                                        s += extract_strings(v)
                                    return s
                                return []

                            strings = extract_strings(obj)
                            if strings:
                                text_parts.append(''.join(strings))
                    else:
                        # Not JSON — treat as a text chunk
                        text_parts.append(line)
            except Exception:
                # Last fallback: return raw text
                try:
                    return raw_text
                except Exception as e:
                    raise OllamaError(f"Failed to read response: {e}")

        # Handle streaming/NDJSON: iterate lines and parse JSON objects
        try:
            for raw_line in resp.iter_lines(decode_unicode=True):
                if not raw_line:
                    continue
                line = raw_line.strip()
                # Some streaming endpoints send plain text chunks
                if line.startswith('{') and line.endswith('}'):
                    try:
                        obj = json.loads(line)
                    except Exception:
                        # Not a JSON object, treat as text
                        text_parts.append(line)
                        continue

                    # Look for common text fields
                    for key in ('token', 'text', 'content', 'output', 'response'):
                        if key in obj:
                            val = obj.get(key)
                            if isinstance(val, str):
                                text_parts.append(val)
                                break
                    else:
                        # obj may have a nested 'response' or 'choices'
                        # Try to extract any string values
                        def extract_strings(o):
                            if isinstance(o, str):
                                return [o]
                            if isinstance(o, dict):
                                s = []
                                for v in o.values():
                                    s += extract_strings(v)
                                return s
                            if isinstance(o, list):
                                s = []
                                for v in o:
                                    s += extract_strings(v)
                                return s
                            return []

                        strings = extract_strings(obj)
                        if strings:
                            text_parts.append(''.join(strings))
                else:
                    # Not JSON — treat as a text chunk
                    text_parts.append(line)
        except Exception:
            # Last fallback: return raw text
            try:
                return resp.text
            except Exception as e:
                raise OllamaError(f"Failed to read response: {e}")

        result = ''.join(text_parts).strip()

        # If the streamed response contains many NDJSON objects, it's common
        # for Ollama to stream JSON fragments where the actual JSON array is
        # embedded inside the concatenated 'response' fields. We'll try to
        # find the first balanced JSON array (handles brackets inside strings
        # and escaped characters) and return that substring.
        def _find_first_json_array(text: str) -> str | None:
            start = None
            in_str = False
            esc = False
            depth = 0
            for i, ch in enumerate(text):
                if start is None:
                    if ch == '[':
                        start = i
                        depth = 1
                        continue
                else:
                    if esc:
                        esc = False
                        continue
                    if ch == '\\':
                        esc = True
                        continue
                    if ch == '"':
                        in_str = not in_str
                        continue
                    if in_str:
                        continue
                    if ch == '[':
                        depth += 1
                        continue
                    if ch == ']':
                        depth -= 1
                        if depth == 0:
                            return text[start:i+1]
            return None

        try:
            arr = _find_first_json_array(result)
            if arr:
                return arr
        except Exception:
            pass

        # If streaming yielded nothing, try the full response text as a fallback
        if not result:
            try:
                full_text = resp.text
            except Exception:
                full_text = ''

            if full_text and full_text.strip():
                return full_text

            # Nothing meaningful returned by Ollama — raise a helpful error
            snippet = ''
            try:
                snippet = (resp.text or '')[:500]
            except Exception:
                snippet = ''
            raise OllamaError(
                "Empty response from Ollama. The server accepted the request but returned no text. "
                "Check the Ollama server logs for errors (model load failures, OOM, or runner crashes). "
                f"Response snippet: {snippet!r}"
            )

        return result


if __name__ == '__main__':
    # Quick smoke test when run directly
    client = OllamaLLM()
    try:
        print(client.invoke("Say hello"))
    except Exception as e:
        print("OllamaLLM error:", e)
