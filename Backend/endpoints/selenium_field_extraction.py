"""
Selenium Script Field Extraction Endpoint

Clean, modular implementation for extracting form fields from Selenium scripts
and HTML pages. Replaces the monolithic extract-fields-from-folder endpoint.
"""

import os
import zipfile
import tempfile
import logging
from typing import Dict, Any, List
from fastapi import Request, UploadFile, File, HTTPException

from utils.locator_parser import LocatorParser, ScriptAnalyzer
from utils.html_extractor import HTMLFieldExtractor
from utils.schema_generator import SchemaGenerator
from llm_factory import LLMFactory

logger = logging.getLogger(__name__)


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
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            # Step 1: Extract uploaded zip file
            print("="*60)
            print("[STEP 1] Extracting uploaded zip file...")
            logger.info("="*60)
            logger.info("[STEP 1] Extracting uploaded zip file...")
            zip_path = await _save_and_extract_zip(file, tmpdir)
            print(f"[STEP 1] ✓ Extracted to: {tmpdir}")
            logger.info(f"[STEP 1] ✓ Extracted to: {tmpdir}")
            
            # Step 2: Identify script and locator files
            print("[STEP 2] Identifying script and locator files...")
            logger.info("[STEP 2] Identifying script and locator files...")
            main_script, locator_files = ScriptAnalyzer.identify_script_files(tmpdir)
            print(f"[STEP 2] ✓ Found main script: {os.path.basename(main_script) if main_script else 'None'}")
            print(f"[STEP 2] ✓ Found {len(locator_files)} locator files: {[os.path.basename(f) for f in locator_files]}")
            logger.info(f"[STEP 2] ✓ Found main script: {os.path.basename(main_script) if main_script else 'None'}")
            logger.info(f"[STEP 2] ✓ Found {len(locator_files)} locator files: {[os.path.basename(f) for f in locator_files]}")
            
            if not main_script:
                raise HTTPException(
                    status_code=400,
                    detail="No Selenium/automation script found. Upload a folder with a main script file."
                )
            
            # Step 3: Read script content
            print("[STEP 3] Reading script content...")
            logger.info("[STEP 3] Reading script content...")
            with open(main_script, 'r', encoding='utf-8') as f:
                script_content = f.read()
            print(f"[STEP 3] ✓ Read {len(script_content)} characters from script")
            logger.info(f"[STEP 3] ✓ Read {len(script_content)} characters from script")
            
            # Step 4: Extract metadata from script
            print("[STEP 4] Extracting metadata from script...")
            logger.info("[STEP 4] Extracting metadata from script...")
            target_url = ScriptAnalyzer.extract_url(script_content)
            locator_refs = ScriptAnalyzer.extract_locator_references(script_content)
            actions = ScriptAnalyzer.extract_actions(script_content)
            print(f"[STEP 4] ✓ Extracted URL: {target_url}")
            print(f"[STEP 4] ✓ Found {len(locator_refs)} locator references")
            print(f"[STEP 4] ✓ Found {len(actions)} actions")
            logger.info(f"[STEP 4] ✓ Extracted URL: {target_url}")
            logger.info(f"[STEP 4] ✓ Found {len(locator_refs)} locator references")
            logger.info(f"[STEP 4] ✓ Found {len(actions)} actions")
            
            if not target_url:
                # Try to find URL in locator files as fallback
                logger.warning(f"No URL found in {os.path.basename(main_script)}, checking locator files...")
                for locator_file in locator_files:
                    try:
                        with open(locator_file, 'r', encoding='utf-8') as f:
                            locator_content = f.read()
                        fallback_url = ScriptAnalyzer.extract_url(locator_content)
                        if fallback_url:
                            logger.info(f"Found URL in {os.path.basename(locator_file)}: {fallback_url}")
                            target_url = fallback_url
                            break
                    except Exception as e:
                        logger.warning(f"Could not read {locator_file}: {e}")
            
            if not target_url:
                # Provide more helpful error message with all files checked
                script_preview = script_content[:500] if len(script_content) > 500 else script_content
                logger.warning(f"Could not find URL in script: {os.path.basename(main_script)}")
                logger.warning(f"Script preview: {script_preview}")
                
                all_py_files = []
                for root, dirs, files in os.walk(tmpdir):
                    all_py_files.extend([f for f in files if f.endswith('.py')])
                
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Could not find target URL in {os.path.basename(main_script)}. "
                        f"Python files in folder: {', '.join(all_py_files)}. "
                        "Please ensure at least one file contains: "
                        "driver.get('url'), url='https://...', or TARGET_URL='https://...'. "
                        "You can add it at the top of your main script or in the locators config file."
                    )
                )
            
            # Step 5: Parse locator configurations
            print("[STEP 5] Parsing locator configurations...")
            logger.info("[STEP 5] Parsing locator configurations...")
            all_locators = {}
            for locator_file in locator_files:
                try:
                    parsed = LocatorParser.parse_file(locator_file)
                    normalized = LocatorParser.normalize_locator_data(parsed)
                    all_locators.update(normalized)
                    print(f"[STEP 5] ✓ Parsed {len(normalized)} locators from {os.path.basename(locator_file)}")
                    logger.info(f"[STEP 5] ✓ Parsed {len(normalized)} locators from {os.path.basename(locator_file)}")
                except Exception as e:
                    print(f"[STEP 5] ✗ Failed to parse {locator_file}: {e}")
                    logger.warning(f"[STEP 5] ✗ Failed to parse {locator_file}: {e}")
            
            print(f"[STEP 5] ✓ Total locators parsed: {len(all_locators)}")
            logger.info(f"[STEP 5] ✓ Total locators parsed: {len(all_locators)}")
            if not all_locators:
                print("[STEP 5] ⚠ No locators parsed, will extract all fields from HTML")
                logger.warning("[STEP 5] ⚠ No locators parsed, will extract all fields from HTML")
            
            # Step 6: Extract fields from HTML
            print("[STEP 6] Starting HTML field extraction with Selenium...")
            logger.info("[STEP 6] Starting HTML field extraction with Selenium...")
            fields_by_locator = {}
            all_fields = []
            page_sources = []
            
            with HTMLFieldExtractor() as extractor:
                print("[STEP 6] Selenium WebDriver initialized")
                logger.info("[STEP 6] Selenium WebDriver initialized")
                # Navigate and extract fields
                print(f"[STEP 6] Navigating to {target_url} and extracting fields...")
                logger.info(f"[STEP 6] Navigating to {target_url} and extracting fields...")
                page_sources, all_fields = extractor.navigate_and_extract(
                    url=target_url,
                    actions=actions,
                    locators=all_locators,
                    max_pages=20
                )
                print(f"[STEP 6] ✓ Captured {len(page_sources)} pages")
                print(f"[STEP 6] ✓ Extracted {len(all_fields)} fields (before deduplication)")
                logger.info(f"[STEP 6] ✓ Captured {len(page_sources)} pages")
                logger.info(f"[STEP 6] ✓ Extracted {len(all_fields)} fields (before deduplication)")
                
                # If locators are available, also extract specific matches
                if all_locators and locator_refs:
                    print(f"[STEP 6] Extracting fields by {len(locator_refs)} specific locators...")
                    logger.info(f"[STEP 6] Extracting fields by {len(locator_refs)} specific locators...")
                    combined_html = '\n'.join(page_sources)
                    fields_by_locator = extractor.extract_fields_by_locators(
                        html_content=combined_html,
                        locators=all_locators,
                        locator_keys=locator_refs
                    )
                    print(f"[STEP 6] ✓ Found {len(fields_by_locator)} fields by locator")
                    logger.info(f"[STEP 6] ✓ Found {len(fields_by_locator)} fields by locator")
                
                # Deduplicate fields
                all_fields = extractor.deduplicate_fields(all_fields)
                print(f"[STEP 6] ✓ After deduplication: {len(all_fields)} unique fields")
                logger.info(f"[STEP 6] ✓ After deduplication: {len(all_fields)} unique fields")
            
            print(f"[STEP 6] ✓ Total unique fields extracted: {len(all_fields)}")
            logger.info(f"[STEP 6] ✓ Total unique fields extracted: {len(all_fields)}")
            
            # Step 7: Generate schema using LLM or rule-based approach
            form = await request.form()
            ai_model = form.get("ai_model", "ollama")
            print(f"[STEP 7] Generating schema using AI model: {ai_model}")
            logger.info(f"[STEP 7] Generating schema using AI model: {ai_model}")
            
            try:
                llm = LLMFactory.create_llm(provider=ai_model)
                schema_gen = SchemaGenerator(llm=llm)
                print("[STEP 7] Using LLM for schema generation...")
                logger.info("[STEP 7] Using LLM for schema generation...")
                parsed_schema = schema_gen.generate_schema(all_fields, use_llm=True)
                print(f"[STEP 7] ✓ LLM generated {len(parsed_schema)} schema entries")
                logger.info(f"[STEP 7] ✓ LLM generated {len(parsed_schema)} schema entries")
            except Exception as e:
                print(f"[STEP 7] ✗ LLM schema generation failed: {e}")
                logger.warning(f"[STEP 7] ✗ LLM schema generation failed: {e}")
                print("[STEP 7] Falling back to rule-based schema generation...")
                logger.info("[STEP 7] Falling back to rule-based schema generation...")
                schema_gen = SchemaGenerator(llm=None)
                parsed_schema = schema_gen.generate_schema(all_fields, use_llm=False)
                print(f"[STEP 7] ✓ Rule-based generation created {len(parsed_schema)} schema entries")
                logger.info(f"[STEP 7] ✓ Rule-based generation created {len(parsed_schema)} schema entries")
            
            # Step 8: Deduplicate and validate schema
            print("[STEP 8] Post-processing schema...")
            logger.info("[STEP 8] Post-processing schema...")
            parsed_schema = schema_gen.deduplicate_schema(parsed_schema)
            print(f"[STEP 8] ✓ After deduplication: {len(parsed_schema)} schema entries")
            logger.info(f"[STEP 8] ✓ After deduplication: {len(parsed_schema)} schema entries")
            parsed_schema = schema_gen.merge_field_metadata(parsed_schema, all_fields)
            print("[STEP 8] ✓ Merged field metadata")
            logger.info("[STEP 8] ✓ Merged field metadata")
            
            is_valid, errors = schema_gen.validate_schema(parsed_schema)
            print(f"[STEP 8] ✓ Schema validation: {'VALID' if is_valid else 'INVALID'}")
            logger.info(f"[STEP 8] ✓ Schema validation: {'VALID' if is_valid else 'INVALID'}")
            if not is_valid:
                print(f"[STEP 8] ⚠ Schema validation issues: {errors}")
                logger.warning(f"[STEP 8] ⚠ Schema validation issues: {errors}")
                # If schema is empty, try to generate from all_fields as fallback
                if not parsed_schema and all_fields:
                    print("[STEP 8] Generating fallback schema from raw fields...")
                    logger.info("[STEP 8] Generating fallback schema from raw fields...")
                    schema_gen_fallback = SchemaGenerator(llm=None)
                    parsed_schema = schema_gen_fallback.generate_schema(all_fields, use_llm=False)
                    print(f"[STEP 8] ✓ Fallback generated {len(parsed_schema)} schema entries")
                    logger.info(f"[STEP 8] ✓ Fallback generated {len(parsed_schema)} schema entries")
            
            # Step 9: Prepare consolidated field list
            logger.info("[STEP 9] Preparing consolidated field list...")
            consolidated_fields = _prepare_consolidated_fields(all_fields)
            logger.info(f"[STEP 9] ✓ Prepared {len(consolidated_fields)} consolidated fields")
            
            # Step 10: Return comprehensive response
            print("="*60)
            print("✓ EXTRACTION COMPLETE!")
            print(f"  - Script: {os.path.basename(main_script)}")
            print(f"  - URL: {target_url}")
            print(f"  - Pages: {len(page_sources)}")
            print(f"  - Fields: {len(all_fields)}")
            print(f"  - Schema: {len(parsed_schema)} entries")
            print(f"  - Valid: {is_valid}")
            print("="*60)
            logger.info("[STEP 10] Building response...")
            logger.info("="*60)
            logger.info("✓ EXTRACTION COMPLETE!")
            logger.info(f"  - Script: {os.path.basename(main_script)}")
            logger.info(f"  - URL: {target_url}")
            logger.info(f"  - Pages: {len(page_sources)}")
            logger.info(f"  - Fields: {len(all_fields)}")
            logger.info(f"  - Schema: {len(parsed_schema)} entries")
            logger.info(f"  - Valid: {is_valid}")
            logger.info("="*60)
            
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
                "ai_model_used": ai_model
            }
        
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in field extraction: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Field extraction failed: {str(e)}"
            )


async def _save_and_extract_zip(file: UploadFile, tmpdir: str) -> str:
    """Save uploaded file and extract contents."""
    zip_path = os.path.join(tmpdir, "upload.zip")
    
    logger.info(f"Saving uploaded file to {zip_path}")
    file_bytes = await file.read()
    logger.info(f"Uploaded file size: {len(file_bytes)} bytes")
    
    with open(zip_path, "wb") as f:
        f.write(file_bytes)
    
    logger.info("Extracting zip file...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(tmpdir)
    
    return zip_path


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
