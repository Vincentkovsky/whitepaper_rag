import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

"""
Property-based tests for Tool Registry.

**Feature: generic-agentic-rag, Property 3: Tool Registry Round-Trip**
**Feature: generic-agentic-rag, Property 5: Tool Failure Resilience**
"""

from typing import Any, Dict, List
from hypothesis import given, strategies as st, settings, assume
from pydantic import BaseModel

from app.agent.types import Tool, ToolSchema
from app.agent.tools.registry import ToolRegistry, ToolNotFoundError


# Custom strategies for generating valid tool data
valid_tool_name = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
    min_size=1,
    max_size=30
).filter(lambda x: x.strip() != "" and x[0].isalpha())

valid_description = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S", "Z")),
    min_size=1,
    max_size=100
).filter(lambda x: x.strip() != "")


class ToolInvocationResult(BaseModel):
    """Result of a safe tool invocation."""
    success: bool
    result: Any = None
    error: str | None = None


def create_failing_tool(name: str, description: str, error_message: str) -> Tool:
    """Create a tool that always raises an exception."""
    def failing_handler(**kwargs: Any) -> Any:
        raise RuntimeError(error_message)
    
    return Tool(
        schema=ToolSchema(
            name=name,
            description=description,
            parameters={"type": "object", "properties": {}},
            required=[]
        ),
        handler=failing_handler
    )


def create_successful_tool(name: str, description: str, return_value: Any) -> Tool:
    """Create a tool that always succeeds with a given return value."""
    def success_handler(**kwargs: Any) -> Any:
        return return_value
    
    return Tool(
        schema=ToolSchema(
            name=name,
            description=description,
            parameters={"type": "object", "properties": {}},
            required=[]
        ),
        handler=success_handler
    )


# Strategy for generating valid JSON Schema parameter definitions
json_schema_property = st.fixed_dictionaries({
    "type": st.sampled_from(["string", "integer", "boolean", "number"]),
    "description": st.text(min_size=1, max_size=50).filter(lambda x: x.strip() != "")
})

valid_parameters = st.fixed_dictionaries({
    "type": st.just("object"),
    "properties": st.dictionaries(
        keys=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_"),
            min_size=1,
            max_size=20
        ).filter(lambda x: x.strip() != "" and x[0].isalpha()),
        values=json_schema_property,
        min_size=0,
        max_size=5
    )
})

valid_required_list = st.lists(
    st.text(
        alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_"),
        min_size=1,
        max_size=20
    ).filter(lambda x: x.strip() != "" and x[0].isalpha()),
    min_size=0,
    max_size=3,
    unique=True
)


# =============================================================================
# Property 3: Tool Registry Round-Trip
# =============================================================================

@settings(max_examples=100)
@given(
    tool_name=valid_tool_name,
    description=valid_description,
    parameters=valid_parameters,
    required=valid_required_list
)
def test_tool_registry_round_trip(
    tool_name: str,
    description: str,
    parameters: Dict[str, Any],
    required: List[str]
):
    """
    **Feature: generic-agentic-rag, Property 3: Tool Registry Round-Trip**
    
    For any valid tool definition with name, description, and parameter schema,
    registering the tool and then retrieving it by name SHALL return an
    equivalent tool definition.
    
    **Validates: Requirements 2.1**
    """
    # Create a tool with the generated schema
    def dummy_handler(**kwargs: Any) -> str:
        return "result"
    
    original_schema = ToolSchema(
        name=tool_name,
        description=description,
        parameters=parameters,
        required=required
    )
    
    original_tool = Tool(
        schema=original_schema,
        handler=dummy_handler
    )
    
    # Register the tool
    registry = ToolRegistry()
    registry.register(original_tool)
    
    # Retrieve the tool by name
    retrieved_tool = registry.get(tool_name)
    
    # PROPERTY: Retrieved tool should not be None
    assert retrieved_tool is not None, f"Tool '{tool_name}' should be retrievable after registration"
    
    # PROPERTY: Retrieved schema should be equivalent to original
    assert retrieved_tool.schema_.name == original_schema.name, "Tool name should match"
    assert retrieved_tool.schema_.description == original_schema.description, "Tool description should match"
    assert retrieved_tool.schema_.parameters == original_schema.parameters, "Tool parameters should match"
    assert retrieved_tool.schema_.required == original_schema.required, "Tool required fields should match"
    
    # PROPERTY: Tool should appear in list_tools()
    tool_schemas = registry.list_tools()
    assert len(tool_schemas) == 1, "Registry should contain exactly one tool"
    
    listed_schema = tool_schemas[0]
    assert listed_schema.name == original_schema.name, "Listed tool name should match"
    assert listed_schema.description == original_schema.description, "Listed tool description should match"
    assert listed_schema.parameters == original_schema.parameters, "Listed tool parameters should match"
    assert listed_schema.required == original_schema.required, "Listed tool required fields should match"


