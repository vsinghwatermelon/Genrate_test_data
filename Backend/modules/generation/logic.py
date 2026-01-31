import json
import logging
from typing import Dict, List, Any, Optional
from modules.shared.llm import LLMService
from modules.generation.prompts import DataGenerationPrompts
from modules.shared.json_utils import JSONCleaner, JSONExtractor, NDJSONParser

logger = logging.getLogger(__name__)

class DataService:
    """Handles LLM-based test data generation using schema and groups."""
    
    def __init__(self, provider: str = "ollama", model_name: Optional[str] = None):
        self.provider = provider
        # Initialize the LLM once for the service
        self.llm = LLMService.get_llm(provider=provider, model=model_name)

    def generate(
        self,
        schema_fields: List[Dict[str, Any]],
        groups: List[Dict[str, Any]],
        additional_rules: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generates test data for multiple groups sequentially."""
        all_data = []
        group_summary = []
        
        for i, group in enumerate(groups, 1):
            name = group.get('name', f'Group{i}')
            count = group.get('count', 0)
            
            if count <= 0: continue
            
            logger.info(f"Generating group '{name}' ({count} records)")
            
            # Get data for this specific group
            try:
                raw_data = self._generate_group_data(schema_fields, group, additional_rules)
                
                # Attach metadata for tracking
                for record in raw_data:
                    record['_group'] = name
                    record['_wrong_fields'] = group.get('wrong_fields', [])
                
                # Ensure we only return what was requested
                final_data = raw_data[:count]
                all_data.extend(final_data)
                
                group_summary.append({
                    'name': name,
                    'count': len(final_data),
                    'status': 'success'
                })
            except Exception as e:
                logger.error(f"Failed group {name}: {e}")
                group_summary.append({'name': name, 'count': 0, 'status': 'failed', 'error': str(e)})
            
        return {
            "data": all_data,
            "count": len(all_data),
            "groups": group_summary
        }

    def _generate_group_data(self, schema, group, rules) -> List[Dict]:
        """Calls LLM to generate data for a single group with retry logic."""
        prompt = DataGenerationPrompts.create_group_prompt(schema, group, rules)
        
        for attempt in range(2): # Short and simple retry
            try:
                response = self.llm.invoke(prompt)
                if not response: continue
                
                data = self._parse_llm_response(response)
                return data if isinstance(data, list) else [data]
            except Exception as e:
                if attempt == 1: raise e
                
        return []

    def _parse_llm_response(self, response: str) -> List[Dict]:
        """Cleans and repairs LLM JSON output."""
        text = NDJSONParser.parse(response) or response
        json_str = JSONExtractor.extract_json(text, expect_array=True) or text
        cleaned = JSONCleaner.clean(json_str)
        
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            try:
                return json.loads(JSONCleaner.repair(cleaned))
            except:
                return json.loads(JSONCleaner.deep_repair(cleaned))
