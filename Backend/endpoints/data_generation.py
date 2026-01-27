"""
Data Generation Endpoints

Provides multiple entry points for generating test data using AI.
Supports schema-based generation, Selenium script inference, and 
legacy compatibility modes.
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


# ============================================================================
# SECTION 1: SCHEMA-BASED GENERATION (FRONTEND / CUSTOM)
# ============================================================================

@handle_generation_errors("generate_data_from_schema")
async def generate_data_from_schema(request: Request) -> Dict[str, Any]:
    """
    Generate test data from an edited schema and group configuration.
    
    This endpoint is primarily used by the frontend to generate data after
    the user has reviewed or edited the inferred schema.
    
    Expected JSON Body:
        {
            "schema": [...],       # List of field definitions
            "groups": [...],       # Group configurations
            "ai_model": "groq"|... # Model provider to use
        }
    """
    body = await request.json()
    schema = body.get("schema")
    groups = body.get("groups")
    ai_model = body.get("ai_model", "ollama")

    if not schema:
        raise HTTPException(
            status_code=400, 
            detail="Missing schema definition. Please provide fields to generate."
        )
    
    logger.info(f"Generating data using {ai_model} for {len(schema)} fields")
    
    generator = TestDataGenerator(provider=ai_model)
    
    # Calculate total records needed across all groups
    num_records = sum(g.get('count', 0) for g in groups) if groups else 5
    
    result = generator.generate_data(
        schema_fields=schema,
        groups=groups,
        num_records=num_records,
        additional_rules=None
    )
    
    logger.info(f"Successfully generated {len(result['data'])} records")
    return {"test_data": result['data']}


# ============================================================================
# SECTION 2: PYDANTIC-VALIDATED GENERATION
# ============================================================================

@handle_generation_errors("generate_test_data")
async def generate_test_data(request: GenerateRequest) -> GenerateResponse:
    """
    Generate test data based on a structured schema definition.

    Supports both record-based counts (legacy mode) and group-based mode
    for granular control over per-field validity.
    """
    logger.info(
        f"Generating test data: {len(request.schema_fields)} fields, "
        f"{request.num_records} records using {request.model_provider.value}"
    )
    
    # Convert Pydantic models to dictionaries for the logic layer
    schema_fields = convert_schema_to_dict(request.schema_fields)
    groups = convert_groups_to_dict(request.groups)

    # Initialize generator based on request configuration
    generator = create_generator_from_request(request)

    # Perform generation
    result = generator.generate_data(
        schema_fields=schema_fields,
        num_records=request.num_records,
        correct_num_records=request.correct_num_records,
        wrong_num_records=request.wrong_num_records,
        additional_rules=request.additional_rules,
        groups=groups,
    )
    
    logger.info(f"Generation successful. Produced {result['count']} records.")

    return GenerateResponse(
        data=result["data"],
        count=result["count"],
        groups=result.get("groups"),
    )


# ============================================================================
# SECTION 3: SELENIUM-BASED GENERATION
# ============================================================================

@handle_generation_errors("generate_from_selenium")
async def generate_from_selenium(request: SeleniumGenerateRequest) -> SeleniumGenerateResponse:
    """
    Extract form schema from a Selenium script and generate test data.

    Infers field names, types, and validation rules from automation code,
    then uses that information to produce matching test data.
    """
    script_text = request.selenium_script.strip()

    if not script_text:
        raise HTTPException(
            status_code=400,
            detail="Selenium script cannot be empty. Please provide valid automation code.",
        )

    # 1. Preprocess script to clean up common formatting issues
    logger.info("Preprocessing Selenium script for analysis...")
    preprocessed_text = LocatorParser.preprocess_selenium_script(script_text)

    # 2. Extract schema from script using LLM analysis
    try:
        parsed_schema, parse_error = LocatorParser.parse_selenium_script(
            preprocessed_text,
            provider=request.model_provider.value,
        )
    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze Selenium script: {str(e)}",
        )

    # Return immediately if only analysis was requested
    if request.parse_only:
        logger.info(f"Analysis complete. Found {len(parsed_schema)} fields.")
        return SeleniumGenerateResponse(
            parsed_schema=parsed_schema,
            parse_error=parse_error,
        )

    # Validation: Ensure we actually found fields to generate for
    if not parsed_schema:
        failure_reason = "No form fields could be inferred from the Selenium script"
        if parse_error:
            failure_reason += f": {parse_error}"
        raise HTTPException(
            status_code=400,
            detail=failure_reason,
        )

    logger.info(f"Found {len(parsed_schema)} fields. Proceeding to generation...")

    # 3. Format inferred schema for the generator
    schema_fields = [
        {
            "name": field.get("name", ""),
            "type": field.get("type", "string"),
            "rules": field.get("rules", ""),
            "example": field.get("example", ""),
        }
        for field in parsed_schema
    ]

    # Handle record count logic (legacy vs group)
    correct_num = request.correct_num_records if request.correct_num_records is not None else request.num_records
    groups = convert_groups_to_dict(request.groups)

    # 4. Generate the actual test data
    generator = create_generator_from_request(request)
    result = generator.generate_data(
        schema_fields=schema_fields,
        num_records=request.num_records,
        correct_num_records=correct_num,
        wrong_num_records=request.wrong_num_records,
        additional_rules=request.additional_rules,
        groups=groups,
    )
    
    logger.info(f"Production complete. Generated {result['count']} records.")

    return SeleniumGenerateResponse(
        data=result["data"],
        count=result["count"],
        parsed_schema=parsed_schema,
        parse_error=parse_error,
    )


# ============================================================================
# SECTION 4: LEGACY COMPATIBILITY
# ============================================================================

@handle_generation_errors("generate_test_data_legacy")
async def generate_test_data_legacy(request: dict) -> Dict[str, Any]:
    """
    Backward-compatible endpoint for non-validated requests.

    Warning: This endpoint relies on raw dictionaries. Use /generate 
    with structured models whenever possible for better reliability.
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
            detail="schema_fields is required and cannot be empty.",
        )
    
    logger.info(f"Legacy generation request started for {num_records} records.")

    generator = TestDataGenerator(provider=model_provider)
    result = generator.generate_data(
        schema_fields=schema_fields,
        num_records=num_records,
        correct_num_records=correct_num_records,
        wrong_num_records=wrong_num_records,
        additional_rules=additional_rules,
        groups=groups,
    )
    
    logger.info(f"Legacy generation complete. Generated {result['count']} records.")
    return {"data": result["data"], "count": result["count"]}