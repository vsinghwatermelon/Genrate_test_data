import logging
from fastapi import APIRouter, Request, HTTPException
from modules.generation.logic import DataService
from modules.shared.models import LLMProvider

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/generate")
@router.post("/generate-test-data")
async def generate_data(request: Request):
    """Generates test data based on a schema and group configuration."""
    try:
        body = await request.json()
        schema = body.get("schema_fields") or body.get("schema")
        groups = body.get("groups")
        provider = body.get("model_provider", LLMProvider.OLLAMA)
        rules = body.get("additional_rules")

        if not schema:
            raise HTTPException(status_code=400, detail="Missing schema definition.")
        
        # Initialize service and generate
        service = DataService(provider=provider)
        result = service.generate(schema, groups or [], rules)
        
        return {
            "success": True,
            "data": result["data"],
            "count": result["count"],
            "groups": result["groups"]
        }
        
    except Exception as e:
        logger.error(f"Generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
