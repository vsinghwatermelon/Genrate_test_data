"""
Selenium Locator & Script Analyzer

Advanced parser for extracting technical metadata from Selenium automation assets.
Supports dynamic parsing of locator configuration files (JSON, Python dicts)
and high-level semantic analysis of automation scripts for schema inference.
"""

import re
import json
import ast
import os
import uuid
import time
import logging
from typing import Dict, List, Any, Optional, Tuple

from utils.selenium_utils import create_chrome_driver
from llm_factory import LLMFactory, BaseLLM
from prompts import SeleniumParserPrompts
from utils.json_utils import JSONCleaner, JSONExtractor, NDJSONParser
from utils.console import safe_print

logger = logging.getLogger(__name__)


# ============================================================================
# SECTION 1: LOCATOR CONFIGURATION PARSER
# ============================================================================

class LocatorParser:
    """Provides tools for identifying and extracting element locators from asset files."""

    @staticmethod
    def parse_file(file_path: str) -> Dict[str, Any]:
        """Entry point: Automatically detects file format and parses content."""
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.json':
            return LocatorParser.parse_json_file(file_path)
        elif ext == '.py':
            return LocatorParser.parse_python_file(file_path)
        return {}

    @staticmethod
    def parse_python_file(file_path: str) -> Dict[str, Any]:
        """Extracts locator dictionaries and constants from live Python source code."""
        results = {}
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                tree = ast.parse(content)
            
            for node in tree.body:
                # Target: Variable assignments (e.g., locators = {...})
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        # Handle simple name assignments: locators = ...
                        if isinstance(target, ast.Name):
                            val = LocatorParser._resolve_ast_node(node.value)
                            if val: results[target.id] = val
                        # Handle attribute assignments: self.locators = ...
                        elif isinstance(target, ast.Attribute):
                            val = LocatorParser._resolve_ast_node(node.value)
                            if val: results[target.attr] = val
                            
                # Target: Class definitions (locators as class attributes)
                elif isinstance(node, ast.ClassDef):
                    class_data = {}
                    for item in node.body:
                        if isinstance(item, ast.Assign):
                            for t in item.targets:
                                if isinstance(t, ast.Name):
                                    v = LocatorParser._resolve_ast_node(item.value)
                                    if v: class_data[t.id] = v
                                elif isinstance(t, ast.Attribute):
                                    v = LocatorParser._resolve_ast_node(item.value)
                                    if v: class_data[t.attr] = v
                    if class_data: results[node.name] = class_data
                    
            # Fallback: If AST find few/no locators, use Regex for common patterns
            if len(results) < 5:
                # Look for patterns like: "locator_id": {"css": "..."} or "locator_id": ("By.X", "...")
                # and also: locator_id = {"css": "..."}
                regex_locators = {}
                
                # Pattern for dict entries
                dict_pattern = r'["\']([^"\']+)["\']\s*:\s*(\{.*?\}|\(.*?\)|\[.*?\])'
                for match in re.finditer(dict_pattern, content, re.DOTALL):
                    try:
                        key, val_str = match.groups()
                        if 'css' in val_str or 'xpath' in val_str or 'By.' in val_str:
                            try:
                                # Safe evaluation of the dictionary/tuple string
                                regex_locators[key] = ast.literal_eval(val_str)
                            except:
                                regex_locators[key] = val_str
                    except Exception: continue
                
                # Pattern for specialized IDs: locator_XYZ123 = ... or "locator_XYZ123": ...
                id_pattern = r'["\']?(locator_[a-zA-Z0-9_]+)["\']?\s*[:=]\s*(\{.*?\}|\(.*?\)|\[.*?\])'
                for match in re.finditer(id_pattern, content, re.DOTALL):
                    try:
                        key, val_str = match.groups()
                        try:
                            regex_locators[key] = ast.literal_eval(val_str)
                        except:
                            regex_locators[key] = val_str
                    except Exception: continue
                
                # Pattern for anonymous selectors (strings that look like XPaths)
                xpath_pattern = r'["\'](//[a-zA-Z0-9_.*@=\[\]\(\/\'\s\-]+)["\']'
                for i, match in enumerate(re.finditer(xpath_pattern, content)):
                    try:
                        val = match.group(1)
                        if val not in str(regex_locators.values()):
                            regex_locators[f"anonymous_xpath_{i}"] = {"xpath": val}
                    except Exception: continue

                results.update(regex_locators)
                
        except Exception as e:
            logger.error(f"AST parsing failed for {file_path}: {e}")
        return results

    @staticmethod
    def parse_json_file(file_path: str) -> Dict[str, Any]:
        """Standard JSON configuration parsing."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    @staticmethod
    def normalize_locator_data(raw_data: Dict[str, Any]) -> Dict[str, Dict[str, List[str]]]:
        """
        Standardizes diverse locator definitions into a unified internal format.
        
        Output Structure:
        { "key": { "css": [...], "xpath": [...], "id": [...], "name": [...] } }
        """
        normalized = {}
        
        def _process_item(key, value):
            if not isinstance(value, (dict, list, str)): return
            
            entry = {'css': [], 'xpath': [], 'id': [], 'name': []}
            
            # Case 1: Simple string (assumed CSS or XPath)
            if isinstance(value, str):
                if value.startswith(('/', '(')): entry['xpath'].append(value)
                else: entry['css'].append(value)
            
            # Case 2: Tuple/List format (Selenium style: (By.ID, "val"))
            elif isinstance(value, (list, tuple)) and len(value) >= 2:
                by, val = str(value[0]).lower(), str(value[1])
                if 'xpath' in by: entry['xpath'].append(val)
                elif 'css' in by: entry['css'].append(val)
                elif 'id' in by: entry['id'].append(val)
                elif 'name' in by: entry['name'].append(val)
            
            # Case 3: Nested Dictionary
            elif isinstance(value, dict):
                for k, v in value.items():
                    k_lower = k.lower()
                    if k_lower in entry:
                        if isinstance(v, list): entry[k_lower].extend([str(x) for x in v])
                        else: entry[k_lower].append(str(v))
            
            if any(entry.values()): normalized[key] = entry

        # Handle flat dicts or nested class-style dicts
        for k, v in raw_data.items():
            if isinstance(v, dict) and not any(ik in ['css', 'xpath', 'id', 'name'] for ik in v.keys()):
                for sub_k, sub_v in v.items(): _process_item(f"{k}.{sub_k}", sub_v)
            else:
                _process_item(k, v)
                
        return normalized

    @staticmethod
    def _resolve_ast_node(node):
        """
        Recursively resolve AST nodes into Python primitives, 
        with specific support for Selenium 'By' constants.
        """
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Dict):
            return {LocatorParser._resolve_ast_node(k): LocatorParser._resolve_ast_node(v) 
                    for k, v in zip(node.keys, node.values)}
        elif isinstance(node, (ast.List, ast.Tuple)):
            return [LocatorParser._resolve_ast_node(elt) for elt in node.elts]
        elif isinstance(node, ast.Attribute):
            # Handle By.ID, By.XPATH, etc.
            if isinstance(node.value, ast.Name) and node.value.id == 'By':
                return f"By.{node.attr}"
            return f"{LocatorParser._resolve_ast_node(node.value)}.{node.attr}"
        elif isinstance(node, ast.Name):
            return node.id
        return None


# ============================================================================
# SECTION 2: SCRIPT ANALYSIS ENGINE
# ============================================================================

class ScriptAnalyzer:
    """Analyzes automation source code to understand logic and data requirements."""

    @staticmethod
    def extract_url(script_content: str) -> Optional[str]:
        """Identify the primary entry-point URL defined in the script."""
        patterns = [
            r"driver\.get\s*\(\s*['\"]([^'\"]+)['\"]\s*\)",
            r"driver\.navigate\(\)\.to\s*\(\s*['\"]([^'\"]+)['\"]\s*\)",
            r"URL\s*=\s*['\"]([^'\"]+)['\"]"
        ]
        for p in patterns:
            match = re.search(p, script_content, re.IGNORECASE)
            if match: return match.group(1)
        return None

    @staticmethod
    def extract_actions(script_content: str) -> List[Dict[str, Any]]:
        """Sequential decomposition of automation steps into an interaction manifest."""
        actions = []
        # Support for common patterns like helper.click("key") or driver.find_element(...).click()
        patterns = [
            (r"\.click\s*\(\s*['\"]([^'\"]+)['\"]", 'click'),
            (r"\.send_keys\s*\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]", 'send_keys'),
            (r"\.select\s*\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]", 'select')
        ]
        
        for p, a_type in patterns:
            for match in re.finditer(p, script_content):
                actions.append({
                    "type": a_type,
                    "locator": match.group(1),
                    "value": match.group(2) if len(match.groups()) > 1 else None,
                    "index": match.start()
                })
        
        return sorted(actions, key=lambda x: x['index'])

    @staticmethod
    def identify_script_files(directory: str) -> Tuple[Optional[str], List[str]]:
        """Heuristic identification of the main entry-point script and its config dependencies."""
        py_files = []
        json_files = []
        
        # Recursive search for relevant files
        for root, _, files in os.walk(directory):
            for f in files:
                full_path = os.path.join(root, f)
                if f.endswith('.py'): py_files.append(full_path)
                elif f.endswith('.json'): json_files.append(full_path)
        
        main_script = None
        # Priority: files named 'main', 'test', 'run', or containing 'driver.get'
        # Also check for 'scenario' as it's common in this codebase
        for f in py_files:
            fname = os.path.basename(f).lower()
            if any(k in fname for k in ['main', 'test', 'run', 'script', 'scenario']):
                main_script = f; break
        
        if not main_script and py_files: 
            # Fallback to the first python file found
            main_script = py_files[0]
        
        return main_script, py_files + json_files

    @staticmethod
    def preprocess_selenium_script(script_text: str) -> str:
        """
        Prepares a script for high-accuracy LLM analysis.
        
        Condenses script logic into a structured semantic summary to stay
        within token limits while preserving interaction intent.
        """
        url = ScriptAnalyzer.extract_url(script_text)
        actions = ScriptAnalyzer.extract_actions(script_text)
        
        summary = [f"TARGET_URL: {url or 'Unknown'}"]
        summary.append("\nINTERACTION SEQUENCE:")
        for a in actions:
            summary.append(f"- {a['type'].upper()} on target '{a['locator']}'" + (f" with value '{a['value']}'" if a['value'] else ""))
            
        return "\n".join(summary)

    @staticmethod
    def parse_selenium_script(script_text: str, provider: str = "ollama", **kwargs) -> Tuple[List[Dict], Optional[str]]:
        """
        Leverages AI to synthesize a data schema from script logic.
        
        Args:
            script_text: Preprocessed or raw script content.
            provider: LLM provider for inference.
            
        Returns:
            Tuple of (Inferred Schema List, Error Message if any).
        """
        try:
            llm = LLMFactory.create_llm(provider=provider)
            prompt = SeleniumParserPrompts.get_extraction_prompt(script_text)
            
            logger.info(f"Initiating AI script analysis via {provider}...")
            response = llm.invoke(prompt)
            
            # Use consolidated logic for robust JSON extraction from LLM response
            data = JSONExtractor.extract_json(response, expect_array=True)
            if not data: return [], "AI could not identify a valid interaction schema."
            
            parsed = json.loads(JSONCleaner.clean(data))
            return parsed, None
        except Exception as e:
            logger.error(f"AI script analysis failed: {e}")
            return [], str(e)
