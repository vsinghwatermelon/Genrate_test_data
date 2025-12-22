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


class FieldType(str, Enum):
    """Supported field types for data generation."""
    STRING = "string"
    EMAIL = "email"
    PHONE = "phone"
    INTEGER = "integer"
    NUMBER = "number"
    FLOAT = "float"
    DATE = "date"
    DATETIME = "datetime"
    BOOLEAN = "boolean"
    UUID = "uuid"
    URL = "url"
    ADDRESS = "address"
    CITY = "city"
    STATE = "state"
    POSTAL_CODE = "postal_code"
    COUNTRY = "country"
    FIRST_NAME = "first_name"
    LAST_NAME = "last_name"
    FULL_NAME = "full_name"
    USERNAME = "username"
    PASSWORD = "password"
    CREDIT_CARD = "credit_card"
    SSN = "ssn"
    PAN = "pan"
    IFSC = "ifsc"
    ACCOUNT_NUMBER = "account_number"
    CURRENCY = "currency"
    COMPANY = "company"
    JOB_TITLE = "job_title"
    PARAGRAPH = "paragraph"
    SENTENCE = "sentence"
    WORD = "word"
    CUSTOM = "custom"


# =============================================================================
# FIELD MODELS
# =============================================================================

class SchemaField(BaseModel):
    """Definition of a single schema field."""
    name: str = Field(..., min_length=1, description="Field name")
    type: str = Field(default="string", description="Field data type")
    rules: Optional[str] = Field(default=None, description="Validation rules")
    example: Optional[str] = Field(default=None, description="Example value")
    description: Optional[str] = Field(default=None, description="Field description")
    min_length: Optional[int] = Field(default=None, ge=0, description="Minimum length")
    max_length: Optional[int] = Field(default=None, ge=0, description="Maximum length")
    min_value: Optional[float] = Field(default=None, description="Minimum numeric value")
    max_value: Optional[float] = Field(default=None, description="Maximum numeric value")
    pattern: Optional[str] = Field(default=None, description="Regex pattern")
    enum_values: Optional[List[str]] = Field(default=None, description="Allowed values")
    nullable: bool = Field(default=False, description="Whether field can be null")
    unique: bool = Field(default=False, description="Whether values must be unique")
    references: Optional[Dict[str, str]] = Field(default=None, description="FK reference")

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Ensure field name is valid."""
        return v.strip()


class GroupConfig(BaseModel):
    """Configuration for a data generation group."""
    name: str = Field(..., description="Group name")
    count: int = Field(..., ge=0, description="Number of records to generate")
    correct_fields: List[str] = Field(default_factory=list, description="Fields that must be valid")
    wrong_fields: List[str] = Field(default_factory=list, description="Fields that must be invalid")


# =============================================================================
# REQUEST MODELS
# =============================================================================

class GenerateRequest(BaseModel):
    """Request model for /generate endpoint."""
    schema_fields: List[SchemaField] = Field(..., min_length=1, description="Field definitions")
    num_records: int = Field(default=5, ge=1, le=1000, description="Total records to generate")
    correct_num_records: int = Field(default=5, ge=0, description="Number of valid records")
    wrong_num_records: int = Field(default=0, ge=0, description="Number of invalid records")
    additional_rules: Optional[str] = Field(default=None, description="Additional generation rules")
    groups: Optional[List[GroupConfig]] = Field(default=None, description="Group-based generation config")
    model_provider: LLMProvider = Field(default=LLMProvider.OLLAMA, description="LLM provider")

    @field_validator('correct_num_records', 'wrong_num_records')
    @classmethod
    def validate_record_counts(cls, v: int, info) -> int:
        """Validate record count is non-negative."""
        return max(0, v)


class SeleniumGenerateRequest(BaseModel):
    """Request model for /generate-from-selenium endpoint."""
    selenium_script: str = Field(..., min_length=1, description="Selenium script content")
    num_records: int = Field(default=5, ge=1, le=1000, description="Total records to generate")
    correct_num_records: Optional[int] = Field(default=None, ge=0, description="Number of valid records")
    wrong_num_records: int = Field(default=0, ge=0, description="Number of invalid records")
    additional_rules: Optional[str] = Field(default=None, description="Additional generation rules")
    groups: Optional[List[GroupConfig]] = Field(default=None, description="Group-based generation config")
    parse_only: bool = Field(default=False, description="Only parse schema, don't generate data")
    model_provider: LLMProvider = Field(default=LLMProvider.OLLAMA, description="LLM provider")


# =============================================================================
# RESPONSE MODELS
# =============================================================================

class HealthResponse(BaseModel):
    """Response model for /health endpoint."""
    status: str = Field(..., description="Health status: 'healthy' or 'unhealthy'")
    ollama: Optional[str] = Field(default=None, description="Ollama connection status")
    groq: Optional[str] = Field(default=None, description="Groq connection status")
    model: Optional[str] = Field(default=None, description="Active model name")
    error: Optional[str] = Field(default=None, description="Error message if unhealthy")


class GenerateResponse(BaseModel):
    """Response model for /generate endpoint."""
    data: List[Dict[str, Any]] = Field(..., description="Generated records")
    count: int = Field(..., ge=0, description="Number of records generated")
    groups: Optional[List[Dict[str, Any]]] = Field(default=None, description="Group breakdown info")


class ParsedField(BaseModel):
    """A field parsed from Selenium script."""
    name: str
    type: str
    rules: str = ""
    description: str = ""
    example: str = ""
    confidence: float = Field(ge=0.0, le=1.0)


class SeleniumGenerateResponse(BaseModel):
    """Response model for /generate-from-selenium endpoint."""
    data: Optional[List[Dict[str, Any]]] = Field(default=None, description="Generated records")
    count: Optional[int] = Field(default=None, ge=0, description="Number of records generated")
    parsed_schema: Optional[List[ParsedField]] = Field(default=None, description="Parsed schema fields")
    parse_error: Optional[str] = Field(default=None, description="Parsing error if any")


class ErrorResponse(BaseModel):
    """Standard error response."""
    detail: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(default=None, description="Error code for programmatic handling")
