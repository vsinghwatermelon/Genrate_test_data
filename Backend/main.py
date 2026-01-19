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
import logging

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

# Configure logging
if config.generation.enable_logging:
    logging.basicConfig(
        level=logging.DEBUG if os.getenv("DEBUG_LOGGING", "false").lower() == "true" else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    logger.info("Logging enabled")
else:
    logging.basicConfig(level=logging.WARNING)
    logger = logging.getLogger(__name__)
    logger.info("Logging disabled")

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

from endpoints.data_generation import (
    generate_data_from_schema,
    generate_test_data,
    generate_from_selenium,
    generate_test_data_legacy,
)

# Import selenium endpoints
from endpoints.selenium_field_extraction import extract_fields_from_uploaded_folder
from endpoints.script_execution import execute_selenium_script, list_script_actions


async def value_error_handler(request, exc: ValueError):
    """Handle validation errors."""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)},
    )

@app.post("/generate-data-from-schema", tags=["Selenium"])
async def generate_data_from_schema_endpoint(request: Request):
    return await generate_data_from_schema(request)


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
async def generate_test_data_endpoint(request: GenerateRequest):
    return await generate_test_data(request)


@app.post("/generate-from-selenium", response_model=SeleniumGenerateResponse, tags=["Generation"])
async def generate_from_selenium_endpoint(request: SeleniumGenerateRequest):
    return await generate_from_selenium(request)


# =============================================================================
# LEGACY ENDPOINTS (Backward Compatibility)
# =============================================================================

@app.post("/generate-legacy", tags=["Legacy"])
async def generate_test_data_legacy_endpoint(request: dict):
    return await generate_test_data_legacy(request)


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
