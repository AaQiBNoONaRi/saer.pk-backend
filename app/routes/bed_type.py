from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from app.config.database import db_config, Collections
from app.utils.auth import get_current_user
from app.database.db_operations import db_ops
from app.utils.helpers import serialize_doc, serialize_docs
from app.models.bed_type import BedTypeCreate, BedTypeUpdate, BedTypeResponse

router = APIRouter(prefix="/bed-types", tags=["Bed Types"])

@router.post("/", response_model=BedTypeResponse, status_code=status.HTTP_201_CREATED)
async def create_bed_type(
    bed_type: BedTypeCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create new bed type with strict validation"""
    
    # Validation: Only ONE "Room Price" allowed
    if bed_type.is_room_price:
        existing = await db_ops.get_all(Collections.BED_TYPES, {"is_room_price": True})
        if existing:
            raise HTTPException(
                status_code=400, 
                detail="A 'Room Price' bed type already exists. Only one is allowed."
            )
            
    bed_type_dict = bed_type.model_dump()
    created = await db_ops.create(Collections.BED_TYPES, bed_type_dict)
    return serialize_doc(created)

@router.get("/", response_model=List[BedTypeResponse])
async def get_bed_types(
    is_active: bool = None,
    current_user: dict = Depends(get_current_user)
):
    """Get all bed types"""
    filter_query = {}
    if is_active is not None:
        filter_query["is_active"] = is_active
    bed_types = await db_ops.get_all(Collections.BED_TYPES, filter_query)
    return serialize_docs(bed_types)

@router.get("/{bed_type_id}", response_model=BedTypeResponse)
async def get_bed_type(
    bed_type_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get bed type by ID"""
    bed_type = await db_ops.get_by_id(Collections.BED_TYPES, bed_type_id)
    if not bed_type:
        raise HTTPException(status_code=404, detail="Bed type not found")
    return serialize_doc(bed_type)

@router.put("/{bed_type_id}", response_model=BedTypeResponse)
async def update_bed_type(
    bed_type_id: str,
    bed_type_update: BedTypeUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update bed type. CANNOT update name if it is 'Room Price'."""
    
    # Fetch existing
    existing = await db_ops.get_by_id(Collections.BED_TYPES, bed_type_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Bed type not found")
        
    # Validation: Cannot rename "Room Price"
    if existing.get("is_room_price") and bed_type_update.name:
         raise HTTPException(
            status_code=400, 
            detail="Cannot rename the protected 'Room Price' bed type."
        )

    update_data = bed_type_update.model_dump(exclude_unset=True)
    
    # Security: Ensure is_room_price cannot be changed via update
    if "is_room_price" in update_data:
        del update_data["is_room_price"]
        
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
        
    updated = await db_ops.update(Collections.BED_TYPES, bed_type_id, update_data)
    return serialize_doc(updated)

@router.delete("/{bed_type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bed_type(
    bed_type_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete bed type. Protected types cannot be deleted."""
    
    # Fetch existing
    existing = await db_ops.get_by_id(Collections.BED_TYPES, bed_type_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Bed type not found")
        
    # Validation: Cannot delete "Room Price"
    if existing.get("is_room_price"):
        raise HTTPException(
            status_code=400, 
            detail="Cannot delete the protected 'Room Price' bed type."
        )
        
    # FUTURE TODO: Validation: Cannot delete if Rooms use this bed type
    # This will be implemented once HotelRoom model is ready
    # if await rooms_exist_for_bed_type(bed_type_id): ...
    
    deleted = await db_ops.delete(Collections.BED_TYPES, bed_type_id)
    if not deleted:
         # Should not happen given check above, but safe to handle
         raise HTTPException(status_code=404, detail="Bed type not found")
