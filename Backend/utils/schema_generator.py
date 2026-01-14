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
        """Build prompt for LLM schema generation."""
        # Build field details string
        field_details = self._format_fields_for_prompt(fields)
        
        prompt = f"""You are an expert form field analyzer. Generate a clean JSON schema for the following form fields.

CRITICAL RULES:
- Output exactly ONE entry per field (total: {len(fields)} entries)
- NO duplicates
- NO markdown code blocks
- Output ONLY valid JSON array

For each field, provide:
- name: snake_case version of the field name
- type: one of [string, number, email, phone, select, checkbox, radio, combobox, date, textarea]
- rules: human-readable validation rules
- description: user-friendly description (remove asterisks and technical jargon)
- example: realistic sample value
- confidence: 0.6-1.0 based on field clarity

Type Detection Rules:
- Email fields → type: "email"
- Phone/mobile fields → type: "phone"
- Date/DOB fields → type: "date"
- Number/amount/income → type: "number"
- Dropdown/select → type: "select" or "combobox"
- Checkbox → type: "checkbox"
- Radio → type: "radio"
- Text area → type: "textarea"
- Other text → type: "string"

FIELDS TO ANALYZE:
{field_details}

Output ONLY the JSON array:"""
        
        return prompt
    
    def _format_fields_for_prompt(self, fields: List[Dict[str, Any]]) -> str:
        """Format fields for LLM prompt."""
        lines = []
        
        for i, field in enumerate(fields, 1):
            name = field.get('name') or field.get('id') or f'field_{i}'
            field_type = field.get('type', 'text')
            label = field.get('label', '')
            placeholder = field.get('placeholder', '')
            tag = field.get('tag', 'input')
            
            details = f"{i}. FieldName: {name}"
            if label:
                details += f" | Label: {label}"
            if placeholder:
                details += f" | Placeholder: {placeholder}"
            details += f" | Tag: {tag} | Type: {field_type}"
            
            if field.get('required'):
                details += " | Required: Yes"
            
            if field.get('options'):
                options_preview = [opt.get('label', '') for opt in field['options'][:3]]
                details += f" | Options: {', '.join(options_preview)}"
                if len(field['options']) > 3:
                    details += f" ... ({len(field['options'])} total)"
            
            lines.append(details)
        
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
            field_type = entry.get('type', 'string').lower()
            valid_types = ['string', 'number', 'email', 'phone', 'select', 'checkbox', 
                          'radio', 'combobox', 'date', 'textarea']
            if field_type not in valid_types:
                field_type = 'string'
            
            normalized_entry = {
                'name': entry.get('name', ''),
                'type': field_type,
                'rules': entry.get('rules', 'Enter a valid value'),
                'description': entry.get('description', entry.get('name', '')),
                'example': entry.get('example', ''),
                'confidence': float(entry.get('confidence', 0.8))
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
            valid_types = ['string', 'number', 'email', 'phone', 'select', 
                          'checkbox', 'radio', 'combobox', 'date', 'textarea']
            if entry.get('type') not in valid_types:
                errors.append(f"Entry {i}: Invalid type '{entry.get('type')}'")
        
        return len(errors) == 0, errors