@settings(max_examples=100)
@given(
    tool_names=st.lists(valid_tool_name, min_size=2, max_size=5, unique=True),
    description=valid_description
)
def test_tool_registry_multiple_tools_round_trip(
    tool_names: List[str],
    description: str
):
    """
    **Feature: generic-agentic-rag, Property 3: Tool Registry Round-Trip**
    
    For any set of valid tool definitions, registering multiple tools and
    retrieving each by name SHALL return the correct tool for each name.
    
    **Validates: Requirements 2.1**
    """
    registry = ToolRegistry()
    
    # Create and register multiple tools
    tools = {}
    for name in tool_names:
        def make_handler(n: str):
            def handler(**kwargs: Any) -> str:
                return f"result_from_{n}"
            return handler
        
        tool = Tool(
            schema=ToolSchema(
                name=name,
                description=f"{description} for {name}",
                parameters={"type": "object", "properties": {}},
                required=[]
            ),
            handler=make_handler(name)
        )
        tools[name] = tool
        registry.register(tool)
    
    # PROPERTY: Each tool should be retrievable by its name
    for name in tool_names:
        retrieved = registry.get(name)
        assert retrieved is not None, f"Tool '{name}' should be retrievable"
        assert retrieved.schema_.name == name, f"Retrieved tool should have name '{name}'"
        assert retrieved.schema_.description == tools[name].schema_.description, "Description should match"
    
    # PROPERTY: list_tools should return all registered tools
    listed_schemas = registry.list_tools()
    assert len(listed_schemas) == len(tool_names), "All tools should be listed"
    
    listed_names = {s.name for s in listed_schemas}
    assert listed_names == set(tool_names), "All tool names should be present in list"


# =============================================================================
# Property 5: Tool Failure Resilience
# =============================================================================

@settings(max_examples=100)
@given(
    tool_name=valid_tool_name,
    description=valid_description,
    error_message=st.text(min_size=1, max_size=50).filter(lambda x: x.strip() != "")
)
def test_tool_failure_resilience(tool_name: str, description: str, error_message: str):
    """
    **Feature: generic-agentic-rag, Property 5: Tool Failure Resilience**
    
    For any tool invocation that raises an exception, the system SHALL:
    1. Properly catch and handle the exception
    2. Remain in a valid state (registry still usable)
    3. Allow subsequent tool invocations to succeed
    
    **Validates: Requirements 2.4**
    """
    registry = ToolRegistry()
    
    # Register a failing tool
    failing_tool = create_failing_tool(tool_name, description, error_message)
    registry.register(failing_tool)
    
    # Verify the tool is registered
    assert tool_name in registry
    assert registry.get(tool_name) is not None
    
    # Invoke the failing tool - it should raise an exception
    exception_raised = False
    caught_error_message = None
    try:
        registry.invoke(tool_name)
    except RuntimeError as e:
        exception_raised = True
        caught_error_message = str(e)
    
    # Verify exception was raised with correct message
    assert exception_raised, "Failing tool should raise an exception"
    assert error_message in caught_error_message, "Error message should be preserved"
    
    # CRITICAL: Verify registry remains in valid state after failure
    # This is the resilience property - the system should continue to work
    assert tool_name in registry, "Tool should still be registered after failure"
    assert len(registry) == 1, "Registry size should be unchanged"
    
    # Verify we can still list tools
    tool_schemas = registry.list_tools()
    assert len(tool_schemas) == 1
    assert tool_schemas[0].name == tool_name


@settings(max_examples=100)
@given(
    failing_name=valid_tool_name,
    success_name=valid_tool_name,
    description=valid_description,
    error_message=st.text(min_size=1, max_size=50).filter(lambda x: x.strip() != ""),
    return_value=st.one_of(st.text(max_size=20), st.integers(), st.booleans())
)
def test_registry_usable_after_tool_failure(
    failing_name: str,
    success_name: str,
    description: str,
    error_message: str,
    return_value: Any
):
    """
    **Feature: generic-agentic-rag, Property 5: Tool Failure Resilience**
    
    For any registry with multiple tools, if one tool fails, other tools
    SHALL remain invocable and the registry SHALL continue functioning.
    
    **Validates: Requirements 2.4**
    """
    # Ensure different names for the two tools
    assume(failing_name != success_name)
    
    registry = ToolRegistry()
    
    # Register both a failing and a successful tool
    failing_tool = create_failing_tool(failing_name, description, error_message)
    success_tool = create_successful_tool(success_name, description, return_value)
    
    registry.register(failing_tool)
    registry.register(success_tool)
    
    # First, invoke the failing tool
    try:
        registry.invoke(failing_name)
    except RuntimeError:
        pass  # Expected
    
    # CRITICAL: After failure, the successful tool should still work
    result = registry.invoke(success_name)
    assert result == return_value, "Successful tool should return correct value after another tool failed"
    
    # Registry should still be fully functional
    assert len(registry) == 2
    assert failing_name in registry
    assert success_name in registry


@settings(max_examples=100)
@given(
    tool_name=valid_tool_name,
    description=valid_description,
    error_message=st.text(min_size=1, max_size=50).filter(lambda x: x.strip() != ""),
    num_failures=st.integers(min_value=1, max_value=5)
)
def test_multiple_failures_dont_corrupt_registry(
    tool_name: str,
    description: str,
    error_message: str,
    num_failures: int
):
    """
    **Feature: generic-agentic-rag, Property 5: Tool Failure Resilience**
    
    For any number of consecutive tool failures, the registry SHALL
    remain in a valid, usable state.
    
    **Validates: Requirements 2.4**
    """
    registry = ToolRegistry()
    
    failing_tool = create_failing_tool(tool_name, description, error_message)
    registry.register(failing_tool)
    
    # Invoke the failing tool multiple times
    for _ in range(num_failures):
        try:
            registry.invoke(tool_name)
        except RuntimeError:
            pass  # Expected
    
    # Registry should still be in valid state
    assert len(registry) == 1
    assert tool_name in registry
    assert registry.get(tool_name) is not None
    
    # Should be able to list tools
    schemas = registry.list_tools()
    assert len(schemas) == 1
    assert schemas[0].name == tool_name
