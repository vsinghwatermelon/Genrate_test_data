import json
import random
from typing import Dict, List, Any
from data_generator import TestDataGenerator


class DatabaseTestDataGenerator:

    def __init__(self, model_name: str = "llama3:latest", provider: str = "ollama"):
        self.model_name = model_name
        self.provider = provider
        # Only pass model_name for Ollama; Groq uses model from .env
        if provider == "ollama":
            self.table_generator = TestDataGenerator(model_name=model_name, provider=provider)
        else:
            self.table_generator = TestDataGenerator(provider=provider)

    # ------------------------------------------------------------------------
    # Helper Methods
    # ------------------------------------------------------------------------

    def _topo_sort_tables(self, tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Topologically sort tables by FK dependencies (parents before children)."""
        name_to_table = {t["table_name"]: t for t in tables}
        visited = {}
        order = []
        
        def visit(tname):
            if visited.get(tname) == 1:
                return  # Already processed
            
            if visited.get(tname) == -1:
                raise Exception(f"Circular dependency detected for table: {tname}")
            
            visited[tname] = -1  # Mark as being processed
            table = name_to_table.get(tname)
            
            if not table:
                visited[tname] = 1
                return
                
            # Visit all parent tables first
            for field in table.get("fields", []):
                ref = field.get("references")
                if ref:
                    parent_table = ref.get("table")
                    if parent_table and parent_table != tname:
                        visit(parent_table)
            
            visited[tname] = 1
            order.append(table)
        
        # Process all tables
        for table in tables:
            if visited.get(table["table_name"]) != 1:
                visit(table["table_name"])
        
        return order

    def _generate_primary_keys(self, rows: List[Dict], pk_field: str, start_id: int = 1):
        """Generate sequential primary key values."""
        for i, row in enumerate(rows):
            row[pk_field] = start_id + i

    def _inject_foreign_keys(
        self, 
        rows: List[Dict], 
        fk_fields: List[Dict],
        generated_tables: Dict[str, List[Dict]],
        correct_count: int
    ):
        """Inject foreign key values from parent tables."""
        for fk_field in fk_fields:
            fk_name = fk_field["name"]
            ref = fk_field.get("references")
            
            if not ref:
                continue
                
            parent_table_name = ref["table"]
            parent_field_name = ref.get("field", "id")
            
            parent_rows = generated_tables.get(parent_table_name, [])
            
            if not parent_rows:
                print(f"   ⚠️  Warning: Parent table '{parent_table_name}' has no data")
                continue
            
            # Collect parent key values
            parent_keys = [p[parent_field_name] for p in parent_rows if parent_field_name in p]
            
            if not parent_keys:
                print(f"   ⚠️  Warning: No valid keys in '{parent_table_name}.{parent_field_name}'")
                continue
            
            # Inject valid FK values for correct records
            for i in range(min(len(rows), correct_count)):
                rows[i][fk_name] = random.choice(parent_keys)
            
            # Inject invalid FK values for incorrect records
            for i in range(correct_count, len(rows)):
                if fk_field.get("type") in ["integer", "int", "number"]:
                    rows[i][fk_name] = 999999 + i
                else:
                    rows[i][fk_name] = f"INVALID_FK_{parent_table_name.upper()}_{i}"

    def _identify_primary_key(self, fields: List[Dict]) -> str:
        """Identify which field is the primary key."""
        for field in fields:
            if field.get("name") == "id":
                return "id"
            if field.get("primary_key") or field.get("is_primary_key"):
                return field.get("name")
        
        # Default to 'id' if exists
        field_names = [f.get("name") for f in fields]
        if "id" in field_names:
            return "id"
        
        return None

    # ------------------------------------------------------------------------
    # Main Generation Method
    # ------------------------------------------------------------------------

    def generate_database(self, db_schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate database test data with explicit PK/FK definitions.
        
        Schema must include:
        - fields[].references for foreign keys
        - Primary key field (usually 'id')
        """
        tables = db_schema.get("tables", [])
        
        if not tables:
            raise Exception("No tables provided in db_schema")
        
        print(f"\n{'='*70}")
        print(f"🔧 MANUAL DATABASE GENERATION")
        print(f"Database: {db_schema.get('db_name', 'unnamed_db')}")
        print(f"Tables: {len(tables)}")
        print(f"{'='*70}\n")
        
        # Sort tables by dependencies
        try:
            ordered_tables = self._topo_sort_tables(tables)
            table_order = [t['table_name'] for t in ordered_tables]
            print(f"Generation order: {' → '.join(table_order)}\n")
        except Exception as e:
            raise Exception(f"Failed to sort tables: {str(e)}")
        
        result = {
            "db_name": db_schema.get("db_name", "database"),
            "tables": {},
            "counts": {},
            "generation_order": []
        }
        
        generated_tables = {}
        
        # Generate each table in dependency order
        for idx, table in enumerate(ordered_tables, 1):
            table_name = table["table_name"]
            num_records = table.get("num_records", 5)
            correct_count = table.get("correct_num_records", num_records)
            wrong_count = table.get("wrong_num_records", max(0, num_records - correct_count))
            
            print(f"[{idx}/{len(ordered_tables)}] Generating: {table_name}")
            print(f"   Records: {num_records} (valid: {correct_count}, invalid: {wrong_count})")
            
            schema_fields = table.get("fields", [])
            
            if not schema_fields:
                print(f"   ⚠️  Warning: No fields defined. Skipping.\n")
                continue
            
            # Identify FK and PK fields
            fk_fields = [f for f in schema_fields if f.get("references")]
            pk_field = self._identify_primary_key(schema_fields)
            
            # Remove PK from LLM generation (we'll generate it)
            fields_for_llm = [
                f for f in schema_fields 
                if f.get("name") != pk_field
            ] if pk_field else schema_fields
            
            try:
                # Generate data
                gen_result = self.table_generator.generate_data(
                    schema_fields=fields_for_llm,
                    num_records=num_records,
                    correct_num_records=correct_count,
                    wrong_num_records=wrong_count,
                    additional_rules=table.get("additional_rules")
                )
                
                rows = gen_result["data"]
                
                # Generate PKs
                if pk_field:
                    self._generate_primary_keys(rows, pk_field)
                    print(f"   ✓ Generated primary keys: {pk_field}")
                
                # Inject FKs
                if fk_fields:
                    self._inject_foreign_keys(rows, fk_fields, generated_tables, correct_count)
                    fk_names = [f["name"] for f in fk_fields]
                    print(f"   ✓ Injected foreign keys: {', '.join(fk_names)}")
                
                # Store results
                generated_tables[table_name] = rows
                result["tables"][table_name] = rows
                result["counts"][table_name] = {
                    "total": len(rows),
                    "valid": correct_count,
                    "invalid": wrong_count
                }
                result["generation_order"].append(table_name)
                
                print(f"   ✅ Completed: {len(rows)} records\n")
                
            except Exception as e:
                print(f"   ❌ Error: {str(e)}\n")
                raise Exception(f"Failed to generate '{table_name}': {str(e)}")
        
        # Calculate totals
        result["total_records"] = sum(len(rows) for rows in generated_tables.values())
        result["total_tables"] = len(generated_tables)
        
        print(f"{'='*70}")
        print(f"✅ GENERATION COMPLETE!")
        print(f"Total: {result['total_records']} records across {result['total_tables']} tables")
        print(f"{'='*70}\n")
        
        return result


# ============================================================================
# EXAMPLE USAGE (for testing)
# ============================================================================

if __name__ == "__main__":
    db_schema = {
        "db_name": "college_db",
        "tables": [
            {
                "table_name": "departments",
                "num_records": 5,
                "correct_num_records": 5,
                "wrong_num_records": 0,
                "fields": [
                    {"name": "id", "type": "integer", "rules": "primary key, auto-increment"},
                    {"name": "name", "type": "string", "rules": "unique, max 100 characters", "example": "Computer Science"},
                    {"name": "building", "type": "string", "example": "Engineering Hall"}
                ]
            },
            {
                "table_name": "employees",
                "num_records": 10,
                "correct_num_records": 8,
                "wrong_num_records": 2,
                "fields": [
                    {"name": "id", "type": "integer"},
                    {"name": "name", "type": "string", "rules": "max 200 chars"},
                    {"name": "email", "type": "email", "rules": "must be valid email"},
                    {"name": "dept_id", "type": "integer", "references": {"table": "departments", "field": "id"}}
                ]
            }
        ]
    }
    
    generator = DatabaseTestDataGenerator()
    result = generator.generate_database(db_schema)
    print(json.dumps(result, indent=2))
