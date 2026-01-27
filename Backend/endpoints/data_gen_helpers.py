"""
Data Generation Helper Utilities

Centralizes repeated conversion patterns and error handling for data generation
endpoints. These helpers reduce code duplication and ensure consistent behavior
across different generation entry points.
"""

import logging
from typing import List, Dict, Any, Optional, Union
from functools import wraps
from fastapi import HTTPException

from models import SchemaField, GroupConfig, GenerateRequest, SeleniumGenerateRequest
from data_generator import TestDataGenerator

logger = logging.getLogger(__name__)


# ============================================================================
# MODEL CONVERSION
# ============================================================================

def convert_schema_to_dict(schema_fields: List[SchemaField]) -> List[Dict[str, Any]]:
    """
    Convert Pydantic schema models to dictionary format for generator.
    
    The TestDataGenerator expects plain dictionaries, but FastAPI endpoints
    receive Pydantic models for validation. This bridges that gap.
    
    Args:
        schema_fields: List of SchemaField Pydantic models
        
    Returns:
        List of dictionaries suitable for TestDataGenerator
        
    Example:
        >>> fields = [SchemaField(name="email", type="email", rules="valid", example="test@example.com")]
        >>> dicts = convert_schema_to_dict(fields)
        >>> assert dicts[0]["name"] == "email"
    """
    return [field.model_dump(exclude_none=True) for field in schema_fields]


def convert_groups_to_dict(groups: Optional[List[GroupConfig]]) -> Optional[List[Dict[str, Any]]]:
    """
    Convert Pydantic group models to dictionary format for generator.
    
    Groups are optional in the API, so this handles None/empty cases gracefully.
    
    Args:
        groups: Optional list of GroupConfig Pydantic models
        
    Returns:
        List of dictionaries or None if groups is None/empty
    """
    if not groups:
        return None
    return [group.model_dump() for group in groups]


# ============================================================================
# GENERATOR INITIALIZATION
# ============================================================================

def create_generator_from_request(
    request: Union[GenerateRequest, SeleniumGenerateRequest]
) -> TestDataGenerator:
    """
    Create TestDataGenerator from request configuration.
    
    Centralizes generator creation logic to ensure consistent initialization
    across all generation endpoints. Handles both enum and string providers.
    
    Args:
        request: Generation request with model_provider attribute
        
    Returns:
        Configured TestDataGenerator instance
        
    Example:
        >>> from models import GenerateRequest, ModelProvider
        >>> req = GenerateRequest(schema_fields=[], model_provider=ModelProvider.GROQ)
        >>> gen = create_generator_from_request(req)
        >>> assert gen.provider == "groq"
    """
    # Extract provider value (handles both enum and string)
    provider = getattr(request.model_provider, 'value', str(request.model_provider))
    logger.debug(f"Creating TestDataGenerator with provider: {provider}")
    return TestDataGenerator(provider=provider)


# ============================================================================
# ERROR HANDLING
# ============================================================================

def handle_generation_errors(endpoint_name: str):
    """
    Decorator to standardize error handling across data generation endpoints.
    
    Wraps endpoint functions to catch exceptions, log them properly, and
    convert them to HTTPExceptions with appropriate status codes. Preserves
    existing HTTPExceptions without modification.
    
    Args:
        endpoint_name: Name of endpoint for logging context
        
    Returns:
        Decorator function
        
    Example:
        >>> @handle_generation_errors("generate_data")
        >>> async def my_endpoint(request):
        >>>     return {"data": []}
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except HTTPException:
                # Already has proper status code, re-raise as-is
                raise
            except Exception as e:
                logger.error(
                    f"Error in {endpoint_name}: {str(e)}",
                    exc_info=True
                )
                raise HTTPException(
                    status_code=500,
                    detail=f"Error in {endpoint_name}: {str(e)}"
                )
        return wrapper
    return decorator
