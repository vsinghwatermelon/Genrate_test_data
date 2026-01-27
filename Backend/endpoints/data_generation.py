"""
Data Generation Endpoints

Endpoints for generating test data using various methods.
"""

from fastapi import Request, HTTPException
from typing import Optional, Dict, Any
import logging

from data_generator import TestDataGenerator
from llm_factory import LLMFactory
from utils.locator_parser import LocatorParser
from endpoints.data_gen_helpers import (
    convert_schema_to_dict,
    convert_groups_to_dict,
    create_generator_from_request,
    handle_generation_errors,
)
from models import (
    GenerateRequest,
    GenerateResponse,
    SeleniumGenerateRequest,
    SeleniumGenerateResponse,
)

logger = logging.getLogger(__name__)



@handle_generation_errors("generate_data_from_schema")
async def generate_data_from_schema(request: Request) -> Dict[str, Any]:
    """
    Generate test data from edited schema and group config from frontend.
    
    Args:
        request: FastAPI request with JSON body containing schema, groups, and ai_model
        
    Returns:
        Dictionary with test_data key containing generated records
        
    Request JSON: 
        {
            "schema": [...],
            "groups": [...],
            "ai_model": "groq"|"ollama"
        }
    """
    body = await request.json()
    schema = body.get("schema")
    groups = body.get("groups")
    ai_model = body.get("ai_model", "ollama")

    if not schema:
        raise HTTPException(status_code=400, detail="Missing schema definition.")
    
    logger.info(f"Generating data with {ai_model} for {len(schema)} fields")
    
    generator = TestDataGenerator(provider=ai_model)
    num_records = sum(g.get('count', 0) for g in groups) if groups else 5
    result = generator.generate_data(
        schema_fields=schema,
        groups=groups,
        num_records=num_records,
        additional_rules=None
    )
    
    logger.info(f"Generated {len(result['data'])} records")
    return {"test_data": result['data']}



@handle_generation_errors("generate_test_data")
async def generate_test_data(request: GenerateRequest) -> GenerateResponse:
    """
    Generate test data based on schema definition.

    Supports both legacy mode (correct/wrong record counts) and
    group-based mode for fine-grained per-field validity control.

    Args:
        request: Generation request with schema fields and configuration

    Returns:
        Generated data records with count
    """
    logger.info(
        f"Generating test data: {len(request.schema_fields)} fields, "
        f"{request.num_records} records (provider: {request.model_provider.value})"
    )
    
    # Convert Pydantic models to dicts for the generator
    schema_fields = convert_schema_to_dict(request.schema_fields)
    groups = convert_groups_to_dict(request.groups)

    # Create generator
    generator = create_generator_from_request(request)

    # Generate data
    result = generator.generate_data(
        schema_fields=schema_fields,
        num_records=request.num_records,
        correct_num_records=request.correct_num_records,
        wrong_num_records=request.wrong_num_records,
        additional_rules=request.additional_rules,
        groups=groups,
    )
    
    logger.info(f"Generated {result['count']} records successfully")

    return GenerateResponse(
        data=result["data"],
        count=result["count"],
        groups=result.get("groups"),
    )



@handle_generation_errors("generate_from_selenium")
async def generate_from_selenium(request: SeleniumGenerateRequest) ->SeleniumGenerateResponse:
    """
    Parse a Selenium script and generate test data.

    Extracts form field definitions from a Selenium automation script,
    then generates test data based on the inferred schema.

    Args:
        request: Selenium script and generation configuration

    Returns:
        Generated data with parsed schema information
    """
    script_text = request.selenium_script.strip()

    if not script_text:
        raise HTTPException(
            status_code=400,
            detail="Selenium script cannot be empty",
        )

    # Step 1: Preprocess the Selenium script
    logger.info("Preprocessing Selenium script...")
    preprocessed_text = LocatorParser.preprocess_selenium_script(script_text)
    logger.debug(f"Preprocessed text length: {len(preprocessed_text)} chars")

    # Step 2: Parse the script to extract schema
    try:
        parsed_schema, parse_error = LocatorParser.parse_selenium_script(
            preprocessed_text,
            provider=request.model_provider.value,
        )
    except Exception as e:
        logger.error(f"Failed to parse Selenium script: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse Selenium script: {str(e)}",
        )

    # If parse-only mode, return parsed schema
    if request.parse_only:
        logger.info(f"Parse-only mode: returning {len(parsed_schema)} fields")
        return SeleniumGenerateResponse(
            parsed_schema=parsed_schema,
            parse_error=parse_error,
        )

    # Require parsed fields for generation
    if not parsed_schema:
        detail = "No form fields could be parsed from the Selenium script"
        if parse_error:
            detail += f": {parse_error}"
        raise HTTPException(
            status_code=400,
            detail=detail,
        )

    logger.info(f"Parsed {len(parsed_schema)} fields from Selenium script")

    # Step 3: Convert parsed schema to generator format
    schema_fields = [
        {
            "name": field.get("name", ""),
            "type": field.get("type", "string"),
            "rules": field.get("rules", ""),
            "example": field.get("example", ""),
        }
        for field in parsed_schema
    ]

    # Convert groups if provided
    groups = convert_groups_to_dict(request.groups)

    # Determine record counts
    correct_num = request.correct_num_records
    if correct_num is None:
        correct_num = request.num_records

    # Step 4: Generate data
    logger.info(f"Generating {request.num_records} records from parsed schema")
    generator = create_generator_from_request(request)
    result = generator.generate_data(
        schema_fields=schema_fields,
        num_records=request.num_records,
        correct_num_records=correct_num,
        wrong_num_records=request.wrong_num_records,
        additional_rules=request.additional_rules,
        groups=groups,
    )
    
    logger.info(f"Generated {result['count']} records successfully")

    return SeleniumGenerateResponse(
        data=result["data"],
        count=result["count"],
        parsed_schema=parsed_schema,
        parse_error=parse_error,
    )



@handle_generation_errors("generate_test_data_legacy")
async def generate_test_data_legacy(request: dict) -> Dict[str, Any]:
    """
    Legacy endpoint for backward compatibility with dict-based requests.

    Use /generate with Pydantic models for better validation.
    
    Args:
        request: Dictionary with schema_fields, groups, model_provider, etc.
        
    Returns:
        Dictionary with data and count keys
    """
    schema_fields = request.get("schema_fields", [])
    groups = request.get("groups")
    num_records = request.get("num_records", 5)
    correct_num_records = request.get("correct_num_records", 5)
    wrong_num_records = request.get("wrong_num_records", 0)
    additional_rules = request.get("additional_rules")
    model_provider = request.get("model_provider", "ollama")

    if not schema_fields:
        raise HTTPException(
            status_code=400,
            detail="schema_fields is required and cannot be empty",
        )
    
    logger.info(f"Legacy endpoint: generating {num_records} records with {model_provider}")

    generator = TestDataGenerator(provider=model_provider)
    result = generator.generate_data(
        schema_fields=schema_fields,
        num_records=num_records,
        correct_num_records=correct_num_records,
        wrong_num_records=wrong_num_records,
        additional_rules=additional_rules,
        groups=groups,
    )
    
    logger.info(f"Generated {result['count']} records")
    return {"data": result["data"], "count": result["count"]}