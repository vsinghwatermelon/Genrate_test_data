"""
Pydantic Models for Request/Response Validation

This module defines all data models used for API validation,
providing type safety and automatic documentation.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any, Union
from enum import Enum


# =============================================================================
# ENUMS
# =============================================================================

class LLMProvider(str, Enum):
    """Supported LLM providers."""
    OLLAMA = "ollama"
    GROQ = "groq"


# =============================================================================
# FIELD MODELS
# =============================================================================

class SchemaField(BaseModel):
    """Definition of a single schema field."""
    name: str = Field(..., min_length=1, description="Field name")
    type: str = Field(default="string", description="Field data type")
    rules: Optional[Any] = Field(default=None, description="Validation rules or options")
    example: Optional[Any] = Field(default=None, description="Example value")
    description: Optional[str] = Field(default=None, description="Field description")
    min_length: Optional[int] = Field(default=None, ge=0, description="Min string length")
    max_length: Optional[int] = Field(default=None, ge=0, description="Max string length")
    min_value: Optional[float] = Field(default=None, description="Min numeric value")
    max_value: Optional[float] = Field(default=None, description="Max numeric value")
    pattern: Optional[str] = Field(default=None, description="Regex pattern")
    enum_values: Optional[List[str]] = Field(default=None, description="Allowed values for select/radio")
    nullable: bool = Field(default=False, description="Can field be null?")
    unique: bool = Field(default=False, description="Values must be unique across records")
    references: Optional[Dict[str, str]] = Field(default=None, description="FK: {'table': 'T', 'field': 'F'}")

    @field_validator('rules', 'example', mode='before')
    @classmethod
    def convert_to_string(cls, v: Any) -> Optional[str]:
        """Ensure specific fields are strings for LLM prompt processing."""
        if v is None:
            return None
        return str(v)

    @field_validator('name')
    @classmethod
    def clean_name(cls, v: str) -> str:
        """Strip whitespace from field names."""
        return v.strip()


class GroupConfig(BaseModel):
    """Configuration for a data generation group."""
    name: str = Field(..., description="Unique group identifier")
    count: int = Field(..., ge=0, description="Records to generate")
    correct_fields: List[str] = Field(default_factory=list, description="Fields that must follow rules")
    wrong_fields: List[str] = Field(default_factory=list, description="Fields that must violate rules")
    wrong_field_rules: Optional[Dict[str, str]] = Field(default_factory=dict, description="Custom violation logic")


# =============================================================================
# REQUEST MODELS
# =============================================================================

class GenerateRequest(BaseModel):
    """Request model for /generate endpoint."""
    schema_fields: List[SchemaField] = Field(..., min_length=1)
    num_records: int = Field(default=5, ge=1, le=1000)
    correct_num_records: int = Field(default=5, ge=0)
    wrong_num_records: int = Field(default=0, ge=0)
    additional_rules: Optional[str] = None
    groups: Optional[List[GroupConfig]] = None
    model_provider: LLMProvider = LLMProvider.OLLAMA


class SeleniumGenerateRequest(BaseModel):
    """Request model for /generate-from-selenium endpoint."""
    selenium_script: str = Field(..., min_length=1)
    num_records: int = Field(default=5, ge=1, le=1000)
    correct_num_records: Optional[int] = None
    wrong_num_records: int = Field(default=0, ge=0)
    additional_rules: Optional[str] = None
    groups: Optional[List[GroupConfig]] = None
    parse_only: bool = False
    model_provider: LLMProvider = LLMProvider.OLLAMA


# =============================================================================
# RESPONSE MODELS
# =============================================================================

class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    ollama: Optional[str] = None
    groq: Optional[str] = None
    model: Optional[str] = None
    error: Optional[str] = None


class GenerateResponse(BaseModel):
    """Data generation response."""
    data: List[Dict[str, Any]]
    count: int
    groups: Optional[List[Dict[str, Any]]] = None


class ParsedField(BaseModel):
    """A field extracted from Selenium scripts."""
    name: str
    type: str
    rules: str = ""
    description: str = ""
    example: str = ""
    confidence: float = Field(ge=0.0, le=1.0)


class SeleniumGenerateResponse(BaseModel):
    """Selenium-based generation response."""
    data: Optional[List[Dict[str, Any]]] = None
    count: Optional[int] = None
    parsed_schema: Optional[List[ParsedField]] = None
    parse_error: Optional[str] = None


class ErrorResponse(BaseModel):
    """Standard error payload."""
    detail: str
    error_code: Optional[str] = None
