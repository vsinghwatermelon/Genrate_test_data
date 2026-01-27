# Endpoints Module

Professional-grade FastAPI endpoints for Test Data Generator operations.

## Overview

This module provides clean, well-documented API endpoints for:
- 🔄 **Test Data Generation** - From schemas, Selenium scripts, or LLM analysis
- 🎯 **Script Execution** - Run Selenium scripts with comprehensive action tracking  
- 📊 **Field Extraction** - Extract form fields from Selenium automation code
- 🧠 **Element Parsing** - Convert clicked elements to schemas using AI

## Module Structure

```
endpoints/
│
├── common.py (202 lines)
│   └── Shared utilities used across all endpoints:
│       • File Handling (zip extraction with validation)
│       • LLM Integration (provider init with fallback)
│       • Form Data Parsing (boolean conversion, etc.)
│
├── data_gen_helpers.py (134 lines)
│   └── Data generation specific helpers:
│       • Model Conversion (Pydantic → dict)
│       • Generator Initialization  
│       • Error Handling (decorators)
│
├── data_generation.py (261 lines)
│   └── 4 endpoints for test data generation:
│       • /generate-data-from-schema (frontend edited schemas)
│       • /generate (Pydantic validated requests)
│       • /generate-from-selenium (from Selenium scripts)
│       • /generate-legacy (backward compatibility)
│
├── script_execution.py (186 lines)
│   └── 2 endpoints for Selenium operations:
│       • /execute-selenium-script (run with tracking)
│       • /list-script-actions (analyze without running)
│
├── selenium_field_extraction.py (309 lines)
│   └── 1 endpoint for field extraction:
│       • /extract-fields-from-folder (parse scripts + HTML)
│
├── parse_clicked_elements.py (179 lines)
│   └── 1 endpoint for LLM parsing:
│       • /parse-clicked-elements (clicks → schema)
│
├── logger.py (107 lines) ✓ EXCELLENT
│   └── EndpointLogger class for structured logging
│
└── __init__.py (68 lines)
    └── Package documentation and metadata

Total: ~1,446 lines across 8 files
```

## Design Patterns

### 1. Shared Utilities
Common operations are centralized in `common.py`:
```python
from endpoints.common import extract_zip_file, get_llm_with_fallback

# All file uploads use same validation
zip_path = await extract_zip_file(file, tmpdir)

# All LLM calls use same fallback logic
llm = get_llm_with_fallback("groq")
```

### 2. Error Handling Decorator
Data generation endpoints use a decorator for consistent error handling:
```python
from endpoints.data_gen_helpers import handle_generation_errors

@handle_generation_errors("generate_data")
async def generate_test_data(request):
    # Errors automatically logged and converted to HTTPExceptions
    ...
```

### 3. Structured Logging
Complex endpoints use EndpointLogger for client-visible logs:
```python
from endpoints.logger import EndpointLogger

logger = EndpointLogger("field_extraction")
logger.info("Processing 10 fields...")
logger.error("Failed to parse field 5")

return {"logs": logger.get_logs(), "duration": logger.get_duration()}
```

### 4. Consistent Response Format
```json
{
  "success": true,
  "message": "Operation completed successfully",
  "data": {
    // Endpoint-specific payload
  }
}
```

## API Endpoints Summary

| Endpoint | Method | Purpose | Input | Output |
|----------|--------|---------|-------|--------|
| `/generate-data-from-schema` | POST | Generate from frontend | Schema JSON | Test data |
| `/generate` | POST | Generate with validation | GenerateRequest | Test data |
| `/generate-from-selenium` | POST | Generate from script | SeleniumGenerateRequest | Test data |
| `/generate-legacy` | POST | Backward compatibility | Dict | Test data |
| `/execute-selenium-script` | POST | Run script with tracking | ZIP file | Tracked actions |
| `/list-script-actions` | POST | Analyze without running | ZIP file | Parsed actions |
| `/extract-fields-from-folder` | POST | Extract form fields | ZIP file | Field schema |
| `/parse-clicked-elements` | POST | Parse elements to schema | Element list | Schema |

## Code Quality

✅ **Well-Organized** - Clear separation of concerns  
✅ **DRY Principles** - No code duplication  
✅ **Documented** - Every function has docstrings  
✅ **Type-Safe** - FastAPI/Pydantic validation  
✅ **Error Handling** - Consistent across all endpoints  
✅ **Professional** - Production-ready quality  

## Common Utilities Reference

### File Handling
```python
# Extract ZIP with size validation (max 100MB)
zip_path = await extract_zip_file(file, tmpdir)
```

### LLM Integration  
```python
# Get LLM with automatic fallback
llm = get_llm_with_fallback("groq")  # Falls back to ollama if groq fails
```

### JSON Parsing
```python
# Parse JSON from LLM response (handles markdown blocks)
data = parse_llm_json_response(llm_output)
```

### Form Data
```python
# Parse boolean from form submissions
headless = parse_form_bool(form_data.get('headless'), default=True)
```

## Development Guidelines

When adding new endpoints:

1. ✅ **Use Common Utilities** - Don't duplicate extraction/LLM logic
2. ✅ **Add Docstrings** - Include Args, Returns, Raises, Examples
3. ✅ **Handle Errors** - Use decorators or proper try-except
4. ✅ **Type Hints** - Let FastAPI validate automatically
5. ✅ **Log Appropriately** - Use EndpointLogger for multi-step ops
6. ✅ **Test Imports** - Verify no circular dependencies

---

**Version**: 2.0.0  
**Maintainability**: ⭐⭐⭐⭐⭐  
**Code Quality**: Professional/Production-Ready
