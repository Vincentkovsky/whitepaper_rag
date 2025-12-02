"""
Tools module for the Agent.

Contains built-in tools like document_search and web_search,
as well as the ToolRegistry for managing callable tools.
"""

from .registry import ToolRegistry, ToolNotFoundError
from .document_search import create_document_search_tool
from .web_search import create_web_search_tool, WebSearchError

__all__ = [
    "ToolRegistry",
    "ToolNotFoundError",
    "create_document_search_tool",
    "create_web_search_tool",
    "WebSearchError",
]
