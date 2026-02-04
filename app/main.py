from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import close_pool, get_pool
from app.routers import code_samples, doc_pages, pages, projects


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup - initialize connection pool
    get_pool()

    yield

    # Shutdown - close connection pool
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


@app.get("/")
def root():
    """Root endpoint."""
    return {"message": "Knowledge Extraction API", "docs": "/docs"}
