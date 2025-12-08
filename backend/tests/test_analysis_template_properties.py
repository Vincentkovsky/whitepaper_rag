import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

"""
Property-based tests for AnalysisTemplate serialization.

**Feature: generic-agentic-rag, Property 14: Template Serialization Round-Trip**
"""

from hypothesis import given, strategies as st, settings

from app.agent.templates.analysis_template import AnalysisTemplate


# Custom strategies for generating valid AnalysisTemplate data
# Use printable characters only to ensure YAML/JSON compatibility
printable_text = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "S", "Z"),
        blacklist_characters="\x00\x01\x02\x03\x04\x05\x06\x07\x08\x0b\x0c\x0e\x0f"
                            "\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f"
                            "\x7f\x80\x81\x82\x83\x84\x85\x86\x87\x88\x89\x8a\x8b\x8c\x8d\x8e\x8f"
                            "\x90\x91\x92\x93\x94\x95\x96\x97\x98\x99\x9a\x9b\x9c\x9d\x9e\x9f"
    )
)

valid_name_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
    min_size=1,
    max_size=50
).filter(lambda x: x.strip() != "")

valid_description_strategy = printable_text.filter(lambda x: len(x) <= 200)

valid_dimensions_strategy = st.lists(
    st.text(
        alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_"),
        min_size=1,
        max_size=30
    ).filter(lambda x: x.strip() != ""),
    min_size=0,
    max_size=10
)

valid_prompts_strategy = st.dictionaries(
    keys=st.text(
        alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_"),
        min_size=1,
        max_size=30
    ).filter(lambda x: x.strip() != ""),
    values=printable_text.filter(lambda x: len(x) <= 500),
    min_size=0,
    max_size=10
)

# JSON-serializable output schema strategy
json_primitive = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(max_size=50)
)

valid_output_schema_strategy = st.fixed_dictionaries({
    "type": st.just("object"),
    "properties": st.dictionaries(
        keys=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_"),
            min_size=1,
            max_size=20
        ).filter(lambda x: x.strip() != ""),
        values=st.fixed_dictionaries({
            "type": st.sampled_from(["string", "number", "boolean", "array", "object"])
        }),
        min_size=0,
        max_size=5
    )
})


@st.composite
def analysis_template_strategy(draw):
    """Generate valid AnalysisTemplate instances."""
    return AnalysisTemplate(
        name=draw(valid_name_strategy),
        description=draw(valid_description_strategy),
        dimensions=draw(valid_dimensions_strategy),
        prompts=draw(valid_prompts_strategy),
        output_schema=draw(valid_output_schema_strategy)
    )


@settings(max_examples=100)
@given(template=analysis_template_strategy())
def test_json_serialization_round_trip(template: AnalysisTemplate):
    """
    **Feature: generic-agentic-rag, Property 14: Template Serialization Round-Trip**
    
    For any valid AnalysisTemplate, serializing to JSON and deserializing 
    SHALL produce an equivalent template.
    
    **Validates: Requirements 5.3**
    """
    # Serialize to JSON
    json_str = template.to_json()
    
    # Deserialize from JSON
    restored = AnalysisTemplate.from_json(json_str)
    
    # Verify equivalence
    assert restored == template, f"JSON round-trip failed: {template} != {restored}"


@settings(max_examples=100)
@given(template=analysis_template_strategy())
def test_yaml_serialization_round_trip(template: AnalysisTemplate):
    """
    **Feature: generic-agentic-rag, Property 14: Template Serialization Round-Trip**
    
    For any valid AnalysisTemplate, serializing to YAML and deserializing 
    SHALL produce an equivalent template.
    
    **Validates: Requirements 5.3**
    """
    # Serialize to YAML
    yaml_str = template.to_yaml()
    
    # Deserialize from YAML
    restored = AnalysisTemplate.from_yaml(yaml_str)
    
    # Verify equivalence
    assert restored == template, f"YAML round-trip failed: {template} != {restored}"


# Import registry for lifecycle tests
from app.agent.templates.registry import TemplateRegistry


@settings(max_examples=100)
@given(template=analysis_template_strategy())
def test_template_registry_lifecycle(template: AnalysisTemplate):
    """
    **Feature: generic-agentic-rag, Property 13: Analysis Template Lifecycle**
    
    For any valid AnalysisTemplate, registering it SHALL make it retrievable 
    by name, and the retrieved template SHALL be equivalent to the original.
    
    **Validates: Requirements 5.1, 5.2**
    """
    # Create a fresh registry for each test
    registry = TemplateRegistry()
    
    # Register the template
    registry.register(template)
    
    # Retrieve by name
    retrieved = registry.get(template.name)
    
    # Verify retrieval succeeded
    assert retrieved is not None, f"Template '{template.name}' not found after registration"
    
    # Verify equivalence
    assert retrieved == template, f"Retrieved template differs from original: {retrieved} != {template}"


@settings(max_examples=100)
@given(template=analysis_template_strategy())
def test_template_registry_list_contains_registered(template: AnalysisTemplate):
    """
    **Feature: generic-agentic-rag, Property 13: Analysis Template Lifecycle**
    
    For any valid AnalysisTemplate, after registration, list_templates() 
    SHALL include the registered template.
    
    **Validates: Requirements 5.1, 5.2**
    """
    registry = TemplateRegistry()
    
    # Register the template
    registry.register(template)
    
    # List all templates
    all_templates = registry.list_templates()
    
    # Verify the template is in the list
    assert template in all_templates, f"Template '{template.name}' not in list after registration"


@settings(max_examples=100)
@given(template=analysis_template_strategy())
def test_template_registry_unregister(template: AnalysisTemplate):
    """
    **Feature: generic-agentic-rag, Property 13: Analysis Template Lifecycle**
    
    For any valid AnalysisTemplate, after registration and unregistration,
    the template SHALL no longer be retrievable by name.
    
    **Validates: Requirements 5.1, 5.2**
    """
    registry = TemplateRegistry()
    
    # Register the template
    registry.register(template)
    
    # Verify it's registered
    assert registry.get(template.name) is not None
    
    # Unregister
    result = registry.unregister(template.name)
    assert result is True, "Unregister should return True for existing template"
    
    # Verify it's no longer retrievable
    assert registry.get(template.name) is None, f"Template '{template.name}' still found after unregistration"
