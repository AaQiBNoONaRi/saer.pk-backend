"""
Main FastAPI application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
from app.config.database import db_config
from app.config.settings import settings
from app.services.expiry_scheduler import run_expiry_scheduler

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
    form,
    bank_account,
    # Payment System (Kuickapay)
    payment,
    # Booking Routers
    ticket_booking,
    umrah_booking,
    custom_booking,
    # Pax Movement
    pax_movement,
    # Daily Operations
    operations,
    # CRM
    leads,
    passport_leads,
    customers,
    tasks,
    role_groups,
    # AIQS Flight Search
    flight_search,
    # HR Management
    hr,
)
from app.finance import routes as finance_routes
from app.routes import debug


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown events"""
    # Startup
    await db_config.connect_db()
    print(f"🚀 {settings.APP_NAME} v{settings.VERSION} started")
    # Start the booking expiry background scheduler
    expiry_task = asyncio.create_task(run_expiry_scheduler(interval_seconds=60))
    yield
    # Shutdown
    expiry_task.cancel()
    try:
        await expiry_task
    except asyncio.CancelledError:
        pass
    await db_config.close_db()
    print("👋 Application shutdown")

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

# CORS middleware - Must be added before other middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:5176",  # Agency portal
        "http://localhost:5177",
        "http://localhost:5178",
        "http://localhost:5179",
        "http://localhost:5180",  # Public portal
        "http://localhost:5181",
        "http://localhost:5182",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
        "http://127.0.0.1:5176",
        "http://127.0.0.1:5177",
        "http://127.0.0.1:5178",
        "http://127.0.0.1:5179",
        "http://127.0.0.1:5180",
        "http://127.0.0.1:5181",
        "http://127.0.0.1:5182",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Request logging middleware - temporarily disabled to test CORS
# from fastapi import Request
# import time

# @app.middleware("http")
# async def log_requests(request: Request, call_next):
#     start_time = time.time()
#     print(f"\n🌐 {request.method} {request.url.path}")
#     response = await call_next(request)
#     duration = time.time() - start_time
#     print(f"✅ {request.method} {request.url.path} - {response.status_code} ({duration:.2f}s)")
#     return response

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
# Discounted Hotels
from app.routes import discounted_hotels
app.include_router(discounted_hotels.router, prefix="/api")
app.include_router(blog.router, prefix="/api")
app.include_router(form.router, prefix="/api")
app.include_router(bank_account.router, prefix="/api")
app.include_router(payment.router, prefix="/api")

app.include_router(ticket_booking.router, prefix="/api")
app.include_router(umrah_booking.router, prefix="/api")
app.include_router(custom_booking.router, prefix="/api")
app.include_router(pax_movement.router, prefix="/api")
app.include_router(operations.router, prefix="/api")

# Flight Search (AIQS)
app.include_router(flight_search.router, prefix="/api")

# Payment System (Kuickapay)
app.include_router(payment.router)

# CRM
app.include_router(leads.router, prefix="/api")
app.include_router(passport_leads.router, prefix="/api")
app.include_router(customers.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")
app.include_router(role_groups.router, prefix="/api")
app.include_router(debug.router, prefix="/api")

# HR Management
app.include_router(hr.router, prefix="/api")

# Finance & Accounting Module
app.include_router(finance_routes.router, prefix="/api")




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