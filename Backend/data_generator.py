"""
Test Data Generator Module

Provides LLM-based test data generation with support for:
- Single table data generation
- Group-based generation with per-field validity control
- Parent table context for FK relationships
- Robust JSON parsing and error handling
"""

import json
import re
from typing import Dict, List, Any, Optional

from llm_factory import LLMFactory, BaseLLM
from prompts import DataGenerationPrompts
from utils.json_utils import JSONCleaner, JSONExtractor, NDJSONParser, parse_llm_json_response
from utils.console import safe_print, print_header, print_success, print_error
from config import get_config


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
        if provider.lower() == "ollama":
            self.llm: BaseLLM = LLMFactory.create_llm(
                provider=provider, 
                model_name=model_name, 
                temperature=temperature
            )
        else:
            self.llm = LLMFactory.create_llm(
                provider=provider, 
                temperature=temperature
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
            # Use group-based generator if groups provided
            if groups and len(groups) > 0:
                from group_data_generator import GroupDataGenerator
                group_generator = GroupDataGenerator(provider=self.provider)
                return group_generator.generate_groups(
                    schema_fields=schema_fields,
                    groups=groups,
                    additional_rules=additional_rules,
                    parent_tables_data=parent_tables_data
                )
            
            # Legacy mode: generate all at once
            total_records = num_records or (correct_num_records + wrong_num_records)
            
            # Create prompt
            prompt = DataGenerationPrompts.create_generation_prompt(
                schema_fields=schema_fields,
                num_records=total_records,
                correct_num_records=correct_num_records,
                wrong_num_records=wrong_num_records,
                additional_rules=additional_rules,
                parent_tables_data=parent_tables_data,
                groups=groups
            )
            
            # Log prompt if enabled
            if self.config.generation.log_prompts:
                print("\n--- PROMPT SENT TO LLM ---")
                safe_print(prompt)
                print("--- END PROMPT ---\n")
            
            # Invoke LLM
            response = self._invoke_llm(prompt)
            
            # Log response if enabled
            if self.config.generation.log_responses:
                print("\n--- LLM RESPONSE ---")
                safe_print(response)
                print("--- END RESPONSE ---\n")
            
            # Parse response
            generated_data = self._parse_response(response)
            
            # Ensure it's a list
            if not isinstance(generated_data, list):
                generated_data = [generated_data]
            
            # Trim to requested count
            generated_data = generated_data[:total_records]
            
            return {
                "data": generated_data,
                "count": len(generated_data)
            }
            
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse JSON. LLM response format issue: {str(e)}")
        except Exception as e:
            raise Exception(f"Error generating data: {str(e)}")
    
    def _invoke_llm(self, prompt: str) -> str:
        """
        Invoke the LLM with error handling.
        
        Args:
            prompt: The prompt to send
            
        Returns:
            LLM response text
            
        Raises:
            Exception: If LLM invocation fails
        """
        try:
            response = self.llm.invoke(prompt)
            print("LLM invocation successful.")
            return response
        except Exception as e:
            raise Exception(f"LLM connection/error: {e}")
    
    def _parse_response(self, response: str) -> List[Dict[str, Any]]:
        """
        Parse LLM response into structured data.
        
        Args:
            response: Raw LLM response
            
        Returns:
            List of parsed records
            
        Raises:
            json.JSONDecodeError: If parsing fails
        """
        if not response:
            raise ValueError("Empty response from LLM")
        
        # Try NDJSON parsing first (Ollama format)
        assembled = NDJSONParser.parse(response)
        source_text = assembled if assembled else response
        
        # Extract JSON array
        json_str = JSONExtractor.extract_json(source_text, expect_array=True)
        if not json_str:
            json_str = source_text
        
        # Clean JSON
        json_str = JSONCleaner.clean(json_str)
        
        # Try to parse
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            # Apply repairs and try again
            repaired = JSONCleaner.repair(json_str)
            try:
                data = json.loads(repaired)
            except json.JSONDecodeError as e:
                # Include context in error
                raw_snippet = (response or '')[:1000]
                raise json.JSONDecodeError(
                    f"{str(e)} -- raw LLM response snippet: {raw_snippet}",
                    e.doc,
                    e.pos
                )
        
        return data if isinstance(data, list) else [data]
    
    # Legacy method for backward compatibility
    def _clean_json_response(self, response: str) -> str:
        """Clean JSON response (legacy method)."""
        return JSONCleaner.clean(response)