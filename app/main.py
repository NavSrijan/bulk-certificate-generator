from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import init_db
from app.api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context for startup and shutdown initialization."""
    # Initialize DB schema
    init_db()
    yield


app = FastAPI(
    title=settings.APP_TITLE,
    version=settings.APP_VERSION,
    description=settings.APP_DESCRIPTION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable CORS for cross-origin client usage
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API v1 router
app.include_router(router)


@app.get("/", tags=["Root"])
def root():
    """Root metadata endpoint providing links to documentation and status."""
    return {
        "service": settings.APP_TITLE,
        "version": settings.APP_VERSION,
        "documentation": "/docs",
        "redoc": "/redoc",
        "health": "/api/v1/health",
        "endpoints": {
            "create_job": "POST /api/v1/jobs",
            "list_jobs": "GET /api/v1/jobs",
            "get_job": "GET /api/v1/jobs/{job_id}",
            "download_zip": "GET /api/v1/jobs/{job_id}/download",
            "get_certificate": "GET /api/v1/certificates/{certificate_id}",
            "download_certificate": "GET /api/v1/certificates/{certificate_id}/download",
            "verify_certificate": "GET /api/v1/verify/{certificate_code}",
        },
    }
