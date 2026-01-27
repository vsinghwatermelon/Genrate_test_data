import json
import logging
from typing import Dict, List, Any, Optional

from llm_factory import LLMFactory, BaseLLM
from prompts import DataGenerationPrompts
from utils.json_utils import JSONCleaner, JSONExtractor, NDJSONParser
from utils.logger import get_logger

logger = get_logger(__name__)

class GroupDataGenerator:
    """
    Specialized data generator for group-based test data generation.
    
    This generator creates data by processing each group separately,
    allowing fine-grained control over which fields are correct/wrong
    per group.
    """
    
    def __init__(
        self, 
        model_name: str = "llama3:latest", 
        provider: str = "ollama",
        max_retries: int = 3
    ):
        """
        Initialize the group data generator.
        
        Args:
            model_name: Name of the LLM model (for Ollama)
            provider: LLM provider ("ollama" or "groq")
            max_retries: Maximum retry attempts for LLM calls
        """
        self.provider = provider
        self.max_retries = max_retries
        
        logger.debug(f"Initializing GroupDataGenerator with provider={provider}, model={model_name}")
        
        init_kwargs = {"temperature": 0.7}
        if provider.lower() == "ollama":
            init_kwargs["model_name"] = model_name
            
        self.llm: BaseLLM = LLMFactory.create_llm(
            provider=provider, 
            **init_kwargs
        )
    
    def generate_groups(
        self,
        schema_fields: List[Dict[str, Any]],
        groups: List[Dict[str, Any]],
        additional_rules: Optional[str] = None,
        parent_tables_data: Optional[Dict[str, List[Dict]]] = None
    ) -> Dict[str, Any]:
        """
        Generate test data for multiple groups sequentially.
        
        Args:
            schema_fields: List of field definitions
            groups: List of group configurations
            additional_rules: Optional additional context/rules
            parent_tables_data: Optional parent table data for FK integrity
            
        Returns:
            Dict with keys: data (list of records), count (int), groups (list of group info)
        """
        all_data: List[Dict] = []
        group_breakdown: List[Dict] = []
        
        total_requested = sum(g.get('count', 0) for g in groups)
        logger.info(f"Starting group generation: {len(groups)} groups, {total_requested} total records")
        
        for i, group in enumerate(groups, 1):
            group_name = group.get('name', f'Group{i}')
            group_count = group.get('count', 0)
            
            if group_count <= 0:
                logger.debug(f"Skipping group '{group_name}' as requested count is 0")
                continue
            
            logger.info(f"[{i}/{len(groups)}] Generating group '{group_name}' ({group_count} records)")
            
            try:
                # Generate data for this group
                group_data = self._generate_single_group(
                    schema_fields=schema_fields,
                    group=group,
                    additional_rules=additional_rules,
                    parent_tables_data=parent_tables_data
                )
                
                # Add metadata to each record
                for record in group_data:
                    record['_group'] = group_name
                    record['_wrong_fields'] = group.get('wrong_fields', [])
                
                # Limit to requested count
                final_group_data = group_data[:group_count]
                
                logger.info(f"Generated {len(final_group_data)} records for '{group_name}'")
                
                all_data.extend(final_group_data)
                group_breakdown.append({
                    'group_name': group_name,
                    'count': len(final_group_data),
                    'correct_fields': group.get('correct_fields', []),
                    'wrong_fields': group.get('wrong_fields', [])
                })
                
            except Exception as e:
                logger.error(f"Failed to generate group '{group_name}': {e}")
                # We stop on first failure to maintain data integrity
                raise Exception(f"Failed to generate group '{group_name}': {str(e)}")
        
        logger.info(f"Generation complete. Total records: {len(all_data)}")
        
        return {
            "data": all_data,
            "count": len(all_data),
            "groups": group_breakdown
        }
    
    def _generate_single_group(
        self,
        schema_fields: List[Dict[str, Any]],
        group: Dict[str, Any],
        additional_rules: Optional[str] = None,
        parent_tables_data: Optional[Dict[str, List[Dict]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate data for a single group with retry logic.
        """
        prompt = DataGenerationPrompts.create_group_prompt(
            schema_fields=schema_fields,
            group=group,
            additional_rules=additional_rules,
            parent_tables_data=parent_tables_data
        )
        
        for attempt in range(self.max_retries):
            try:
                response = self.llm.invoke(prompt)
                
                if not response or not response.strip():
                    logger.warning(f"Empty response from LLM on attempt {attempt + 1}")
                    continue
                
                data = self._parse_response(response)
                
                if not isinstance(data, list):
                    data = [data]
                
                return data
                
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{self.max_retries} failed for group '{group.get('name')}': {e}")
                if attempt == self.max_retries - 1:
                    logger.error(f"All retry attempts failed for group '{group.get('name')}'")
                    raise e
        
        raise Exception(f"Failed to generate data for group after {self.max_retries} retries")
    
    def _parse_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse LLM response into structured data with multi-level repair."""
        # Clean response (handles NDJSON and extraction)
        source_text = NDJSONParser.parse(response) or response
        json_str = JSONExtractor.extract_json(source_text, expect_array=True) or source_text
        cleaned_json = JSONCleaner.clean(json_str)
        
        try:
            return self._load_json(cleaned_json)
        except json.JSONDecodeError:
            logger.info("Parsing failed, attempting repair...")
            repaired = JSONCleaner.repair(cleaned_json)
            try:
                return self._load_json(repaired)
            except json.JSONDecodeError:
                logger.info("Standard repair failed, attempting deep repair...")
                deep_repaired = JSONCleaner.deep_repair(cleaned_json)
                return self._load_json(deep_repaired)

    def _load_json(self, json_str: str) -> List[Dict[str, Any]]:
        """Helper to load JSON and ensure it's a list."""
        data = json.loads(json_str)
        return data if isinstance(data, list) else [data]
