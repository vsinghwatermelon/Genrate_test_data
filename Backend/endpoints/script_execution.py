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
            use_wire = form_data.get('use_wire', 'false').lower() == 'true'
            
            logger.info(f"Received script execution request (headless={headless}, use_wire={use_wire})")
            
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
            # The executor will handle extraction to a temporary directory,
            # set sys.path priority, and manage module isolation.
            print("\n[STEP 2] Executing script...")
            result = SeleniumScriptExecutor.execute_from_zip(
                zip_path=zip_path,
                headless=headless,
                use_wire=use_wire
            )
            
            if not result.get('success'):
                logger.error(f"Script execution failed: {result.get('error')}")
                raise HTTPException(
                    status_code=400,
                    detail=result.get('error', 'Script execution failed')
                )
            
            print("\n[ENDPOINT] ✓ Script execution completed successfully")
            print("="*80 + "\n")
            
            # Helper to sanitize non-JSON-serializable data (like bytes from selenium-wire)
            def make_json_serializable(obj):
                if isinstance(obj, bytes):
                    # Try to decompress if it's gzip-compressed
                    import gzip
                    import base64
                    
                    # Strategy 1: Check if gzip-compressed (starts with magic bytes 0x1f 0x8b)
                    if len(obj) > 2 and obj[0:2] == b'\x1f\x8b':
                        try:
                            obj = gzip.decompress(obj)
                        except:
                            pass
                    
                    # Strategy 2: UTF-8 decoding (most common for JSON APIs)
                    try:
                        decoded = obj.decode('utf-8')
                        # If it looks like JSON, try to parse and return the object
                        if decoded.strip().startswith(('{', '[')):
                            try:
                                return json.loads(decoded)
                            except:
                                pass
                        return decoded
                    except UnicodeDecodeError:
                        pass
                    
                    # Strategy 3: Latin-1 (handles all byte values but might give garbled text)
                    # We'll skip this for now since it produces garbled output
                    
                    # Strategy 4: For binary data, represent as base64
                    try:
                        return f"[Binary data - Base64: {base64.b64encode(obj).decode('ascii')[:200]}...]"
                    except:
                        return f"<bytes: {len(obj)}>"
                        
                elif isinstance(obj, dict):
                    return {k: make_json_serializable(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [make_json_serializable(i) for i in obj]
                elif isinstance(obj, tuple):
                    return tuple(make_json_serializable(i) for i in obj)
                elif isinstance(obj, set):
                    return [make_json_serializable(i) for i in obj]
                else:
                    return obj

            # Clean the result before identifying it as JSON
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
