"""
Parse Clicked Elements to Schema
Uses LLM to convert tracked Selenium actions into a structured schema for test data generation
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import json
import logging

from endpoints.common import get_llm_with_fallback
from prompts_config.llm_prompts import get_parse_elements_prompt

logger = logging.getLogger(__name__)
router = APIRouter()

# Constants
MAX_ELEMENTS = 1000  # Maximum number of elements to process

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
    Parse clicked elements into a schema using LLM.
    
    Args:
        request: ParseRequest containing clicked_elements and filled_fields
        
    Returns:
        Dictionary with success status, parsed schema, and field count
        
    Raises:
        HTTPException: If parsing fails or input validation fails
    """
    try:
        # Validate input
        total_elements = len(request.clicked_elements) + len(request.filled_fields or [])
        if total_elements == 0:
            raise HTTPException(
                status_code=400,
                detail="No elements provided. Please provide at least one clicked or filled element."
            )
        if total_elements > MAX_ELEMENTS:
            raise HTTPException(
                status_code=400,
                detail=f"Too many elements ({total_elements}). Maximum allowed: {MAX_ELEMENTS}"
            )
        
        logger.info(f"Parsing {len(request.clicked_elements)} clicked elements and {len(request.filled_fields or [])} filled fields")
        
        # Get LLM with automatic fallback
        llm = get_llm_with_fallback("groq")
        
        # Format the clicked elements for the LLM
        elements_text = _format_elements_for_llm(request.clicked_elements, request.filled_fields or [])
        
        # Create the prompt using centralized config
        prompt = get_parse_elements_prompt(elements_text)
        
        logger.info(f"Calling LLM ({getattr(llm, 'model_name', 'unknown')}) to parse elements...")
        response_text = llm.invoke(prompt).strip()
        
        # Parse JSON from response (handles markdown code blocks)
        try:
            # Clean up response (remove code blocks)
            clean_response = response_text
            if "```json" in clean_response:
                clean_response = clean_response.split("```json")[-1].split("```")[0]
            elif "```" in clean_response:
                clean_response = clean_response.split("```")[1] if len(clean_response.split("```")) >= 2 else clean_response
            clean_response = clean_response.strip()
            
            parsed_schema = json.loads(clean_response)
            
            # Validate schema structure
            if not isinstance(parsed_schema, list):
                raise ValueError("Schema must be a JSON array")
            
            logger.info(f"Successfully parsed {len(parsed_schema)} fields from {total_elements} elements")
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"Response preview: {response_text[:500]}...")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to parse LLM response as valid JSON: {str(e)}"
            )
        except ValueError as e:
            logger.error(f"Invalid schema structure: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Invalid schema structure: {str(e)}"
            )

        
        return {
            "success": True,
            "parsed_schema": parsed_schema,
            "total_fields": len(parsed_schema)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to parse clicked elements: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse clicked elements: {str(e)}"
        )


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
