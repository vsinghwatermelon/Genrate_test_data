"""
LLM Prompts Configuration

Centralized storage for all LLM prompts used across endpoints.
Separating prompts from code improves maintainability and version control.
"""

# ============================================================================
# PARSE CLICKED ELEMENTS PROMPT
# ============================================================================

PARSE_CLICKED_ELEMENTS_SYSTEM_PROMPT = """You are acting as a Senior QA Architect and Test Data Specialist. 
Your goal is to transform a raw log of UI interactions into a professional, production-ready Test Data Schema."""

PARSE_CLICKED_ELEMENTS_USER_PROMPT = """### INPUT DATA: TRACKED UI INTERACTIONS
{elements_text}

### YOUR TASK
Analyze the "Purpose", "Semantic Role", "Context", and "Options" of the interacted components to generate a JSON Schema. 
Ignore layout-only elements (divs, spans) unless they represent a logical choice. Focus exclusively on fields that require data.

### INTELLIGENT DEDUCTION RULES:
1. **ENTITY RECOGNITION**: Use 'Page Context' (Section/Label) to name fields appropriately. 
   - If Section='Personal Details' and Label='Name', name it 'personal_full_name'.
   - Avoid generic names like 'input_1' or 'div_text'.
2. **FIELD TYPE INFERENCE**: 
   - If it has 'Dropdown Options', type is 'select'.
   - If Purpose mentions 'Email', type is 'email'.
   - If Purpose mentions 'Mobile' or 'Phone', type is 'phone'.
   - If it's a date picker interaction, type is 'date'.
3. **LOGICAL DEDUPLICATION (CRITICAL)**:
   - Users often click a label, then a wrapper, then the input. 
   - ALL these interactions for the same field MUST be merged into a SINGLE schema entry.
   - Use the interaction with the most information (like Options or Input Value) as the source of truth.
4. **ENUMERATION**: For 'select', 'radio', or 'dropdown_option' types, capture the possible options in the 'rules' field (e.g., "Must be one of: [Option A, Option B]").
5. **REALISM**: Example values must be high-quality. No 'test_value'. Use 'John Doe', '9876543210', '1990-05-15', etc.

### OUTPUT JSON STRUCTURE:
Generate a JSON array of objects:
{{
    "name": "structured_snake_case_name",
    "type": "string | number | email | phone | date | select | checkbox | currency | ssn",
    "rules": "Detailed validation rules, format requirements, or list of options.",
    "description": "Explanatory text describing what this field represents in the application flow.",
    "example": "A realistic, valid example value.",
    "confidence": 0.0 to 1.0 (float reflecting certainty of the field purpose)
}}

Return ONLY the valid JSON array."""


def get_parse_elements_prompt(elements_text: str) -> str:
    """
    Generate the complete prompt for parsing clicked elements.
    
    Args:
        elements_text: Formatted text describing all UI elements
        
    Returns:
        Complete prompt ready for LLM
    """
    return PARSE_CLICKED_ELEMENTS_USER_PROMPT.format(elements_text=elements_text)
