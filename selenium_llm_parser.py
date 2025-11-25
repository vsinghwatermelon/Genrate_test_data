import re
import json
from typing import Tuple, List, Optional

from langchain_ollama import OllamaLLM
from data_generator import TestDataGenerator



def parse_selenium_script(script_text: str) -> Tuple[List[dict], Optional[str]]:

    script_text = script_text or ''
    llm = OllamaLLM(model="llama3:latest", temperature=0.0)
    # Stronger, more explicit prompt to handle opaque IDs, label->input mapping, Tab sequences, and value-based inference.
    parse_prompt = (
        """You are an expert parser assistant. Given a Selenium-like script (Python or JS), extract all form fields the script interacts with (calls like driver.enter_text, driver.get_text).
Return ONLY a JSON array. Each item must be an object with keys exactly: name (snake_case), type (one of string,email,phone,pan,ifsc,account_number,postal_code,city,state,address,number,date), rules (short string or empty), description (one-sentence), example (realistic example), confidence (float 0.0-1.0).

General instructions and strong heuristics (use these to infer fields even when element IDs are opaque/random):
- Primary evidence: driver.enter_text('<id>', '<value>', ...). Use the written value to infer type and a sensible name.
- Label mapping: If you see driver.get_text(id) or (often on a label) immediately before an enter_text call (within the next 1-3 interactions), treat the label text as the field label for that enter_text.
- Tab-based mapping: If the script uses press_key('Tab') between enter_text calls, and there is no explicit label, map the two enter_texts as adjacent fields. Use value patterns and ordering to name them. Common sequence heuristics:
  - If first looks like a personal name and second looks like a surname, name them first_name and last_name (or first_name/last_name).
  - If a field value contains '@' -> email. If numeric >=10 digits -> phone. If 6 consecutive digits -> postal_code. If matches date formats -> date.
- switch_Tab or switch_Tab text: treat the visible tab title or switch target as contextual text that can indicate section or label meaning near subsequent inputs.
- If identifiers contain readable tokens (email, phone, name, dob, zip, addr, pan, ifsc, acct, amount), prefer those as the canonical field name (convert to snake_case).
- When only a value exists, infer name from value pattern or from nearby textual context (get_text, switch_Tab, surrounding comments).
- For addresses: values containing street tokens (Lane, St, Road, Apt, #, comma-separated address) -> address.
- For currency/amounts: values with commas and digits or currency symbols -> number.
- For PAN/IFSC/account_number: follow the patterns:
  - pan: 10-char Indian PAN pattern (5 letters + 4 digits + 1 letter) -> pan
  - ifsc: 11-char (4 letters + 0 + 6 alnum) -> ifsc
  - account_number: long numeric string (8+ digits) without IFSC/PAN pattern
- Confidence scoring rules:
  - 0.95+ for exact pattern matches or explicit identifier hints (email pattern, PAN, IFSC, explicit label token).
  - ~0.8 for strong contextual matches (label->input, get_text mapping).
  - ~0.6 for reasonable inference from value alone.
  - ~0.4 for weak guesses or ambiguous mapping.
- Naming rules: produce short, canonical snake_case names. Map common labels to canonical names: email -> email, phone -> phone, first name -> first_name, last name -> last_name, name/fullname -> name, dob/birthdate -> date_of_birth or date, zip/postal -> postal_code, city/state/address/amount/account_number/pan/ifsc as appropriate.
- Always produce realistic example values in the example field (use the actual value from the script when given).
- Return a JSON array only. No extra text, explanation, or markup. Ensure confidence is a float.

FEW-SHOT EXAMPLES (demonstrating opaque IDs and tab inference):

Example A - explicit ids:
Script:
driver.enter_text('input_email', 'user@example.com', 0, False)
Output:
[{
  "name": "email",
  "type": "email",
  "rules": "",
  "description": "Email address used for login/contact.",
  "example": "user@example.com",
  "confidence": 0.98
}]

Example B - opaque ids with get_text label:
Script:
driver.get_text('label_23')  # text: "Contact Email"
driver.enter_text('rnd_abc_1', 'alice@company.com', 0, False)
Output:
[{
  "name": "email",
  "type": "email",
  "rules": "",
  "description": "Contact email address.",
  "example": "alice@company.com",
  "confidence": 0.95
}]

Example C - opaque ids + Tab sequence (name pair):
Script:
driver.enter_text('fld_a1', 'John', 0, False)
driver.press_key('Tab')
driver.enter_text('fld_a2', 'Doe', 0, False)
Output:
[{
  "name": "first_name",
  "type": "string",
  "rules": "",
  "description": "Person's given/first name.",
  "example": "John",
  "confidence": 0.8
}, {
  "name": "last_name",
  "type": "string",
  "rules": "",
  "description": "Person's family/last name.",
  "example": "Doe",
  "confidence": 0.8
}]

Example D - opaque ids + amount/address/phone inference:
Script:
driver.enter_text('xyz1', '100,000', 0, False)
driver.enter_text('xyz2', '123, jane lane', 0, False)
driver.enter_text('xyz3', '9898988787', 0, False)
Output:
[{
  "name": "amount",
  "type": "number",
  "rules": "numeric/currency",
  "description": "Transaction amount.",
  "example": "100,000",
  "confidence": 0.88
}, {
  "name": "address",
  "type": "address",
  "rules": "",
  "description": "Full street address.",
  "example": "123, jane lane",
  "confidence": 0.9
}, {
  "name": "phone",
  "type": "phone",
  "rules": ">=10 digits",
  "description": "Contact phone number.",
  "example": "9898988787",
  "confidence": 0.95
}]

Now parse the following Selenium script and return the JSON array only.

Selenium script:
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

      try:
        parsed = json.loads(json_str)
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