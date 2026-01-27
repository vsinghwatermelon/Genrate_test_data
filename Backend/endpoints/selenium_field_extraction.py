"""
Selenium Script Field Extraction Endpoint

Provides structured logic for extracting form fields from Selenium scripts 
and their target HTML pages. Automatically identifies script structure,
parses locators, navigates target URLs, and generates an AI-powered schema.
"""

import os
import tempfile
import logging
from typing import Dict, Any, List, Tuple
from fastapi import Request, UploadFile, File, HTTPException

from utils.locator_parser import LocatorParser, ScriptAnalyzer
from utils.html_extractor import HTMLFieldExtractor
from utils.schema_generator import SchemaGenerator
from llm_factory import LLMFactory
from endpoints.logger import EndpointLogger
from endpoints.common import extract_zip_file

logger = logging.getLogger(__name__)

# Extraction Constraints
MAX_FORM_PAGES = 100
MAX_FIELD_COUNT = 500
MAX_LOCATOR_COUNT = 1000


# ============================================================================
# MAIN EXTRACTION ENDPOINT
# ============================================================================

async def extract_fields_from_uploaded_folder(
    request: Request,
    file: UploadFile = File(...)
) -> Dict[str, Any]:
    """
    Extract form fields and generate a schema from an uploaded Selenium package.
    
    The process involves:
    1. Processing the uploaded ZIP and identifying core files.
    2. Analyzing script metadata (target URL, actions).
    3. Parsing all associated locator configurations.
    4. Navigating the target site with Selenium to extract live HTML fields.
    5. Using AI to generate a clean, labeled schema for test data.
    """
    endpoint_logger = EndpointLogger("field_extraction")

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            endpoint_logger.info("=" * 60)
            endpoint_logger.info("STARTING DEEP FIELD EXTRACTION")
            endpoint_logger.info("=" * 60)
            
            # 1. Asset Identification
            main_script, locator_files = await _identify_script_assets(file, tmpdir, endpoint_logger)
            
            # 2. Metadata Extraction
            target_url, actions, locator_refs = _extract_script_metadata(main_script, locator_files, endpoint_logger)
            
            # 3. Locator Parsing
            all_locators = _parse_locator_configs(locator_files, endpoint_logger)
            
            # 4. Selenium-based HTML Extraction
            page_sources, all_fields, fields_by_locator = _run_selenium_extraction(
                target_url, actions, all_locators, locator_refs, endpoint_logger
            )
            
            # 5. Metadata Processing and Deduplication
            if len(all_fields) > MAX_FIELD_COUNT:
                endpoint_logger.warning(f"Truncating fields to {MAX_FIELD_COUNT} limit.")
                all_fields = all_fields[:MAX_FIELD_COUNT]
            
            # 6. AI Schema Generation
            form_data = await request.form()
            ai_model = form_data.get("ai_model", "ollama")
            parsed_schema, is_valid, errors = _generate_ai_schema(all_fields, ai_model, endpoint_logger)
            
            # 7. Final Consolidation
            consolidated_fields = _prepare_consolidated_fields(all_fields)
            
            endpoint_logger.info("=" * 60)
            endpoint_logger.info("EXTRACTION SUCCESSFUL")
            endpoint_logger.info(f"Fields: {len(all_fields)}, Schema: {len(parsed_schema)}")
            endpoint_logger.info("=" * 60)
            
            return {
                "success": True,
                "url": target_url,
                "script_name": os.path.basename(main_script),
                "locator_files": [os.path.basename(f) for f in locator_files],
                "pages_captured": len(page_sources),
                "unique_field_count": len(all_fields),
                "fields_by_locator": fields_by_locator,
                "consolidated_fields": consolidated_fields,
                "parsed_schema": parsed_schema,
                "schema_valid": is_valid,
                "schema_errors": errors or None,
                "ai_model_used": ai_model,
                "logs": endpoint_logger.get_logs()
            }
        
        except HTTPException:
            raise
        except Exception as e:
            endpoint_logger.error(f"Critical failure in extraction pipeline: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Field extraction pipeline failed: {str(e)}"
            )


# ============================================================================
# HELPER METHODS (PIPELINE STEPS)
# ============================================================================

async def _identify_script_assets(file: UploadFile, tmpdir: str, log: EndpointLogger) -> Tuple[str, List[str]]:
    """Download and extract the ZIP package to find scripts and locators."""
    log.info("[STEP 1] Validating and extracting script package...")
    await extract_zip_file(file, tmpdir)
    
    main_script, locator_files = ScriptAnalyzer.identify_script_files(tmpdir)
    
    if not main_script:
        raise HTTPException(
            status_code=400,
            detail="No Python Selenium script identified in the package."
        )
    
    log.info(f"Found main script: {os.path.basename(main_script)}")
    log.info(f"Found {len(locator_files)} locator files.")
    return main_script, locator_files


