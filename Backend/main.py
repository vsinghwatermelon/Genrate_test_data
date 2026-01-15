# =============================================================================
# NEW ENDPOINT: Generate Data from Confirmed Schema & Groups
# =============================================================================

from fastapi import Request


"""
Test Data Generator API

FastAPI application providing endpoints for generating test data
using LLM-based generation with support for:
- Single table generation
- Selenium script parsing
- Group-based generation with per-field validity control
"""

import traceback
import re
from typing import Optional

from fastapi import FastAPI, HTTPException, status, UploadFile, File
from fastapi.responses import JSONResponse
import zipfile
import io
import tempfile
import os

from config import get_config
from data_generator import TestDataGenerator
from llm_factory import LLMFactory
from selenium_llm_parser import parse_selenium_script
from selenium_extractor import preprocess_selenium_script, download_html_from_script, extract_fields_from_html
from models import (
    GenerateRequest,
    GenerateResponse,
    SeleniumGenerateRequest,
    SeleniumGenerateResponse,
    HealthResponse,
    LLMProvider,
)
from endpoints.parse_clicked_elements import router as parse_router


# =============================================================================
# APPLICATION SETUP
# =============================================================================

config = get_config()

app = FastAPI()

# Add CORS middleware to allow frontend requests
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Handle OPTIONS requests for CORS preflight
@app.options("/{path:path}")
async def options_handler(path: str):
    """Handle CORS preflight requests."""
    return {"message": "OK"}

# Include routers
app.include_router(parse_router, tags=["Parsing"])

# =============================================================================
# NEW ENDPOINT: Upload Selenium Folder and Extract HTML Fields
# =============================================================================

from fastapi import Request
from endpoints.selenium_field_extraction import extract_fields_from_uploaded_folder
from endpoints.script_execution import execute_selenium_script, list_script_actions

@app.post("/extract-fields-from-folder", tags=["Selenium"])
async def extract_fields_from_folder(request: Request, file: UploadFile = File(...)):
    """
    Extract form fields from uploaded Selenium script folder.
    
    Accepts a zipped folder containing:
    - Selenium/automation scripts (any .py file with driver.get())
    - Locator configuration files (any format: .py, .json, .yaml)
    
    Dynamically:
    - Identifies scripts and locators
    - Extracts target URL and actions
    - Navigates website and captures HTML
    - Extracts all form fields
    - Generates user-editable schema using LLM or rules
    
    Returns comprehensive field data and schema for frontend editing.
    """
    return await extract_fields_from_uploaded_folder(request, file)


@app.post("/execute-selenium-script", tags=["Selenium"])
async def execute_script(request: Request, file: UploadFile = File(...)):
    """
    Execute uploaded Selenium script and track all actions.
    
    This endpoint:
    - Accepts a zip file with Selenium script and locator configs
    - Executes the script with action tracking
    - Logs all clicked buttons and filled fields
    - Returns detailed information about all interactions
    
    Query Parameters:
    - headless (optional): Run browser in headless mode (default: true)
    
    Returns tracked actions including clicks and field inputs.
    """
    return await execute_selenium_script(request, file)


@app.post("/analyze-selenium-script", tags=["Selenium"])
async def analyze_script(request: Request, file: UploadFile = File(...)):
    """
    Analyze Selenium script without execution.
    
    Lightweight endpoint that parses the script to show expected actions
    without actually running the browser automation.
    
    Returns script metadata, target URL, and list of actions.
    """
    return await list_script_actions(request, file)


async def value_error_handler(request, exc: ValueError):
    """Handle validation errors."""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)},
    )

@app.post("/generate-data-from-schema", tags=["Selenium"])
async def generate_data_from_schema(request: Request):
    """
    Accepts edited schema and group config from frontend, generates test data accordingly.
    Request JSON: { schema: [...], groups: [...], ai_model: "groq"|"ollama" }
    """
    try:
        body = await request.json()
        schema = body.get("schema")
        groups = body.get("groups")
        ai_model = body.get("ai_model", "ollama")
        if not schema:
            raise HTTPException(status_code=400, detail="Missing schema definition.")
        generator = TestDataGenerator(provider=ai_model)
        num_records = sum(g.get('count', 0) for g in groups) if groups else 5
        result = generator.generate_data(
            schema_fields=schema,
            groups=groups,
            num_records=num_records,
            additional_rules=None
        )
        return {"test_data": result['data']}
    except Exception as e:
        print(f"[ERROR] Data generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Data generation failed: {e}")

@app.get("/", tags=["Health"])
async def root():
    """Root endpoint - API readiness check."""
    return {"message": "Test Data Generator API - Ready", "version": "2.0.0"}


