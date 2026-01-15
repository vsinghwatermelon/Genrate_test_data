"""
Script Execution Endpoint

Endpoint for uploading Selenium script folders and executing them with action tracking.
"""

import os
import tempfile
import logging
from typing import Dict, Any
from fastapi import Request, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

from utils.script_executor import SeleniumScriptExecutor

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
            print("="*80)
            print("[ENDPOINT] Execute Selenium Script")
            print("="*80)
            
            # Get parameters from form data
            form_data = await request.form()
            headless = form_data.get('headless', 'true').lower() == 'true'
            
            logger.info(f"Received script execution request (headless={headless})")
            
            # Step 1: Save uploaded file
            print("\n[STEP 1] Saving uploaded file...")
            zip_path = os.path.join(tmpdir, "uploaded_script.zip")
            
            contents = await file.read()
            with open(zip_path, 'wb') as f:
                f.write(contents)
            
            file_size_mb = len(contents) / (1024 * 1024)
            print(f"[STEP 1] ✓ Saved {file_size_mb:.2f} MB to {zip_path}")
            logger.info(f"Saved uploaded file: {file_size_mb:.2f} MB")
            
            # Step 2: Execute script with tracking
            print("\n[STEP 2] Executing script...")
            result = SeleniumScriptExecutor.execute_from_zip(
                zip_path=zip_path,
                headless=headless
            )
            
            if not result.get('success'):
                logger.error(f"Script execution failed: {result.get('error')}")
                raise HTTPException(
                    status_code=400,
                    detail=result.get('error', 'Script execution failed')
                )
            
            print("\n[ENDPOINT] ✓ Script execution completed successfully")
            print("="*80 + "\n")
            
            # Return tracked actions
            return JSONResponse(content={
                "success": True,
                "message": "Script executed successfully",
                "data": result
            })
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in execute_selenium_script endpoint: {str(e)}")
            import traceback
            traceback.print_exc()
            
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
            logger.error(f"Error analyzing script: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to analyze script: {str(e)}"
            )
