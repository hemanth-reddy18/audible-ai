"""Set up logging before importing anything else"""

try:
    import sentry_sdk
except ImportError:
    sentry_sdk = None

from api.constants import (
    CORS_ALLOWED_ORIGINS,
    DEPLOYMENT_MODE,
    ENABLE_TELEMETRY,
    SENTRY_DSN,
)
from api.logging_config import ENVIRONMENT, setup_logging

# Set up logging and get the listener for cleanup
setup_logging()


if sentry_sdk and SENTRY_DSN and (
    DEPLOYMENT_MODE != "oss" or (DEPLOYMENT_MODE == "oss" and ENABLE_TELEMETRY)
):
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        send_default_pii=True,
        environment=ENVIRONMENT,
    )
    print(f"Sentry initialized in environment: {ENVIRONMENT}")


import asyncio
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from api.constants import REDIS_URL
from api.errors.mps import MPS_UNAVAILABLE_PUBLIC_MESSAGE, MPSUnavailableError
from api.mcp_server import mcp
from api.routes.main import router as main_router
from api.services.pipecat.tracing_config import (
    handle_langfuse_sync,
    load_all_org_langfuse_credentials,
)
from api.services.pipecat.tts_cache.runtime import close_speech_cache
from api.services.worker_sync.manager import (
    WorkerSyncManager,
    set_worker_sync_manager,
)
from api.services.worker_sync.protocol import WorkerSyncEventType
from api.tasks.arq import get_arq_redis

API_PREFIX = "/api/v1"

mcp_app = mcp.http_app(path="/", stateless_http=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with mcp_app.lifespan(app):
        # Auto-initialize database schema if using SQLite
        try:
            from api.db import db_client
            from api.db.models import Base
            async with db_client.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database schema verified/created successfully.")
        except Exception as e:
            logger.warning(f"Database schema initialization: {e}")

        # warmup arq pool (optional in offline dev mode)
        try:
            await asyncio.wait_for(get_arq_redis(), timeout=1.0)
        except Exception as e:
            logger.warning(f"Arq Redis warmup skipped (offline dev mode): {e}")

        # Pre-register all org-specific Langfuse exporters so they're ready
        # before any pipeline runs, without per-call DB lookups.
        try:
            await load_all_org_langfuse_credentials()
        except Exception as e:
            logger.warning(f"Langfuse credentials preload skipped: {e}")

        # Start cross-worker sync manager so config changes propagate to all workers
        sync_manager = None
        try:
            sync_manager = WorkerSyncManager(REDIS_URL)
            sync_manager.register(
                WorkerSyncEventType.LANGFUSE_CREDENTIALS, handle_langfuse_sync
            )
            await asyncio.wait_for(sync_manager.start(), timeout=1.0)
            set_worker_sync_manager(sync_manager)
        except Exception as e:
            logger.warning(f"WorkerSyncManager skipped: {e}")

        from api.services.observability import loop_exceptions, loop_lag, metrics
        from api.services.observability.call_events import (
            delivery as call_event_delivery,
        )

        try:
            call_event_delivery.start()
        except Exception as e:
            logger.warning(f"Call event delivery start skipped: {e}")

        # Event-loop lag gauge — per-pod saturation signal read off
        # /health/active-calls during autoscaling load tests.
        try:
            metrics.start()
            loop_lag.start()
            # Routes exceptions that escape tasks and timer callbacks; demotes one
            # known aioice teardown race and leaves everything else at ERROR.
            loop_exceptions.install()
        except Exception as e:
            logger.warning(f"Observability loop monitors skipped: {e}")

        try:
            yield  # Run app
        finally:
            logger.info("Starting graceful shutdown...")
            from api.services.workflow.text_chat_stream import (
                finish_streaming_text_chat_turns,
            )

            try:
                await finish_streaming_text_chat_turns()
            except Exception:
                pass
            try:
                await call_event_delivery.shutdown()
            except Exception:
                pass
            if sync_manager is not None:
                try:
                    await sync_manager.stop()
                except Exception:
                    pass
            try:
                await close_speech_cache()
            except Exception:
                pass
            try:
                await loop_lag.stop()
            except Exception:
                pass
            try:
                metrics.stop()
            except Exception:
                pass


app = FastAPI(
    title="Audible AI API",
    description="Enterprise REST & Real-time WebSocket API for Audible AI Voice Platform",
    version="1.0.0",
    openapi_url=f"{API_PREFIX}/openapi.json",
    lifespan=lifespan,
    servers=[
        {"url": "http://localhost:8000", "description": "Local development"},
    ],
)


@app.exception_handler(MPSUnavailableError)
async def handle_mps_unavailable_error(
    _request: Request,
    _exc: MPSUnavailableError,
) -> JSONResponse:
    """Tell callers this is a Dograh outage, not invalid customer config."""

    return JSONResponse(
        status_code=503,
        content={"detail": MPS_UNAVAILABLE_PUBLIC_MESSAGE},
    )


# Configure CORS.
# OSS is typically deployed with UI and API behind a single reverse proxy
# (same-origin, so CORS does not apply). Keep it permissive without
# credentials — wildcard + credentials is rejected by browsers and unsafe.
# SaaS deployments must set CORS_ALLOWED_ORIGINS to an explicit allowlist.
if DEPLOYMENT_MODE == "oss":
    cors_origins: list[str] = ["*"]
    cors_allow_credentials = False
else:
    if not CORS_ALLOWED_ORIGINS:
        raise RuntimeError(
            "CORS_ALLOWED_ORIGINS must be set to an explicit origin allowlist "
            "when DEPLOYMENT_MODE != 'oss'"
        )
    if "*" in CORS_ALLOWED_ORIGINS:
        raise RuntimeError(
            "CORS_ALLOWED_ORIGINS cannot contain '*' with credentialed requests"
        )
    cors_origins = CORS_ALLOWED_ORIGINS
    cors_allow_credentials = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Workflow-Run-Id"],
)


def _add_public_embed_cors_middleware() -> None:
    from api.routes.public_embed import PublicEmbedCORSMiddleware

    app.add_middleware(PublicEmbedCORSMiddleware, api_prefix=API_PREFIX)


_add_public_embed_cors_middleware()

api_router = APIRouter()

# include subrouters here
api_router.include_router(main_router)

# main router with api prefix
app.include_router(api_router, prefix=API_PREFIX)

# Mount the MCP server — agents reach it at /api/v1/mcp over Streamable HTTP,
# authenticating with the same X-API-Key header used by the REST API.
# Mounted under /api/v1 so existing reverse-proxy rules (nginx etc.) route it
# without any extra configuration.
app.mount(f"{API_PREFIX}/mcp", mcp_app)