def _extract_script_metadata(script_path: str, locator_files: List[str], log: EndpointLogger) -> Tuple[str, List[Dict], List[str]]:
    """Extract URL, actions, and locator references from the script code."""
    log.info("[STEP 2] Analyzing script source code...")
    
    with open(script_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    target_url = ScriptAnalyzer.extract_url(content)
    locator_refs = ScriptAnalyzer.extract_locator_references(content)
    actions = ScriptAnalyzer.extract_actions(content)
    
    # Fallback to locator files for URL if missing in main script
    if not target_url:
        for loc_file in locator_files:
            try:
                with open(loc_file, 'r', encoding='utf-8') as f:
                    url = ScriptAnalyzer.extract_url(f.read())
                    if url:
                        target_url = url
                        log.info(f"Retrieved URL from locator file: {url}")
                        break
            except Exception:
                continue
                
    if not target_url:
        raise HTTPException(
            status_code=400,
            detail="Target URL not found in script or configuration files."
        )
        
    return target_url, actions, locator_refs


def _parse_locator_configs(locator_files: List[str], log: EndpointLogger) -> Dict[str, Any]:
    """Parse all identified locator configurations into a normalized dictionary."""
    log.info("[STEP 3] Normalizing locator configurations...")
    combined_locators = {}
    
    for loc_file in locator_files:
        try:
            parsed = LocatorParser.parse_file(loc_file)
            normalized = LocatorParser.normalize_locator_data(parsed)
            
            if len(combined_locators) + len(normalized) > MAX_LOCATOR_COUNT:
                log.warning("Max locator limit reached. Skipping additional configurations.")
                break
                
            combined_locators.update(normalized)
        except Exception as e:
            log.error(f"Failed to parse locator file {os.path.basename(loc_file)}: {e}")
            
    return combined_locators


def _run_selenium_extraction(url: str, actions: List, locators: Dict, refs: List[str], log: EndpointLogger):
    """Execution Selenium to extract live HTML fields from the target URL."""
    log.info("[STEP 4] Starting live field extraction via Selenium...")
    
    with HTMLFieldExtractor() as extractor:
        # Wrap the extractor's internal logs into our endpoint logger
        def callback(msg): log.info(f"[EXTRACTOR] {msg}")
        
        page_sources, all_fields = extractor.navigate_and_extract(
            url=url,
            actions=actions,
            locators=locators,
            max_pages=MAX_FORM_PAGES,
            log_callback=callback
        )
        
        # Link fields specifically referenced in the script
        fields_by_locator = {}
        if locators and refs:
            combined_html = '\n'.join(page_sources)
            found_by_loc = extractor.extract_fields_by_locators(combined_html, locators, refs)
            
            for loc_key, matches in found_by_loc.items():
                if matches:
                    field = matches[0]
                    field['is_verified_locator'] = True
                    field['locator_key'] = loc_key
                    fields_by_locator[loc_key] = matches
                    all_fields.insert(0, field)  # Prioritize verified fields
        
        deduplicated = extractor.deduplicate_fields(all_fields)
        return page_sources, deduplicated, fields_by_locator


def _generate_ai_schema(fields: List[Dict], model: str, log: EndpointLogger) -> Tuple[List, bool, List]:
    """Use AI or Rule-based logic to convert raw fields into a structured schema."""
    log.info(f"[STEP 5] Generating schema using {model}...")
    
    try:
        llm = LLMFactory.create_llm(provider=model)
        schema_gen = SchemaGenerator(llm=llm)
        schema = schema_gen.generate_schema(fields, use_llm=True)
    except Exception as e:
        log.error(f"AI Generation failed: {e}. Falling back to rules.")
        schema_gen = SchemaGenerator(llm=None)
        schema = schema_gen.generate_schema(fields, use_llm=False)
        
    # Standard cleanup and metadata merging
    schema = schema_gen.deduplicate_schema(schema)
    schema = schema_gen.merge_field_metadata(schema, fields)
    
    is_valid, errors = schema_gen.validate_schema(schema)
    return schema, is_valid, errors


def _prepare_consolidated_fields(fields: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter raw field attributes to only those necessary for the frontend UI."""
    return [
        {
            'name': f.get('name', ''),
            'id': f.get('id', ''),
            'type': f.get('detected_type', f.get('type', 'string')),
            'label': f.get('label', ''),
            'placeholder': f.get('placeholder', ''),
            'required': f.get('required', False),
            'options': f.get('options'),
            'locator_key': f.get('locator_key')
        }
        for f in fields
    ]
