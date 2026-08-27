"""
FastAPI application entry point for Road Defect Detection System
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.config import settings
from app.db import init_db
from app.api import evidence, defects, verify

# Application startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 Road Defect API starting up...")
    try:
        init_db()
        print("✅ Database initialized successfully")
    except Exception as e:
        print(f"⚠️ Database initialization warning: {e}")
    yield
    # Shutdown
    print("🛑 Road Defect API shutting down...")


# Initialize FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="Smart road-defect detection and maintenance prioritization system",
    version=settings.app_version,
    lifespan=lifespan,
    debug=settings.debug,
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "service": "Road Defect API",
        "version": settings.app_version,
        "environment": settings.environment,
    }


@app.get("/", tags=["Info"])
async def root():
    """Root endpoint with API information"""
    return {
        "name": settings.app_name,
        "description": "Smart road-defect detection and maintenance prioritization system",
        "version": settings.app_version,
        "environment": settings.environment,
        "docs": "/docs",
        "health": "/health",
        "api_prefix": settings.api_prefix,
    }


# Include API routers
app.include_router(evidence.router, prefix=settings.api_prefix)
app.include_router(defects.router, prefix=settings.api_prefix)
app.include_router(verify.router, prefix=settings.api_prefix)

# TODO: Add routes for:
# - POST /evidence/bulk - Bulk upload
# - POST /defects/{id}/repair - Repair scheduling
# - GET /repairs - Get repair history
# - Authentication middleware
# - Rate limiting
# - Error handling middleware


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
    )
