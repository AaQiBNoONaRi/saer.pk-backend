from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, File, UploadFile
from typing import List, Optional
from app.config.database import db_config, Collections
from app.utils.auth import get_current_user
from app.database.db_operations import db_ops
from app.config.database import Collections
from app.utils.helpers import serialize_doc, serialize_docs
from app.models.hotel import HotelCreate, HotelUpdate, HotelResponse
from app.config.settings import settings
from datetime import date, datetime
from app.utils.auth import get_current_user
from app.models.hotel import HotelCreate, HotelUpdate, HotelResponse

import os
import shutil
import uuid

router = APIRouter(prefix="/hotels", tags=["Inventory: Hotels"])
router = APIRouter(prefix="/hotels", tags=["Inventory: Hotels"])

def convert_dates_to_strings(data: dict) -> dict:
    """Convert date objects to ISO format strings for MongoDB compatibility"""
    result = data.copy()
    
    # Convert top-level date fields
    if 'available_from' in result and isinstance(result['available_from'], date):
        result['available_from'] = result['available_from'].isoformat()
    if 'available_until' in result and isinstance(result['available_until'], date):
        result['available_until'] = result['available_until'].isoformat()
    
    # Convert date fields in prices array
    if 'prices' in result and isinstance(result['prices'], list):
        for price in result['prices']:
            if 'date_from' in price and isinstance(price['date_from'], date):
                price['date_from'] = price['date_from'].isoformat()
            if 'date_to' in price and isinstance(price['date_to'], date):
                price['date_to'] = price['date_to'].isoformat()
    
    return result



