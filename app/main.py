from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pymongo.database import Database

from app.routers import code_samples, doc_pages, pages, projects

# Database state
_db_instance: Database | None = None


def get_db_dependency() -> Database:
    """Get database instance for FastAPI dependency injection."""
    if _db_instance is None:
        raise RuntimeError("Database not initialized")
    return _db_instance


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    import os

    from app.db import get_client

    global _db_instance
    # Startup
    client = get_client()
    db_name = os.getenv("MONGODB_DATABASE", "app")
    _db_instance = client[db_name]
    app.state.mongo_client = client

    yield

    # Shutdown
    if hasattr(app.state, "mongo_client"):
        app.state.mongo_client.close()
    _db_instance = None


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


@app.get("/")
def root():
    """Root endpoint."""
    return {"message": "Knowledge Extraction API", "docs": "/docs"}
