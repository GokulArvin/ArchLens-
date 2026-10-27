"""
ArchLens Backend - FastAPI Application
Architecture Conformance Checking System
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

from app.core.config import settings
from app.api.routes import diagram, repository, conformance, violations, reports

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="ArchLens API",
    description=(
        "Architecture Conformance Checking with Computer Vision, "
        "Static Analysis and Evidence-Grounded LLM Reasoning"
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(diagram.router, prefix="/api/v1", tags=["Diagram Analysis"])
app.include_router(repository.router, prefix="/api/v1", tags=["Repository Analysis"])
app.include_router(conformance.router, prefix="/api/v1", tags=["Conformance"])
app.include_router(violations.router, prefix="/api/v1", tags=["Violations"])
app.include_router(reports.router, prefix="/api/v1", tags=["Reports"])


@app.get("/", tags=["Health"])
async def root():
    return {"message": "ArchLens API is running", "version": "0.1.0"}


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "service": "archlens-backend"}


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Check logs for details."},
    )
