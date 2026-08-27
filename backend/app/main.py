"""
FastAPI application entry point for Road Defect Detection System
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.config import settings
from app.db import init_db

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
    }


# TODO: Add routes for:
# - POST /evidence - Upload observation data
# - GET /defects - Get defect list with priority queue
# - GET /defects/{id} - Get defect details
# - POST /defects/{id}/verify - Officer verification
# - POST /defects/{id}/repair - Repair scheduling
# - GET /repairs - Get repair history


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
    )
