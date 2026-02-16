"""
Transport routes
"""
from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from app.models.transport import TransportCreate, TransportUpdate, TransportResponse
from app.database.db_operations import db_ops
from app.config.database import Collections
from app.utils.helpers import serialize_doc, serialize_docs
from app.utils.auth import get_current_user

router = APIRouter(prefix="/transport", tags=["Inventory: Transport"])

@router.post("/", response_model=TransportResponse, status_code=status.HTTP_201_CREATED)
async def create_transport(
    transport: TransportCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new transport vehicle"""
    transport_dict = transport.model_dump()
    created_transport = await db_ops.create(Collections.TRANSPORT, transport_dict)
    return serialize_doc(created_transport)

@router.get("/", response_model=List[TransportResponse])
async def get_transports(
    vehicle_type: str = None,
    skip: int = 0,
    limit: int = 20,
    current_user: dict = Depends(get_current_user)
):
    """Get all transport with optional filtering"""
    filter_query = {}
    if vehicle_type:
        filter_query["vehicle_type"] = {"$regex": vehicle_type, "$options": "i"}
        
    transports = await db_ops.get_all(Collections.TRANSPORT, filter_query, skip=skip, limit=limit)
    return serialize_docs(transports)

@router.get("/{transport_id}", response_model=TransportResponse)
async def get_transport(
    transport_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get transport by ID"""
    transport = await db_ops.get_by_id(Collections.TRANSPORT, transport_id)
    if not transport:
        raise HTTPException(status_code=404, detail="Transport not found")
    return serialize_doc(transport)

@router.put("/{transport_id}", response_model=TransportResponse)
async def update_transport(
    transport_id: str,
    transport_update: TransportUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update transport"""
    update_data = transport_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
        
    updated_transport = await db_ops.update(Collections.TRANSPORT, transport_id, update_data)
    if not updated_transport:
        raise HTTPException(status_code=404, detail="Transport not found")
        
    return serialize_doc(updated_transport)

@router.delete("/{transport_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transport(
    transport_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete transport"""
    deleted = await db_ops.delete(Collections.TRANSPORT, transport_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Transport not found")
