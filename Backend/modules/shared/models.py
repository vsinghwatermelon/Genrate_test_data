from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum

class LLMProvider(str, Enum):
    OLLAMA = "ollama"
    GROQ = "groq"

class SchemaField(BaseModel):
    """Field definition for data generation."""
    name: str
    type: str = "string"
    rules: Optional[str] = None
    example: Optional[str] = None

class GroupConfig(BaseModel):
    """Configuration for a generation group."""
    name: str
    count: int
    correct_fields: List[str] = []
    wrong_fields: List[str] = []

class GenerateRequest(BaseModel):
    """Request for group-based data generation."""
    schema_fields: List[SchemaField]
    groups: List[GroupConfig]
    additional_rules: Optional[str] = None
    model_provider: LLMProvider = LLMProvider.OLLAMA

class ClickedElement(BaseModel):
    """Captured UI element from Selenium."""
    locator: str
    tag_name: str
    text: Optional[str] = ""
    attributes: Dict[str, str] = {}
    semantic_type: Optional[str] = None
    exact_purpose: Optional[str] = None
    context: Optional[Dict[str, str]] = {}

class ParseRequest(BaseModel):
    """Request to convert interactions into a schema."""
    clicked_elements: List[ClickedElement]
    filled_fields: List[ClickedElement] = []
