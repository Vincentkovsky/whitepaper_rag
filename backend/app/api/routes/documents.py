from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, HttpUrl
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import UserContext, get_settings
from ...core.security import get_current_user
from ...core.database import get_db
from ...models.document import Document, DocumentListItem
from ...repositories.document_repository import PostgresDocumentRepository
from ...services.document_service import DocumentService
from ...services.subscription_service import get_subscription_service
from ...tasks.document_tasks import TaskPriority
from uuid import UUID

router = APIRouter(prefix="/api/documents", tags=["documents"])

settings = get_settings()


def get_document_service(
    session: AsyncSession = Depends(get_db),
) -> DocumentService:
    """Dependency to get document service with PostgreSQL repository"""
    repo = PostgresDocumentRepository(session)
    subscription = get_subscription_service() # Keep this as it's not explicitly removed in the instruction
    return DocumentService(repo=repo, settings=settings, subscription_service=subscription)


class UrlSubmitRequest(BaseModel):
    url: HttpUrl


class UploadResponse(BaseModel):
    document_id: str
    status: str


class DocumentStatusResponse(BaseModel):
    document_id: str
    status: str
    error_message: str | None = None


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_pdf(
    file: UploadFile = File(...),
    current_user: UserContext = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
) -> UploadResponse:
    priority = TaskPriority.PREMIUM if current_user.is_subscriber else TaskPriority.STANDARD
    document = await service.upload_pdf(
        file,
        user_id=current_user.id,
        priority=priority,
    )
    return UploadResponse(document_id=document.id, status=document.status.value)


@router.post("/submit-url", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def submit_url(
    payload: UrlSubmitRequest,
    current_user: UserContext = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
) -> UploadResponse:
    priority = TaskPriority.PREMIUM if current_user.is_subscriber else TaskPriority.STANDARD
    document = await service.submit_url(
        str(payload.url),
        user_id=current_user.id,
        priority=priority,
    )
    return UploadResponse(document_id=document.id, status=document.status.value)


@router.get("", response_model=List[DocumentListItem])
async def list_documents(
    current_user: UserContext = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    return await service.list_documents(current_user.id)


@router.get("/{document_id}", response_model=Document)
async def get_document(
    document_id: str,
    current_user: UserContext = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    return await service.get_document(
        document_id=document_id,
        user_id=current_user.id,
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    current_user: UserContext = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
) -> Response:
    await service.delete_document(
        document_id=document_id,
        user_id=current_user.id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(
    document_id: UUID, # <--- 2. 这里改成 UUID，FastAPI 会自动拒绝 "undefined" 这种非法字符串
    current_user: UserContext = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    try:
        # 注意：因为上面 document_id 已经是 UUID 对象了，
        # 如果 service 接收字符串，这里可能需要 str(document_id)
        status_payload = await service.get_document_status(
            document_id=str(document_id), 
            user_id=current_user.id,
        )
        
        return DocumentStatusResponse(
            document_id=status_payload["document_id"],
            status=status_payload["status"].value if hasattr(status_payload["status"], "value") else status_payload["status"],
            error_message=status_payload["error_message"],
        )

    except ValueError as e:
        # <--- 3. 捕获 Service 抛出的找不到文档的错误
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e) # 返回 "Document not found or access denied"
        )
        
    except Exception as e:
        # <--- 4. 捕获其他未知错误，防止服务器崩成 500
        # 建议这里加个 logger.error(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )