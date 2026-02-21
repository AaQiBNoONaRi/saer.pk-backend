"""
Main FastAPI application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.config.database import db_config
from app.config.settings import settings

from app.routes import (
    organization,
    branch,
    agency,
    employee,
    hotel, # Old name, might need rename if I changed the file name
    flight,
    transport,
    admin,
    others,
    package,
    branch_auth,
    agency_auth,
    discount,
    commission,
    service_charge,
    # Hotel PMS Routers
    hotel_category,
    bed_type,
    hotel_floor,
    hotel_room,
    hotel_room_booking,
    blog,
    form
)

from app.routes import organization, branch, agency, employee, hotel, flight, transport, admin, others, package, branch_auth, agency_auth, discount, commission, service_charge, ticket_booking, umrah_booking, custom_booking


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

# Request logging middleware
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import time
import json

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    body = None
    try:
        body = await request.json()
    except Exception:
        pass
    # Round-trip through json with default=str to handle non-serializable objects (e.g. ValueError)
    safe_errors = json.loads(json.dumps(exc.errors(), default=str))
    print("\n" + "="*60)
    print(f"❌ 422 VALIDATION ERROR on {request.method} {request.url.path}")
    print(f"📋 ERRORS: {json.dumps(safe_errors, indent=2)}")
    if body:
        print(f"📦 BODY SENT: {json.dumps(body, indent=2, default=str)}")
    print("="*60 + "\n")
    return JSONResponse(status_code=422, content={"detail": safe_errors})

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    print(f"\n🌐 {request.method} {request.url.path}")
    response = await call_next(request)
    duration = time.time() - start_time
    print(f"✅ {request.method} {request.url.path} - {response.status_code} ({duration:.2f}s)")
    return response

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
# Hotel Inventory System
app.include_router(hotel.router, prefix="/api") # Main Hotel Router
app.include_router(hotel_category.router, prefix="/api")
app.include_router(bed_type.router, prefix="/api")
app.include_router(hotel_floor.router, prefix="/api")
app.include_router(hotel_room.router, prefix="/api")
app.include_router(hotel_room_booking.router, prefix="/api")

# Other Routers
app.include_router(flight.router, prefix="/api")
app.include_router(transport.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(others.router, prefix="/api")
app.include_router(package.router, prefix="/api")
app.include_router(discount.router, prefix="/api")
app.include_router(commission.router, prefix="/api")
app.include_router(service_charge.router, prefix="/api")

app.include_router(blog.router, prefix="/api")
app.include_router(form.router, prefix="/api")

app.include_router(ticket_booking.router, prefix="/api")
app.include_router(umrah_booking.router, prefix="/api")
app.include_router(custom_booking.router, prefix="/api")


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