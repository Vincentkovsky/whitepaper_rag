import os
from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient

from backend.app.api.routes import documents, subscription as subscription_routes, qa as qa_routes
from backend.app.core.config import get_settings
from backend.app.repositories.document_repository import LocalDocumentRepository
from backend.app.services.document_service import DocumentService
from backend.app.services.subscription_service import SubscriptionService, get_subscription_service


class StubEmbedder:
    def __init__(self):
        self.deleted = []

    def delete_document_vectors(self, document_id: str, user_id: str) -> None:
        self.deleted.append((document_id, user_id))


@pytest.fixture(scope="function")
def client(tmp_path_factory: pytest.TempPathFactory) -> Generator[TestClient, None, None]:
    uploads_dir: Path = tmp_path_factory.mktemp("uploads")
    os.environ["STORAGE_BASE_PATH"] = str(uploads_dir)
    os.environ["DOCUMENT_PIPELINE_ENABLED"] = "false"

    get_settings.cache_clear()
    from backend.app.main import create_app

    repo = LocalDocumentRepository(store_path=uploads_dir / "documents.json")
    settings = get_settings()
    embedder = StubEmbedder()
    subscription = get_subscription_service()
    service = DocumentService(
        repo=repo,
        settings=settings,
        embedder=embedder,
        subscription_service=subscription,
    )

    app = create_app()
    app.state.test_embedder = embedder
    app.state.test_subscription = subscription
    app.state.test_service = service
    app.dependency_overrides[documents.get_document_service] = lambda: service
    app.dependency_overrides[subscription_routes.get_subscription_service_dep] = lambda: subscription
    app.dependency_overrides[qa_routes.get_subscription_service_dep] = lambda: subscription

    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def reset_subscription_service():
    get_subscription_service.cache_clear()
    yield
    get_subscription_service.cache_clear()

