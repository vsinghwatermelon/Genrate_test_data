import json
import logging
from typing import Dict, List, Any, Optional

from llm_factory import LLMFactory, BaseLLM
from prompts import DataGenerationPrompts
from utils.json_utils import JSONCleaner, JSONExtractor, NDJSONParser
from utils.logger import get_logger
from config import get_config

logger = get_logger(__name__)

class TestDataGenerator:
    """
    Main test data generator class.
    
    Generates test data using LLM prompts with support for:
    - Schema-based field definitions
    - Valid/invalid record generation
    - Group-based generation with per-field control
    - Parent table context for referential integrity
    """
    
    def __init__(
        self, 
        model_name: str = "llama3:latest", 
        provider: str = "ollama",
        temperature: float = 0.7
    ):
        """
        Initialize the test data generator.
        
        Args:
            model_name: LLM model name (for Ollama)
            provider: LLM provider ("ollama" or "groq")
            temperature: Generation temperature (0.0-1.0)
        """
        self.provider = provider
        self.config = get_config()
        
        # Create LLM client
        logger.debug(f"Initializing TestDataGenerator with provider={provider}, model={model_name}")
        
        init_kwargs = {"temperature": temperature}
        if provider.lower() == "ollama":
            init_kwargs["model_name"] = model_name
            
        self.llm: BaseLLM = LLMFactory.create_llm(
            provider=provider, 
            **init_kwargs
        )
    
    def generate_data(
        self, 
        schema_fields: List[Dict[str, Any]], 
        num_records: int = 5, 
        correct_num_records: int = 5, 
        wrong_num_records: int = 0, 
        additional_rules: Optional[str] = None, 
        parent_tables_data: Optional[Dict[str, List[Dict]]] = None,
        groups: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Generate test data based on schema definition.
        
        Args:
            schema_fields: List of field definitions with name, type, rules, etc.
            num_records: Total number of records to generate
            correct_num_records: Number of valid records (legacy mode)
            wrong_num_records: Number of invalid records (legacy mode)
            additional_rules: Optional additional generation rules/context
            parent_tables_data: Optional parent table data for FK relationships
            groups: Optional group-based configuration for per-field validity control
            
        Returns:
            Dict with 'data' (list of records) and 'count' (int)
            
        Raises:
            Exception: If generation or parsing fails
        """
        try:
            # 1. Check for group-based generation
            if groups and len(groups) > 0:
                return self._generate_groups(
                    schema_fields, groups, additional_rules, parent_tables_data
                )
            
            # 2. Prepare prompt
            total_records = num_records or (correct_num_records + wrong_num_records)
            prompt = DataGenerationPrompts.create_generation_prompt(
                schema_fields=schema_fields,
                num_records=total_records,
                correct_num_records=correct_num_records,
                wrong_num_records=wrong_num_records,
                additional_rules=additional_rules,
                parent_tables_data=parent_tables_data,
                groups=groups
            )
            
            if self.config.generation.log_prompts:
                logger.debug(f"Generation Prompt: {prompt}")
            
            # 3. Invoke LLM
            response = self._invoke_llm(prompt)
            
            if self.config.generation.log_responses:
                logger.debug(f"LLM Response: {response}")
            
            # 4. Parse response
            generated_data = self._parse_response(response)
            
            # Ensure it's a list and trim to requested count
            if not isinstance(generated_data, list):
                generated_data = [generated_data]
            
            final_data = generated_data[:total_records]
            
            logger.info(f"Successfully generated {len(final_data)} records")
            return {
                "data": final_data,
                "count": len(final_data)
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error in LLM response: {e}")
            raise Exception(f"Failed to parse LLM response as JSON: {str(e)}")
        except Exception as e:
            logger.error(f"Data generation failure: {e}")
            raise Exception(f"Error generating data: {str(e)}")

    def _generate_groups(
        self,
        schema_fields: List[Dict[str, Any]],
        groups: List[Dict[str, Any]],
        additional_rules: Optional[str],
        parent_tables_data: Optional[Dict[str, List[Dict]]]
    ) -> Dict[str, Any]:
        """Helper to delegate to GroupDataGenerator."""
        from group_data_generator import GroupDataGenerator
        logger.info(f"Delegating to GroupDataGenerator for {len(groups)} groups")
        group_generator = GroupDataGenerator(provider=self.provider)
        return group_generator.generate_groups(
            schema_fields=schema_fields,
            groups=groups,
            additional_rules=additional_rules,
            parent_tables_data=parent_tables_data
        )
    
    def _invoke_llm(self, prompt: str) -> str:
        """Invoke the LLM with standardized error handling and logging."""
        try:
            response = self.llm.invoke(prompt)
            logger.debug("LLM invocation successful")
            return response
        except Exception as e:
            logger.error(f"LLM invocation error: {e}")
            raise Exception(f"LLM communication failure: {e}")
    
    def _parse_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse LLM response into structured data with robust error recovery."""
        if not response:
            raise ValueError("LLM returned an empty response")
        
        # Try NDJSON parsing first
        source_text = NDJSONParser.parse(response) or response
        
        # Extract JSON array
        json_str = JSONExtractor.extract_json(source_text, expect_array=True) or source_text
        
        # Clean and attempt parse
        cleaned_json = JSONCleaner.clean(json_str)
        try:
            data = json.loads(cleaned_json)
        except json.JSONDecodeError:
            logger.warning("Standard JSON parsing failed, attempting repair...")
            repaired = JSONCleaner.repair(cleaned_json)
            try:
                data = json.loads(repaired)
                logger.info("JSON repair successful")
            except json.JSONDecodeError as e:
                snippet = response[:500]
                logger.error(f"JSON repair failed. Response snippet: {snippet!r}")
                raise json.JSONDecodeError(
                    f"{str(e)} (Snippet: {snippet})",
                    e.doc,
                    e.pos
                )
        
        return data if isinstance(data, list) else [data]