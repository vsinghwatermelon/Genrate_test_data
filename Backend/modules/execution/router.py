import logging
import tempfile
from fastapi import APIRouter, Request, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from modules.execution.engine.executor import SeleniumScriptExecutor
from modules.shared.json_utils import make_json_serializable
from modules.shared.common_utils import extract_zip_file, parse_form_bool

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/execute")
@router.post("/execute-selenium-script")
async def execute_script(request: Request, file: UploadFile = File(...)):
    """Executes a zipped Selenium script and tracks interactions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            logger.info("New execution request received")
            
            form = await request.form()
            headless = parse_form_bool(form.get('headless'), default=True)
            use_wire = parse_form_bool(form.get('use_wire'), default=False)
            
            # Extract and validate the uploaded package
            zip_path = await extract_zip_file(file, tmpdir)
            
            # Trigger the execution engine
            result = SeleniumScriptExecutor.execute_from_zip(
                zip_path=zip_path,
                headless=headless,
                use_wire=use_wire
            )
            
            if not result.get('success'):
                raise HTTPException(status_code=400, detail=result.get('error'))
            
            # Return sanitized results (removes non-serializable objects)
            return JSONResponse(content={
                "success": True,
                "data": make_json_serializable(result)
            })
            
        except HTTPException: raise
        except Exception as e:
            logger.error(f"Execution failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