@app.get("/ping", tags=["Health"])
async def ping():
    """Simple ping endpoint for frontend health checks."""
    return {"status": "ok", "message": "pong"}


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check(provider: str = "ollama"):
    """
    Health check endpoint.
    
    Performs a minimal LLM invocation to verify connectivity.
    
    Args:
        provider: LLM provider to check ("ollama" or "groq")
    """
    try:
        llm = LLMFactory.create_llm(provider=provider)
        llm.invoke("test")
        
        return HealthResponse(
            status="healthy",
            ollama="connected" if provider == "ollama" else None,
            groq="connected" if provider == "groq" else None,
            model=llm.model_name,
        )
    except Exception as e:
        return HealthResponse(
            status="unhealthy",
            error=str(e),
        )


@app.post("/generate", response_model=GenerateResponse, tags=["Generation"])
async def generate_test_data(request: GenerateRequest):
    """
    Generate test data based on schema definition.
    
    Supports both legacy mode (correct/wrong record counts) and
    group-based mode for fine-grained per-field validity control.
    
    Args:
        request: Generation request with schema fields and configuration
        
    Returns:
        Generated data records with count
    """
    try:
        # Convert Pydantic models to dicts for the generator
        schema_fields = [field.model_dump(exclude_none=True) for field in request.schema_fields]
        
        # Convert groups if provided
        groups = None
        if request.groups:
            groups = [group.model_dump() for group in request.groups]
        
        # Create generator
        generator = TestDataGenerator(provider=request.model_provider.value)
        
        # Generate data
        result = generator.generate_data(
            schema_fields=schema_fields,
            num_records=request.num_records,
            correct_num_records=request.correct_num_records,
            wrong_num_records=request.wrong_num_records,
            additional_rules=request.additional_rules,
            groups=groups,
        )
        
        return GenerateResponse(
            data=result["data"],
            count=result["count"],
            groups=result.get("groups"),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating data: {str(e)}",
        )


@app.post("/generate-from-selenium", response_model=SeleniumGenerateResponse, tags=["Generation"])
async def generate_from_selenium(request: SeleniumGenerateRequest):
    """
    Parse a Selenium script and generate test data.
    
    Extracts form field definitions from a Selenium automation script,
    then generates test data based on the inferred schema.
    
    Args:
        request: Selenium script and generation configuration
        
    Returns:
        Generated data with parsed schema information
    """
    try:
        script_text = request.selenium_script.strip()
        
        if not script_text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
            preprocessed_text = preprocess_selenium_script(script_text)
            )
        
        # Step 1: Preprocess the Selenium script
        print("Preprocessing Selenium script...")
        preprocessed_text = preprocess_selenium_script(script_text)
        print(f"Preprocessed text length: {len(preprocessed_text)} chars")
        
        # Step 2: Parse the script to extract schema
        try:
            parsed_schema, parse_error = parse_selenium_script(
                preprocessed_text, 
                provider=request.model_provider.value,
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to parse Selenium script: {str(e)}",
            )
        
        # If parse-only mode, return parsed schema
        if request.parse_only:
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
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=detail,
            )
        
        print(f"Parsed {len(parsed_schema)} fields from Selenium script")
        
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
        groups = None
        if request.groups:
            groups = [group.model_dump() for group in request.groups]
        
        # Determine record counts
        correct_num = request.correct_num_records
        if correct_num is None:
            correct_num = request.num_records
        
        # Step 4: Generate data
        generator = TestDataGenerator(provider=request.model_provider.value)
        result = generator.generate_data(
            schema_fields=schema_fields,
            num_records=request.num_records,
            correct_num_records=correct_num,
            wrong_num_records=request.wrong_num_records,
            additional_rules=request.additional_rules,
            groups=groups,
        )
        
        return SeleniumGenerateResponse(
            data=result["data"],
            count=result["count"],
            parsed_schema=parsed_schema,
            parse_error=parse_error,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating from Selenium script: {str(e)}",
        )


# =============================================================================
# LEGACY ENDPOINTS (Backward Compatibility)
# =============================================================================

@app.post("/generate-legacy", tags=["Legacy"])
async def generate_test_data_legacy(request: dict):
    """
    Legacy endpoint for backward compatibility with dict-based requests.
    
    Use /generate with Pydantic models for better validation.
    """
    try:
        schema_fields = request.get("schema_fields", [])
        groups = request.get("groups")
        num_records = request.get("num_records", 5)
        correct_num_records = request.get("correct_num_records", 5)
        wrong_num_records = request.get("wrong_num_records", 0)
        additional_rules = request.get("additional_rules")
        model_provider = request.get("model_provider", "ollama")
        
        if not schema_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="schema_fields is required and cannot be empty",
            )
        
        generator = TestDataGenerator(provider=model_provider)
        result = generator.generate_data(
            schema_fields=schema_fields,
            num_records=num_records,
            correct_num_records=correct_num_records,
            wrong_num_records=wrong_num_records,
            additional_rules=additional_rules,
            groups=groups,
        )
        
        return {"data": result["data"], "count": result["count"]}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error: {str(e)}",
        )


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=config.server.host,
        port=config.server.port,
        reload=config.server.debug,
    )
