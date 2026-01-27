# Backend Utilities Module

Advanced technical utilities for the Test Data Generator, providing the core 
logic for Selenium automation, HTML analysis, and AI-driven schema synthesis.

---

## 🏗️ Architecture & Organization

The `utils` directory is organized into a systematic hierarchy of logic, 
analysis, and execution layers:

### 1. Extraction Suite (The "Scanner")
Core components that work together to reveal and classify form fields.
- **[`field_extractor.py`](file:///Users/vinayak/Genrate_test_data/Backend/utils/field_extractor.py)**: The Logic Hub. Contains the pure heuristic rules for field types, label detection, and confidence scoring.
- **[`element_extractor.py`](file:///Users/vinayak/Genrate_test_data/Backend/utils/element_extractor.py)**: The Analyzer. Specialized in extracting deep metadata (ARIA roles, JS attributes, DOM state) from live Selenium elements.
- **[`html_extractor.py`](file:///Users/vinayak/Genrate_test_data/Backend/utils/html_extractor.py)**: The Engine. Manages Selenium session lifecycles, navigation, iframe traversal, and multi-page discovery.

### 2. Monitoring & Tracking
- **[`selenium_tracker.py`](file:///Users/vinayak/Genrate_test_data/Backend/utils/selenium_tracker.py)**: High-fidelity interaction monitor. Records clicks, inputs, and correlates them with intercepted API traffic for schema synthesis.
- **[`locator_parser.py`](file:///Users/vinayak/Genrate_test_data/Backend/utils/locator_parser.py)**: Advanced parser for automation assets. Dynamically reads JSON/Python configs and analyzes script intent for the LLM.

### 3. Data & Communication
- **[`json_utils.py`](file:///Users/vinayak/Genrate_test_data/Backend/utils/json_utils.py)**: Standardized logic for LLM response cleaning, aggressive JSON repair, and non-standard type serialization (Bytes/Gzip).

---

## 🛠️ Usage Patterns

### Field Classification
```python
from utils.field_extractor import detect_field_type

# Infer type from raw attributes
field_type = detect_field_type({"name": "email_input", "type": "text"})
# Result: "email"
```

### End-to-End Extraction
```python
from utils.html_extractor import HTMLFieldExtractor

with HTMLFieldExtractor(headless=True) as engine:
    pages, fields = engine.navigate_and_extract(url, actions, locators)
    clean_schema = engine.deduplicate_fields(fields)
```

### JSON Serialization
```python
from utils.json_utils import make_json_serializable

# Handles bytes, gzip, sets, etc.
safe_payload = make_json_serializable(my_binary_data)
```

---

## 🧩 Design Principles

1. **Sectioned Logic**: Every file is partitioned into clear, labeled logical blocks (Lifecycle, Methods, etc.).
2. **Consolidated Heuristics**: Extraction rules are centralized in `field_extractor.py` to prevent logic rot across the suite.
3. **Professional Documentation**: All code uses natural language "Why-Not-What" commentary for rapid developer onboarding.
4. **Resilient Patterns**: Optimized JavaScript execution minimizes 'StaleElement' exceptions and maximizes performance.

---

**Version**: 2.5.0  
**Quality**: Professional / Production-Ready
