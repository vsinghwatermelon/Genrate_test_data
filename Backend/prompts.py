"""
Prompt Templates Module

Contains all prompt templates for LLM-based data generation.
Separating prompts from logic improves maintainability and testing.
"""

from typing import List, Dict, Optional, Any


class DataGenerationPrompts:
    """Templates for data generation prompts."""
    
    @staticmethod
    def build_field_details(schema_fields: List[Dict[str, Any]]) -> str:
        """Build formatted field details for the prompt."""
        field_details = []
        for field in schema_fields:
            field_info = f"- {field.get('name', 'unknown')}: type={field.get('type', 'string')}"
            
            if field.get('rules'):
                field_info += f", rules={field.get('rules')}"
            if field.get('example'):
                field_info += f", example={field.get('example')}"
            if field.get('min_length') is not None:
                field_info += f", min_length={field.get('min_length')}"
            if field.get('max_length') is not None:
                field_info += f", max_length={field.get('max_length')}"
            if field.get('min_value') is not None:
                field_info += f", min_value={field.get('min_value')}"
            if field.get('max_value') is not None:
                field_info += f", max_value={field.get('max_value')}"
            if field.get('pattern'):
                field_info += f", pattern={field.get('pattern')}"
            if field.get('enum_values'):
                field_info += f", allowed_values={field.get('enum_values')}"
            if field.get('nullable'):
                field_info += ", nullable=true"
            if field.get('unique'):
                field_info += ", unique=true"
                
            field_details.append(field_info)
        
        return '\n'.join(field_details)
    
    @staticmethod
    def build_parent_context(parent_tables_data: Optional[Dict[str, List[Dict]]]) -> str:
        """Build parent tables context for FK relationships."""
        if not parent_tables_data:
            return ""
        
        context = "\n=== PARENT TABLES DATA (USE THESE ACTUAL VALUES!) ===\n\n"
        
        for table_name, rows in parent_tables_data.items():
            context += f"{table_name.upper()} Table (already generated):\n"
            
            # Show sample rows
            sample_count = min(10, len(rows))
            for row in rows[:sample_count]:
                context += f"  {row}\n"
            
            if len(rows) > sample_count:
                context += f"  ... and {len(rows) - sample_count} more records\n"
            context += "\n"
            
            # Extract available values for each key
            if rows:
                sample_row = rows[0]
                for key in sample_row.keys():
                    if key != "is_valid":
                        values = list(set(str(row.get(key, "")) for row in rows if key in row))[:20]
                        context += f"Available {table_name}.{key} values: {', '.join(values)}\n"
            context += "\n"
        
        return context
    
    @staticmethod
    def build_group_instructions(groups: List[Dict[str, Any]]) -> str:
        """Build instructions for group-based generation."""
        instructions = []
        record_offset = 0
        
        for i, group in enumerate(groups, 1):
            group_name = group.get('name', f'Group{i}')
            count = group.get('count', 0)
            correct_fields = group.get('correct_fields', [])
            wrong_fields = group.get('wrong_fields', [])
            
            start_idx = record_offset + 1
            end_idx = record_offset + count
            record_offset = end_idx
            
            inst = f"\n=== {group_name} (Records {start_idx}-{end_idx}) ===\n"
            inst += f"Generate {count} records where:\n"
            
            if correct_fields:
                inst += f"✓ CORRECT/VALID fields: {', '.join(correct_fields)}\n"
                inst += "  These fields MUST follow all schema rules perfectly.\n"
            
            if wrong_fields:
                inst += f"✗ INCORRECT/INVALID fields: {', '.join(wrong_fields)}\n"
                inst += "  These fields MUST clearly violate their schema rules.\n"
                inst += "  Use different violation types for each record.\n"
            
            if not correct_fields and not wrong_fields:
                inst += "All fields should be VALID (follow schema rules).\n"
            
            is_valid = len(wrong_fields) == 0
            inst += f"Set is_valid = {str(is_valid).lower()} for all records in this group.\n"
            
            instructions.append(inst)
        
        return ''.join(instructions)
    
    @classmethod
    def create_generation_prompt(
        cls,
        schema_fields: List[Dict[str, Any]],
        num_records: int,
        correct_num_records: int,
        wrong_num_records: int,
        additional_rules: Optional[str] = None,
        parent_tables_data: Optional[Dict[str, List[Dict]]] = None,
        groups: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Create the main data generation prompt.
        
        Args:
            schema_fields: List of field definitions
            num_records: Total number of records to generate
            correct_num_records: Number of valid records (legacy mode)
            wrong_num_records: Number of invalid records (legacy mode)
            additional_rules: Optional additional generation rules
            parent_tables_data: Optional parent table data for FK context
            groups: Optional group-based configuration
            
        Returns:
            Formatted prompt string
        """
        field_names = [f.get('name', '') for f in schema_fields if f.get('name')]
        field_details = cls.build_field_details(schema_fields)
        parent_context = cls.build_parent_context(parent_tables_data)
        
        # Determine total records and instructions based on mode
        if groups:
            total_records = sum(g.get('count', 0) for g in groups)
            record_instructions = cls.build_group_instructions(groups)
        else:
            total_records = num_records
            record_instructions = f"""- First {correct_num_records} records → STRICTLY VALID (is_valid = true)
- Next {wrong_num_records} records → CLEARLY INVALID (is_valid = false)
- Maintain this exact order in output."""
        
        # Build example structure
        example_fields = ', '.join([f'"{name}": "value_{i}"' for i, name in enumerate(field_names)])
        
        prompt = f"""You are an expert test data generator. Generate {total_records} UNIQUE, DIVERSE, and REALISTIC test data records.

=== SCHEMA DEFINITION ===
{field_details}

{f"=== ADDITIONAL CONTEXT/RULES ===\n{additional_rules}\n" if additional_rules else ""}
{parent_context}

=== CRITICAL INSTRUCTIONS ===

1. DATA DIVERSITY & UNIQUENESS:
   - Every record must have COMPLETELY UNIQUE values
   - No repetition of any field value across records
   - All values must look realistic and natural
   - Never copy or reuse any example value
{f"   - CRITICAL: Use actual values from parent tables above for referential integrity" if parent_tables_data else ""}

2. RECORD COUNT & GROUPS:
   - Generate EXACTLY {total_records} total records
   {record_instructions}

3. STRUCTURE:
   - Each record must include ALL {len(field_names)} fields: {', '.join(field_names)}
   - Plus one extra field: "is_valid" (boolean)
   - No missing or extra fields

4. VALID RECORDS (is_valid = true):
   - Must PERFECTLY follow all schema rules and types
   - Follow examples and constraints exactly
   - Ensure realistic, production-quality data

5. INVALID RECORDS (is_valid = false):
   - Each must CLEARLY break at least ONE schema rule
   - Use DIFFERENT violation types for each record:
     * Wrong type (string instead of number, etc.)
     * Wrong format (invalid email, malformed phone, etc.)
     * Wrong length (too short or too long)
     * Invalid values (nonsensical data)
   - Make violations OBVIOUS

6. OUTPUT FORMAT - CRITICAL:
   - Output MUST be a SINGLE JSON array ONLY
   - Start with [ and end with ]
   - NO markdown code blocks (no ```)
   - NO comments
   - NO explanations before or after
   - NO double brackets [[ ]]
   - NO trailing commas
   - Valid JSON that can be parsed directly

7. EXAMPLE STRUCTURE:
[
  {{{example_fields}, "is_valid": true}},
  {{{example_fields}, "is_valid": false}}
]

Now generate {total_records} unique records:"""

        return prompt
    
    @classmethod
    def create_group_prompt(
        cls,
        schema_fields: List[Dict[str, Any]],
        group: Dict[str, Any],
        additional_rules: Optional[str] = None,
        parent_tables_data: Optional[Dict[str, List[Dict]]] = None
    ) -> str:
        """
        Create a specialized prompt for single group generation.
        
        Args:
            schema_fields: List of field definitions
            group: Group configuration
            additional_rules: Optional additional rules
            parent_tables_data: Optional parent table data
            
        Returns:
            Formatted prompt string
        """
        group_name = group.get('name', 'Group')
        group_count = group.get('count', 0)
        correct_fields = group.get('correct_fields', [])
        wrong_fields = group.get('wrong_fields', [])
        is_valid_group = len(wrong_fields) == 0
        
        field_details = cls.build_field_details(schema_fields)
        parent_context = cls.build_parent_context(parent_tables_data)
        
        prompt = f"""You are an expert test data generator. Generate EXACTLY {group_count} UNIQUE records for {group_name}.

=== SCHEMA DEFINITION ===
{field_details}

{f"=== ADDITIONAL CONTEXT/RULES ===\n{additional_rules}\n" if additional_rules else ""}
{parent_context}

=== GROUP SPECIFICATION: {group_name} ===

"""
        
        if correct_fields:
            prompt += f"""✓ CORRECT/VALID FIELDS: {', '.join(correct_fields)}
- These fields MUST be PERFECTLY VALID
- Follow ALL schema rules exactly
- Use realistic, production-quality values
- Each record must have UNIQUE values

"""
        
        if wrong_fields:
            prompt += f"""✗ WRONG/INVALID FIELDS: {', '.join(wrong_fields)}
- These fields MUST be CLEARLY INVALID
- Deliberately violate their schema rules
- Use DIFFERENT violation types for each record:
  * Wrong type (string instead of number, etc.)
  * Wrong format (invalid email, malformed phone)
  * Wrong length (too short or too long)
  * Invalid values (gibberish, nonsensical data)
- Make violations OBVIOUS and DIVERSE

IMPORTANT: Include ALL fields in every record. Invalid fields should have WRONG values, not be missing.

"""
        
        if not correct_fields and not wrong_fields:
            prompt += "All fields should be VALID (follow schema rules perfectly).\n\n"
        
        prompt += f"""=== OUTPUT REQUIREMENTS ===

1. Output EXACTLY {group_count} records
2. Each record is a JSON object with ALL schema fields
3. Add "is_valid": {str(is_valid_group).lower()} to each record
4. Output MUST be a single JSON array ONLY
5. Start with [ and end with ]
6. NO markdown, NO code blocks, NO comments
7. Valid JSON that can be parsed directly
{f"8. Use actual values from parent tables if provided above" if parent_tables_data else ""}

NOW GENERATE {group_count} RECORDS:"""

        return prompt


class SeleniumParserPrompts:
    """Templates for Selenium script parsing prompts."""

    @staticmethod
    def create_parse_prompt(script_text: str) -> str:
        """
        Create prompt for parsing Selenium script to extract form fields.
        If no HTML fields are found, extract fields directly from the Selenium script.
        """
        # Detect if HTML fields are present
        has_html_fields = "Extracted HTML Page Details:" in script_text and "--- Fields from downloaded page" in script_text
        if has_html_fields:
            return f"""You are an expert parser assistant. Analyze the following EXTRACTED FIELD VALUES and EXTRACTED HTML PAGE DETAILS.

IMPORTANT: "Extracted HTML Page Details" is the PRIMARY SOURCE OF TRUTH for the list of fields. 
The "Extracted form field values" section is secondary and only provides example values.

Your task:
1. Scan the "Extracted HTML Page Details" section.
2. For EVERY Input, Select, Textarea, Radio, or Checkbox found in the HTML details, you MUST create a field definition in the output JSON.
3. If a field appears in the HTML but not in the Selenium script, INCLUDE IT anyway. The HTML list represents the complete form found on the page.

Field Name Logic:
    - Example: Label="Date of Birth" -> name="date_of_birth"
    - Example: Placeholder="Enter your full name" -> name="full_name"

Field Type Logic:

Return ONLY a valid JSON array. Each item must be:
{{
    "name": "snake_case_name",
    "type": "string|email|phone|date|number|select|radio|checkbox|...",
    "rules": "validation rules or options",
    "description": "Brief description",
    "example": "Example value",
    "confidence": 0.95
}}

=== EXAMPLE OUTPUT ===
[
    {{"name": "full_name", "type": "string", "rules": "", "description": "Full Name field", "example": "John Doe", "confidence": 1.0}},
    {{"name": "city", "type": "select", "rules": "Options: NY, LA", "description": "Select City", "example": "NY", "confidence": 1.0}},
    {{"name": "gender", "type": "radio", "rules": "Male, Female", "description": "Gender selection", "example": "Male", "confidence": 1.0}}
]

Now analyze the text below inside the <DATA> tags. REMEMBER: Output ALL fields found in the HTML section.

<DATA>
{script_text}
</DATA>"""
        else:
            return f"""You are an expert parser assistant. Analyze the following EXTRACTED FIELD VALUES from a Selenium automation script.

IMPORTANT: The Selenium script is the ONLY SOURCE OF TRUTH for the list of fields. Extract every field the script interacts with (calls like driver.enter_text, driver.get_text, etc.).

Your task:
1. Scan the Selenium script and extract every form field (input, select, textarea, radio, checkbox) that is interacted with.
2. For each field, infer a clean snake_case name, type, rules (if any), description, realistic example value, and confidence score.

Field Name Logic:

Return ONLY a valid JSON array. Each item must be:
{{
    "name": "snake_case_name",
    "type": "string|email|phone|date|number|select|radio|checkbox|...",
    "rules": "validation rules or options",
    "description": "Brief description",
    "example": "Example value",
    "confidence": 0.95
}}

=== EXAMPLE OUTPUT ===
[
    {{"name": "full_name", "type": "string", "rules": "", "description": "Full Name field", "example": "John Doe", "confidence": 1.0}},
    {{"name": "email", "type": "email", "rules": "", "description": "Email address", "example": "user@example.com", "confidence": 1.0}},
    {{"name": "phone", "type": "phone", "rules": "", "description": "Phone number", "example": "9876543210", "confidence": 1.0}}
]

Now analyze the text below inside the <DATA> tags. Output ALL fields found in the Selenium script.

<DATA>
{script_text}
</DATA>"""
