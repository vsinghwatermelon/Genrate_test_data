"""
AGENT ARCHITECTURE:
1. PrimaryKeyDetectionAgent - Detects/creates table-specific primary keys (e.g., customer_id)
2. ForeignKeyDetectionAgent - Detects existing foreign key relationships
3. SchemaEnhancementAgent - Suggests and adds missing FK fields for proper relationships
4. RelationshipInferenceAgent - Infers business rules and realistic data constraints
5. DataGenerationCoordinator - Generates data with parent table context for logical consistency
6. DataValidationAgent - Validates referential integrity across all tables

WORKFLOW:
Phase 0: Pre-processing (remove duplicates)
Phase 1: PK Detection → Each table gets a unique identifier
Phase 2: FK Detection → Identify existing relationships
Phase 3: Schema Enhancement → Add missing relationships
Phase 4: Relationship Inference → Generate business rules
Phase 5: Topological Sort → Determine generation order
Phase 6: Data Generation → Generate with parent table context
Phase 7: Validation → Verify referential integrity

"""

import json
import re
import random
from typing import Dict, List, Any
from data_generator import TestDataGenerator
from llm_factory import LLMFactory


# ============================================================================
# AGENT 1: PRIMARY KEY DETECTION
# ============================================================================

class PrimaryKeyDetectionAgent:
    """
    Specialized agent for detecting and creating primary keys.
    Ensures every table has a proper unique identifier.
    """
    
    def __init__(self, model_name: str = "llama3:latest", provider: str = "ollama"):
        self.provider = provider
        self.llm = LLMFactory.create_llm(provider=provider, model_name=model_name, temperature=0.1)
    
    def detect_or_create_primary_key(self, table: Dict[str, Any]) -> str:
        """
        Detect existing PK or determine where to add one.
        Returns the primary key field name.
        """
        table_name = table.get("table_name", "unknown")
        fields = table.get("fields", [])
        
        # Generate table-specific ID name (e.g., "customer_id" for "customer" table)
        # Handle both singular and plural table names
        table_name_singular = table_name.rstrip('s') if table_name.endswith('s') and len(table_name) > 1 else table_name
        auto_id_name = f"{table_name_singular}_id"
        
        # Check if explicit id field exists
        for field in fields:
            fname = field.get("name", "").strip().lower()
            if fname == "id" or fname == auto_id_name.lower() or fname == f"{table_name.lower()}_id":
                return field.get("name").strip()
        
        # Ask LLM if any field could serve as PK
        field_info = [{"name": f.get("name"), "type": f.get("type"), "rules": f.get("rules", "")} for f in fields]
        
        prompt = f"""You are a database design expert. Analyze this table and determine the PRIMARY KEY.

Table: {table_name}
Fields: {json.dumps(field_info, indent=2)}

TASK: Identify which field should be the primary key, or if we need to add an '{auto_id_name}' field.

Rules:
- Primary key must uniquely identify each record
- Look for fields like: id, {table_name}_id, {auto_id_name}, or unique identifiers
- If no suitable PK exists, we should add a '{auto_id_name}' field

OUTPUT ONLY JSON:
{{
  "primary_key": "field_name or 'NONE' if need to add id",
  "reasoning": "brief explanation",
  "should_add_id": true/false
}}"""
        
        try:
            response = self.llm.invoke(prompt)
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(0))
                
                if result.get("should_add_id") or result.get("primary_key") == "NONE":
                    # Add table-specific id field (e.g., "customer_id" for "customer" table)
                    id_field = {
                        "name": auto_id_name,
                        "type": "integer",
                        "rules": "auto-generated primary key",
                        "_auto_generated": True
                    }
                    table["fields"].insert(0, id_field)
                    return auto_id_name
                else:
                    return result.get("primary_key", auto_id_name)
        except Exception as e:
            print(f"   ⚠️  PK detection failed, adding default '{auto_id_name}': {e}")
        
        # Fallback: add table-specific id field
        id_field = {
            "name": auto_id_name,
            "type": "integer",
            "rules": "auto-generated primary key",
            "_auto_generated": True
        }
        table["fields"].insert(0, id_field)
        return auto_id_name


# ============================================================================
# AGENT 2: FOREIGN KEY DETECTION
# ============================================================================

