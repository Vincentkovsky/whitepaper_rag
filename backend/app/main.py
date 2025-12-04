from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

try:  # pragma: no cover - optional dependency
    from sentry_sdk import init as sentry_init  # type: ignore[import]
    from sentry_sdk.integrations.fastapi import FastApiIntegration  # type: ignore[import]
except ImportError:  # pragma: no cover
    sentry_init = None
    FastApiIntegration = None

from .api.routes import auth, documents, subscription, qa, agent, admin
from .core.config import get_settings
from .logging_utils import setup_logging
from .middleware.logging_middleware import RequestLoggingMiddleware


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings)
    if settings.sentry_dsn and sentry_init and FastApiIntegration:
        sentry_init(
            dsn=settings.sentry_dsn,
            integrations=[FastApiIntegration()],
            environment=settings.environment,
            traces_sample_rate=0.2,
        )

    app = FastAPI(title=settings.app_name)

    # Add SessionMiddleware for OAuth (must be added before other middleware)
    app.add_middleware(SessionMiddleware, secret_key=settings.jwt_secret_key)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLoggingMiddleware)

    app.include_router(auth.router)
    app.include_router(documents.router)
    app.include_router(subscription.router)
    app.include_router(qa.router)
    app.include_router(agent.router)
    app.include_router(admin.router)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/metrics")
    async def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()

