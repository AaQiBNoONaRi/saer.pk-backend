from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from app.models.discounted_hotel import (
    DiscountedHotelCreate,
    DiscountedHotelUpdate,
    DiscountedHotelResponse,
)
from app.utils.auth import get_current_user, has_module_permission
from app.database.db_operations import db_ops
from app.config.database import Collections
from app.utils.helpers import serialize_doc, serialize_docs

router = APIRouter(prefix="/discounted-hotels", tags=["Discounted Hotels"])


@router.post("/", response_model=DiscountedHotelResponse, status_code=status.HTTP_201_CREATED)
async def create_discounted_hotel(hotel: DiscountedHotelCreate, current_user: dict = Depends(get_current_user)):
    # Permission check
    if not has_module_permission(current_user, "hotels.discounted", "add"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    hotel_doc = hotel.model_dump(mode='json')
    # Stamp organization and creator
    org_id = current_user.get("organization_id")
    emp_id = current_user.get("emp_id") or current_user.get("_id")
    if org_id:
        hotel_doc["organization_id"] = org_id
    if emp_id:
        hotel_doc["created_by_employee_id"] = emp_id

    created = await db_ops.create(Collections.DISCOUNTED_HOTELS, hotel_doc)
    return serialize_doc(created)


@router.get("/", response_model=List[DiscountedHotelResponse])
async def list_discounted_hotels(skip: int = 0, limit: int = 50, current_user: dict = Depends(get_current_user)):
    # Only return hotels belonging to the user's organization
    org_id = current_user.get("organization_id")
    if not org_id and not current_user.get('sub'):
        # non-admin users must have organization context
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context missing")

    filter_q = {}
    if org_id:
        filter_q["organization_id"] = org_id

    docs = await db_ops.get_all(Collections.DISCOUNTED_HOTELS, filter_query=filter_q, skip=skip, limit=limit)
    return serialize_docs(docs)


@router.get("/{hotel_id}", response_model=DiscountedHotelResponse)
async def get_discounted_hotel(hotel_id: str, current_user: dict = Depends(get_current_user)):
    doc = await db_ops.get_by_id(Collections.DISCOUNTED_HOTELS, hotel_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found")
    # enforce org isolation
    org_id = current_user.get("organization_id")
    if org_id and doc.get("organization_id") != org_id and not current_user.get('sub'):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return serialize_doc(doc)


@router.put("/{hotel_id}", response_model=DiscountedHotelResponse)
async def update_discounted_hotel(hotel_id: str, hotel_update: DiscountedHotelUpdate, current_user: dict = Depends(get_current_user)):
    # Permission check
    if not has_module_permission(current_user, "hotels.discounted", "update"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    existing = await db_ops.get_by_id(Collections.DISCOUNTED_HOTELS, hotel_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found")

    org_id = current_user.get("organization_id")
    if org_id and existing.get("organization_id") != org_id and not current_user.get('sub'):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    # Optionally restrict updates to creator
    emp_id = current_user.get("emp_id") or current_user.get("_id")
    if existing.get("created_by_employee_id") and emp_id and existing.get("created_by_employee_id") != emp_id and not current_user.get('sub'):
        # Allow admins to bypass
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only creator or admin can update")

    update_data = hotel_update.model_dump(exclude_unset=True, mode='json')
    updated = await db_ops.update(Collections.DISCOUNTED_HOTELS, hotel_id, update_data)
    return serialize_doc(updated)


@router.delete("/{hotel_id}")
async def delete_discounted_hotel(hotel_id: str, current_user: dict = Depends(get_current_user)):
    if not has_module_permission(current_user, "hotels.discounted", "delete"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    existing = await db_ops.get_by_id(Collections.DISCOUNTED_HOTELS, hotel_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found")

    org_id = current_user.get("organization_id")
    if org_id and existing.get("organization_id") != org_id and not current_user.get('sub'):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    emp_id = current_user.get("emp_id") or current_user.get("_id")
    if existing.get("created_by_employee_id") and emp_id and existing.get("created_by_employee_id") != emp_id and not current_user.get('sub'):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only creator or admin can delete")

    await db_ops.delete(Collections.DISCOUNTED_HOTELS, hotel_id)
    return {"status": "deleted"}
