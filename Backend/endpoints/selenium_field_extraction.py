"""
Selenium Script Field Extraction Endpoint

Clean, modular implementation for extracting form fields from Selenium scripts
and HTML pages. Replaces the monolithic extract-fields-from-folder endpoint.
"""

import os
import tempfile
import logging
from typing import Dict, Any, List
from fastapi import Request, UploadFile, File, HTTPException

from utils.locator_parser import LocatorParser, ScriptAnalyzer
from utils.html_extractor import HTMLFieldExtractor
from utils.schema_generator import SchemaGenerator
from llm_factory import LLMFactory
from endpoints.logger import EndpointLogger
from endpoints.common import extract_zip_file

logger = logging.getLogger(__name__)

# Constants
MAX_FORM_PAGES = 100  # Maximum pages to extract for complex forms
MAX_FIELD_COUNT = 500  # Maximum fields to extract
MAX_LOCATOR_COUNT = 1000  # Maximum locators to parse


async def extract_fields_from_uploaded_folder(
    request: Request,
    file: UploadFile = File(...)
) -> Dict[str, Any]:
    """
    Extract form fields from uploaded Selenium script folder.
    
    Dynamic approach that handles any script structure:
    1. Extract and identify scripts/locator files automatically
    2. Parse locator configurations in any format
    3. Navigate website and extract fields dynamically
    4. Generate clean, user-editable schema
    
    Args:
        request: FastAPI request (to get form data like ai_model)
        file: Uploaded zip file containing scripts and locator configs
    
    Returns:
        Dictionary with extracted fields, schema, and metadata
    """
    endpoint_logger = EndpointLogger("field_extraction")

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            # Step 1: Extract uploaded zip file
            endpoint_logger.info("="*60)
            endpoint_logger.info("[STEP 1] Extracting uploaded zip file...")
            await extract_zip_file(file, tmpdir)
            endpoint_logger.info(f"[STEP 1] ✓ Extracted to: {tmpdir}")
            
            # Step 2: Identify script and locator files
            endpoint_logger.info("[STEP 2] Identifying script and locator files...")
            main_script, locator_files = ScriptAnalyzer.identify_script_files(tmpdir)
            endpoint_logger.info(
                f"[STEP 2] ✓ Found main script: {os.path.basename(main_script) if main_script else 'None'}"
            )
            endpoint_logger.info(
                f"[STEP 2] ✓ Found {len(locator_files)} locator files: "
                f"{[os.path.basename(f) for f in locator_files]}"
            )
            
            if not main_script:
                raise HTTPException(
                    status_code=400,
                    detail="No Selenium/automation script found. Upload a folder with a main script file."
                )
            
            # Step 3: Read script content
            endpoint_logger.info("[STEP 3] Reading script content...")
            with open(main_script, 'r', encoding='utf-8') as f:
                script_content = f.read()
            endpoint_logger.info(f"[STEP 3] ✓ Read {len(script_content)} characters from script")
            
            # Step 4: Extract metadata from script
            endpoint_logger.info("[STEP 4] Extracting metadata from script...")
            target_url = ScriptAnalyzer.extract_url(script_content)
            locator_refs = ScriptAnalyzer.extract_locator_references(script_content)
            actions = ScriptAnalyzer.extract_actions(script_content)
            endpoint_logger.info(f"[STEP 4] ✓ Extracted URL: {target_url}")
            endpoint_logger.info(f"[STEP 4] ✓ Found {len(locator_refs)} locator references")
            endpoint_logger.info(f"[STEP 4] ✓ Found {len(actions)} actions")
            
            if not target_url:
                # Try to find URL in locator files as fallback
                endpoint_logger.warning(
                    f"No URL found in {os.path.basename(main_script)}, checking locator files..."
                )
                for locator_file in locator_files:
                    try:
                        with open(locator_file, 'r', encoding='utf-8') as f:
                            locator_content = f.read()
                        fallback_url = ScriptAnalyzer.extract_url(locator_content)
                        if fallback_url:
                            endpoint_logger.info(
                                f"Found URL in {os.path.basename(locator_file)}: {fallback_url}"
                            )
                            target_url = fallback_url
                            break
                    except Exception as e:
                        endpoint_logger.warning(f"Could not read {locator_file}: {e}")
            
            if not target_url:
                raise HTTPException(
                    status_code=400,
                    detail=f"Could not find target URL in {os.path.basename(main_script)} or locator files."
                )
            
            # Step 5: Parse locator configurations
            endpoint_logger.info("[STEP 5] Parsing locator configurations...")
            all_locators = {}
            for locator_file in locator_files:
                try:
                    parsed = LocatorParser.parse_file(locator_file)
                    normalized = LocatorParser.normalize_locator_data(parsed)
                    
                    # Validate locator count
                    if len(all_locators) + len(normalized) > MAX_LOCATOR_COUNT:
                        endpoint_logger.warning(
                            f"Exceeded max locators ({MAX_LOCATOR_COUNT}), skipping remaining files"
                        )
                        break
                    
                    all_locators.update(normalized)
                    endpoint_logger.info(
                        f"[STEP 5] ✓ Parsed {len(normalized)} locators from {os.path.basename(locator_file)}"
                    )
                except Exception as e:
                    endpoint_logger.error(f"[STEP 5] ✗ Failed to parse {locator_file}: {e}")
            
            endpoint_logger.info(f"[STEP 5] ✓ Total locators parsed: {len(all_locators)}")
            
            # Step 6: Extract fields from HTML
            endpoint_logger.info("[STEP 6] Starting HTML field extraction with Selenium...")
            fields_by_locator = {}
            all_fields = []
            page_sources = []
            
            with HTMLFieldExtractor() as extractor:
                endpoint_logger.info("[STEP 6] Selenium WebDriver initialized")
                endpoint_logger.info(f"[STEP 6] Navigating to {target_url} and extracting fields...")
                
                # Custom logging callback for extractor
                def extractor_log(msg: str):
                    endpoint_logger.info(f"[STEP 6] {msg}")
                
                # Capture pages and fields
                page_sources, all_fields = extractor.navigate_and_extract(
                    url=target_url,
                    actions=actions,
                    locators=all_locators,
                    max_pages=MAX_FORM_PAGES,
                    log_callback=extractor_log
                )
                endpoint_logger.info(f"[STEP 6] ✓ Captured {len(page_sources)} pages")
                endpoint_logger.info(f"[STEP 6] ✓ Extracted {len(all_fields)} fields (before deduplication)")
                
                if all_locators and locator_refs:
                    endpoint_logger.info(
                        f"[STEP 6] Extracting fields by {len(locator_refs)} specific locators from script..."
                    )
                    combined_html = '\n'.join(page_sources)
                    fields_by_locator = extractor.extract_fields_by_locators(
                        html_content=combined_html,
                        locators=all_locators,
                        locator_keys=locator_refs
                    )
                    endpoint_logger.info(f"[STEP 6] ✓ Found {len(fields_by_locator)} fields by locator")
                    
                    # Log specific locator matches for transparency
                    for loc_key, matched_list in fields_by_locator.items():
                        if matched_list:
                            field = matched_list[0]
                            name = field.get('label') or field.get('name') or field.get('id')
                            endpoint_logger.info(f"   ✓ {loc_key} matched: {name}")

                    locator_matched_list = []
                    for loc_key, matched_list in fields_by_locator.items():
                        for field in matched_list:
                            field['is_verified_locator'] = True
                            field['locator_key'] = loc_key
                            locator_matched_list.append(field)
                    
                    all_fields = locator_matched_list + all_fields
                
                all_fields = extractor.deduplicate_fields(all_fields)
                endpoint_logger.info(f"[STEP 6] ✓ After deduplication: {len(all_fields)} unique fields")
            
            # Validate field count
            if len(all_fields) > MAX_FIELD_COUNT:
                endpoint_logger.warning(
                    f"Extracted {len(all_fields)} fields, truncating to {MAX_FIELD_COUNT}"
                )
                all_fields = all_fields[:MAX_FIELD_COUNT]
            
            endpoint_logger.info(f"[STEP 6] ✓ Total unique fields extracted: {len(all_fields)}")
            
            # Step 7: Generate schema using LLM
            form = await request.form()
            ai_model = form.get("ai_model", "ollama")
            endpoint_logger.info(f"[STEP 7] Generating schema using AI model: {ai_model}")
            
            try:
                llm = LLMFactory.create_llm(provider=ai_model)
                schema_gen = SchemaGenerator(llm=llm)
                endpoint_logger.info("[STEP 7] Using LLM for schema generation...")
                parsed_schema = schema_gen.generate_schema(all_fields, use_llm=True)
                endpoint_logger.info(f"[STEP 7] ✓ LLM generated {len(parsed_schema)} schema entries")
            except Exception as e:
                endpoint_logger.error(f"[STEP 7] ✗ LLM schema generation failed: {e}")
                endpoint_logger.info("[STEP 7] Falling back to rule-based schema generation...")
                schema_gen = SchemaGenerator(llm=None)
                parsed_schema = schema_gen.generate_schema(all_fields, use_llm=False)
                endpoint_logger.info(f"[STEP 7] ✓ Rule-based generation created {len(parsed_schema)} schema entries")
            
            # Step 8: Post-processing schema
            endpoint_logger.info("[STEP 8] Post-processing schema...")
            parsed_schema = schema_gen.deduplicate_schema(parsed_schema)
            endpoint_logger.info(f"[STEP 8] ✓ After deduplication: {len(parsed_schema)} schema entries")
            parsed_schema = schema_gen.merge_field_metadata(parsed_schema, all_fields)
            endpoint_logger.info("[STEP 8] ✓ Merged field metadata")
            
            # Step 9: Validate schema
            is_valid, errors = schema_gen.validate_schema(parsed_schema)
            endpoint_logger.info(f"[STEP 8] ✓ Schema validation: {'VALID' if is_valid else 'INVALID'}")
            if errors:
                for error in errors:
                    endpoint_logger.warning(f"Schema validation error: {error}")
            
            # Step 10: Prepare consolidated field list
            endpoint_logger.info("[STEP 9] Preparing consolidated field list...")
            consolidated_fields = _prepare_consolidated_fields(all_fields)
            
            # Step 11: Return comprehensive response
            endpoint_logger.info("="*60)
            endpoint_logger.info("✓ EXTRACTION COMPLETE!")
            endpoint_logger.info(f"  - Script: {os.path.basename(main_script)}")
            endpoint_logger.info(f"  - URL: {target_url}")
            endpoint_logger.info(f"  - Pages: {len(page_sources)}")
            endpoint_logger.info(f"  - Fields: {len(all_fields)}")
            endpoint_logger.info(f"  - Schema: {len(parsed_schema)} entries")
            endpoint_logger.info(f"  - Valid: {is_valid}")
            endpoint_logger.info(f"  - Duration: {endpoint_logger.get_duration():.2f}s")
            endpoint_logger.info("="*60)
            
            return {
                "success": True,
                "url": target_url,
                "script_name": os.path.basename(main_script),
                "locator_files": [os.path.basename(f) for f in locator_files],
                "pages_captured": len(page_sources),
                "actions_executed": len(actions),
                "locator_keys": locator_refs,
                "unique_field_count": len(all_fields),
                "fields_by_locator": fields_by_locator,
                "consolidated_fields": consolidated_fields,
                "parsed_schema": parsed_schema,
                "schema_valid": is_valid,
                "schema_errors": errors if errors else None,
                "ai_model_used": ai_model,
                "logs": endpoint_logger.get_logs()
            }
        
        except HTTPException:
            raise
        except Exception as e:
            endpoint_logger.error(f"Unexpected error in field extraction: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Field extraction failed: {str(e)}"
            )



def _prepare_consolidated_fields(fields: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Prepare consolidated field list with only essential information for frontend.
    """
    consolidated = []
    
    for field in fields:
        consolidated_field = {
            'name': field.get('name', ''),
            'id': field.get('id', ''),
            'type': field.get('detected_type', field.get('type', 'string')),
            'label': field.get('label', ''),
            'placeholder': field.get('placeholder', ''),
            'required': field.get('required', False),
        }
        
        # Add options for select fields
        if field.get('options'):
            consolidated_field['options'] = field['options']
        
        # Add locator info if available
        if field.get('locator_key'):
            consolidated_field['locator_key'] = field['locator_key']
        
        consolidated.append(consolidated_field)
    
    return consolidated
