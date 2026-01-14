"""
API Endpoints Package

Modular endpoint implementations for the Test Data Generator API.
"""

from .selenium_field_extraction import extract_fields_from_uploaded_folder

__all__ = ['extract_fields_from_uploaded_folder']
