import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

"""
Property-based tests for Execution Tracer.

**Feature: generic-agentic-rag, Property 19: Trace Format Compliance**
**Feature: generic-agentic-rag, Property 21: Latency Metrics Recording**
"""

import time
from typing import Any, Dict, List

from hypothesis import given, strategies as st, settings, assume

from app.agent.tracing import ExecutionTracer, ExecutionTrace, TraceSpan


# =============================================================================
# Custom Strategies
# =============================================================================

# Valid span names (alphanumeric with underscores)
valid_span_name = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_"),
    min_size=1,
    max_size=30
).filter(lambda x: x.strip() != "" and x[0].isalpha())

# Valid input/output dictionaries
valid_dict_value = st.one_of(
    st.text(max_size=50),
    st.integers(min_value=-1000, max_value=1000),
    st.booleans(),
    st.floats(allow_nan=False, allow_infinity=False),
    st.none()
)

valid_inputs = st.dictionaries(
    keys=st.text(
        alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_"),
        min_size=1,
        max_size=20
    ).filter(lambda x: x.strip() != "" and x[0].isalpha()),
    values=valid_dict_value,
    min_size=0,
    max_size=5
)

valid_outputs = st.dictionaries(
    keys=st.text(
        alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_"),
        min_size=1,
        max_size=20
    ).filter(lambda x: x.strip() != "" and x[0].isalpha()),
    values=valid_dict_value,
    min_size=0,
    max_size=5
)

valid_metadata = st.dictionaries(
    keys=st.text(
        alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_"),
        min_size=1,
        max_size=20
    ).filter(lambda x: x.strip() != "" and x[0].isalpha()),
    values=valid_dict_value,
    min_size=0,
    max_size=3
)


# =============================================================================
# Property 19: Trace Format Compliance
# =============================================================================

@settings(max_examples=100)
@given(
    span_name=valid_span_name,
    inputs=valid_inputs,
    outputs=valid_outputs,
    metadata=valid_metadata
)
def test_trace_format_compliance_single_span(
    span_name: str,
    inputs: Dict[str, Any],
    outputs: Dict[str, Any],
    metadata: Dict[str, Any]
):
    """
    **Feature: generic-agentic-rag, Property 19: Trace Format Compliance**
    
    For any agent execution with tracing enabled, the exported trace SHALL
    conform to LangSmith/LangFuse schema (containing trace_id, spans with
    start_time, end_time, inputs, outputs).
    
    **Validates: Requirements 8.1**
    """
    tracer = ExecutionTracer()
    
    # Start and end a span
    span_id = tracer.start_span(span_name, inputs, metadata=metadata)
    tracer.end_span(span_id, outputs)
    
    # Export to LangSmith format
    exported = tracer.export_langsmith()
    
    # PROPERTY: Exported trace must have required top-level fields
    assert "id" in exported, "Exported trace must have 'id' field"
    assert "name" in exported, "Exported trace must have 'name' field"
    assert "start_time" in exported, "Exported trace must have 'start_time' field"
    assert "end_time" in exported, "Exported trace must have 'end_time' field"
    assert "inputs" in exported, "Exported trace must have 'inputs' field"
    assert "outputs" in exported, "Exported trace must have 'outputs' field"
    assert "runs" in exported, "Exported trace must have 'runs' field"
    
    # PROPERTY: trace_id must be a non-empty string
    assert isinstance(exported["id"], str), "trace_id must be a string"
    assert len(exported["id"]) > 0, "trace_id must be non-empty"
    
    # PROPERTY: runs must be a list
    assert isinstance(exported["runs"], list), "runs must be a list"
    assert len(exported["runs"]) == 1, "Should have exactly one run for single span"
    
    # PROPERTY: Each run must have required fields
    run = exported["runs"][0]
    assert "id" in run, "Run must have 'id' field"
    assert "name" in run, "Run must have 'name' field"
    assert "start_time" in run, "Run must have 'start_time' field"
    assert "end_time" in run, "Run must have 'end_time' field"
    assert "inputs" in run, "Run must have 'inputs' field"
    assert "outputs" in run, "Run must have 'outputs' field"
    
    # PROPERTY: Run name should match span name
    assert run["name"] == span_name, "Run name should match span name"
    
    # PROPERTY: Run inputs should match provided inputs
    assert run["inputs"] == inputs, "Run inputs should match provided inputs"
    
    # PROPERTY: Run outputs should match provided outputs
    assert run["outputs"] == outputs, "Run outputs should match provided outputs"
    
    # PROPERTY: start_time and end_time should be ISO format strings
    assert isinstance(run["start_time"], str), "start_time must be a string"
    assert isinstance(run["end_time"], str), "end_time must be a string"


