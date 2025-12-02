"""
Templates module for the Agent system.

This module provides extensible analysis templates that can be customized
for different document types and use cases.
"""

from .analysis_template import AnalysisTemplate
from .registry import (
    TemplateRegistry,
    get_template_registry,
    get_default_template,
    get_or_default,
)

__all__ = [
    "AnalysisTemplate",
    "TemplateRegistry",
    "get_template_registry",
    "get_default_template",
    "get_or_default",
]
