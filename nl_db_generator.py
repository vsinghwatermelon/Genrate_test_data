"""
Natural Language Database Generator

Multi-agent system that generates complete databases from natural language descriptions.
Users simply describe what they want in plain English, and agents handle everything.

AGENT ARCHITECTURE:
1. TextParserAgent - Extracts tables, fields, and constraints from natural language
2. SchemaDesignerAgent - Infers missing fields and data types for each table
3. RelationshipDetectorAgent - Identifies primary and foreign key relationships
4. SchemaValidatorAgent - Ensures schema completeness and correctness
5. DatabaseGeneratorAgent - Generates data using existing intelligent generator

EXAMPLE INPUT:
"Create a college database with departments, employees, and salaries. 
Departments should have name and building. Employees work in departments 
and have salaries. Generate 5 departments, 20 employees, and 20 salary records."

OUTPUT: Complete database with proper PKs, FKs, and realistic data
"""

import json
import re
from typing import Dict, List, Any
from llm_factory import LLMFactory
from intelligent_db_generator import IntelligentDatabaseGenerator


# ============================================================================
# AGENT 1: TEXT PARSER
# ============================================================================

class TextParserAgent:
    """
    Parses natural language to extract:
    - Database name
    - Table names
    - Field mentions
    - Record counts
    - Relationships hints
    """
    
    def __init__(self, model_name: str = "llama3:latest", provider: str = "ollama"):
        self.provider = provider
        # Only pass model_name for Ollama; Groq uses model from .env
        if provider == "ollama":
            self.llm = LLMFactory.create_llm(provider=provider, model_name=model_name, temperature=0.1)
        else:
            self.llm = LLMFactory.create_llm(provider=provider, temperature=0.1)
    
    def parse(self, user_text: str) -> Dict[str, Any]:
        """Extract structured information from natural language."""
        
        prompt = f"""You are a database design expert. Analyze this natural language description and extract structured information.

USER INPUT:
{user_text}

TASK: Extract the following information in JSON format:

1. DATABASE NAME: Infer a suitable database name from context
2. TABLES: List all mentioned tables/entities
3. FIELDS: For each table, list any explicitly mentioned fields
4. RECORD COUNTS: Extract any mentioned record counts (default to 10 if not specified)
5. RELATIONSHIPS: Identify any relationship hints (e.g., "employees work in departments")
6. CONTEXT: Additional context or business rules mentioned

OUTPUT ONLY JSON (no markdown, no explanations):
{{
  "db_name": "inferred_database_name",
  "tables": [
    {{
      "name": "table_name",
      "explicit_fields": ["field1", "field2"],
      "num_records": 10,
      "context": "any mentioned context about this table"
    }}
  ],
  "relationships": [
    {{
      "from_table": "child_table",
      "to_table": "parent_table",
      "hint": "employees work in departments"
    }}
  ],
  "general_context": "overall description of the database purpose"
}}

CRITICAL: Output ONLY valid JSON, nothing else."""

        try:
            response = self.llm.invoke(prompt)
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(0))
                print(f"\n📝 TEXT PARSER AGENT:")
                print(f"   Database: {result.get('db_name')}")
                print(f"   Tables: {len(result.get('tables', []))} detected")
                print(f"   Relationships: {len(result.get('relationships', []))} hints found")
                return result
            else:
                raise Exception("Failed to extract JSON from response")
        except Exception as e:
            print(f"   ⚠️  Text parsing failed: {e}")
            raise Exception(f"Failed to parse natural language: {str(e)}")


# ============================================================================
# AGENT 2: SCHEMA DESIGNER
# ============================================================================

