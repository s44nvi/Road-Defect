"""
FastAPI application entry point for Road Defect Detection System
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os

# Application startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 Road Defect API starting up...")
    yield
    # Shutdown
    print("🛑 Road Defect API shutting down...")


# Initialize FastAPI app
app = FastAPI(
    title="Road Defect Detection API",
    description="Smart road-defect detection and maintenance prioritization system",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Configuration
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
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
        "version": "1.0.0"
    }


@app.get("/", tags=["Info"])
async def root():
    """Root endpoint with API information"""
    return {
        "name": "Road Defect Detection API",
        "description": "Smart road-defect detection and maintenance prioritization system",
        "docs": "/docs",
        "health": "/health"
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
    uvicorn.run(app, host="0.0.0.0", port=8000)
