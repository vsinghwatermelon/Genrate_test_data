"""
Script Execution Endpoint

Endpoint for uploading Selenium script folders and executing them with action tracking.
"""

import os
import json
import tempfile
import logging
from typing import Dict, Any
from fastapi import Request, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

from utils.script_executor import SeleniumScriptExecutor
from utils.json_serializer import make_json_serializable

logger = logging.getLogger(__name__)


async def execute_selenium_script(
    request: Request,
    file: UploadFile = File(...)
) -> Dict[str, Any]:
    """
    Execute uploaded Selenium script and track all clicks and field inputs
    
    This endpoint:
    1. Receives a zip file containing a Selenium script
    2. Extracts and identifies the main script and locator files
    3. Executes the script with action tracking
    4. Returns all clicked buttons and filled fields
    
    Args:
        request: FastAPI request
        file: Uploaded zip file containing Selenium script and configs
    
    Returns:
        Dictionary with tracked actions (clicks, field inputs, etc.)
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            logger.info("="*80)
            logger.info("[ENDPOINT] Execute Selenium Script")
            logger.info("="*80)
            
            # Get parameters from form data
            form_data = await request.form()
            headless = form_data.get('headless', 'true').lower() == 'true'
            use_wire = form_data.get('use_wire', 'false').lower() == 'true'
            
            logger.info(f"Received script execution request (headless={headless}, use_wire={use_wire})")
            
            # Step 1: Save uploaded file
            logger.info("[STEP 1] Saving uploaded file...")
            zip_path = os.path.join(tmpdir, "uploaded_script.zip")
            
            contents = await file.read()
            file_size_mb = len(contents) / (1024 * 1024)
            
            # Validate file size (max 100MB)
            if file_size_mb > 100:
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large ({file_size_mb:.2f}MB). Maximum allowed: 100MB"
                )
            
            with open(zip_path, 'wb') as f:
                f.write(contents)
            
            logger.info(f"[STEP 1] ✓ Saved {file_size_mb:.2f}MB to {zip_path}")
            
            # Step 2: Execute script with tracking
            # The executor will handle extraction to a temporary directory,
            # set sys.path priority, and manage module isolation.
            logger.info("[STEP 2] Executing script...")
            result = SeleniumScriptExecutor.execute_from_zip(
                zip_path=zip_path,
                headless=headless,
                use_wire=use_wire
            )
            
            if not result.get('success'):
                error_msg = result.get('error', 'Unknown error')
                logger.error(f"Script execution failed: {error_msg}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Script execution failed: {error_msg}"
                )
            
            logger.info("[ENDPOINT] ✓ Script execution completed successfully")
            logger.info("="*80)
            
            # Clean the result to make it JSON-serializable
            # (handles bytes from selenium-wire API requests)
            logger.debug("Sanitizing result for JSON serialization...")
            cleaned_result = make_json_serializable(result)

            # Return tracked actions
            return JSONResponse(content={
                "success": True,
                "message": "Script executed successfully",
                "data": cleaned_result
            })
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in execute_selenium_script endpoint: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to execute script: {str(e)}"
            )


async def list_script_actions(
    request: Request,
    file: UploadFile = File(...)
) -> Dict[str, Any]:
    """
    Analyze Selenium script without execution - just list expected actions
    
    This is a lightweight alternative that parses the script to show
    what actions it will perform without actually running it.
    
    Args:
        request: FastAPI request
        file: Uploaded zip file containing Selenium script
    
    Returns:
        Dictionary with parsed actions from script
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            import zipfile
            from utils.locator_parser import ScriptAnalyzer
            
            # Save and extract zip
            zip_path = os.path.join(tmpdir, "script.zip")
            contents = await file.read()
            with open(zip_path, 'wb') as f:
                f.write(contents)
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(tmpdir)
            
            # Find script
            main_script, locator_files = ScriptAnalyzer.identify_script_files(tmpdir)
            
            if not main_script:
                raise HTTPException(
                    status_code=400,
                    detail="No Selenium script found in uploaded folder"
                )
            
            # Read script content
            with open(main_script, 'r', encoding='utf-8') as f:
                script_content = f.read()
            
            # Extract metadata
            url = ScriptAnalyzer.extract_url(script_content)
            actions = ScriptAnalyzer.extract_actions(script_content)
            locator_refs = ScriptAnalyzer.extract_locator_references(script_content)
            
            return JSONResponse(content={
                "success": True,
                "message": "Script analyzed successfully",
                "data": {
                    "script_name": os.path.basename(main_script),
                    "target_url": url,
                    "actions": actions,
                    "locator_references": locator_refs,
                    "total_actions": len(actions),
                    "locator_files": [os.path.basename(f) for f in locator_files]
                }
            })
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error analyzing script: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to analyze script: {str(e)}"
            )