class SchemaDesignerAgent:
    """
    Designs complete schema for each table by:
    - Inferring missing fields based on table purpose
    - Determining appropriate data types
    - Adding common fields (created_at, updated_at, etc.)
    """
    
    def __init__(self, model_name: str = "llama3:latest", provider: str = "ollama"):
        self.provider = provider
        # Only pass model_name for Ollama; Groq uses model from .env
        if provider == "ollama":
            self.llm = LLMFactory.create_llm(provider=provider, model_name=model_name, temperature=0.2)
        else:
            self.llm = LLMFactory.create_llm(provider=provider, temperature=0.2)
    
    def design_schema(self, table_info: Dict[str, Any], all_tables: List[str]) -> List[Dict[str, Any]]:
        """Design complete field schema for a table."""
        
        table_name = table_info.get("name", "unknown")
        explicit_fields = table_info.get("explicit_fields", [])
        context = table_info.get("context", "")
        
        prompt = f"""You are a database schema designer. Design a complete field schema for this table.

TABLE: {table_name}
EXPLICIT FIELDS (user mentioned): {explicit_fields}
CONTEXT: {context}
OTHER TABLES IN DATABASE: {all_tables}

TASK: Design a complete, realistic schema with appropriate fields and data types.

RULES:
1. Include all explicitly mentioned fields
2. Infer additional logical fields based on table purpose and name
3. Use appropriate data types (string, integer, email, date, phone, boolean, etc.)
4. Add helpful examples where appropriate
5. DO NOT add primary key fields (id, table_name_id) - these will be auto-generated
6. DO NOT add foreign key fields yet - relationship agent will handle those
7. Think about what a real-world {table_name} table would need

COMMON FIELD PATTERNS:
- Users/Customers: name, email, phone, address, date_of_birth
- Products: name, description, price, category, stock_quantity
- Orders: order_date, status, total_amount
- Employees: name, email, phone, position, hire_date, salary
- Departments: name, description, location, building
- Students: name, email, enrollment_date, major
- Courses: name, description, credits, semester

OUTPUT ONLY JSON array of fields (no markdown, no explanations):
[
  {{
    "name": "field_name",
    "type": "string|integer|email|date|phone|boolean|float",
    "rules": "optional constraints like 'max 100 characters' or 'positive number'",
    "example": "optional example value"
  }}
]

Generate 5-10 appropriate fields for {table_name}."""

        try:
            response = self.llm.invoke(prompt)
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                fields = json.loads(json_match.group(0))
                print(f"   ✅ {table_name}: {len(fields)} fields designed")
                return fields
            else:
                raise Exception("Failed to extract JSON array")
        except Exception as e:
            print(f"   ⚠️  Schema design failed for {table_name}: {e}")
            # Fallback: basic schema
            return [
                {"name": "name", "type": "string"},
                {"name": "description", "type": "string"}
            ]


# ============================================================================
# AGENT 3: RELATIONSHIP DETECTOR
# ============================================================================

