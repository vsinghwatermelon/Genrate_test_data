"""
Configuration Management Module

Centralized configuration for the Test Data Generator application.
Supports environment variables and default values.
"""

import os
from dataclasses import dataclass, field
from typing import Optional, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@dataclass
class LLMConfig:
    """Configuration for LLM providers."""
    
    # Ollama settings
    ollama_model: str = field(default_factory=lambda: os.getenv("OLLAMA_MODEL", "llama3:latest"))
    ollama_base_url: str = field(default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
    ollama_timeout: int = field(default_factory=lambda: int(os.getenv("OLLAMA_TIMEOUT", "120")))
    
    # Groq settings
    groq_api_key: Optional[str] = field(default_factory=lambda: os.getenv("groq_api_key") or os.getenv("GROQ_API_KEY"))
    groq_model: str = field(default_factory=lambda: os.getenv("model", "openai/gpt-oss-20b").strip('"'))
    
    # Generation settings
    default_temperature: float = field(default_factory=lambda: float(os.getenv("LLM_TEMPERATURE", "0.7")))
    max_tokens: int = field(default_factory=lambda: int(os.getenv("LLM_MAX_TOKENS", "8192")))
    max_retries: int = field(default_factory=lambda: int(os.getenv("LLM_MAX_RETRIES", "3")))


@dataclass
class ServerConfig:
    """Configuration for FastAPI server."""
    
    host: str = field(default_factory=lambda: os.getenv("SERVER_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(os.getenv("SERVER_PORT", "8000")))
    debug: bool = field(default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true")
    cors_origins: List[str] = field(default_factory=lambda: os.getenv(
        "CORS_ORIGINS", 
        "http://localhost:3000,http://127.0.0.1:3000"
    ).split(","))


@dataclass
class GenerationConfig:
    """Configuration for data generation."""
    
    max_records_per_request: int = field(default_factory=lambda: int(os.getenv("MAX_RECORDS", "1000")))
    default_records: int = field(default_factory=lambda: int(os.getenv("DEFAULT_RECORDS", "5")))
    enable_logging: bool = field(default_factory=lambda: os.getenv("ENABLE_LOGGING", "true").lower() == "true")
    log_prompts: bool = field(default_factory=lambda: os.getenv("LOG_PROMPTS", "true").lower() == "true")
    log_responses: bool = field(default_factory=lambda: os.getenv("LOG_RESPONSES", "false").lower() == "true")


@dataclass
class AppConfig:
    """Main application configuration."""
    
    llm: LLMConfig = field(default_factory=LLMConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    generation: GenerationConfig = field(default_factory=GenerationConfig)


# Global configuration instance
config = AppConfig()


def get_config() -> AppConfig:
    """Get the global configuration instance."""
    return config


def reload_config() -> AppConfig:
    """Reload configuration from environment variables."""
    global config
    load_dotenv(override=True)
    config = AppConfig()
    return config