@settings(max_examples=100)
@given(
    span_names=st.lists(valid_span_name, min_size=2, max_size=5, unique=True),
    inputs_list=st.lists(valid_inputs, min_size=2, max_size=5),
    outputs_list=st.lists(valid_outputs, min_size=2, max_size=5)
)
def test_trace_format_compliance_multiple_spans(
    span_names: List[str],
    inputs_list: List[Dict[str, Any]],
    outputs_list: List[Dict[str, Any]]
):
    """
    **Feature: generic-agentic-rag, Property 19: Trace Format Compliance**
    
    For any agent execution with multiple spans, the exported trace SHALL
    contain all spans with proper parent-child relationships preserved.
    
    **Validates: Requirements 8.1**
    """
    # Ensure we have matching lengths
    min_len = min(len(span_names), len(inputs_list), len(outputs_list))
    assume(min_len >= 2)
    
    span_names = span_names[:min_len]
    inputs_list = inputs_list[:min_len]
    outputs_list = outputs_list[:min_len]
    
    tracer = ExecutionTracer()
    span_ids = []
    
    # Create spans with parent-child relationships
    for i, (name, inputs, outputs) in enumerate(zip(span_names, inputs_list, outputs_list)):
        parent_id = span_ids[-1] if span_ids else None
        span_id = tracer.start_span(name, inputs, parent_id=parent_id)
        span_ids.append(span_id)
        tracer.end_span(span_id, outputs)
    
    # Export to LangSmith format
    exported = tracer.export_langsmith()
    
    # PROPERTY: Should have all spans as runs
    assert len(exported["runs"]) == len(span_names), "Should have all spans as runs"
    
    # PROPERTY: Each run should have required fields
    for run in exported["runs"]:
        assert "id" in run
        assert "name" in run
        assert "start_time" in run
        assert "inputs" in run
        assert "outputs" in run
        assert "parent_run_id" in run
        assert "run_type" in run
    
    # PROPERTY: First run should have no parent
    assert exported["runs"][0]["parent_run_id"] is None, "First run should have no parent"
    
    # PROPERTY: Subsequent runs should have parent_run_id set
    for i in range(1, len(exported["runs"])):
        assert exported["runs"][i]["parent_run_id"] is not None, f"Run {i} should have parent"


@settings(max_examples=100)
@given(
    span_name=valid_span_name,
    inputs=valid_inputs,
    outputs=valid_outputs
)
def test_trace_format_run_type_inference(
    span_name: str,
    inputs: Dict[str, Any],
    outputs: Dict[str, Any]
):
    """
    **Feature: generic-agentic-rag, Property 19: Trace Format Compliance**
    
    For any span, the exported run_type SHALL be one of the valid LangSmith
    run types: "llm", "tool", "chain", or "retriever".
    
    **Validates: Requirements 8.1**
    """
    tracer = ExecutionTracer()
    
    span_id = tracer.start_span(span_name, inputs)
    tracer.end_span(span_id, outputs)
    
    exported = tracer.export_langsmith()
    
    # PROPERTY: run_type must be one of the valid types
    valid_run_types = {"llm", "tool", "chain", "retriever"}
    for run in exported["runs"]:
        assert run["run_type"] in valid_run_types, f"run_type must be one of {valid_run_types}"


# =============================================================================
# Property 21: Latency Metrics Recording
# =============================================================================