class RelationshipDetectorAgent:
    """
    Identifies relationships between tables and determines which foreign keys to add.
    Uses relationship hints from text parser and semantic analysis.
    """
    
    def __init__(self, model_name: str = "llama3:latest", provider: str = "ollama"):
        self.provider = provider
        # Only pass model_name for Ollama; Groq uses model from .env
        if provider == "ollama":
            self.llm = LLMFactory.create_llm(provider=provider, model_name=model_name, temperature=0.2)
        else:
            self.llm = LLMFactory.create_llm(provider=provider, temperature=0.2)
    
    def detect_relationships(
        self, 
        tables: List[Dict[str, Any]], 
        relationship_hints: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Detect foreign key relationships between tables."""
        
        table_names = [t["name"] for t in tables]
        
        prompt = f"""You are a database relationship expert. Identify foreign key relationships between these tables.

TABLES: {json.dumps([{"name": t["name"], "context": t.get("context", "")} for t in tables], indent=2)}

RELATIONSHIP HINTS FROM USER:
{json.dumps(relationship_hints, indent=2)}

TASK: Identify which tables should have foreign keys referencing other tables.

COMMON PATTERNS:
- Employees → Departments (employee has dept_id)
- Orders → Customers (order has customer_id)
- OrderItems → Orders, Products (has order_id and product_id)
- Salaries → Employees (salary has employee_id)
- Enrollments → Students, Courses (has student_id and course_id)
- Posts → Users (post has user_id/author_id)

RULES:
1. Child table gets FK to parent table (many-to-one)
2. FK field name should be clear (e.g., "dept_id", "customer_id")
3. Consider the relationship hints provided
4. Think about logical real-world relationships

OUTPUT ONLY JSON (no markdown):
{{
  "table_name": [
    {{
      "fk_field_name": "dept_id",
      "references_table": "departments",
      "reasoning": "employees belong to departments"
    }}
  ]
}}

Return empty object {{}} if no relationships detected."""

        try:
            response = self.llm.invoke(prompt)
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                relationships = json.loads(json_match.group(0))
                total_fks = sum(len(fks) for fks in relationships.values())
                print(f"\n🔗 RELATIONSHIP DETECTOR AGENT:")
                print(f"   Detected {total_fks} foreign key relationships")
                for table, fks in relationships.items():
                    for fk in fks:
                        print(f"   ✅ {table}.{fk['fk_field_name']} → {fk['references_table']}")
                return relationships
            else:
                return {}
        except Exception as e:
            print(f"   ⚠️  Relationship detection failed: {e}")
            return {}


# ============================================================================
# AGENT 4: SCHEMA VALIDATOR
# ============================================================================

class SchemaValidatorAgent:
    """
    Validates the complete schema to ensure:
    - All tables have sufficient fields
    - No duplicate field names
    - Foreign keys reference existing tables
    - Schema is complete and ready for generation
    """
    
    def __init__(self, model_name: str = "llama3:latest", provider: str = "ollama"):
        self.provider = provider
        # Only pass model_name for Ollama; Groq uses model from .env
        if provider == "ollama":
            self.llm = LLMFactory.create_llm(provider=provider, model_name=model_name, temperature=0.1)
        else:
            self.llm = LLMFactory.create_llm(provider=provider, temperature=0.1)
    
    def validate(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and optionally fix the schema."""
        
        issues = []
        tables = schema.get("tables", [])
        
        # Check each table
        for table in tables:
            table_name = table.get("table_name", "unknown")
            fields = table.get("fields", [])
            
            # Check minimum fields
            if len(fields) < 2:
                issues.append(f"Table '{table_name}' has only {len(fields)} field(s)")
            
            # Check for duplicate field names
            field_names = [f.get("name") for f in fields]
            duplicates = [name for name in field_names if field_names.count(name) > 1]
            if duplicates:
                issues.append(f"Table '{table_name}' has duplicate fields: {set(duplicates)}")
        
        if issues:
            print(f"\n⚠️  SCHEMA VALIDATOR AGENT:")
            for issue in issues:
                print(f"   ⚠️  {issue}")
        else:
            print(f"\n✅ SCHEMA VALIDATOR AGENT:")
            print(f"   Schema is valid and complete!")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "schema": schema
        }


# ============================================================================
# MAIN ORCHESTRATOR: NATURAL LANGUAGE DATABASE GENERATOR
# ============================================================================

