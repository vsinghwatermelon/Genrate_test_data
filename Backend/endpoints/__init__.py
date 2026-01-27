"""
Endpoints Package

Professional-grade FastAPI endpoints for the Test Data Generator API.

This package provides modular, well-documented endpoints for:
- Generating test data from schemas
- Executing Selenium scripts with tracking
- Extracting form fields from Selenium scripts
- Parsing clicked elements into schemas

## Module Organization

```
endpoints/
├── common.py              # Shared utilities (file handling, LLM integration)
├── data_gen_helpers.py    # Data generation helpers (model conversion, error handling)
├── data_generation.py     # Test data generation endpoints
├── script_execution.py    # Selenium script execution endpoints
├── selenium_field_extraction.py  # Form field extraction from scripts
├── parse_clicked_elements.py     # LLM-based element parsing
├── logger.py              # Structured logging with log accumulation
└── __init__.py            # Package initialization
```

## Usage

These endpoint functions are registered in the main FastAPI app:

```python
from fastapi import FastAPI
from endpoints import data_generation, script_execution

app = FastAPI()

# Register generation endpoints
app.post("/generate")(data_generation.generate_test_data)
app.post("/generate-from-selenium")(data_generation.generate_from_selenium)

# Register execution endpoints
app.post("/execute-selenium-script")(script_execution.execute_selenium_script)
```

## Common Patterns

### File Upload Handling
All file upload endpoints use `common.extract_zip_file()` for consistent
validation and extraction with size limits.

### LLM Integration
Endpoints that use LLMs call `common.get_llm_with_fallback()` which
automatically falls back to ollama if the preferred provider fails.

### Error Handling
Data generation endpoints use the `@handle_generation_errors` decorator
for consistent error logging and HTTP exception handling.

### Logging
Complex endpoints use `EndpointLogger` from `logger.py` to accumulate
logs that can be returned to the client for debugging.

## API Response Format

All endpoints follow a consistent response structure:

```json
{
  "success": true,
  "message": "Operation completed successfully",
  "data": {
    // Endpoint-specific data
  }
}
```

Error responses:

```json
{
  "detail": "Error message describing what went wrong"
}
```

## Development Guidelines

When adding new endpoints:

1. **Use common utilities** - Don't duplicate file handling or LLM init
2. **Add docstrings** - Include Args, Returns, Raises, and Example
3. **Handle errors** - Use decorators or try-except with proper logging
4. **Return consistent structure** - Follow the success/message/data pattern
5. **Add type hints** - Use FastAPI's type system for automatic validation

## Dependencies

- **FastAPI**: Web framework and request validation
- **Pydantic**: Request/response models  
- **utils.script_executor**: Selenium script execution
- **data_generator**: Test data generation logic
- **llm_factory**: LLM provider abstraction

---

**Version**: 2.0.0  
**Total Endpoints**: 7 active endpoints across 4 endpoint files
"""

# Package metadata
__version__ = "2.0.0"
__all__ = [
    "common",
    "data_gen_helpers",
    "data_generation",
    "script_execution",
    "selenium_field_extraction",
    "parse_clicked_elements",
    "logger",
]
