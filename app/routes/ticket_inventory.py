"""
Ticket Inventory routes
API endpoints for managing flight ticket inventory
"""
from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Optional
from app.models.ticket_inventory import (
    TicketInventoryCreate,
    TicketInventoryUpdate,
    TicketInventoryResponse
)
from app.database.db_operations import db_ops
from app.config.database import Collections
from app.utils.helpers import serialize_doc, serialize_docs
from app.utils.auth import get_current_user

router = APIRouter(prefix="/ticket-inventory", tags=["Inventory: Ticket Inventory"])

@router.post("/", response_model=TicketInventoryResponse, status_code=status.HTTP_201_CREATED)
async def create_ticket_inventory(
    ticket: TicketInventoryCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new ticket inventory entry"""
    ticket_dict = ticket.model_dump()
    created_ticket = await db_ops.create(Collections.TICKET_INVENTORY, ticket_dict)
    return serialize_doc(created_ticket)

@router.get("/", response_model=List[TicketInventoryResponse])
async def get_ticket_inventory(
    group_name: Optional[str] = None,
    group_type: Optional[str] = None,
    trip_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    skip: int = 0,
    limit: int = 20,
    current_user: dict = Depends(get_current_user)
):
    """Get all ticket inventory with optional filtering"""
    filter_query = {}
    if group_name:
        filter_query["group_name"] = {"$regex": group_name, "$options": "i"}
    if group_type:
        filter_query["group_type"] = {"$regex": group_type, "$options": "i"}
    if trip_type:
        filter_query["trip_type"] = trip_type
    if is_active is not None:
        filter_query["is_active"] = is_active
        
    tickets = await db_ops.get_all(Collections.TICKET_INVENTORY, filter_query, skip=skip, limit=limit)
    return serialize_docs(tickets)

@router.get("/{ticket_id}", response_model=TicketInventoryResponse)
async def get_ticket_inventory_by_id(
    ticket_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get ticket inventory by ID"""
    ticket = await db_ops.get_by_id(Collections.TICKET_INVENTORY, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket inventory not found")
    return serialize_doc(ticket)

@router.put("/{ticket_id}", response_model=TicketInventoryResponse)
async def update_ticket_inventory(
    ticket_id: str,
    ticket_update: TicketInventoryUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update ticket inventory"""
    update_data = ticket_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
        
    updated_ticket = await db_ops.update(Collections.TICKET_INVENTORY, ticket_id, update_data)
    if not updated_ticket:
        raise HTTPException(status_code=404, detail="Ticket inventory not found")
        
    return serialize_doc(updated_ticket)

@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ticket_inventory(
    ticket_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete ticket inventory"""
    deleted = await db_ops.delete(Collections.TICKET_INVENTORY, ticket_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Ticket inventory not found")
