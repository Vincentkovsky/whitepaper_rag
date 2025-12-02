"""
Template Registry for managing AnalysisTemplate instances.

This module provides a registry for registering, retrieving, and loading
analysis templates from configuration files.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional

from .analysis_template import AnalysisTemplate


class TemplateRegistry:
    """
    Registry for managing AnalysisTemplate instances.
    
    Supports:
    - Registering templates programmatically
    - Retrieving templates by name
    - Loading templates from JSON/YAML files
    - Listing all registered templates
    """
    
    def __init__(self):
        self._templates: Dict[str, AnalysisTemplate] = {}
    
    def register(self, template: AnalysisTemplate) -> None:
        """
        Register a template with the registry.
        
        Args:
            template: The AnalysisTemplate to register
        """
        self._templates[template.name] = template
    
    def get(self, name: str) -> Optional[AnalysisTemplate]:
        """
        Get a template by name.
        
        Args:
            name: The name of the template to retrieve
            
        Returns:
            The template if found, None otherwise
        """
        return self._templates.get(name)
    
    def list_templates(self) -> List[AnalysisTemplate]:
        """
        List all registered templates.
        
        Returns:
            List of all registered templates
        """
        return list(self._templates.values())

    def unregister(self, name: str) -> bool:
        """
        Unregister a template by name.
        
        Args:
            name: The name of the template to unregister
            
        Returns:
            True if the template was found and removed, False otherwise
        """
        if name in self._templates:
            del self._templates[name]
            return True
        return False
    
    def clear(self) -> None:
        """Clear all registered templates."""
        self._templates.clear()
    
    def load_from_file(self, file_path: str) -> AnalysisTemplate:
        """
        Load a template from a JSON or YAML file and register it.
        
        Args:
            file_path: Path to the JSON or YAML file
            
        Returns:
            The loaded and registered template
            
        Raises:
            FileNotFoundError: If the file does not exist
            ValueError: If the file format is not supported
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Template file not found: {file_path}")
        
        content = path.read_text(encoding="utf-8")
        suffix = path.suffix.lower()
        
        if suffix == ".json":
            template = AnalysisTemplate.from_json(content)
        elif suffix in (".yaml", ".yml"):
            template = AnalysisTemplate.from_yaml(content)
        else:
            raise ValueError(f"Unsupported file format: {suffix}. Use .json, .yaml, or .yml")
        
        self.register(template)
        return template
    
    def load_from_directory(self, directory_path: str) -> List[AnalysisTemplate]:
        """
        Load all templates from a directory.
        
        Args:
            directory_path: Path to the directory containing template files
            
        Returns:
            List of loaded templates
            
        Raises:
            FileNotFoundError: If the directory does not exist
        """
        path = Path(directory_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Template directory not found: {directory_path}")
        
        if not path.is_dir():
            raise ValueError(f"Path is not a directory: {directory_path}")
        
        loaded_templates = []
        
        for file_path in path.iterdir():
            if file_path.suffix.lower() in (".json", ".yaml", ".yml"):
                try:
                    template = self.load_from_file(str(file_path))
                    loaded_templates.append(template)
                except Exception:
                    # Skip files that fail to load
                    continue
        
        return loaded_templates


# Global registry instance
_global_registry: Optional[TemplateRegistry] = None


def get_template_registry() -> TemplateRegistry:
    """
    Get the global template registry instance.
    
    Returns:
        The global TemplateRegistry instance
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = TemplateRegistry()
    return _global_registry


# Path to the default template
DEFAULT_TEMPLATE_PATH = Path(__file__).parent / "default.yaml"


def get_default_template() -> AnalysisTemplate:
    """
    Get the default general-purpose analysis template.
    
    Returns:
        The default AnalysisTemplate
        
    Raises:
        FileNotFoundError: If the default template file is missing
    """
    if not DEFAULT_TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Default template not found: {DEFAULT_TEMPLATE_PATH}")
    
    content = DEFAULT_TEMPLATE_PATH.read_text(encoding="utf-8")
    return AnalysisTemplate.from_yaml(content)


def get_or_default(registry: TemplateRegistry, name: str) -> AnalysisTemplate:
    """
    Get a template by name, falling back to the default template if not found.
    
    Args:
        registry: The template registry to search
        name: The name of the template to retrieve
        
    Returns:
        The requested template, or the default template if not found
    """
    template = registry.get(name)
    if template is None:
        return get_default_template()
    return template
