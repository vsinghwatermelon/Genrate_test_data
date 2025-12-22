"""
Selenium Script Parser Module

Parses Selenium automation scripts to extract form field definitions
using LLM-powered analysis.
"""

import json
from typing import Tuple, List, Dict, Any, Optional

from llm_factory import LLMFactory, BaseLLM
from prompts import SeleniumParserPrompts
from utils.json_utils import JSONCleaner, JSONExtractor, NDJSONParser
from utils.console import safe_print


def parse_selenium_script(
    script_text: str, 
    provider: str = "ollama", 
    model_name: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Parse a Selenium script to extract form field definitions.
    
    Args:
        script_text: The Selenium script or extracted field values
        provider: LLM provider ("ollama" or "groq")
        model_name: Model name for Ollama (ignored for Groq)
        
    Returns:
        Tuple of (list of parsed fields, error message or None)
    """
    script_text = script_text or ''
    
    # Create LLM instance
    llm: BaseLLM
    if provider.lower() == "ollama":
        llm = LLMFactory.create_llm(
            provider=provider, 
            model_name=model_name or "llama3:latest", 
            temperature=0.0
        )
    else:
        llm = LLMFactory.create_llm(provider=provider, temperature=0.0)
    
    # Build prompt
    prompt = SeleniumParserPrompts.create_parse_prompt(script_text)
    
    try:
        # Invoke LLM
        response = llm.invoke(prompt)
        
        # Parse response
        parsed_fields, error = _parse_response(response)
        
        if error:
            return [], error
        
        return parsed_fields, None
        
    except Exception as e:
        return [], f"LLM parsing failed: {str(e)}"


def _parse_response(response: str) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Parse LLM response into field definitions.
    
    Args:
        response: Raw LLM response
        
    Returns:
        Tuple of (list of parsed fields, error message or None)
    """
    if not response:
        return [], "Empty response from LLM"
    
    # Try NDJSON parsing first (Ollama format)
    assembled = NDJSONParser.parse(response)
    source_text = assembled if assembled else response
    
    # Extract JSON array
    json_str = JSONExtractor.extract_json(source_text, expect_array=True)
    if not json_str:
        json_str = source_text.strip()
    
    # Clean JSON
    json_str = JSONCleaner.clean(json_str)
    
    try:
        parsed = json.loads(json_str, strict=False)
    except json.JSONDecodeError as e:
        safe_print(f"JSON parse failed at position {e.pos}: {e.msg}")
        
        # Try to repair
        try:
            repaired = JSONCleaner.repair(json_str)
            parsed = json.loads(repaired, strict=False)
            safe_print("✓ Parsed successfully after repair")
        except Exception:
            snippet = source_text[:2000] if source_text else ''
            return [], f"Failed to parse JSON: {str(e)}\nRaw snippet: {snippet}"
    
    if not isinstance(parsed, list):
        parsed = [parsed]
    
    # Normalize fields
    normalized = _normalize_fields(parsed)
    
    if not normalized:
        snippet = source_text[:1500] if source_text else ''
        return [], f"No fields parsed from LLM output. Raw snippet:\n{snippet}"
    
    return normalized, None


def _normalize_fields(parsed: List[Any]) -> List[Dict[str, Any]]:
    """
    Normalize parsed fields to standard format.
    
    Args:
        parsed: List of parsed field dictionaries
        
    Returns:
        List of normalized field definitions
    """
    normalized: List[Dict[str, Any]] = []
    
    for item in parsed:
        if not isinstance(item, dict):
            continue
        
        normalized.append({
            'name': str(item.get('name', '')).strip(),
            'type': str(item.get('type', 'string')),
            'rules': str(item.get('rules', '') or ''),
            'description': str(item.get('description', '') or ''),
            'example': str(item.get('example', '') or ''),
            'confidence': float(item.get('confidence', 0.0))
        })
    
    return normalized
