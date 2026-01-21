"""
Parse Clicked Elements to Schema
Uses LLM to convert tracked Selenium actions into a structured schema for test data generation
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import json
from llm_factory import LLMFactory
import os

router = APIRouter()

class ClickedElement(BaseModel):
    locator: str
    tag_name: str
    text: Optional[str] = ""
    attributes: Dict[str, str] = {}
    semantic_type: Optional[str] = None
    exact_purpose: Optional[str] = None
    role_description: Optional[str] = None
    context: Optional[Dict[str, str]] = {}
    dropdown_options: Optional[List[Dict[str, Any]]] = []

class ParseRequest(BaseModel):
    clicked_elements: List[ClickedElement]
    filled_fields: Optional[List[ClickedElement]] = []

class SchemaField(BaseModel):
    name: str
    type: str
    rules: str
    description: str
    example: str
    confidence: float

@router.post("/parse-clicked-elements")
async def parse_clicked_elements(request: ParseRequest):
    """
    Parse clicked elements into a schema using LLM
    """
    try:
        # Use LLMFactory instead of direct Groq client
        # Default to groq for this specific high-intelligence task if possible, else use ollama
        provider = os.getenv("LLM_PROVIDER", "groq")
        model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile") if provider == "groq" else None
        
        try:
            llm = LLMFactory.create_llm(provider=provider, model_name=model)
        except Exception as e:
            # Fallback to ollama if groq fails/not config
            print(f"[WARN] Failed to init {provider}, falling back to ollama: {e}")
            llm = LLMFactory.create_llm(provider="ollama")
        
        # Format the clicked elements for the LLM
        elements_text = _format_elements_for_llm(request.clicked_elements, request.filled_fields)
        
        # Create the prompt for the LLM
        prompt = f"""You are acting as a Senior QA Architect and Test Data Specialist. 
Your goal is to transform a raw log of UI interactions into a professional, production-ready Test Data Schema.

### INPUT DATA: TRACKED UI INTERACTIONS
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

        print(f"[PARSE] Calling LLM ({llm.model_name}) to parse {len(request.clicked_elements)} elements...")
        
        response_text = llm.invoke(prompt).strip()
        
        # Clean up the response
        if "```json" in response_text:
            response_text = response_text.split("```json")[-1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[-1].split("```")[0]
        response_text = response_text.strip()
        
        # Parse the JSON
        try:
            parsed_schema = json.loads(response_text)
        except json.JSONDecodeError as e:
            print(f"[ERROR] Failed to parse LLM response: {e}")
            print(f"Response was: {response_text}")
            raise HTTPException(status_code=500, detail="Failed to parse LLM response as JSON")
        
        print(f"[PARSE] ✓ Successfully parsed {len(parsed_schema)} fields from semantic data")
        
        return {
            "success": True,
            "parsed_schema": parsed_schema,
            "total_fields": len(parsed_schema)
        }
        
    except Exception as e:
        print(f"[ERROR] Failed to parse clicked elements: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


def _format_elements_for_llm(clicked_elements: List[ClickedElement], filled_fields: List[ClickedElement]) -> str:
    """Format elements with semantic insights for the LLM"""
    lines = []
    
    combined = []
    # Mix them keeping some order but preferring filled fields if they overlap
    seen_locators = set()
    
    # Process filled fields first as they are definitely inputs
    for field in filled_fields:
        combined.append(field)
        seen_locators.add(field.locator)
        
    # Add clicked elements that aren't already captured as filled
    for elem in clicked_elements:
        if elem.locator not in seen_locators:
            combined.append(elem)

    for idx, elem in enumerate(combined, 1):
        lines.append(f"COMPONENT #{idx}:")
        lines.append(f"   Locator: {elem.locator}")
        lines.append(f"   Purpose: {elem.exact_purpose or 'Unknown'}")
        lines.append(f"   Semantic Role: {elem.role_description or 'Unknown'}")
        lines.append(f"   Detected Type: {elem.semantic_type or 'Unknown'}")
        
        if elem.context:
            ctx = elem.context
            if ctx.get('container_heading'): lines.append(f"   Section: {ctx['container_heading']}")
            if ctx.get('label'): lines.append(f"   Label: {ctx['label']}")
            if ctx.get('surrounding_text'): lines.append(f"   Nearby: {ctx['surrounding_text']}")

        if elem.dropdown_options:
            opts = [f"{o.get('text')} (Value: {o.get('value')})" for o in elem.dropdown_options[:10]]
            lines.append(f"   Options: {', '.join(opts)}")
            if len(elem.dropdown_options) > 10:
                lines.append(f"   (... and {len(elem.dropdown_options)-10} more options)")

        lines.append(f"   HTML: <{elem.tag_name} name=\"{elem.attributes.get('name', '')}\" placeholder=\"{elem.attributes.get('placeholder', '')}\">")
        if elem.text:
            lines.append(f"   Visible Text: {elem.text}")
        
        lines.append("")
    
    return "\n".join(lines)
