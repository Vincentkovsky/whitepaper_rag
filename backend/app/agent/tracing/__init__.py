"""
Tracing module for execution observability.

Contains:
- ExecutionTracer for recording agent execution
- LangSmith/LangFuse compatible trace export
- Latency metrics recording
"""

from .tracer import (
    ExecutionTrace,
    ExecutionTracer,
    TraceSpan,
)

__all__ = [
    "ExecutionTrace",
    "ExecutionTracer",
    "TraceSpan",
]
