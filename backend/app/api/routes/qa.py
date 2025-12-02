from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Callable, Optional

from ...core.security import UserContext, get_current_user
from ...services.rag_service import RAGService
from ...services.subscription_service import SubscriptionService, get_subscription_service
from ...tasks.document_tasks import enqueue_generate_analysis
from ...tasks.priority import TaskPriority


router = APIRouter(prefix="/api/qa", tags=["qa"])


class QueryRequest(BaseModel):
    document_id: str
    question: str
    model: str = "mini"


class AnalysisRequest(BaseModel):
    document_id: str


def get_rag_service_dep() -> RAGService:
    return RAGService()


def get_subscription_service_dep() -> SubscriptionService:
    return get_subscription_service()


def get_enqueue_analysis_dep() -> Callable[..., Optional[dict]]:
    return enqueue_generate_analysis


def _sku_for_model(model: str) -> str:
    return "qa_turbo" if model == "turbo" else "qa_mini"


@router.post("/query")
async def query_document(
    payload: QueryRequest,
    current_user: UserContext = Depends(get_current_user),
    rag_service: RAGService = Depends(get_rag_service_dep),
    subscription: SubscriptionService = Depends(get_subscription_service_dep),
) -> dict:
    sku = _sku_for_model(payload.model)
    if not subscription.check_and_consume(current_user.id, sku):
        usage = subscription.get_usage(current_user.id)
        remaining = usage.get("remaining_credits", 0)
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"积分不足，剩余 {remaining} 。",
        )
    try:
        response = rag_service.query(
            question=payload.question,
            document_id=payload.document_id,
            user_id=current_user.id,
            model=payload.model,
        )
        return response
    except Exception as exc:
        subscription.refund_credits(current_user.id, sku, reason="qa_failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.post("/analysis/generate", status_code=status.HTTP_202_ACCEPTED)
async def generate_analysis(
    payload: AnalysisRequest,
    current_user: UserContext = Depends(get_current_user),
    subscription: SubscriptionService = Depends(get_subscription_service_dep),
    dispatch_analysis: Callable[..., Optional[dict]] = Depends(get_enqueue_analysis_dep),
):
    sku = "analysis_report"
    if not subscription.check_and_consume(current_user.id, sku):
        usage = subscription.get_usage(current_user.id)
        remaining = usage.get("remaining_credits", 0)
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"积分不足，剩余 {remaining} 。",
        )
    priority = TaskPriority.PREMIUM if current_user.is_subscriber else TaskPriority.STANDARD
    try:
        result = dispatch_analysis(payload.document_id, current_user.id, priority=priority, sku=sku)
    except Exception as exc:
        subscription.refund_credits(current_user.id, sku, reason="analysis_failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    if result is not None:
        return {"status": "completed", "report": result}
    return {"status": "queued"}


@router.get("/analysis/{document_id}")
async def get_analysis(
    document_id: str,
    current_user: UserContext = Depends(get_current_user),
    rag_service: RAGService = Depends(get_rag_service_dep),
):
    report = rag_service.get_analysis(document_id)
    if report:
        return {"status": "completed", "report": report}
    # In a real app, we might check Celery task status here to differentiate between "queued" and "not found"
    return {"status": "processing"}