@router.post("/", response_model=HotelResponse, status_code=status.HTTP_201_CREATED)
async def create_hotel(
    hotel: HotelCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create new hotel with validation rules"""
    hotel_dict = hotel.model_dump(mode='json')
    hotel_dict = convert_dates_to_strings(hotel_dict)

    # Stamp the creating org's ID onto the hotel
    org_id = (current_user.get("organization_id") or "").strip()
    emp_id = current_user.get("emp_id") or current_user.get("_id")
    is_super_admin = current_user.get('role') == 'super_admin'
    # Require org context for everyone except a super_admin with no org (global admin)
    if not org_id and not is_super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context missing")

    if org_id:
        hotel_dict["organization_id"] = org_id
    if emp_id:
        hotel_dict["created_by_employee_id"] = emp_id

    # Ensure dates are strings for MongoDB (Motor can't encode datetime.date)
    for key, value in hotel_dict.items():
        if isinstance(value, date):
            hotel_dict[key] = value.isoformat()
        elif key == "prices" and isinstance(value, list):
            for price in value:
                if isinstance(price.get("date_from"), date):
                    price["date_from"] = price["date_from"].isoformat()
                if isinstance(price.get("date_to"), date):
                    price["date_to"] = price["date_to"].isoformat()

    created_hotel = await db_ops.create(Collections.HOTELS, hotel_dict)
    return serialize_doc(created_hotel)

@router.get("/", response_model=List[HotelResponse])
async def get_hotels(
    city: str = None,
    category_id: Optional[str] = None,
    available_from: Optional[date] = None,
    available_until: Optional[date] = None,
    min_rating: Optional[int] = None,
    skip: int = 0,
    limit: int = 20,
    current_user: dict = Depends(get_current_user)
):
    """Get all hotels with optional filtering — scoped to the caller's org"""
    filter_query = {}

    # Org-scoping:
    # - If token carries an organization_id → always filter by it (no exceptions, any role)
    # - If no organization_id AND role==super_admin → global view (no filter)
    # - If no organization_id AND NOT super_admin → 403
    org_id = (current_user.get("organization_id") or "").strip()
    is_super_admin = current_user.get('role') == 'super_admin'
    if org_id:
        filter_query["organization_id"] = org_id
    elif not is_super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context missing")

    if city:
        filter_query["city"] = {"$regex": city, "$options": "i"}

    if category_id:
        filter_query["category_id"] = category_id

    # Date availability check logic (simple): hotel.available_from <= requested available_from
    # and hotel.available_until >= requested available_until
    if available_from:
        filter_query["available_from"] = {"$lte": available_from.isoformat()}
    if available_until:
        filter_query["available_until"] = {"$gte": available_until.isoformat()}

    # Minimum star rating filter
    if min_rating is not None:
        filter_query["star_rating"] = {"$gte": min_rating}

    hotels = await db_ops.get_all(Collections.HOTELS, filter_query, skip=skip, limit=limit)

    # Enrichment: Populate category name
    results = []
    for hotel in hotels:
        if hotel.get("category_id"):
            category = await db_ops.get_by_id(Collections.HOTEL_CATEGORIES, hotel["category_id"])
            if category:
                hotel["category_name"] = category.get("name")
        results.append(hotel)

    return serialize_docs(results)

@router.get("/{hotel_id}", response_model=HotelResponse)
async def get_hotel(
    hotel_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get hotel by ID"""
    hotel = await db_ops.get_by_id(Collections.HOTELS, hotel_id)
    if not hotel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hotel not found"
        )
    org_id = (current_user.get("organization_id") or "").strip()
    is_super_admin = current_user.get('role') == 'super_admin'
    if org_id:
        if hotel.get('organization_id') != org_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    elif not is_super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context missing")
    return serialize_doc(hotel)

@router.put("/{hotel_id}", response_model=HotelResponse)
async def update_hotel(
    hotel_id: str,
    hotel_update: HotelUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update hotel"""
    update_data = hotel_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    update_data = convert_dates_to_strings(update_data)
    # Ensure org isolation and creator restriction
    existing = await db_ops.get_by_id(Collections.HOTELS, hotel_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Hotel not found")

    org_id = (current_user.get("organization_id") or "").strip()
    emp_id = current_user.get("emp_id") or current_user.get("_id")
    is_super_admin = current_user.get('role') == 'super_admin'
    if org_id:
        if existing.get('organization_id') != org_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    elif not is_super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context missing")

    # Optional: only creator or admin can modify
    if existing.get('created_by_employee_id') and emp_id and existing.get('created_by_employee_id') != emp_id and not current_user.get('sub'):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only creator or admin can update")

    updated_hotel = await db_ops.update(Collections.HOTELS, hotel_id, update_data)
    if not updated_hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")
        
    return serialize_doc(updated_hotel)

@router.delete("/{hotel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_hotel(
    hotel_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete hotel"""
    existing = await db_ops.get_by_id(Collections.HOTELS, hotel_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Hotel not found")

    org_id = (current_user.get("organization_id") or "").strip()
    emp_id = current_user.get("emp_id") or current_user.get("_id")
    is_super_admin = current_user.get('role') == 'super_admin'
    if org_id:
        if existing.get('organization_id') != org_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    elif not is_super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context missing")

    if existing.get('created_by_employee_id') and emp_id and existing.get('created_by_employee_id') != emp_id and not current_user.get('sub'):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only creator or admin can delete")

    deleted = await db_ops.delete(Collections.HOTELS, hotel_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Hotel not found")

@router.post("/upload-images")
async def upload_images(
    hotel_name: str = Query(...),
    files: List[UploadFile] = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Upload multiple images for a hotel and store them in a structured folder"""
    try:
        # Create a safe folder name from hotel name
        safe_name = "".join([c if c.isalnum() else "_" for c in hotel_name])
        hotel_dir = os.path.join(settings.UPLOAD_DIR, "hotels", safe_name)
        
        if not os.path.exists(hotel_dir):
            os.makedirs(hotel_dir)
            
        uploaded_urls = []
        for file in files:
            # Generate unique filename to prevent overwrites
            ext = os.path.splitext(file.filename)[1]
            filename = f"{uuid.uuid4()}{ext}"
            file_path = os.path.join(hotel_dir, filename)
            
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            # Construct accessible URL
            url = f"http://localhost:8000/uploads/hotels/{safe_name}/{filename}"
            uploaded_urls.append(url)
            
        return {"urls": uploaded_urls}
    except Exception as e:
        print(f"Error uploading images: {e}")
        raise HTTPException(status_code=500, detail=str(e))
