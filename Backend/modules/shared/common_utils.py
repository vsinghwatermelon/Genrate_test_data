import logging
import os
import zipfile
from typing import Any
from fastapi import UploadFile, HTTPException
from modules.shared.llm import LLMService
from modules.shared.json_utils import parse_llm_json_response

logger = logging.getLogger(__name__)

async def extract_zip_file(file: UploadFile, tmpdir: str) -> str:
    """Extracts uploaded zip to target directory after basic size check."""
    zip_path = os.path.join(tmpdir, "upload.zip")
    content = await file.read()
    
    if len(content) > 100 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File exceeds 100MB limit")
        
    try:
        with open(zip_path, "wb") as f: f.write(content)
        with zipfile.ZipFile(zip_path, 'r') as z: z.extractall(tmpdir)
        return zip_path
    except Exception as e:
        logger.error(f"ZIP error: {e}")
        raise HTTPException(status_code=400, detail="Invalid package format")

def get_llm_with_fallback(preferred: str = "groq") -> Any:
    """Returns LLM client with automatic fallback logic."""
    try:
        return LLMService.get_llm(preferred)
    except Exception:
        logger.warning(f"Fallback to ollama triggered")
        return LLMService.get_llm("ollama")

def parse_form_bool(value: Any, default: bool = False) -> bool:
    """Safely parse boolean from form data (strings or raw bools)."""
    if value is None: return default
    if isinstance(value, bool): return value
    if isinstance(value, str):
        return value.lower() in ('true', '1', 'yes', 'on')
    return default
