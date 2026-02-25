import logging
import logging.config
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import close_pool, get_pool
from app.dependencies import set_session_manager
from app.routers import chat, code_query, code_samples, doc_pages, metrics, pages, projects, sessions
from app.services.sessions import SessionManager

# Load environment variables from .env file (no-op in Docker where env is injected)
load_dotenv()

logging.config.dictConfig({
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "stdout": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "formatter": "default",
        },
    },
    "root": {
        "handlers": ["stdout"],
        "level": os.environ.get("LOG_LEVEL", "INFO"),
    },
})

logger = logging.getLogger(__name__)


def _run_migrations():
    """Apply any pending yoyo migrations against DATABASE_URL."""
    import os
    from yoyo import get_backend, read_migrations

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.warning("DATABASE_URL not set — skipping migrations")
        return

    try:
        backend = get_backend(database_url)
        migrations = read_migrations("migrations")
        with backend.lock():
            pending = backend.to_apply(migrations)
            if pending:
                logger.info(f"Applying {len(pending)} pending migration(s)")
                backend.apply_migrations(pending)
            else:
                logger.info("No pending migrations")
    except Exception:
        logger.exception("Migration failed")
        raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Run database migrations before accepting traffic
    _run_migrations()

    # Startup - initialize connection pool
    get_pool()

    # Initialize session manager
    session_manager = SessionManager()
    set_session_manager(session_manager)
    session_manager.start_cleanup_task()
    logger.info("Session manager started")

    yield

    # Shutdown - stop cleanup task and close pool
    await session_manager.stop_cleanup_task()
    logger.info("Session manager shutdown complete")

    close_pool()


app = FastAPI(
    title="Knowledge Extraction API",
    description="API for managing projects, pages, code samples, and documentation",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — restrict origins in production via CORS_ORIGINS env var
# Set to a comma-separated list, e.g. "https://app.example.com,https://admin.example.com"
_cors_origins_env = os.environ.get("CORS_ORIGINS", "*")
_cors_origins = [o.strip() for o in _cors_origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(projects.router)
app.include_router(pages.router)
app.include_router(code_samples.router)
app.include_router(doc_pages.router)
app.include_router(code_query.router)
app.include_router(metrics.router)
app.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
app.include_router(chat.router, prefix="/sessions", tags=["chat"])


@app.get("/")
def root():
    """Root endpoint."""
    return {"message": "Knowledge Extraction API", "docs": "/docs"}


@app.get("/health", tags=["health"])
def health():
    """Health check endpoint for load balancers and container orchestration."""
    return {"status": "ok"}
