"""
Script Execution Endpoint

Handles the execution of uploaded Selenium scripts with live action tracking.
Allows users to upload a ZIP containing scripts and locators, executes them 
in a controlled environment, and returns all recorded interactions.
"""

import os
import json
import tempfile
import logging
from typing import Dict, Any, Tuple
from fastapi import Request, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

from utils.script_executor import SeleniumScriptExecutor
from utils.json_utils import make_json_serializable
from endpoints.common import extract_zip_file, parse_form_bool

logger = logging.getLogger(__name__)


# ============================================================================
# SECTION 1: EXECUTION ENDPOINTS
# ============================================================================

async def execute_selenium_script(
    request: Request,
    file: UploadFile = File(...)
) -> JSONResponse:
    """
    Execute an uploaded Selenium script and record all interaction data.
    
    Processing Steps:
    1. Validate and extract the uploaded ZIP configuration.
    2. Parse execution flags (headless mode, API interception).
    3. Run the script using the SeleniumScriptExecutor.
    4. Serialize and return the resulting action logs.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            # 1. Initialize execution metadata
            logger.info("=" * 60)
            logger.info("[EXECUTION] New Selenium script execution request")
            logger.info("=" * 60)
            
            headless, use_wire = await _parse_execution_params(request)
            logger.info(f"Target settings: headless={headless}, api_interception={use_wire}")
            
            # 2. File handling and validation
            # We use common utility to ensure consistent size checks and extraction logic
            logger.info("Extracting script package...")
            zip_path = await extract_zip_file(file, tmpdir)
            
            # 3. Core execution logic
            # This triggers the dynamic module loading and tracking proxy system
            logger.info("Starting script execution engine...")
            result = SeleniumScriptExecutor.execute_from_zip(
                zip_path=zip_path,
                headless=headless,
                use_wire=use_wire
            )
            
            # 4. Result validation
            if not result.get('success'):
                reason = result.get('error', 'Execution interrupted by an internal fault')
                logger.error(f"Script failure detected: {reason}")
                raise HTTPException(status_code=400, detail=f"Script failed: {reason}")
            
            logger.info("Execution complete. Finalizing result set...")
            
            # 5. Serialization and response
            # Cleanup bytes and non-serializable objects (especially from API interception)
            sanitized_data = make_json_serializable(result)

            return JSONResponse(content={
                "success": True,
                "message": "Script execution completed successfully.",
                "data": sanitized_data
            })
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Endpoint fault in execute_selenium_script: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Internal server error during script execution: {str(e)}"
            )


async def list_script_actions(
    request: Request,
    file: UploadFile = File(...)
) -> JSONResponse:
    """
    Analyze a Selenium script code without performing actual execution.
    
    Parses the script to infer:
    - Target URL
    - Sequential list of actions (clicks, inputs, etc.)
    - Locator usage and external file dependencies
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            import zipfile
            from utils.locator_parser import ScriptAnalyzer
            
            # Save and extract source package
            zip_path = await extract_zip_file(file, tmpdir)
            
            # Identify core components
            main_script, locator_files = ScriptAnalyzer.identify_script_files(tmpdir)
            
            if not main_script:
                raise HTTPException(
                    status_code=400,
                    detail="No valid Python Selenium script found in the uploaded package."
                )
            
            # Analyze source code
            with open(main_script, 'r', encoding='utf-8') as f:
                content = f.read()
            
            metadata = {
                "script_name": os.path.basename(main_script),
                "target_url": ScriptAnalyzer.extract_url(content),
                "actions": ScriptAnalyzer.extract_actions(content),
                "locator_references": ScriptAnalyzer.extract_locator_references(content),
                "locator_files": [os.path.basename(f) for f in locator_files]
            }
            
            logger.info(f"Analysis successful for {metadata['script_name']}.")
            
            return JSONResponse(content={
                "success": True,
                "message": "Script analysis complete.",
                "data": metadata
            })
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to analyze script package: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Critical error during script analysis: {str(e)}"
            )


# ============================================================================
# SECTION 2: HELPER UTILITIES
# ============================================================================

async def _parse_execution_params(request: Request) -> Tuple[bool, bool]:
    """Parse execution flags from form-encoded request data."""
    try:
        form = await request.form()
        headless = parse_form_bool(form.get('headless'), default=True)
        use_wire = parse_form_bool(form.get('use_wire'), default=False)
        return headless, use_wire
    except Exception:
        # Fallback to defaults if form parsing fails
        return True, False
