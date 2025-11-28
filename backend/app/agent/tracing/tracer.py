"""
Execution Tracer for Agent observability.

This module provides tracing capabilities for agent execution,
supporting LangSmith/LangFuse compatible trace export and latency metrics.

**Feature: generic-agentic-rag**
**Requirements: 8.1, 8.3**
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TraceSpan(BaseModel):
    """A single span in the execution trace."""
    span_id: str = Field(description="Unique identifier for this span")
    parent_id: Optional[str] = Field(default=None, description="ID of the parent span, if any")
    name: str = Field(description="Name of the operation (e.g., 'tool_call', 'llm_call')")
    start_time: datetime = Field(description="When the span started")
    end_time: Optional[datetime] = Field(default=None, description="When the span ended")
    inputs: Dict[str, Any] = Field(default_factory=dict, description="Input data for this span")
    outputs: Optional[Dict[str, Any]] = Field(default=None, description="Output data from this span")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    latency_ms: Optional[float] = Field(default=None, description="Latency in milliseconds")


class ExecutionTrace(BaseModel):
    """Complete execution trace containing all spans."""
    trace_id: str = Field(description="Unique identifier for this trace")
    spans: List[TraceSpan] = Field(default_factory=list, description="All spans in this trace")
    total_latency_ms: float = Field(default=0.0, description="Total execution time in milliseconds")


class ExecutionTracer:
    """
    Records agent execution for observability and debugging.
    
    Supports:
    - Hierarchical span tracking with parent-child relationships
    - Latency metrics for each span
    - LangSmith/LangFuse compatible trace export
    
    Usage:
        tracer = ExecutionTracer()
        span_id = tracer.start_span("tool_call", {"tool": "search", "query": "test"})
        # ... do work ...
        tracer.end_span(span_id, {"results": ["item1", "item2"]})
        trace = tracer.get_trace()
    """
    
    def __init__(self, trace_id: Optional[str] = None):
        """
        Initialize a new ExecutionTracer.
        
        Args:
            trace_id: Optional trace ID. If not provided, a UUID will be generated.
        """
        self._trace_id = trace_id or str(uuid.uuid4())
        self._spans: Dict[str, TraceSpan] = {}
        self._span_order: List[str] = []  # Maintain insertion order
        self._start_time: Optional[datetime] = None
        self._current_parent_id: Optional[str] = None
    
    @property
    def trace_id(self) -> str:
        """Get the trace ID."""
        return self._trace_id
    
    def start_span(
        self,
        name: str,
        inputs: Dict[str, Any],
        parent_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Start a new trace span.
        
        Args:
            name: Name of the operation (e.g., "tool_call", "llm_call", "reasoning_step")
            inputs: Input data for this span
            parent_id: Optional parent span ID for hierarchical tracing
            metadata: Optional additional metadata
        
        Returns:
            Unique span_id for this span
        """
        span_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        
        # Record trace start time from first span
        if self._start_time is None:
            self._start_time = now
        
        span = TraceSpan(
            span_id=span_id,
            parent_id=parent_id or self._current_parent_id,
            name=name,
            start_time=now,
            inputs=inputs,
            metadata=metadata or {}
        )
        
        self._spans[span_id] = span
        self._span_order.append(span_id)
        
        return span_id
    
    def end_span(self, span_id: str, outputs: Dict[str, Any]) -> None:
        """
        End a trace span with outputs.
        
        Args:
            span_id: The ID of the span to end
            outputs: Output data from this span
        
        Raises:
            ValueError: If the span_id is not found
        """
        if span_id not in self._spans:
            raise ValueError(f"Span not found: {span_id}")
        
        span = self._spans[span_id]
        now = datetime.now(timezone.utc)
        
        span.end_time = now
        span.outputs = outputs
        
        # Calculate latency in milliseconds
        if span.start_time:
            delta = now - span.start_time
            span.latency_ms = delta.total_seconds() * 1000
    
    def set_parent(self, parent_id: Optional[str]) -> None:
        """
        Set the current parent span ID for subsequent spans.
        
        Args:
            parent_id: The parent span ID, or None to clear
        """
        self._current_parent_id = parent_id
    
    def get_trace(self) -> ExecutionTrace:
        """
        Get the complete execution trace.
        
        Returns:
            ExecutionTrace with all spans and total latency
        """
        # Calculate total latency from first to last span
        total_latency_ms = 0.0
        
        if self._span_order:
            first_span = self._spans[self._span_order[0]]
            
            # Find the latest end_time among all spans
            latest_end: Optional[datetime] = None
            for span_id in self._span_order:
                span = self._spans[span_id]
                if span.end_time:
                    if latest_end is None or span.end_time > latest_end:
                        latest_end = span.end_time
            
            if latest_end and first_span.start_time:
                delta = latest_end - first_span.start_time
                total_latency_ms = delta.total_seconds() * 1000
        
        # Return spans in order
        ordered_spans = [self._spans[span_id] for span_id in self._span_order]
        
        return ExecutionTrace(
            trace_id=self._trace_id,
            spans=ordered_spans,
            total_latency_ms=total_latency_ms
        )
    
    def export_langsmith(self) -> Dict[str, Any]:
        """
        Export trace in LangSmith compatible format.
        
        Returns:
            Dictionary conforming to LangSmith trace schema with:
            - id: trace ID
            - name: "agent_execution"
            - start_time: ISO format timestamp
            - end_time: ISO format timestamp
            - inputs: aggregated inputs from root spans
            - outputs: aggregated outputs from final spans
            - runs: list of span runs
        """
        trace = self.get_trace()
        
        # Find root spans (no parent) and leaf spans (no children)
        root_spans = [s for s in trace.spans if s.parent_id is None]
        child_span_ids = {s.parent_id for s in trace.spans if s.parent_id}
        leaf_spans = [s for s in trace.spans if s.span_id not in child_span_ids]
        
        # Aggregate inputs from root spans
        aggregated_inputs: Dict[str, Any] = {}
        for span in root_spans:
            aggregated_inputs.update(span.inputs)
        
        # Aggregate outputs from leaf spans
        aggregated_outputs: Dict[str, Any] = {}
        for span in leaf_spans:
            if span.outputs:
                aggregated_outputs.update(span.outputs)
        
        # Determine start and end times
        start_time: Optional[str] = None
        end_time: Optional[str] = None
        
        if trace.spans:
            start_time = trace.spans[0].start_time.isoformat()
            
            # Find latest end time
            for span in trace.spans:
                if span.end_time:
                    if end_time is None or span.end_time.isoformat() > end_time:
                        end_time = span.end_time.isoformat()
        
        # Convert spans to LangSmith run format
        runs = []
        for span in trace.spans:
            run = {
                "id": span.span_id,
                "name": span.name,
                "start_time": span.start_time.isoformat(),
                "end_time": span.end_time.isoformat() if span.end_time else None,
                "inputs": span.inputs,
                "outputs": span.outputs,
                "parent_run_id": span.parent_id,
                "run_type": self._infer_run_type(span.name),
                "extra": {
                    "metadata": span.metadata,
                    "latency_ms": span.latency_ms
                }
            }
            runs.append(run)
        
        return {
            "id": trace.trace_id,
            "name": "agent_execution",
            "start_time": start_time,
            "end_time": end_time,
            "inputs": aggregated_inputs,
            "outputs": aggregated_outputs,
            "runs": runs,
            "extra": {
                "total_latency_ms": trace.total_latency_ms
            }
        }
    
    def _infer_run_type(self, span_name: str) -> str:
        """
        Infer the LangSmith run type from span name.
        
        Args:
            span_name: The name of the span
        
        Returns:
            Run type string: "llm", "tool", "chain", or "retriever"
        """
        name_lower = span_name.lower()
        
        if "llm" in name_lower or "model" in name_lower or "generate" in name_lower:
            return "llm"
        elif "tool" in name_lower:
            return "tool"
        elif "retriev" in name_lower or "search" in name_lower:
            return "retriever"
        else:
            return "chain"
    
    def clear(self) -> None:
        """Clear all spans and reset the tracer."""
        self._spans.clear()
        self._span_order.clear()
        self._start_time = None
        self._current_parent_id = None
