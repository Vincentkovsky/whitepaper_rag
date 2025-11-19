from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Response
from fastapi import status
from pydantic import BaseModel, HttpUrl

from ...core.config import UserContext, get_settings
from ...core.security import get_current_user
from ...models.document import Document
from ...repositories.document_repository import DocumentRepository
from ...services.document_service import DocumentService

router = APIRouter(prefix="/api/documents", tags=["documents"])


def get_document_service() -> DocumentService:
    settings = get_settings()
    repo = DocumentRepository(store_path=settings.storage_base_path.parent / "documents.json")
    return DocumentService(repo=repo, settings=settings)


class UploadResponse(BaseModel):
    document_id: str
    status: str


class SubmitUrlRequest(BaseModel):
    url: HttpUrl


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    current_user: UserContext = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
) -> UploadResponse:
    document = service.upload_pdf(file, user_id=current_user.id)
    return UploadResponse(document_id=document.id, status=document.status.value)


@router.post("/from-url", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def submit_document_url(
    payload: SubmitUrlRequest,
    current_user: UserContext = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
) -> UploadResponse:
    document = service.submit_url(payload.url, user_id=current_user.id)
    return UploadResponse(document_id=document.id, status=document.status.value)


@router.get("", response_model=List[Document])
async def list_documents(
    current_user: UserContext = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    return service.list_documents(current_user.id)


@router.get("/{document_id}", response_model=Document)
async def get_document(
    document_id: str,
    current_user: UserContext = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    return service.get_document(document_id=document_id, user_id=current_user.id)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    current_user: UserContext = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
) -> Response:
    service.delete_document(document_id=document_id, user_id=current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

