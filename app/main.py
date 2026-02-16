"""
Main FastAPI application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.config.database import db_config
from app.config.settings import settings
from app.routes import organization, branch, agency, employee, hotel, flight, transport, admin, others, package, branch_auth, agency_auth, discount, commission, service_charge

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown events"""
    # Startup
    await db_config.connect_db()
    print(f"🚀 {settings.APP_NAME} v{settings.VERSION} started")
    yield
    # Shutdown
    await db_config.close_db()
    print("👋 Application shutdown")

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174", 
        "http://localhost:5175",  # Organization portal
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
from fastapi.staticfiles import StaticFiles
import os
if not os.path.exists(settings.UPLOAD_DIR):
    os.makedirs(settings.UPLOAD_DIR)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# Include routers
app.include_router(organization.router, prefix="/api")
app.include_router(branch.router, prefix="/api")
app.include_router(branch_auth.router, prefix="/api")
app.include_router(agency.router, prefix="/api")
app.include_router(agency_auth.router, prefix="/api")
app.include_router(employee.router, prefix="/api")
app.include_router(hotel.router, prefix="/api")
app.include_router(flight.router, prefix="/api")
app.include_router(transport.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(others.router, prefix="/api")
app.include_router(package.router, prefix="/api")
app.include_router(discount.router, prefix="/api")
app.include_router(commission.router, prefix="/api")
app.include_router(service_charge.router, prefix="/api")

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "app": settings.APP_NAME,
        "version": settings.VERSION,
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}