class ForeignKeyDetectionAgent:
    """
    Specialized agent for detecting foreign key relationships between tables.
    Identifies which fields in one table reference primary keys in other tables.
    """
    
    def __init__(self, model_name: str = "llama3:latest", provider: str = "ollama"):
        self.provider = provider
        # Only pass model_name for Ollama; Groq uses model from .env
        if provider == "ollama":
            self.llm = LLMFactory.create_llm(provider=provider, model_name=model_name, temperature=0.2)
        else:
            self.llm = LLMFactory.create_llm(provider=provider, temperature=0.2)
    
    def detect_foreign_keys(
        self, 
        table: Dict[str, Any], 
        all_tables: List[Dict[str, Any]],
        primary_keys: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """
        Detect which existing fields in the table are foreign keys.
        """
        table_name = table.get("table_name", "unknown")
        fields = table.get("fields", [])
        user_context = table.get("additional_context", "")
        
        # Build info about other tables
        other_tables_info = []
        for t in all_tables:
            if t["table_name"] != table_name:
                other_tables_info.append({
                    "name": t["table_name"],
                    "primary_key": primary_keys.get(t["table_name"], "id"),
                    "context": t.get("additional_context", ""),
                    "fields": [f.get("name") for f in t.get("fields", [])]
                })
        
        prompt = f"""You are a database relationship expert. Analyze which EXISTING fields in this table are FOREIGN KEYS.

Current Table: {table_name}
User Context: {user_context}
Fields: {json.dumps([{"name": f.get("name"), "type": f.get("type"), "rules": f.get("rules", "")} for f in fields], indent=2)}

Other Tables:
{json.dumps(other_tables_info, indent=2)}

**CRITICAL RULES**:
1. Only identify EXISTING fields as FKs (don't suggest new fields yet)
2. EXCLUDE aggregate/count fields (e.g., "number of employee", "total", "count") - these are NOT foreign keys
3. Look for:
   - Fields ending with "_id" (e.g., "dept_id", "employee_id")
   - Fields matching table names (e.g., "department" might reference department table)
   - Fields semantically suggesting relationships

OUTPUT ONLY JSON:
{{
  "foreign_keys": [
    {{
      "field": "existing_field_name",
      "references_table": "table_name",
      "references_field": "primary_key_of_that_table",
      "reasoning": "why this is a FK"
    }}
  ]
}}"""
        
        try:
            response = self.llm.invoke(prompt)
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(0))
                return result.get("foreign_keys", [])
        except Exception as e:
            print(f"   ⚠️  FK detection failed: {e}")
        
        return []


# ============================================================================
# AGENT 3: SCHEMA ENHANCEMENT (Missing Relationships)
# ============================================================================