@settings(max_examples=100)
@given(
    span_name=valid_span_name,
    inputs=valid_inputs,
    outputs=valid_outputs
)
def test_latency_metrics_recording_single_span(
    span_name: str,
    inputs: Dict[str, Any],
    outputs: Dict[str, Any]
):
    """
    **Feature: generic-agentic-rag, Property 21: Latency Metrics Recording**
    
    For any agent execution, each tool invocation and reasoning step SHALL
    have a recorded latency_ms value greater than 0.
    
    **Validates: Requirements 8.3**
    """
    tracer = ExecutionTracer()
    
    # Start span
    span_id = tracer.start_span(span_name, inputs)
    
    # Simulate some work (small sleep to ensure measurable latency)
    time.sleep(0.001)  # 1ms minimum
    
    # End span
    tracer.end_span(span_id, outputs)
    
    # Get trace
    trace = tracer.get_trace()
    
    # PROPERTY: Should have exactly one span
    assert len(trace.spans) == 1, "Should have exactly one span"
    
    span = trace.spans[0]
    
    # PROPERTY: latency_ms must be recorded and greater than 0
    assert span.latency_ms is not None, "latency_ms must be recorded"
    assert span.latency_ms > 0, "latency_ms must be greater than 0"
    
    # PROPERTY: end_time must be set
    assert span.end_time is not None, "end_time must be set"
    
    # PROPERTY: start_time must be before end_time
    assert span.start_time < span.end_time, "start_time must be before end_time"


@settings(max_examples=100)
@given(
    span_names=st.lists(valid_span_name, min_size=2, max_size=5, unique=True),
    inputs_list=st.lists(valid_inputs, min_size=2, max_size=5),
    outputs_list=st.lists(valid_outputs, min_size=2, max_size=5)
)
def test_latency_metrics_recording_multiple_spans(
    span_names: List[str],
    inputs_list: List[Dict[str, Any]],
    outputs_list: List[Dict[str, Any]]
):
    """
    **Feature: generic-agentic-rag, Property 21: Latency Metrics Recording**
    
    For any agent execution with multiple steps, each step SHALL have
    its own latency_ms value recorded independently.
    
    **Validates: Requirements 8.3**
    """
    # Ensure we have matching lengths
    min_len = min(len(span_names), len(inputs_list), len(outputs_list))
    assume(min_len >= 2)
    
    span_names = span_names[:min_len]
    inputs_list = inputs_list[:min_len]
    outputs_list = outputs_list[:min_len]
    
    tracer = ExecutionTracer()
    
    # Create and complete spans sequentially
    for name, inputs, outputs in zip(span_names, inputs_list, outputs_list):
        span_id = tracer.start_span(name, inputs)
        time.sleep(0.001)  # Small delay to ensure measurable latency
        tracer.end_span(span_id, outputs)
    
    # Get trace
    trace = tracer.get_trace()
    
    # PROPERTY: Should have all spans
    assert len(trace.spans) == len(span_names), "Should have all spans"
    
    # PROPERTY: Each span must have latency_ms > 0
    for i, span in enumerate(trace.spans):
        assert span.latency_ms is not None, f"Span {i} must have latency_ms recorded"
        assert span.latency_ms > 0, f"Span {i} latency_ms must be greater than 0"
    
    # PROPERTY: total_latency_ms must be recorded
    assert trace.total_latency_ms > 0, "total_latency_ms must be greater than 0"


@settings(max_examples=100)
@given(
    span_name=valid_span_name,
    inputs=valid_inputs,
    outputs=valid_outputs
)
def test_latency_in_exported_trace(
    span_name: str,
    inputs: Dict[str, Any],
    outputs: Dict[str, Any]
):
    """
    **Feature: generic-agentic-rag, Property 21: Latency Metrics Recording**
    
    For any exported trace, the latency_ms SHALL be included in the
    extra metadata of each run.
    
    **Validates: Requirements 8.3**
    """
    tracer = ExecutionTracer()
    
    span_id = tracer.start_span(span_name, inputs)
    time.sleep(0.001)
    tracer.end_span(span_id, outputs)
    
    # Export to LangSmith format
    exported = tracer.export_langsmith()
    
    # PROPERTY: Each run should have latency_ms in extra
    for run in exported["runs"]:
        assert "extra" in run, "Run must have 'extra' field"
        assert "latency_ms" in run["extra"], "Run extra must have 'latency_ms'"
        assert run["extra"]["latency_ms"] is not None, "latency_ms must not be None"
        assert run["extra"]["latency_ms"] > 0, "latency_ms must be greater than 0"
    
    # PROPERTY: Total latency should be in trace extra
    assert "extra" in exported, "Exported trace must have 'extra' field"
    assert "total_latency_ms" in exported["extra"], "Trace extra must have 'total_latency_ms'"
    assert exported["extra"]["total_latency_ms"] > 0, "total_latency_ms must be greater than 0"
