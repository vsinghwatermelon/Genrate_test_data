"""
Group Data Generator Module

Specialized generator for group-based test data generation.
Allows fine-grained control over which fields are valid/invalid per group.
"""

import json
from typing import Dict, List, Any, Optional

from llm_factory import LLMFactory, BaseLLM
from prompts import DataGenerationPrompts
from utils.json_utils import JSONCleaner, JSONExtractor, NDJSONParser
from utils.console import (
    safe_print, 
    print_header, 
    print_subheader, 
    print_success, 
    print_error,
    print_warning,
)


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
        
        if provider.lower() == "ollama":
            self.llm: BaseLLM = LLMFactory.create_llm(
                provider=provider, 
                model_name=model_name, 
                temperature=0.7
            )
        else:
            self.llm = LLMFactory.create_llm(provider=provider, temperature=0.7)
    
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
        
        total_records = sum(g.get('count', 0) for g in groups)
        
        print_header("GROUP-BASED DATA GENERATION")
        safe_print(f"Total Groups: {len(groups)}")
        safe_print(f"Total Records: {total_records}")
        
        for i, group in enumerate(groups, 1):
            group_name = group.get('name', f'Group{i}')
            group_count = group.get('count', 0)
            
            if group_count <= 0:
                safe_print(f"⊘ Skipping {group_name} (count = 0)")
                continue
            
            print_subheader(f"[{i}/{len(groups)}] Generating {group_name}")
            safe_print(f"  Records: {group_count}")
            safe_print(f"  Correct Fields: {', '.join(group.get('correct_fields', [])) or 'All'}")
            safe_print(f"  Wrong Fields: {', '.join(group.get('wrong_fields', [])) or 'None'}")
            
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
                group_data = group_data[:group_count]
                
                print_success(f"Generated {len(group_data)} records for {group_name}")
                
                all_data.extend(group_data)
                group_breakdown.append({
                    'group_name': group_name,
                    'count': len(group_data),
                    'correct_fields': group.get('correct_fields', []),
                    'wrong_fields': group.get('wrong_fields', [])
                })
                
            except Exception as e:
                print_error(f"Error generating {group_name}: {str(e)}")
                raise Exception(f"Failed to generate {group_name}: {str(e)}")
        
        print_header("GENERATION COMPLETE")
        safe_print(f"Total Records Generated: {len(all_data)}")
        safe_print(f"Groups Processed: {len(group_breakdown)}")
        
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
        
        Args:
            schema_fields: List of field definitions
            group: Group configuration
            additional_rules: Optional additional context
            parent_tables_data: Optional parent table data
            
        Returns:
            List of generated records
        """
        # Create specialized prompt for this group
        prompt = DataGenerationPrompts.create_group_prompt(
            schema_fields=schema_fields,
            group=group,
            additional_rules=additional_rules,
            parent_tables_data=parent_tables_data
        )
        
        safe_print(f"  Prompt length: {len(prompt)} characters")
        
        # Retry loop
        for attempt in range(self.max_retries):
            try:
                # Generate data using LLM
                response = self.llm.invoke(prompt)
                safe_print(f"  LLM response received ({len(response) if response else 0} chars)")
                
                # Check for empty response
                if not response or len(response.strip()) == 0:
                    if attempt < self.max_retries - 1:
                        print_warning(f"Empty response, retrying... ({attempt + 2}/{self.max_retries})")
                        continue
                    else:
                        raise Exception("LLM returned empty response after all retries")
                
                # Parse the response
                data = self._parse_response(response)
                
                if not isinstance(data, list):
                    data = [data]
                
                return data
                
            except json.JSONDecodeError as e:
                if attempt < self.max_retries - 1:
                    print_warning(f"JSON parse error: {str(e)}")
                    print_warning(f"Retrying... ({attempt + 2}/{self.max_retries})")
                    continue
                else:
                    print_error(f"Failed to parse JSON after all retries")
                    raise Exception(f"Failed to parse JSON: {str(e)}")
                    
            except Exception as e:
                if attempt < self.max_retries - 1:
                    print_warning(f"LLM error: {e}")
                    print_warning(f"Retrying... ({attempt + 2}/{self.max_retries})")
                    continue
                else:
                    raise Exception(f"LLM error after all retries: {e}")
        
        raise Exception("Failed to generate data after all retries")
    
    def _parse_response(self, response: str) -> List[Dict[str, Any]]:
        """
        Parse LLM response into structured data.
        
        Args:
            response: Raw LLM response
            
        Returns:
            List of parsed records
        """
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
            except json.JSONDecodeError:
                # Try deep repair as last resort
                deep_repaired = JSONCleaner.deep_repair(json_str)
                data = json.loads(deep_repaired)
        
        return data if isinstance(data, list) else [data]