class SchemaEnhancementAgent:
    """
    Specialized agent for adding missing foreign key fields to establish relationships.
    This agent suggests NEW fields that should be added for proper relational design.
    """
    
    def __init__(self, model_name: str = "llama3:latest", provider: str = "ollama"):
        self.provider = provider
        self.llm = LLMFactory.create_llm(provider=provider, model_name=model_name, temperature=0.3)
    
    def suggest_missing_relationships(
        self,
        table: Dict[str, Any],
        all_tables: List[Dict[str, Any]],
        primary_keys: Dict[str, str],
        existing_fks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Suggest new FK fields that should be added for proper relationships.
        """
        table_name = table.get("table_name", "unknown")
        fields = table.get("fields", [])
        user_context = table.get("additional_context", "")
        
        existing_fk_tables = [fk["references_table"] for fk in existing_fks]
        existing_field_names = [f.get("name") for f in fields]
        
        # Build info about other tables
        other_tables_info = []
        for t in all_tables:
            if t["table_name"] != table_name and t["table_name"] not in existing_fk_tables:
                other_tables_info.append({
                    "name": t["table_name"],
                    "primary_key": primary_keys.get(t["table_name"], "id"),
                    "primary_key_type": "integer",  # Assuming auto-generated IDs are integers
                    "context": t.get("additional_context", "")
                })
        
        if not other_tables_info:
            return []
        
        prompt = f"""You are a database design expert. Determine if this table is MISSING foreign key relationships.

Current Table: {table_name}
User Context: {user_context}
Existing Fields: {existing_field_names}
Already Has FKs to: {existing_fk_tables}

Other Tables Available:
{json.dumps(other_tables_info, indent=2)}

TASK: Based on semantic relationships and common database patterns, suggest NEW FK fields to add.

Examples:
- If table is "Employee" and "Department" exists → add "dept_id" or "department_id"
- If table is "Salary" and "Employee" exists → add "employee_id"
- If table is "Order" and "Customer" exists → add "customer_id"

IMPORTANT:
- Use common naming conventions: <table>_id (e.g., "employee_id", "dept_id")
- Only suggest if it makes SEMANTIC sense
- Don't suggest if already exists
- Consider user context carefully

OUTPUT ONLY JSON:
{{
  "suggested_foreign_keys": [
    {{
      "field_name": "new_field_name_to_add",
      "field_type": "integer",
      "references_table": "table_name",
      "references_field": "primary_key",
      "reasoning": "why this relationship makes sense"
    }}
  ]
}}

If no additional FKs needed, return empty array."""
        
        try:
            response = self.llm.invoke(prompt)
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(0))
                return result.get("suggested_foreign_keys", [])
        except Exception as e:
            print(f"   ⚠️  Schema enhancement failed: {e}")
        
        return []


# ============================================================================
# AGENT 4: RELATIONSHIP INFERENCE (Business Rules)
# ============================================================================

class RelationshipInferenceAgent:
    """
    Agent that infers additional context and rules for each table
    based on its purpose and relationships.
    """
    
    def __init__(self, model_name: str = "llama3:latest", provider: str = "ollama"):
        self.provider = provider
        self.llm = LLMFactory.create_llm(provider=provider, model_name=model_name, temperature=0.3)
    
    def infer_additional_rules(self, table: Dict[str, Any], schema_analysis: Dict[str, Any]) -> str:
        """
        Infer additional generation rules for a table based on context.
        """
        table_name = table.get("table_name", "unknown")
        fields = table.get("fields", [])
        fks = schema_analysis.get("foreign_keys", [])
        
        prompt = f"""You are a test data generation expert. Given this table schema, suggest ADDITIONAL RULES for generating realistic test data.

TABLE: {table_name}
FIELDS: {json.dumps(fields, indent=2)}
FOREIGN KEYS: {json.dumps(fks, indent=2)}

Consider:
- What real-world entity does this table represent?
- What business rules or constraints apply?
- What data patterns are typical for this domain?
- What diversity is needed for good test coverage?

Examples:
- For "employees": "Generate diverse job titles (Professor, Assistant, Dean), email should match name pattern, hire dates should be in past"
- For "students": "Age between 18-30, emails should have student format, enrollment dates recent, diverse majors"
- For "orders": "Order dates should be recent, amounts should vary, status should include pending/completed/cancelled"

Return ONLY a concise string of additional rules (2-3 sentences max), NO JSON, NO extra formatting:"""

        try:
            response = self.llm.invoke(prompt)
            rules = response.strip()
            
            # Remove any markdown or code blocks
            rules = re.sub(r'```.*?```', '', rules, flags=re.DOTALL)
            rules = re.sub(r'`', '', rules)
            
            # Take first 2-3 sentences
            sentences = rules.split('. ')
            rules = '. '.join(sentences[:3])
            
            if rules and not rules.endswith('.'):
                rules += '.'
            
            print(f"   Additional Rules: {rules}")
            return rules
            
        except Exception as e:
            print(f"⚠️  Rule inference failed: {e}")
            return f"Generate diverse, realistic data for {table_name} table."


# ============================================================================
# AGENT 6: DATA VALIDATION
# ============================================================================

class DataValidationAgent:
    """
    Agent that validates generated data for:
    - Referential integrity
    - Data type correctness
    - Business rule compliance
    - Uniqueness constraints
    """
    
    def __init__(self, model_name: str = "llama3:latest", provider: str = "ollama"):
        self.provider = provider
        self.llm = LLMFactory.create_llm(provider=provider, model_name=model_name, temperature=0.1)
    
    def validate_database(
        self, 
        db_data: Dict[str, List[Dict]], 
        schema_analyses: Dict[str, Dict]
    ) -> Dict[str, Any]:
        """
        Validate entire database for correctness.
        """
        validation_report = {
            "overall_valid": True,
            "tables": {},
            "errors": [],
            "warnings": []
        }
        
        print(f"\n🔍 Validating generated database...")
        
        for table_name, rows in db_data.items():
            table_validation = self._validate_table(
                table_name, 
                rows, 
                schema_analyses.get(table_name, {}),
                db_data
            )
            validation_report["tables"][table_name] = table_validation
            
            if not table_validation["valid"]:
                validation_report["overall_valid"] = False
            
            validation_report["errors"].extend(table_validation.get("errors", []))
            validation_report["warnings"].extend(table_validation.get("warnings", []))
        
        # Print summary
        if validation_report["overall_valid"]:
            print(f"✅ Validation passed! All data is correct.")
        else:
            print(f"⚠️  Validation found issues:")
            for error in validation_report["errors"][:5]:  # Show first 5
                print(f"   ❌ {error}")
        
        return validation_report
    
    def _validate_table(
        self, 
        table_name: str, 
        rows: List[Dict],
        schema_analysis: Dict,
        all_data: Dict[str, List[Dict]]
    ) -> Dict[str, Any]:
        """
        Validate a single table's data.
        """
        validation = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "stats": {
                "total_records": len(rows),
                "valid_records": 0,
                "invalid_records": 0
            }
        }
        
        pk_field = schema_analysis.get("primary_key")
        fks = schema_analysis.get("foreign_keys", [])
        
        # Track PKs for uniqueness
        seen_pks = set()
        
        for i, row in enumerate(rows):
            is_valid = row.get("is_valid", True)
            
            if is_valid:
                validation["stats"]["valid_records"] += 1
            else:
                validation["stats"]["invalid_records"] += 1
            
            # Validate PK uniqueness
            if pk_field and pk_field in row:
                pk_value = row[pk_field]
                if pk_value in seen_pks:
                    validation["errors"].append(
                        f"{table_name}[{i}]: Duplicate primary key {pk_field}={pk_value}"
                    )
                    validation["valid"] = False
                seen_pks.add(pk_value)
            
            # Validate FK references (only for valid records)
            if is_valid:
                for fk in fks:
                    fk_field = fk["field"]
                    ref_table = fk["references_table"]
                    ref_field = fk.get("references_field", "id")
                    
                    if fk_field in row and ref_table in all_data:
                        fk_value = row[fk_field]
                        ref_values = [r.get(ref_field) for r in all_data[ref_table]]
                        
                        if fk_value not in ref_values:
                            validation["errors"].append(
                                f"{table_name}[{i}]: FK {fk_field}={fk_value} references non-existent {ref_table}.{ref_field}"
                            )
                            validation["valid"] = False
        
        return validation


# ============================================================================
# MAIN ORCHESTRATOR: INTELLIGENT DATABASE GENERATOR
# ============================================================================

class IntelligentDatabaseGenerator:
    """
    Main orchestrator that uses multiple specialized agents to generate database test data.
    
    Agent Workflow:
    1. PrimaryKeyDetectionAgent - Ensures every table has a PK
    2. ForeignKeyDetectionAgent - Detects existing FK relationships
    3. SchemaEnhancementAgent - Adds missing FK fields for relationships
    4. RelationshipInferenceAgent - Infers business rules
    5. DataGenerationCoordinator - Generates data with context
    6. DataValidationAgent - Validates referential integrity
    """
    
    def __init__(self, model_name: str = "llama3:latest", provider: str = "ollama"):
        self.model_name = model_name
        self.provider = provider
        # Specialized agents - only pass model_name for Ollama
        if provider == "ollama":
            self.pk_detector = PrimaryKeyDetectionAgent(model_name, provider)
            self.fk_detector = ForeignKeyDetectionAgent(model_name, provider)
            self.schema_enhancer = SchemaEnhancementAgent(model_name, provider)
            self.relationship_inferencer = RelationshipInferenceAgent(model_name, provider)
            self.data_validator = DataValidationAgent(model_name, provider)
            self.table_generator = TestDataGenerator(model_name, provider)
        else:
            self.pk_detector = PrimaryKeyDetectionAgent(provider=provider)
            self.fk_detector = ForeignKeyDetectionAgent(provider=provider)
            self.schema_enhancer = SchemaEnhancementAgent(provider=provider)
            self.relationship_inferencer = RelationshipInferenceAgent(provider=provider)
            self.data_validator = DataValidationAgent(provider=provider)
            self.table_generator = TestDataGenerator(provider=provider)
    
    def generate_database(self, db_schema: Dict[str, Any]) -> Dict[str, Any]:
        tables = db_schema.get("tables", [])
        
        if not tables:
            raise Exception("No tables provided in db_schema")
        
        # Normalize table and field names (remove extra spaces)
        for table in tables:
            table["table_name"] = table["table_name"].strip()
            for field in table.get("fields", []):
                field["name"] = field["name"].strip()
        
        print(f"NTELLIGENT MULTI-AGENT DATABASE GENERATION")
        print(f"Database: {db_schema.get('db_name', 'unnamed_db')}")
        print(f"Tables: {len(tables)}")
        
        # PHASE 0: Remove duplicates
        print(f"PHASE 0: Pre-processing - Remove Duplicates...")
        for table in tables:
            table_name = table["table_name"]
            fields = table.get("fields", [])
            
            # Remove duplicate field names
            seen_names = set()
            unique_fields = []
            for field in fields:
                field_name = field.get("name", "").strip()
                if field_name not in seen_names:
                    seen_names.add(field_name)
                    unique_fields.append(field)
                else:
                    print(f" Removed duplicate field '{field_name}' from {table_name}")
            
            table["fields"] = unique_fields
        
        # PHASE 1: Primary Key Detection (Agent 1)
        print(f"\n PHASE 1: Primary Key Detection Agent...")
        primary_keys = {}
        for table in tables:
            table_name = table["table_name"]
            pk_field = self.pk_detector.detect_or_create_primary_key(table)
            primary_keys[table_name] = pk_field
            print(f" {table_name}.{pk_field} (Primary Key)")
        
        # PHASE 2: Foreign Key Detection (Agent 2)
        print(f"\n PHASE 2: Foreign Key Detection Agent...")
        detected_fks = {}
        for table in tables:
            table_name = table["table_name"]
            fks = self.fk_detector.detect_foreign_keys(table, tables, primary_keys)
            detected_fks[table_name] = fks
            
            # Apply detected FKs to fields
            for fk in fks:
                field_name = fk["field"]
                ref_table = fk["references_table"]
                ref_field = fk["references_field"]
                
                # Find and update the field
                for field in table["fields"]:
                    if field["name"] == field_name:
                        field["references"] = {
                            "table": ref_table,
                            "field": ref_field
                        }
                        print(f" Detected: {table_name}.{field_name} → {ref_table}.{ref_field}")
                        break
        
        # PHASE 3: Schema Enhancement (Agent 3)
        print(f"\n PHASE 3: Schema Enhancement Agent (Adding Missing Relationships)...")
        for table in tables:
            table_name = table["table_name"]
            existing_fks = detected_fks.get(table_name, [])
            
            # Get suggestions for missing FK fields
            suggested_fks = self.schema_enhancer.suggest_missing_relationships(
                table, tables, primary_keys, existing_fks
            )
            
            for suggestion in suggested_fks:
                field_name = suggestion["field_name"]
                
                # Check if field already exists
                field_exists = any(f["name"] == field_name for f in table["fields"])
                
                if field_exists:
                    # Just add the reference
                    for field in table["fields"]:
                        if field["name"] == field_name:
                            field["references"] = {
                                "table": suggestion["references_table"],
                                "field": suggestion["references_field"]
                            }
                            print(f"   ✨ Enhanced: {table_name}.{field_name} → {suggestion['references_table']}.{suggestion['references_field']}")
                            print(f"      Reason: {suggestion['reasoning']}")
                            break
                else:
                    # Add new FK field
                    new_field = {
                        "name": field_name,
                        "type": suggestion["field_type"],
                        "rules": f"foreign key to {suggestion['references_table']}",
                        "references": {
                            "table": suggestion["references_table"],
                            "field": suggestion["references_field"]
                        },
                        "_ai_generated": True
                    }
                    table["fields"].append(new_field)
                    print(f"   ✨ Added: {table_name}.{field_name} → {suggestion['references_table']}.{suggestion['references_field']}")
                    print(f"      Reason: {suggestion['reasoning']}")
        
        # PHASE 4: Relationship Inference (Agent 4)
        print(f"\nPHASE 4: Relationship Inference Agent (Business Rules)...")
        for table in tables:
            table_name = table["table_name"]
            # Create a simple analysis dict for compatibility
            analysis = {
                "primary_key": primary_keys.get(table_name),
                "foreign_keys": []
            }
            additional_rules = self.relationship_inferencer.infer_additional_rules(table, analysis)
            table["_inferred_rules"] = additional_rules
            print(f"  {table_name}: {additional_rules[:100]}...")
        
        # PHASE 5: Topological Sort
        print(f"\nPHASE 5: Determining Generation Order...")
        try:
            ordered_tables = self._topo_sort_tables(tables)
            print(f"   Generation order: {' → '.join([t['table_name'] for t in ordered_tables])}")
        except Exception as e:
            raise Exception(f"Failed to sort tables: {str(e)}")
        
        # PHASE 6: Data Generation (Agent 5 - Coordinator)
        print(f"\n PHASE 6: Data Generation Coordinator Agent...")
        result = {
            "db_name": db_schema.get("db_name", "database"),
            "tables": {},
            "counts": {},
            "generation_order": [],
            "primary_keys": primary_keys
        }
        
        generated_tables = {}
        
        for idx, table in enumerate(ordered_tables, 1):
            table_name = table["table_name"]
            # Convert to integers to handle string inputs from frontend
            num_records = int(table.get("num_records", 5))
            correct_count = int(table.get("correct_num_records", num_records))
            wrong_count = int(table.get("wrong_num_records", max(0, num_records - correct_count)))
            
            print(f"\n[{idx}/{len(ordered_tables)}] Generating: {table_name}")
            print(f"   Records: {num_records} (valid: {correct_count}, invalid: {wrong_count})")
            
            # Combine user context with inferred rules
            user_context = table.get("additional_context", "")
            inferred_rules = table.get("_inferred_rules", "")
            combined_rules = f"{user_context}. {inferred_rules}".strip()
            
            schema_fields = table.get("fields", [])
            pk_field = primary_keys.get(table_name, "id")
            fk_fields = [f for f in schema_fields if f.get("references")]
            
            # Remove PK and FK fields from LLM generation (they'll be auto-generated/injected)
            fields_for_llm = [
                f for f in schema_fields 
                if f.get("name") != pk_field and not f.get("references")
            ]
            
            # Prepare parent tables data context for logical consistency
            parent_tables_context = {}
            for fk_field in fk_fields:
                ref = fk_field.get("references")
                if ref:
                    parent_table_name = ref["table"]
                    if parent_table_name in generated_tables:
                        parent_tables_context[parent_table_name] = generated_tables[parent_table_name]
            
            try:
                # Generate data with parent table context
                gen_result = self.table_generator.generate_data(
                    schema_fields=fields_for_llm,
                    num_records=num_records,
                    correct_num_records=correct_count,
                    wrong_num_records=wrong_count,
                    additional_rules=combined_rules,
                    parent_tables_data=parent_tables_context if parent_tables_context else None
                )
                
                rows = gen_result["data"]
                
                # Generate PKs
                if pk_field:
                    self._generate_primary_keys(rows, pk_field)
                    print(f"   ✓ Generated primary keys: {pk_field}")
                
                # Inject FKs
                if fk_fields:
                    self._inject_foreign_keys(rows, fk_fields, generated_tables, correct_count, pk_field)
                    fk_names = [f["name"] for f in fk_fields]
                    print(f"   ✓ Injected foreign keys: {', '.join(fk_names)}")
                
                # Show sample records with all fields (including FKs)
                print(f"\n    Sample records (with FKs):")
                for i in range(min(3, len(rows))):
                    print(f"      Record {i+1}: {rows[i]}")
                
                generated_tables[table_name] = rows
                result["tables"][table_name] = rows
                result["counts"][table_name] = {
                    "total": len(rows),
                    "valid": correct_count,
                    "invalid": wrong_count
                }
                result["generation_order"].append(table_name)
                
                print(f"    Completed: {len(rows)} records")
                
            except Exception as e:
                print(f"    Error: {str(e)}")
                raise
        
        # PHASE 7: Validation (Agent 6)
        print(f"\n PHASE 7: Data Validation Agent...")
        # Build schema_analyses for validation compatibility
        schema_analyses_for_validation = {}
        for table_name, pk in primary_keys.items():
            schema_analyses_for_validation[table_name] = {
                "primary_key": pk,
                "foreign_keys": []
            }
        
        validation_report = self.data_validator.validate_database(generated_tables, schema_analyses_for_validation)
        result["validation"] = validation_report
        
        result["total_records"] = sum(len(rows) for rows in generated_tables.values())
        result["total_tables"] = len(generated_tables)
        
        print(f"\n{'='*70}")
        print(f"🎉 DATABASE GENERATION COMPLETE!")
        print(f"Total: {result['total_records']} records across {result['total_tables']} tables")
        print(f"Validation: {'PASSED' if validation_report['overall_valid'] else '⚠️  HAS ISSUES'}")
        print(f"{'='*70}\n")
        
        return result
    
    # ------------------------------------------------------------------------
    # Helper Methods
    # ------------------------------------------------------------------------
    
    def _topo_sort_tables(self, tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Topological sort by FK dependencies.

        Uses Kahn's algorithm and is tolerant to cycles: if cycles are present
        it will log a warning and break them deterministically to produce a
        best-effort generation order instead of raising an exception. This
        keeps the generator from crashing when agents produce mutually
        referencing FK suggestions.
        """
        # Map table name -> table dict
        name_to_table = {t["table_name"]: t for t in tables}

        # Build graph: parent -> set(children)
        parents_to_children = {name: set() for name in name_to_table}
        in_degree = {name: 0 for name in name_to_table}

        for t in tables:
            child = t["table_name"]
            for field in t.get("fields", []):
                ref = field.get("references")
                if ref:
                    parent = ref.get("table")
                    if parent and parent in name_to_table and parent != child:
                        parents_to_children[parent].add(child)
                        in_degree[child] = in_degree.get(child, 0) + 1

        # Kahn's algorithm
        queue = [name for name, deg in in_degree.items() if deg == 0]
        order_names = []

        while queue:
            node = queue.pop(0)
            order_names.append(node)
            for child in list(parents_to_children.get(node, [])):
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)

        # If not all nodes were processed, we have a cycle. Break cycles deterministically
        remaining = [name for name, deg in in_degree.items() if deg > 0]
        if remaining:
            print(f"   ⚠️  Circular dependency detected among tables: {remaining}")
            # Append remaining nodes in a deterministic order to complete ordering
            # This breaks cycles by allowing some tables to be generated before
            # their parents; foreign keys will still be injected but parents
            # may be absent at that generation step (warnings will be printed).
            for name in sorted(remaining):
                if name not in order_names:
                    order_names.append(name)

        # Convert names back to table dicts preserving the order
        ordered_tables = [name_to_table[name] for name in order_names if name in name_to_table]
        return ordered_tables
    
    def _generate_primary_keys(self, rows: List[Dict], pk_field: str, start_id: int = 1):
        """Generate sequential primary keys."""
        for i, row in enumerate(rows):
            row[pk_field] = start_id + i
    
    def _inject_foreign_keys(
        self, 
        rows: List[Dict], 
        fk_fields: List[Dict],
        generated_tables: Dict[str, List[Dict]],
        correct_count: int,
        pk_field: str = None
    ):
        """Inject foreign key values."""
        for fk_field in fk_fields:
            fk_name = fk_field["name"]
            ref = fk_field.get("references")
            
            if not ref:
                continue
            
            parent_table_name = ref["table"]
            parent_field_name = ref.get("field", "id")
            
            parent_rows = generated_tables.get(parent_table_name, [])
            
            if not parent_rows:
                print(f"     Warning: Parent table '{parent_table_name}' has no data")
                continue
            
            parent_keys = [p[parent_field_name] for p in parent_rows if parent_field_name in p]
            
            if not parent_keys:
                print(f"     Warning: No valid keys in '{parent_table_name}.{parent_field_name}'")
                continue

            # Avoid overwriting this table's primary key when an FK has the same name
            if pk_field and fk_name == pk_field:
                print(f"     ⚠️  Skipping injection for FK '{fk_name}' because it matches the primary key '{pk_field}' and would overwrite PK values")
                continue

            print(f"        FK '{fk_name}' → {parent_table_name}.{parent_field_name}")
            print(f"           Available parent values: {parent_keys[:5]}{'...' if len(parent_keys) > 5 else ''}")

            # Valid records get real FK values
            for i in range(min(len(rows), correct_count)):
                rows[i][fk_name] = random.choice(parent_keys)
            
            # Invalid records get broken FK values
            for i in range(correct_count, len(rows)):
                if fk_field.get("type") in ["integer", "int", "number"]:
                    rows[i][fk_name] = 999999 + i
                else:
                    rows[i][fk_name] = f"INVALID_FK_{parent_table_name.upper()}_{i}"
            
            # Show sample of injected values
            sample_injected = [rows[i][fk_name] for i in range(min(3, len(rows)))]
            print(f"         Sample injected: {sample_injected}")

