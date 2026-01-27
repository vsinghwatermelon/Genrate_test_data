"""
Schema Generator Module

Generates user-editable schema from extracted fields using LLM or rule-based approach.
Provides consistent schema format for test data generation.
"""

from typing import Dict, List, Any, Optional, Tuple
import json
import re
from utils.field_extractor import (
    detect_field_type,
    generate_validation_rules,
    generate_example_value,
    calculate_confidence,
    normalize_field_name
)

# Constants
VALID_FIELD_TYPES = [
    'string', 'number', 'integer', 'float', 'email', 'phone', 
    'select', 'checkbox', 'radio', 'combobox', 'date', 'textarea', 'boolean'
]
DEFAULT_FIELD_TYPE = 'string'
DEFAULT_RULES = 'Enter a valid value'
DEFAULT_CONFIDENCE = 0.8
MAX_OPTIONS_TO_SHOW = 10  # Max dropdown options to display in prompts
MAX_SCHEMA_FIELDS = 100  # Maximum fields in a schema
MIN_CONFIDENCE_SCORE = 0.3  # Minimum confidence to include a field
HIGH_CONFIDENCE_THRESHOLD = 0.9  # Threshold for high confidence


class SchemaGenerator:
    """Generate test data schema from extracted HTML fields."""
    
    def __init__(self, llm=None):
        """
        Initialize schema generator.
        
        Args:
            llm: Optional LLM instance for enhanced schema generation
        """
        self.llm = llm
    
    def generate_schema(
        self,
        fields: List[Dict[str, Any]],
        use_llm: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Generate schema from extracted fields.
        
        Args:
            fields: List of extracted field dictionaries
            use_llm: Whether to use LLM for schema enhancement
        
        Returns:
            List of schema field definitions
        """
        if use_llm and self.llm:
            return self._generate_schema_with_llm(fields)
        else:
            return self._generate_schema_rule_based(fields)
    
    def _generate_schema_rule_based(self, fields: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate schema using rule-based approach (no LLM)."""
        schema = []
        
        for field in fields:
            schema_entry = {
                'name': normalize_field_name(field),
                'type': detect_field_type(field),
                'rules': generate_validation_rules(field),
                'description': self._generate_description(field),
                'example': generate_example_value(field),
                'confidence': calculate_confidence(field)
            }
            
            # Add options for select/combobox fields
            if field.get('options'):
                schema_entry['options'] = field['options']
            
            # Add validation constraints
            if field.get('required'):
                schema_entry['required'] = True
            
            if field.get('pattern'):
                schema_entry['pattern'] = field['pattern']
            
            schema.append(schema_entry)
        
        return schema
    
    def _generate_schema_with_llm(self, fields: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate schema using LLM for better field understanding."""
        # Build prompt for LLM
        prompt = self._build_llm_prompt(fields)
        
        try:
            # Invoke LLM
            response = self.llm.invoke(prompt)
            
            # Parse LLM response
            schema = self._parse_llm_response(response)
            
            # Validate and normalize schema
            schema = self._normalize_schema(schema, fields)
            
            return schema
        
        except Exception as e:
            print(f"[WARNING] LLM schema generation failed: {e}, falling back to rule-based")
            return self._generate_schema_rule_based(fields)
    
    def _build_llm_prompt(self, fields: List[Dict[str, Any]]) -> str:
        """Build a professional, architect-level prompt for LLM schema generation."""
        # Build field details string
        field_details = self._format_fields_for_prompt(fields)
        
        prompt = f"""You are acting as a Senior QA Architect and Test Data Specialist. 
Your goal is to transform a raw list of UI elements extracted from an automation script into a professional, production-ready Test Data Schema.

### INPUT DATA:
Below are {len(fields)} UI components detected during script execution:
{field_details}

### ARCHITECT'S OBJECTIVES:
1. **Semantic Entity Recognition**: Look beyond technical IDs. If a field is in a "Personal Information" section with a label "Name", the schema field should be `personal_full_name`.
2. **Contextual Type Inference**: 
   - Fields requesting numbers should be `integer` or `float`.
   - Fields requesting contact info should be `email` or `phone`.
   - Fields with options must be `select` or `combobox`.
   - All other text inputs should be `string`.
3. **Logical Deduplication**: If multiple entries seem to refer to the same logical interaction (e.g., clicking a label then an input), merge them into one professional field definition.
4. **Rich Rules**: Generate human-readable validation rules that a tester would understand (e.g., "Must be a valid 10-digit mobile number starting with 7-9").
5. **Production-Ready Examples**: Provide HIGH-QUALITY, realistic examples. No "test" or "asdf". Use "John Doe", "john.doe@example.com", "+91 9876543210", etc.

### OUTPUT FORMAT:
You MUST return ONLY a valid JSON array of objects. NO EXPLANATIONS. NO MARKDOWN.
Each object must follow this structure:
{{
  "name": "logical_snake_case_name",
  "type": "string|integer|float|email|phone|date|select|combobox|checkbox|boolean",
  "description": "Clear purpose of this field",
  "rules": "Validation constraints in plain English",
  "example": "Realistic value",
  "confidence": 0.95
}}

Analyze the components and generate the schema now:"""
        
        return prompt
    
    def _format_fields_for_prompt(self, fields: List[Dict[str, Any]]) -> str:
        """Format fields with rich technical and semantic context for the LLM."""
        lines = []
        
        for i, field in enumerate(fields, 1):
            is_verified = field.get('is_verified_locator', False)
            status = "[PRIMARY/VERIFIED]" if is_verified else "[DISCOVERED]"
            lines.append(f"COMPONENT #{i} {status}:")
            
            # Technical identifiers
            name = field.get('name') or field.get('id') or f'unknown_field_{i}'
            if is_verified and field.get('locator_key'):
                lines.append(f"   Script Locator Key: {field['locator_key']}")
            
            lines.append(f"   Identifier: {name}")
            lines.append(f"   HTML Tag: <{field.get('tag', 'input')}>")
            lines.append(f"   Input Type: {field.get('type', 'text')}")
            
            # Semantic cues
            if field.get('label'):
                lines.append(f"   Visible Label: {field['label']}")
            if field.get('placeholder'):
                lines.append(f"   Placeholder: {field['placeholder']}")
            if field.get('nearby_context'):
                lines.append(f"   Nearby Context: {field['nearby_context']}")
            if field.get('title'):
                lines.append(f"   Title Attribute: {field['title']}")
                
            # Requirements and constraints
            if field.get('required'):
                lines.append("   Constraints: REQUIRED")
            
            # Options for choice fields
            if field.get('options'):
                opts = [opt.get('label', '') or opt.get('value', '') for opt in field['options'][:MAX_OPTIONS_TO_SHOW]]
                lines.append(f"   Available Options: {', '.join(opts)}")
                if len(field['options']) > MAX_OPTIONS_TO_SHOW:
                    lines.append(f"   (... and {len(field['options'])-MAX_OPTIONS_TO_SHOW} more options)")
            
            lines.append("")
        
        return '\n'.join(lines)
    
    def _parse_llm_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse LLM response to extract JSON schema."""
        # Remove markdown code blocks if present
        response = re.sub(r'```json\s*', '', response)
        response = re.sub(r'```\s*', '', response)
        response = response.strip()
        
        # Try to find JSON array in response
        json_match = re.search(r'\[.*\]', response, re.DOTALL)
        if json_match:
            response = json_match.group(0)
        
        try:
            schema = json.loads(response)
            if isinstance(schema, list):
                return schema
        except json.JSONDecodeError as e:
            print(f"[ERROR] Failed to parse LLM response as JSON: {e}")
            print(f"Response preview: {response[:500]}")
        
        return []
    
    def _normalize_schema(
        self,
        schema: List[Dict[str, Any]],
        original_fields: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Normalize and validate LLM-generated schema."""
        normalized = []
        
        for entry in schema:
            # Ensure required fields exist
            if not entry.get('name'):
                continue
            
            # Normalize type
            field_type = entry.get('type', DEFAULT_FIELD_TYPE).lower()
            if field_type not in VALID_FIELD_TYPES:
                field_type = DEFAULT_FIELD_TYPE
            
            normalized_entry = {
                'name': entry.get('name', ''),
                'type': field_type,
                'rules': entry.get('rules', DEFAULT_RULES),
                'description': entry.get('description', entry.get('name', '')),
                'example': entry.get('example', ''),
                'confidence': float(entry.get('confidence', DEFAULT_CONFIDENCE))
            }
            
            # Add options if present
            if entry.get('options'):
                normalized_entry['options'] = entry['options']
            
            # Add required flag
            if entry.get('required'):
                normalized_entry['required'] = True
            
            normalized.append(normalized_entry)
        
        return normalized
    
    def _generate_description(self, field: Dict[str, Any]) -> str:
        """Generate user-friendly description for a field."""
        # Prefer label, then placeholder, then name
        label = field.get('label')
        if label:
            return label.replace('*', '').strip()
        
        placeholder = field.get('placeholder')
        if placeholder:
            return placeholder.strip()
        
        name = field.get('name') or field.get('id', '')
        # Convert snake_case/camelCase to readable text
        readable = re.sub(r'[_-]', ' ', name)
        readable = re.sub(r'([a-z])([A-Z])', r'\1 \2', readable)
        return readable.title().strip()
    
    def deduplicate_schema(self, schema: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove duplicate entries from schema based on field name.
        
        Keeps the entry with highest confidence.
        """
        seen = {}
        
        for entry in schema:
            name = entry.get('name', '')
            if not name:
                continue
            
            if name not in seen:
                seen[name] = entry
            else:
                # Keep entry with higher confidence
                existing_conf = seen[name].get('confidence', 0)
                new_conf = entry.get('confidence', 0)
                if new_conf > existing_conf:
                    seen[name] = entry
        
        return list(seen.values())
    
    def merge_field_metadata(
        self,
        schema: List[Dict[str, Any]],
        raw_fields: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Merge additional metadata from raw fields into schema.
        
        Useful for preserving technical details like locator_key, matched_by, etc.
        """
        # Create lookup by name
        field_lookup = {}
        for field in raw_fields:
            name = normalize_field_name(field)
            if name:
                field_lookup[name] = field
        
        # Merge metadata
        for schema_entry in schema:
            name = schema_entry.get('name', '')
            raw_field = field_lookup.get(name)
            
            if raw_field:
                # Add technical metadata if available
                if raw_field.get('locator_key'):
                    schema_entry['locator_key'] = raw_field['locator_key']
                
                if raw_field.get('matched_by'):
                    schema_entry['matched_by'] = raw_field['matched_by']
                
                if raw_field.get('id'):
                    schema_entry['html_id'] = raw_field['id']
                
                if raw_field.get('name'):
                    schema_entry['html_name'] = raw_field['name']
        
        return schema
    
    def validate_schema(self, schema: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
        """
        Validate schema for completeness and correctness.
        
        Returns:
            (is_valid, list_of_errors)
        """
        errors = []
        
        if not schema:
            errors.append("Schema is empty")
            return False, errors
        
        seen_names = set()
        
        for i, entry in enumerate(schema, 1):
            # Check required fields
            if not entry.get('name'):
                errors.append(f"Entry {i}: Missing 'name' field")
            
            if not entry.get('type'):
                errors.append(f"Entry {i}: Missing 'type' field")
            
            # Check for duplicates
            name = entry.get('name', '')
            if name in seen_names:
                errors.append(f"Entry {i}: Duplicate name '{name}'")
            seen_names.add(name)
            
            # Validate type
            if entry.get('type') not in VALID_FIELD_TYPES:
                errors.append(f"Entry {i}: Invalid type '{entry.get('type')}'")
        
        return len(errors) == 0, errors
