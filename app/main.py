import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import close_pool, get_pool
from app.dependencies import set_session_manager
from app.routers import chat, code_query, code_samples, doc_pages, pages, projects, sessions
from app.services.sessions import SessionManager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup - initialize connection pool
    get_pool()

    # Initialize session manager
    session_manager = SessionManager()
    set_session_manager(session_manager)
    session_manager.start_cleanup_task()
    logger.info("Session manager started")

    yield

    # Shutdown - cleanup sessions and close pool
    await session_manager.stop_cleanup_task()
    await session_manager.close_all_sessions()
    logger.info("Session manager shutdown complete")

    close_pool()


app = FastAPI(
    title="Knowledge Extraction API",
    description="API for managing projects, pages, code samples, and documentation",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware - allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
app.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
app.include_router(chat.router, prefix="/sessions", tags=["chat"])


@app.get("/")
def root():
    """Root endpoint."""
    return {"message": "Knowledge Extraction API", "docs": "/docs"}
