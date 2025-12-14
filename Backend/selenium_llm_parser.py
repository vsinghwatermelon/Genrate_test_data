import re
import json
from typing import Tuple, List, Optional

from llm_factory import LLMFactory
from data_generator import TestDataGenerator



def parse_selenium_script(script_text: str, provider: str = "ollama", model_name: str = None) -> Tuple[List[dict], Optional[str]]:

    script_text = script_text or ''
    # Only pass model_name for Ollama; Groq uses model from .env
    if provider == "ollama":
        llm = LLMFactory.create_llm(provider=provider, model_name=model_name or "llama3:latest", temperature=0.0)
    else:
        llm = LLMFactory.create_llm(provider=provider, temperature=0.0)
    # Stronger, more explicit prompt to handle extracted values and contextual information.
    parse_prompt = (
        """You are an expert parser assistant. You will receive EXTRACTED FIELD VALUES from a Selenium form automation script, along with optional contextual information (labels, tab sections).

Your task: Analyze each extracted value and infer the form field's name, type, and other properties.

Return ONLY a valid, properly escaped JSON array. Each item must be an object with keys exactly: name (snake_case), type (one of string,email,phone,pan,ifsc,account_number,postal_code,city,state,address,number,date), rules (short string or empty), description (one-sentence), example (realistic example), confidence (float 0.0-1.0).

CRITICAL JSON FORMATTING RULES:
- Output MUST be valid JSON that can be parsed by standard JSON parsers
- All string values MUST be properly quoted with double quotes
- All special characters in strings MUST be properly escaped (e.g., URLs, newlines, quotes)
- URLs must be complete with proper quotes: "example": "https://example.com/"
- NO control characters (ASCII < 32) except spaces, tabs, newlines in proper JSON format
- Ensure ALL JSON string values are closed with matching quotes before the next field
- Each field must be complete: "example": "complete_value_here" (not truncated)
- Test that your output is valid JSON before returning it

INFERENCE RULES - Analyze each value to determine field type and name:
- Email pattern (contains @): type=email, name=email
- Phone pattern (10+ digits): type=phone, name=phone
- PAN pattern (5 letters + 4 digits + 1 letter, 10 chars): type=pan, name=pan
- IFSC pattern (4 letters + 0 + 6 alphanumeric, 11 chars): type=ifsc, name=ifsc
- Account number (8+ digits, not PAN/IFSC): type=account_number, name=account_number
- Postal/ZIP code (6 consecutive digits): type=postal_code, name=postal_code
- Date patterns (DD/MM/YYYY, YYYY-MM-DD, etc.): type=date, name=date or date_of_birth
- Address (contains street indicators: Lane, St, Road, Apt, #, comma-separated): type=address, name=address
- Currency/Amount (digits with commas, currency symbols): type=number, name=amount
- City names (common city names): type=city, name=city
- State names (common state names/abbreviations): type=state, name=state
- Names in sequence: first value -> first_name, second value -> last_name
- Generic text: type=string, infer name from context or use descriptive name

CONTEXTUAL HINTS:
- If labels are provided, use them to refine field names (e.g., "Contact Email" -> email)
- If tab sections are mentioned, use them to add context to descriptions
- Use the order of values to infer related fields (e.g., first_name followed by last_name)

CONFIDENCE SCORING:
- 0.95+ for exact pattern matches (email @, PAN/IFSC pattern, explicit phone digits)
- 0.85-0.90 for strong contextual matches (label hints, clear address/city patterns)
- 0.70-0.80 for reasonable inference from value patterns
- 0.50-0.65 for generic strings with minimal context

NAMING CONVENTIONS:
- Use snake_case for all field names
- Use canonical names: email, phone, first_name, last_name, date_of_birth, postal_code, city, state, address, amount, pan, ifsc, account_number
- Keep names short and descriptive

FEW-SHOT EXAMPLES:

Example A - Email value:
Input:
1. user@example.com
Output:
[{
  "name": "email",
  "type": "email",
  "rules": "",
  "description": "Email address for contact or login.",
  "example": "user@example.com",
  "confidence": 0.98
}]

Example B - Name sequence:
Input:
1. John
2. Doe
Output:
[{
  "name": "first_name",
  "type": "string",
  "rules": "",
  "description": "Person's first name.",
  "example": "John",
  "confidence": 0.80
}, {
  "name": "last_name",
  "type": "string",
  "rules": "",
  "description": "Person's last name.",
  "example": "Doe",
  "confidence": 0.80
}]

Example C - Financial data:
Input:
1. 100,000
2. 123, jane lane
3. 9898988787
4. ABCDE1234F
5. HDFC0001234
Output:
[{
  "name": "amount",
  "type": "number",
  "rules": "numeric/currency",
  "description": "Transaction or account amount.",
  "example": "100,000",
  "confidence": 0.88
}, {
  "name": "address",
  "type": "address",
  "rules": "",
  "description": "Full street address.",
  "example": "123, jane lane",
  "confidence": 0.90
}, {
  "name": "phone",
  "type": "phone",
  "rules": "10 digits",
  "description": "Contact phone number.",
  "example": "9898988787",
  "confidence": 0.95
}, {
  "name": "pan",
  "type": "pan",
  "rules": "10 chars: 5 letters + 4 digits + 1 letter",
  "description": "PAN card number.",
  "example": "ABCDE1234F",
  "confidence": 0.98
}, {
  "name": "ifsc",
  "type": "ifsc",
  "rules": "11 chars: 4 letters + 0 + 6 alphanumeric",
  "description": "Bank IFSC code.",
  "example": "HDFC0001234",
  "confidence": 0.98
}]

Example D - With contextual labels:
Input:
1. alice@company.com
2. New York
Additional context:
Labels found: Contact Email, City

Output:
[{
  "name": "email",
  "type": "email",
  "rules": "",
  "description": "Contact email address.",
  "example": "alice@company.com",
  "confidence": 0.95
}, {
  "name": "city",
  "type": "city",
  "rules": "",
  "description": "City name.",
  "example": "New York",
  "confidence": 0.92
}]

IMPORTANT REMINDER: Your output must be ONLY a valid JSON array with properly escaped strings. Ensure all URLs, descriptions, and examples are complete and properly quoted. No control characters, no truncated values.

Now analyze the following extracted values and return the JSON array only:

""" + script_text
    )

    try:
      resp = llm.invoke(parse_prompt)

      # Assemble NDJSON stream if present (Ollama streams many small JSON objects).
      assembled = ''
      try:
        for line in (resp or '').splitlines():
          line = line.strip()
          if not line:
            continue
          try:
            obj = json.loads(line)
            if isinstance(obj, dict) and 'response' in obj:
              assembled += obj['response']
          except Exception:
            # not a JSON line, ignore
            continue
      except Exception:
        assembled = ''

      source_text = assembled if assembled else (resp or '')

      def _extract_first_json_array(text: str) -> Optional[str]:
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
                return text[start:i+1]
          i += 1
        return None

      json_str = _extract_first_json_array(source_text)
      if not json_str:
        # fallback to naive regex on raw resp
        m = re.search(r'\[.*\]', resp, re.DOTALL)
        if m:
          json_str = m.group(0)
        else:
          json_str = source_text.strip()

      # Clean and attempt to parse
      cleaner = TestDataGenerator()
      json_str = cleaner._clean_json_response(json_str)
      
      import re
      
      # Step 1: Remove all control characters (ASCII < 32 except \n, \r, \t)
      cleaned_chars = []
      for char in json_str:
        code = ord(char)
        if code >= 32 or char in '\n\r\t':
          cleaned_chars.append(char)
      json_str = ''.join(cleaned_chars)
      
      # Step 2: Fix the specific broken pattern from Groq
      # Pattern: "example": "https: "confidence" (missing closing quote, comma, and rest of URL)
      # This happens when control char truncates the string value
      # Look for: ": "text without closing quote before next field
      
      # Find all occurrences of incomplete string values
      # Pattern: ": "[^"]*" "[a-z_]+" where the second quote should be comma+quote
      json_str = re.sub(
        r'(:\s*"[^"]*)\s+"([a-z_]+)"\s*:',  # Match: : "value" "nextkey" :
        r'\1", "\2":',                        # Replace with: : "value", "nextkey":
        json_str
      )
      
      # Step 3: Normalize whitespace
      json_str = re.sub(r'  +', ' ', json_str)

      try:
        # Try with strict=False first to be more lenient
        parsed = json.loads(json_str, strict=False)
      except json.JSONDecodeError as e:
        print(f"JSON parse failed at position {e.pos}: {e.msg}")
        error_start = max(0, e.pos - 100)
        error_end = min(len(json_str), e.pos + 100)
        print(f"Problematic JSON section: {json_str[error_start:error_end]}")
        
        # Try to repair common issues
        try:
          # Replace any remaining problematic patterns
          repaired = json_str
          
          # Fix incomplete string values before field names
          # Pattern: "value" "field": should be "value", "field":
          repaired = re.sub(r'"\s+"([a-z_]+)":\s*', r'", "\1": ', repaired)
          
          # Try parsing repaired version
          parsed = json.loads(repaired, strict=False)
          print("✓ Parsed successfully after repair")
        except Exception as repair_error:
          # Show detailed error context
          snippet = (source_text or '')[:2000]
          error_context = json_str[max(0, e.pos - 50):min(len(json_str), e.pos + 50)]
          return [], f"Failed to JSON-decode parser output: {str(e)}\nError context: ...{error_context}...\nRaw snippet: {snippet}"
      except Exception as e:
        snippet = (source_text or '')[:1500]
        return [], f"Failed to JSON-decode parser output: {str(e)}\nRaw snippet:\n{snippet}"

      if not isinstance(parsed, list):
        parsed = [parsed]

      normalized = []
      for item in parsed:
        if not isinstance(item, dict):
          continue
        normalized.append({
          'name': item.get('name', '').strip(),
          'type': item.get('type', 'string'),
          'rules': item.get('rules', '') or '',
          'description': item.get('description', '') or '',
          'example': item.get('example', '') or '',
          'confidence': float(item.get('confidence', 0.0))
        })

      if not normalized:
        snippet = (source_text or '')[:1500]
        return [], f"No fields parsed from LLM output. Raw LLM snippet:\n{snippet}"

      return normalized, None
    except Exception as e:
      return [], f"LLM parsing failed: {str(e)}"