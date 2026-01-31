"""
Parse Clicked Elements to Schema

Uses LLM logic to bridge the gap between low-level Selenium tracking data 
and structured field definitions. Converts interaction sequences into a 
user-reviewable schema for test data generation.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import json
import logging

from modules.shared.common_utils import get_llm_with_fallback
from modules.shared.json_utils import parse_llm_json_response
from modules.generation.prompts_config.llm_prompts import get_parse_elements_prompt

logger = logging.getLogger(__name__)
router = APIRouter()

# Data Constraints
MAX_ELEMENTS_TO_PROCESS = 1000


# ============================================================================
# DATA MODELS
# ============================================================================

class ClickedElement(BaseModel):
    """Represents a single UI element captured during script execution."""
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
    """Request payload containing all interaction data for schema inference."""
    clicked_elements: List[ClickedElement]
    filled_fields: Optional[List[ClickedElement]] = []

class InfereedSchemaField(BaseModel):
    """A structured field definition produced by the LLM."""
    name: str
    type: str
    rules: str
    description: str
    example: str
    confidence: float


# ============================================================================
# ENDPOINT: ELEMENT PARSING
# ============================================================================

@router.post("/parse-clicked-elements")
async def parse_clicked_elements(request: ParseRequest) -> Dict[str, Any]:
    """
    Synthesize an actionable schema from a list of clicked and modified UI elements.
    
    This endpoint uses AI to analyze the context of each interaction (labels,
    visible text, semantic roles) and produce valid test data field definitions.
    """
    try:
        # 1. Input Validation
        elements = request.clicked_elements
        fields = request.filled_fields or []
        total_count = len(elements) + len(fields)
        
        if total_count == 0:
            raise HTTPException(
                status_code=400,
                detail="No interaction data provided for parsing."
            )
            
        if total_count > MAX_ELEMENTS_TO_PROCESS:
            raise HTTPException(
                status_code=400,
                detail=f"Interaction set is too large ({total_count}). Limit is {MAX_ELEMENTS_TO_PROCESS}."
            )
        
        logger.info(f"Analyzing user flow: {len(elements)} clicks and {len(fields)} form interactions.")
        
        # 2. LLM Initialization and Prompting
        # Falls back to local models if cloud-based inference fails
        llm = get_llm_with_fallback("groq")
        
        # Convert raw element data into a readable semantic context for the AI
        context_string = _format_interactions_for_ai(elements, fields)
        prompt = get_parse_elements_prompt(context_string)
        
        logger.info("Requesting schema synthesis from AI...")
        response = llm.invoke(prompt).strip()
        
        # 3. Structure Parsing
        # Utilizes common logic to handle common LLM response quirks like markdown blocks
        parsed_schema = parse_llm_json_response(response)
        
        if not isinstance(parsed_schema, list):
            logger.error("AI produced malformed schema structure (not an array).")
            raise HTTPException(
                status_code=500,
                detail="The AI produced an invalid schema structure. Please try again."
            )
            
        logger.info(f"Successfully synthesized {len(parsed_schema)} fields.")
        
        return {
            "success": True,
            "parsed_schema": parsed_schema,
            "total_fields": len(parsed_schema)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to synthesize schema from interactions: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal error during schema synthesis: {str(e)}"
        )


# ============================================================================
# PRIVATE SEMANTIC HELPERS
# ============================================================================

def _format_interactions_for_ai(clicks: List[ClickedElement], inputs: List[ClickedElement]) -> str:
    """Consolidation logic to present the AI with a logical user flow context."""
    narrative_lines = []
    
    # Priority consolidation: if an element was both clicked and filled, 
    # the filled state usually contains richer context
    seen_identifiers = set()
    ordered_interactions = []
    
    for input_element in inputs:
        ordered_interactions.append(input_element)
        seen_identifiers.add(input_element.locator)
        
    for click_element in clicks:
        if click_element.locator not in seen_identifiers:
            ordered_interactions.append(click_element)

    for i, item in enumerate(ordered_interactions, 1):
        narrative_lines.append(f"INTERACTION #{i}:")
        narrative_lines.append(f"   Target: {item.locator}")
        narrative_lines.append(f"   Contextual Purpose: {item.exact_purpose or 'Context needed'}")
        narrative_lines.append(f"   UI Role: {item.role_description or 'Unknown'}")
        
        if item.context:
            ctx = item.context
            if ctx.get('label'): narrative_lines.append(f"   Label: {ctx['label']}")
            if ctx.get('container_heading'): narrative_lines.append(f"   Container/Section: {ctx['container_heading']}")
            if ctx.get('surrounding_text'): narrative_lines.append(f"   Nearby Clues: {ctx['surrounding_text']}")

        if item.dropdown_options:
            opts_summary = [f"{o.get('text')} ({o.get('value')})" for o in item.dropdown_options[:8]]
            narrative_lines.append(f"   Data Options: {', '.join(opts_summary)}")
        
        # Present raw HTML context only if metadata is sparse
        name_attr = item.attributes.get('name', '')
        place_attr = item.attributes.get('placeholder', '')
        narrative_lines.append(f"   HTML Hook: <{item.tag_name} name=\"{name_attr}\" placeholder=\"{place_attr}\">")
        
        if item.text:
            narrative_lines.append(f"   Display Text: {item.text}")
        
        narrative_lines.append("")
    
    return "\n".join(narrative_lines)