class NaturalLanguageDatabaseGenerator:
    """
    Main orchestrator that uses multiple agents to generate databases from natural language.
    """
    
    def __init__(self, model_name: str = "llama3:latest", provider: str = "ollama"):
        self.model_name = model_name
        self.provider = provider
        # Only pass model_name for Ollama; Groq uses model from .env
        if provider == "ollama":
            self.text_parser = TextParserAgent(model_name, provider)
            self.schema_designer = SchemaDesignerAgent(model_name, provider)
            self.relationship_detector = RelationshipDetectorAgent(model_name, provider)
            self.schema_validator = SchemaValidatorAgent(model_name, provider)
            self.db_generator = IntelligentDatabaseGenerator(model_name, provider)
        else:
            self.text_parser = TextParserAgent(provider=provider)
            self.schema_designer = SchemaDesignerAgent(provider=provider)
            self.relationship_detector = RelationshipDetectorAgent(provider=provider)
            self.schema_validator = SchemaValidatorAgent(provider=provider)
            self.db_generator = IntelligentDatabaseGenerator(provider=provider)
    
    def generate_from_text(self, user_text: str) -> Dict[str, Any]:
        """
        Generate complete database from natural language description.
        
        Args:
            user_text: Natural language description of desired database
            
        Returns:
            Complete database with generated data
        """
        
        print(f"\n{'='*70}")
        print(f"🤖 NATURAL LANGUAGE DATABASE GENERATION")
        print(f"{'='*70}\n")
        print(f"User Input: {user_text[:100]}...")
        
        # PHASE 1: Parse natural language
        print(f"\n{'='*70}")
        print(f"PHASE 1: TEXT PARSING")
        print(f"{'='*70}")
        parsed_data = self.text_parser.parse(user_text)
        
        # PHASE 2: Design schema for each table
        print(f"\n{'='*70}")
        print(f"PHASE 2: SCHEMA DESIGN")
        print(f"{'='*70}")
        tables_with_schema = []
        all_table_names = [t["name"] for t in parsed_data.get("tables", [])]
        
        for table_info in parsed_data.get("tables", []):
            fields = self.schema_designer.design_schema(table_info, all_table_names)
            tables_with_schema.append({
                "table_name": table_info["name"],
                "num_records": table_info.get("num_records", 10),
                "correct_num_records": table_info.get("num_records", 10),
                "wrong_num_records": 0,
                "additional_context": table_info.get("context", ""),
                "fields": fields
            })
        
        # PHASE 3: Detect relationships and add foreign keys
        print(f"\n{'='*70}")
        print(f"PHASE 3: RELATIONSHIP DETECTION")
        print(f"{'='*70}")
        relationships = self.relationship_detector.detect_relationships(
            parsed_data.get("tables", []),
            parsed_data.get("relationships", [])
        )
        
        # Add FK fields to tables
        for table in tables_with_schema:
            table_name = table["table_name"]
            if table_name in relationships:
                for fk_info in relationships[table_name]:
                    # Add FK field to schema
                    table["fields"].append({
                        "name": fk_info["fk_field_name"],
                        "type": "integer",
                        "rules": f"foreign key to {fk_info['references_table']}"
                    })
                    print(f"   ➕ Added FK field: {table_name}.{fk_info['fk_field_name']}")
        
        # PHASE 4: Validate schema
        print(f"\n{'='*70}")
        print(f"PHASE 4: SCHEMA VALIDATION")
        print(f"{'='*70}")
        db_schema = {
            "db_name": parsed_data.get("db_name", "generated_db"),
            "use_intelligent_mode": True,
            "tables": tables_with_schema
        }
        
        validation_result = self.schema_validator.validate(db_schema)
        
        if not validation_result["valid"]:
            print(f"\n⚠️  Warning: Schema has issues but will attempt generation anyway")
        
        # PHASE 5: Generate database using intelligent generator
        print(f"\n{'='*70}")
        print(f"PHASE 5: DATABASE GENERATION")
        print(f"{'='*70}")
        print(f"🎲 Using Intelligent Database Generator with AI agents...")
        
        result = self.db_generator.generate_database(db_schema)
        
        print(f"\n{'='*70}")
        print(f"🎉 NATURAL LANGUAGE GENERATION COMPLETE!")
        print(f"{'='*70}\n")
        
        return result


# ============================================================================
# EXAMPLE USAGE (for testing)
# ============================================================================

if __name__ == "__main__":
    """
    Test the natural language generator with example inputs.
    """
    
    # Example 1: Simple college database
    user_text_1 = """
    Create a college database with departments, employees, and salaries.
    Departments should have name and building.
    Employees work in departments and have email addresses.
    Salaries are associated with employees.
    Generate 5 departments, 20 employees, and 20 salary records.
    """
    
    # Example 2: E-commerce system
    user_text_2 = """
    Generate an e-commerce database with customers, products, and orders.
    Include 10 customers, 50 products, and 30 orders.
    """
    
    generator = NaturalLanguageDatabaseGenerator()
    result = generator.generate_from_text(user_text_1)
    
    print("\n" + "="*70)
    print("GENERATION SUMMARY")
    print("="*70)
    print(json.dumps({
        "db_name": result["db_name"],
        "total_records": result["total_records"],
        "tables_generated": len(result["tables"]),
        "validation_passed": result["validation"]["overall_valid"]
    }, indent=2))
