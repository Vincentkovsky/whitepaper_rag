"""
Analysis Template model for extensible document analysis workflows.

This module defines the AnalysisTemplate model that allows users to define
custom analysis workflows without modifying core code.
"""

from typing import Any, Dict, List

import json
import yaml
from pydantic import BaseModel, Field


class AnalysisTemplate(BaseModel):
    """
    Template for defining custom document analysis workflows.
    
    Attributes:
        name: Unique identifier for the template
        description: Human-readable description of what the template analyzes
        dimensions: List of analysis dimensions (e.g., "summary", "key_points")
        prompts: Dictionary mapping dimension names to prompt templates
        output_schema: JSON Schema defining the expected output structure
    """
    name: str = Field(description="Unique identifier for the template")
    description: str = Field(description="Human-readable description of the template")
    dimensions: List[str] = Field(
        default_factory=list,
        description="List of analysis dimensions"
    )
    prompts: Dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of dimension names to prompt templates"
    )
    output_schema: Dict[str, Any] = Field(
        default_factory=dict,
        description="JSON Schema defining the expected output structure"
    )

    def to_json(self) -> str:
        """Serialize the template to JSON string."""
        return self.model_dump_json()

    def to_yaml(self) -> str:
        """Serialize the template to YAML string."""
        return yaml.dump(self.model_dump(), allow_unicode=True, default_flow_style=False)

    @classmethod
    def from_json(cls, json_str: str) -> "AnalysisTemplate":
        """Deserialize a template from JSON string."""
        data = json.loads(json_str)
        return cls.model_validate(data)

    @classmethod
    def from_yaml(cls, yaml_str: str) -> "AnalysisTemplate":
        """Deserialize a template from YAML string."""
        data = yaml.safe_load(yaml_str)
        return cls.model_validate(data)
