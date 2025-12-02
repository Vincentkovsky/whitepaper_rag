"""
Agent API endpoints for the Generic Agentic RAG System.

This module provides API endpoints for interacting with the ReAct agent,
including both synchronous and streaming (SSE) interfaces.

Requirements:
- 7.2: THE Agentic_RAG_System SHALL add new agent-specific endpoints under /api/agent/ prefix.
- 8.2: WHEN the API request includes a trace parameter, THE Agentic_RAG_System SHALL
       return an intermediate_steps field showing tool inputs and outputs.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ...core.security import UserContext, get_current_user
from ...services.subscription_service import SubscriptionService, get_subscription_service
from ...services.agent_service import AgentService, get_agent_service
from ...agent.types import AgentResponse, ThoughtStep


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["agent"])


class ChatRequest(BaseModel):
    """Request body for agent chat endpoints."""
    question: str = Field(description="The user's question")
    model: str = Field(default="mini", description="Model to use: 'mini' or 'turbo'")


class ChatResponse(BaseModel):
    """Response from the agent chat endpoint."""
    answer: str = Field(description="The agent's final answer")
    sources: list = Field(default_factory=list, description="Sources used for the answer")
    model_used: str = Field(description="The model that was used")
    intermediate_steps: Optional[list] = Field(
        default=None,
        description="Reasoning steps (only included when trace=true)"
    )


def get_agent_service_dep() -> AgentService:
    """Dependency for getting the AgentService instance."""
    return get_agent_service()


def get_subscription_service_dep() -> SubscriptionService:
    """Dependency for getting the subscription service."""
    return get_subscription_service()


def _sku_for_model(model: str) -> str:
    """Get the SKU for billing based on model selection."""
    return "qa_turbo" if model == "turbo" else "qa_mini"


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    trace: bool = Query(default=False, description="Include intermediate reasoning steps"),
    current_user: UserContext = Depends(get_current_user),
    agent_service: AgentService = Depends(get_agent_service_dep),
    subscription: SubscriptionService = Depends(get_subscription_service_dep),
) -> ChatResponse:
    """
    Chat with the agent about a document.
    
    This endpoint processes the user's question using the ReAct agent,
    which can use tools like document search to find relevant information.
    
    Args:
        payload: The chat request containing document_id and question
        trace: If true, include intermediate_steps in the response (Requirement 8.2)
        current_user: The authenticated user
        agent_service: The AgentService instance for orchestration
        subscription: The subscription service for billing
        
    Returns:
        ChatResponse with the agent's answer and optionally intermediate steps
    """
    # Check subscription/credits
    sku = _sku_for_model(payload.model)
    if not subscription.check_and_consume(current_user.id, sku):
        usage = subscription.get_usage(current_user.id)
        remaining = usage.get("remaining_credits", 0)
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"积分不足，剩余 {remaining} 。",
        )
    
    try:
        # Run the agent via AgentService
        response: AgentResponse = await agent_service.chat(
            query=payload.question,
            user_id=current_user.id,
            trace_enabled=trace,
        )
        
        # Build response
        result = ChatResponse(
            answer=response.answer,
            sources=response.sources,
            model_used=response.model_used,
        )
        
        # Include intermediate steps if trace=true (Requirement 8.2)
        if trace:
            result.intermediate_steps = [
                {
                    "thought": step.thought,
                    "action": step.action,
                    "action_input": step.action_input,
                    "observation": step.observation,
                }
                for step in response.intermediate_steps
            ]
        
        return result
        
    except Exception as exc:
        logger.error(f"Agent chat failed: {exc}", exc_info=True)
        # Refund credits on failure
        subscription.refund_credits(current_user.id, sku, reason="agent_chat_failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.post("/chat/stream")
async def chat_stream(
    payload: ChatRequest,
    trace: bool = Query(default=False, description="Include intermediate reasoning steps"),
    current_user: UserContext = Depends(get_current_user),
    agent_service: AgentService = Depends(get_agent_service_dep),
    subscription: SubscriptionService = Depends(get_subscription_service_dep),
) -> StreamingResponse:
    """
    Stream chat responses from the agent using Server-Sent Events (SSE).
    
    This endpoint streams the agent's reasoning process in real-time,
    emitting events for thinking, tool calls, tool results, and the final answer.
    
    Event types:
    - thinking: The agent's current thought process
    - tool_call: When the agent invokes a tool
    - tool_result: The result from a tool invocation
    - answer: The final answer
    - error: If an error occurs
    
    Args:
        payload: The chat request containing document_id and question
        trace: If true, include more detailed step information in events
        current_user: The authenticated user
        agent_service: The AgentService instance for orchestration
        subscription: The subscription service for billing
        
    Returns:
        StreamingResponse with SSE events
    """
    # Check subscription/credits
    sku = _sku_for_model(payload.model)
    if not subscription.check_and_consume(current_user.id, sku):
        usage = subscription.get_usage(current_user.id)
        remaining = usage.get("remaining_credits", 0)
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"积分不足，剩余 {remaining} 。",
        )
    
    async def event_generator():
        """Generate SSE events from the agent stream."""
        try:
            async for event in agent_service.chat_stream(
                query=payload.question,
                user_id=current_user.id,
                trace_enabled=trace,
            ):
                # Format as SSE event
                event_data = {
                    "event_type": event.event_type,
                    "content": event.content,
                }
                
                # Include metadata if trace is enabled or for certain event types
                if trace and event.metadata:
                    event_data["metadata"] = event.metadata
                elif event.event_type == "answer" and event.metadata:
                    # Always include latency in answer event
                    event_data["metadata"] = event.metadata
                
                yield f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"
            
            # Send done event
            yield f"data: {json.dumps({'event_type': 'done'})}\n\n"
            
        except Exception as exc:
            logger.error(f"Agent stream failed: {exc}", exc_info=True)
            # Refund credits on failure
            subscription.refund_credits(current_user.id, sku, reason="agent_stream_failed")
            # Send error event
            error_data = {
                "event_type": "error",
                "content": str(exc),
            }
            yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
