"""
Tool Registry for the Agent module.

Manages registration, retrieval, and invocation of callable tools.
"""

import logging
from typing import Any, Dict, List, Optional

from ..types import Tool, ToolSchema


class ToolNotFoundError(ValueError):
    """Raised when a requested tool is not found in the registry."""
    pass


class ToolRegistry:
    """Registry for managing callable tools.
    
    Provides methods to register, retrieve, list, and invoke tools.
    Implements the ToolRegistryProtocol interface.
    """
    
    def __init__(self) -> None:
        """Initialize an empty tool registry."""
        self._tools: Dict[str, Tool] = {}
        self._logger = logging.getLogger("app.agent.tools.registry")
    
    def register(self, tool: Tool) -> None:
        """Register a tool with the registry.
        
        Args:
            tool: The tool to register
            
        Note:
            If a tool with the same name already exists, it will be overwritten.
        """
        name = tool.schema_.name
        if name in self._tools:
            self._logger.warning(f"Overwriting existing tool: {name}")
        self._tools[name] = tool
        self._logger.debug(f"Registered tool: {name}")
    
    def get(self, name: str) -> Optional[Tool]:
        """Get a tool by name.
        
        Args:
            name: The unique name of the tool
            
        Returns:
            The tool if found, None otherwise
        """
        return self._tools.get(name)
    
    def list_tools(self) -> List[ToolSchema]:
        """List all registered tool schemas.
        
        Returns:
            List of all registered tool schemas
        """
        return [tool.schema_ for tool in self._tools.values()]
    
    def invoke(self, name: str, **kwargs: Any) -> Any:
        """Invoke a tool by name with given parameters.
        
        Args:
            name: The name of the tool to invoke
            **kwargs: Parameters to pass to the tool
            
        Returns:
            The result of the tool invocation
            
        Raises:
            ToolNotFoundError: If the tool is not found
        """
        tool = self._tools.get(name)
        if tool is None:
            self._logger.error(f"Tool not found: {name}")
            raise ToolNotFoundError(f"Tool not found: {name}")
        
        self._logger.debug(f"Invoking tool: {name} with params: {kwargs}")
        try:
            result = tool.handler(**kwargs)
            self._logger.debug(f"Tool {name} completed successfully")
            return result
        except Exception as e:
            self._logger.error(f"Tool {name} failed: {e}")
            raise
    
    def __len__(self) -> int:
        """Return the number of registered tools."""
        return len(self._tools)
    
    def __contains__(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools
