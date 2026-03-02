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
    branch_auth,
    agency_auth,
    employee,
    hotel,
    flight,
    transport,
    admin,
    others,
    package,
    discount,
    commission,
    service_charge,
    ticket_booking,
    umrah_booking,
    custom_booking,
    # Hotel PMS Routers
    hotel_category,
    bed_type,
    hotel_floor,
    hotel_room,
    hotel_room_booking,
    # Shared Inventory
    org_links,
    inventory_shares,
    # Flight Search (AIQS)
    flight_search,
    bank_account,
    blog,
    form,
    # HR, Payments, Operations, Pax Movement, Commission Records
    hr,
    payment,
    operations,
    pax_movement,
    commission_records,
    # CRM, Bookings, Role Groups, Tasks, Debug
    booking,
    customers,
    leads,
    passport_leads,
    role_groups,
    tasks,
    debug,
    discounted_hotels,
    ticket_inventory,
    dashboard,
    customer_booking,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown events"""
    # Startup
    await db_config.connect_db()
    print(f"[START] {settings.APP_NAME} v{settings.VERSION} started")
    yield
    # Shutdown
    await db_config.close_db()
    print("[STOP] Application shutdown")

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
        "http://localhost:5175",
        "http://localhost:5176",
        "http://localhost:5177",
        "http://localhost:5178",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
        "http://127.0.0.1:5176",
        "http://127.0.0.1:5177",
        "http://127.0.0.1:5178",
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
    print(f"[422] VALIDATION ERROR on {request.method} {request.url.path}")
    print(f"[ERRORS] {json.dumps(safe_errors, indent=2)}")
    if body:
        print(f"[BODY] {json.dumps(body, indent=2, default=str)}")
    print("="*60 + "\n")
    return JSONResponse(status_code=422, content={"detail": safe_errors})

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    print(f"\n[REQ] {request.method} {request.url.path}")
    response = await call_next(request)
    duration = time.time() - start_time
    print(f"[RES] {request.method} {request.url.path} - {response.status_code} ({duration:.2f}s)")
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
# Shared Inventory
app.include_router(org_links.router, prefix="/api")
app.include_router(inventory_shares.router, prefix="/api")
# Flight Search (AIQS)
app.include_router(flight_search.router, prefix="/api")
app.include_router(blog.router, prefix="/api")
app.include_router(form.router, prefix="/api")
app.include_router(bank_account.router, prefix="/api")

app.include_router(ticket_booking.router, prefix="/api")
app.include_router(umrah_booking.router, prefix="/api")
app.include_router(custom_booking.router, prefix="/api")
app.include_router(customer_booking.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")

# HR, Payments, Operations, Pax Movement, Commission Records
app.include_router(hr.router, prefix="/api")
app.include_router(payment.router, prefix="/api")
app.include_router(operations.router, prefix="/api")
app.include_router(pax_movement.router, prefix="/api")
app.include_router(commission_records.router, prefix="/api")

# CRM, Bookings, Role Groups, Tasks, Debug, Discounted Hotels
app.include_router(booking.router, prefix="/api")
app.include_router(customers.router, prefix="/api")
app.include_router(leads.router, prefix="/api")
app.include_router(passport_leads.router, prefix="/api")
app.include_router(role_groups.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")
app.include_router(debug.router, prefix="/api")
app.include_router(discounted_hotels.router, prefix="/api")
app.include_router(ticket_inventory.router, prefix="/api")




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