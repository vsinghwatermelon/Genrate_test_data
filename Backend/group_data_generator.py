from langchain_ollama import OllamaError
import json
import re
import sys
from llm_factory import LLMFactory


def _safe_print(text: str) -> None:
    """Print text safely to consoles that may not support some Unicode chars."""
    try:
        print(text)
    except Exception:
        try:
            enc = sys.stdout.encoding or 'utf-8'
            print(text.encode(enc, errors='replace').decode(enc))
        except Exception:
            print(text.encode('utf-8', errors='replace').decode('utf-8'))


class GroupDataGenerator:
    """
    Specialized data generator for group-based test data generation.
    
    This generator creates data by processing each group separately,
    allowing fine-grained control over which fields are correct/wrong
    per group.
    """
    
    def __init__(self, model_name: str = "llama3:latest", provider: str = "ollama"):
        """
        Initialize the group data generator.
        
        Args:
            model_name: Name of the LLM model (for Ollama)
            provider: LLM provider ("ollama" or "groq")
        """
        self.provider = provider
        if provider == "ollama":
            self.llm = LLMFactory.create_llm(provider=provider, model_name=model_name, temperature=0.7)
        else:
            self.llm = LLMFactory.create_llm(provider=provider, temperature=0.7)
    
    def generate_groups(
        self,
        schema_fields: list,
        groups: list,
        additional_rules: str = None,
        parent_tables_data: dict = None
    ) -> dict:
        """
        Generate test data for multiple groups sequentially.
        
        Args:
            schema_fields: List of field definitions
            groups: List of group configurations [{name, count, correct_fields, wrong_fields}]
            additional_rules: Optional additional context/rules
            parent_tables_data: Optional parent table data for referential integrity
            
        Returns:
            dict with keys: data (list of records), count (int), groups (list of group info)
        """
        all_data = []
        group_breakdown = []
        
        print(f"\n{'='*60}")
        print(f"  GROUP-BASED DATA GENERATION")
        print(f"{'='*60}")
        print(f"Total Groups: {len(groups)}")
        print(f"Total Records: {sum(g.get('count', 0) for g in groups)}")
        print(f"{'='*60}\n")
        
        for i, group in enumerate(groups, 1):
            group_name = group.get('name', f'Group{i}')
            group_count = group.get('count', 0)
            
            if group_count <= 0:
                print(f"⊘ Skipping {group_name} (count = 0)")
                continue
            
            print(f"\n{'─'*60}")
            print(f"  [{i}/{len(groups)}] Generating {group_name}")
            print(f"{'─'*60}")
            print(f"  Records: {group_count}")
            print(f"  Correct Fields: {', '.join(group.get('correct_fields', [])) or 'None'}")
            print(f"  Wrong Fields: {', '.join(group.get('wrong_fields', [])) or 'None'}")
            print(f"{'─'*60}")
            
            try:
                # Generate data for this group
                group_data = self._generate_single_group(
                    schema_fields=schema_fields,
                    group=group,
                    additional_rules=additional_rules,
                    parent_tables_data=parent_tables_data
                )
                
                # Add metadata to each record
                for record in group_data:
                    record['_group'] = group_name
                    record['_wrong_fields'] = group.get('wrong_fields', [])
                
                # Limit to requested count
                group_data = group_data[:group_count]
                
                print(f"✓ Successfully generated {len(group_data)} records for {group_name}")
                
                all_data.extend(group_data)
                group_breakdown.append({
                    'group_name': group_name,
                    'count': len(group_data),
                    'correct_fields': group.get('correct_fields', []),
                    'wrong_fields': group.get('wrong_fields', [])
                })
                
            except Exception as e:
                print(f"✗ Error generating {group_name}: {str(e)}")
                raise Exception(f"Failed to generate {group_name}: {str(e)}")
        
        print(f"\n{'='*60}")
        print(f"  GENERATION COMPLETE")
        print(f"{'='*60}")
        print(f"Total Records Generated: {len(all_data)}")
        print(f"Groups Processed: {len(group_breakdown)}")
        print(f"{'='*60}\n")
        
        return {
            "data": all_data,
            "count": len(all_data),
            "groups": group_breakdown
        }
    
    def _generate_single_group(
        self,
        schema_fields: list,
        group: dict,
        additional_rules: str = None,
        parent_tables_data: dict = None,
        max_retries: int = 3
    ) -> list:
        """
        Generate data for a single group with retry logic.
        
        Args:
            schema_fields: List of field definitions
            group: Group configuration
            additional_rules: Optional additional context
            parent_tables_data: Optional parent table data
            max_retries: Maximum number of retry attempts
            
        Returns:
            List of generated records
        """
        # Create specialized prompt for this group
        prompt = self._create_group_prompt(
            schema_fields=schema_fields,
            group=group,
            additional_rules=additional_rules,
            parent_tables_data=parent_tables_data
        )
        
        print(f"\n  Prompt length: {len(prompt)} characters")
        
        # Retry loop for LLM generation
        for attempt in range(max_retries):
            try:
                # Generate data using LLM
                response = self.llm.invoke(prompt)
                print(f"  LLM response received (length: {len(response) if response else 0} chars)")
                
                # Check for empty response
                if not response or len(response.strip()) == 0:
                    if attempt < max_retries - 1:
                        print(f"  ⚠ Empty response, retrying... (attempt {attempt + 2}/{max_retries})")
                        continue
                    else:
                        raise Exception("LLM returned empty response after all retries")
                
                # Parse the response
                assembled = self._assemble_ndjson(response)
                source_text = assembled if assembled else response
                print(f"  Assembled text length: {len(source_text)} chars")
                
                # Extract JSON array
                json_str = self._extract_json_array(source_text, response)
                print(f"  Extracted JSON length: {len(json_str)} chars")
                
                # Clean and parse
                json_str = self._clean_json(json_str)
                
                try:
                    data = json.loads(json_str)
                    
                    if not isinstance(data, list):
                        data = [data]
                    
                    # Success!
                    return data
                    
                except json.JSONDecodeError as e:
                    if attempt < max_retries - 1:
                        print(f"  ⚠ JSON parse error: {str(e)}")
                        print(f"  Retrying... (attempt {attempt + 2}/{max_retries})")
                        continue
                    else:
                        print(f"  ERROR: Failed to parse JSON after all retries")
                        print(f"  Error at: {str(e)}")
                        print(f"  JSON snippet (first 500 chars): {json_str[:500]}")
                        print(f"  JSON snippet (last 500 chars): {json_str[-500:]}")
                        raise Exception(f"Failed to parse JSON: {str(e)}")
                        
            except OllamaError as e:
                if attempt < max_retries - 1:
                    print(f"  ⚠ LLM error: {e}")
                    print(f"  Retrying... (attempt {attempt + 2}/{max_retries})")
                    continue
                else:
                    raise Exception(f"LLM error after all retries: {e}")
        
        # Should never reach here
        raise Exception("Failed to generate data after all retries")
    
    def _create_group_prompt(
        self,
        schema_fields: list,
        group: dict,
        additional_rules: str = None,
        parent_tables_data: dict = None
    ) -> str:
        """
        Create a specialized prompt for group-based data generation.
        
        This prompt is optimized for generating one group at a time with
        specific field-level correct/wrong specifications.
        """
        group_name = group.get('name', 'Group')
        group_count = group.get('count', 0)
        correct_fields = group.get('correct_fields', [])
        wrong_fields = group.get('wrong_fields', [])
        
        # Build field details
        field_details = []
        for field in schema_fields:
            field_info = f"- {field.get('name', 'unknown')}: type={field.get('type', 'string')}"
            if field.get('rules'):
                field_info += f", rules={field.get('rules')}"
            if field.get('example'):
                field_info += f", example={field.get('example')}"
            field_details.append(field_info)
        
        # Build parent tables context if provided
        parent_tables_context = ""
        if parent_tables_data:
            parent_tables_context = "\n=== PARENT TABLES DATA (USE THESE ACTUAL VALUES!) ===\n\n"
            for parent_table_name, parent_rows in parent_tables_data.items():
                parent_tables_context += f"{parent_table_name.upper()} Table (already generated):\n"
                sample_count = min(10, len(parent_rows))
                for row in parent_rows[:sample_count]:
                    parent_tables_context += f"  {row}\n"
                if len(parent_rows) > sample_count:
                    parent_tables_context += f"  ... and {len(parent_rows) - sample_count} more records\n"
                parent_tables_context += "\n"
        
        # Determine if this group should be valid or invalid
        is_valid_group = len(wrong_fields) == 0
        
        prompt = f"""You are an expert test data generator. Generate EXACTLY {group_count} UNIQUE, DIVERSE, and REALISTIC test data records for {group_name}.

=== SCHEMA DEFINITION ===
{chr(10).join(field_details)}

{f"=== ADDITIONAL CONTEXT/RULES ===\n{additional_rules}\n" if additional_rules else ""}
{parent_tables_context}

=== GROUP SPECIFICATION: {group_name} ===
Generate {group_count} records with the following field-level requirements:

"""
        
        if correct_fields and len(correct_fields) > 0:
            prompt += f"""✓ CORRECT/VALID FIELDS: {', '.join(correct_fields)}
These fields MUST be PERFECTLY VALID:
- Follow ALL schema rules exactly (type, format, length, pattern)
- Use realistic, production-quality values
- Each record must have UNIQUE values for these fields
- Examples: If email is correct, use proper format like "user123@example.com"

"""
        
        if wrong_fields and len(wrong_fields) > 0:
            prompt += f"""✗ WRONG/INVALID FIELDS: {', '.join(wrong_fields)}
These fields MUST be CLEARLY INVALID:
- Deliberately violate their schema rules
- Use DIFFERENT violation types for each record:
  * Wrong type (string instead of number, number instead of string, etc.)
  * Wrong format (missing @, wrong email pattern, malformed phone, etc.)
  * Wrong length (too short or too long)
  * Invalid values (nonsensical data, gibberish, random characters)
- Make violations OBVIOUS and DIVERSE across records
- Examples for wrong fields:
  * Wrong email: "notanemail", "missing-at-sign.com", "123", "abc", "@@@", "email.com"
  * Wrong password: "", "1", "ab", "toolongpasswordthatexceedslimits"
  * Wrong name: "123", "@#$", "", "x", "verylongnamethatisunrealistic"
  * Wrong phone: "123", "abcd", "999999999999999", "12-34", ""
  * Wrong number: "not_a_number", "abc", "-999999", "", "NULL"

IMPORTANT: Even though fields are invalid, you MUST still generate complete JSON!
- Include ALL fields in every record
- Invalid fields should have WRONG values, not be missing
- The JSON structure itself must be valid and parseable

"""
        
        if not correct_fields and not wrong_fields:
            prompt += """All fields should be VALID (follow schema rules perfectly).

"""
        
        prompt += f"""=== CRITICAL OUTPUT REQUIREMENTS ===

1. UNIQUENESS & DIVERSITY:
   - Every record must be COMPLETELY UNIQUE
   - NO repetition of values across records
   - Use diverse, realistic data
   - Vary all field values significantly

2. STRUCTURE:
   - Output EXACTLY {group_count} records
   - Each record is a JSON object with ALL schema fields
   - Add "is_valid": {str(is_valid_group).lower()} to each record
   - NO extra or missing fields

3. JSON FORMAT - ABSOLUTELY CRITICAL:
   - Output MUST be a single JSON array ONLY
   - Start with [ and end with ]
   - NO markdown, NO code blocks, NO ```json
   - NO comments (// or /* */)
   - NO explanations before or after
   - NO double brackets [[ ]]
   - NO trailing commas
   - Proper JSON escaping for all strings
   - Valid JSON that can be parsed directly

4. QUALITY:
   - Correct fields: Perfect, production-ready data
   - Wrong fields: Obvious, diverse violations
   - Each record tells a clear story
   {f"- CRITICAL: Use actual values from parent tables if provided above" if parent_tables_data else ""}

=== EXAMPLE OUTPUT STRUCTURE ===
[
  {{"field1": "unique_value_1", "field2": "unique_value_2", ..., "is_valid": {str(is_valid_group).lower()}}},
  {{"field1": "unique_value_3", "field2": "unique_value_4", ..., "is_valid": {str(is_valid_group).lower()}}}
]

NOW GENERATE EXACTLY {group_count} RECORDS FOR {group_name}:
"""
        
        return prompt
    
    def _assemble_ndjson(self, response: str) -> str:
        """Assemble NDJSON stream (Ollama format) into single string."""
        assembled = ''
        try:
            for line in (response or '').splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict) and 'response' in obj:
                        assembled += obj['response']
                except Exception:
                    continue
        except Exception:
            assembled = ''
        return assembled
    
    def _extract_json_array(self, text: str, fallback: str) -> str:
        """Extract first JSON array from text."""
        if not text:
            return fallback
        
        start = text.find('[')
        if start == -1:
            # Fallback to regex
            m = re.search(r'\[.*\]', fallback, re.DOTALL)
            if m:
                return m.group(0)
            return text
        
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
        
        # If we didn't find complete array, try to fix truncated JSON
        incomplete = text[start:]
        
        # Check if it looks like truncated JSON (ends mid-object)
        if incomplete.count('{') > incomplete.count('}'):
            # Close any open objects
            open_objects = incomplete.count('{') - incomplete.count('}')
            for _ in range(open_objects):
                # Find last comma or opening brace to truncate properly
                last_comma = incomplete.rfind(',')
                last_brace = incomplete.rfind('{')
                
                if last_comma > last_brace:
                    # Truncate at last complete object
                    incomplete = incomplete[:last_comma]
                elif last_brace > 0:
                    # Remove incomplete object
                    incomplete = incomplete[:last_brace]
                else:
                    break
            
            # Ensure proper closing
            incomplete = incomplete.rstrip(',').rstrip() + '\n]'
        
        return incomplete
    
    def _clean_json(self, json_str: str) -> str:
        """Clean JSON response for parsing."""
        # Remove control characters
        cleaned = []
        for char in json_str:
            code = ord(char)
            if code >= 32 or char in '\n\r\t':
                cleaned.append(char)
            else:
                cleaned.append(' ')
        json_str = ''.join(cleaned)
        
        # Remove double brackets
        json_str = re.sub(r'^\s*\[\s*\[', '[', json_str)
        json_str = re.sub(r'\]\s*\]\s*$', ']', json_str)
        
        # Remove comments
        json_str = re.sub(r'//.*', '', json_str)
        json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
        
        # Remove trailing commas
        json_str = re.sub(r',(\s*\])', r'\1', json_str)
        json_str = re.sub(r',(\s*\})', r'\1', json_str)
        
        # Remove blank lines
        json_str = '\n'.join([line for line in json_str.splitlines() if line.strip()])
        
        # Fix escaped single quotes
        json_str = json_str.replace("\\'", "'")
        
        # Remove lone null tokens
        json_str = re.sub(r',\s*null\s*,', ',', json_str)
        json_str = re.sub(r',\s*null\s*}', '}', json_str)
        json_str = re.sub(r'{\s*null\s*,', '{', json_str)
        
        # Collapse multiple commas
        json_str = re.sub(r',\s*,+', ',', json_str)
        
        return json_str
