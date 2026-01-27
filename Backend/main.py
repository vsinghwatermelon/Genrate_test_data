"""
Test Data Generator API Entrypoint

FastAPI application serving as the central hub for:
- Selenium-based field extraction
- LLM-powered test data generation
- Group-based validation control
"""

import os
import logging
from typing import Optional

from fastapi import FastAPI, HTTPException, status, UploadFile, File, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Internal imports
from config import get_config
from llm_factory import LLMFactory
from utils.logger import get_logger
from models import (
    GenerateRequest,
    GenerateResponse,
    SeleniumGenerateRequest,
    SeleniumGenerateResponse,
    HealthResponse,
)

# Route imports
from endpoints.parse_clicked_elements import router as parse_router
from endpoints.data_generation import (
    generate_data_from_schema,
    generate_test_data,
    generate_from_selenium,
    generate_test_data_legacy,
)
from endpoints.selenium_field_extraction import extract_fields_from_uploaded_folder
from endpoints.script_execution import execute_selenium_script, list_script_actions

# =============================================================================
# APPLICATION CONFIGURATION
# =============================================================================

config = get_config()
logger = get_logger(__name__)

def setup_app() -> FastAPI:
    """Initialize and configure the FastAPI application."""
    fastapi_app = FastAPI(
        title="Test Data Generator API",
        description="LLM-based test data generation with Selenium integration",
        version="2.1.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )

    # CORS configuration
    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=config.server.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Global Exception Handlers
    @fastapi_app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        logger.warning(f"Validation error: {exc}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc)},
        )

    return fastapi_app

app = setup_app()

# =============================================================================
# ROUTERS
# =============================================================================

app.include_router(parse_router, tags=["Parsing"])

# =============================================================================
# SELENIUM ENDPOINTS
# =============================================================================

@app.post("/generate-data-from-schema", tags=["Selenium"])
async def generate_data_from_schema_endpoint(request: Request):
    """Generate data from a confirmed schema and groups."""
    return await generate_data_from_schema(request)

@app.post("/extract-fields-from-folder", tags=["Selenium"])
async def extract_fields_from_folder(request: Request, file: UploadFile = File(...)):
    """
    Extract form fields from uploaded Selenium script folder.
    
    Accepts a zip containing scripts and locators. Returns extracted schema.
    """
    return await extract_fields_from_uploaded_folder(request, file)

@app.post("/execute-selenium-script", tags=["Selenium"])
async def execute_script(request: Request, file: UploadFile = File(...)):
    """
    Execute uploaded Selenium script and capture all actions.
    """
    return await execute_selenium_script(request, file)

@app.post("/analyze-selenium-script", tags=["Selenium"])
async def analyze_script(request: Request, file: UploadFile = File(...)):
    """
    Analyze Selenium script without execution to list actions.
    """
    return await list_script_actions(request, file)

# =============================================================================
# GENERATION ENDPOINTS
# =============================================================================

@app.post("/generate", response_model=GenerateResponse, tags=["Generation"])
async def generate_test_data_endpoint(request: GenerateRequest):
    """Generate test data using schema-based field definitions."""
    return await generate_test_data(request)

@app.post("/generate-from-selenium", response_model=SeleniumGenerateResponse, tags=["Generation"])
async def generate_from_selenium_endpoint(request: SeleniumGenerateRequest):
    """Generate test data directly from a Selenium script content."""
    return await generate_from_selenium(request)

@app.post("/generate-legacy", tags=["Legacy"])
async def generate_test_data_legacy_endpoint(request: dict):
    """Legacy generation endpoint for backward compatibility."""
    return await generate_test_data_legacy(request)

# =============================================================================
# HEALTH & UTILITIES
# =============================================================================

@app.get("/", tags=["Health"])
async def root():
    """API Root - Basic readiness check."""
    return {"message": "Test Data Generator API - Ready", "version": "2.1.0"}

@app.get("/ping", tags=["Health"])
async def ping():
    """Simple health ping."""
    return {"status": "ok", "message": "pong"}

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check(provider: str = "ollama"):
    """
    Comprehensive health check.
    
    Verifies LLM connectivity for the selected provider.
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
        logger.error(f"Health check failed for {provider}: {e}")
        return HealthResponse(
            status="unhealthy",
            error=str(e),
        )

# =============================================================================
# SERVER RUNNER
# =============================================================================

if __name__ == "__main__":
    logger.info(f"Starting server on {config.server.host}:{config.server.port}")
    uvicorn.run(
        "main:app",
        host=config.server.host,
        port=config.server.port,
        reload=config.server.debug,
    )
