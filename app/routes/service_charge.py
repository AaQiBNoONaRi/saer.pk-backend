"""
Service Charge routes
"""
from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from app.models.service_charge import ServiceChargeCreate, ServiceChargeUpdate, ServiceChargeResponse
from app.database.db_operations import db_ops
from app.config.database import Collections
from app.utils.helpers import serialize_doc, serialize_docs
from app.utils.auth import get_current_user, get_org_id

router = APIRouter(prefix="/service-charges", tags=["Service Charges"])

@router.post("/", response_model=ServiceChargeResponse, status_code=status.HTTP_201_CREATED)
async def create_service_charge(
    service_charge: ServiceChargeCreate,
    org_id: str = Depends(get_org_id),
):
    """Create a new service charge – stamped with caller's org"""
    service_charge_dict = service_charge.model_dump(mode='json')
    service_charge_dict["organization_id"] = org_id
    created_service_charge = await db_ops.create(Collections.SERVICE_CHARGES, service_charge_dict)
    return serialize_doc(created_service_charge)

@router.get("/", response_model=List[ServiceChargeResponse])
async def get_service_charges(
    skip: int = 0,
    limit: int = 100,
    is_active: bool = None,
    is_automatic: bool = None,
    org_id: str = Depends(get_org_id),
):
    """Get service charges scoped to caller's org"""
    filter_query: dict = {"organization_id": org_id}
    if is_active is not None:
        filter_query["is_active"] = is_active
    if is_automatic is not None:
        filter_query["is_automatic"] = is_automatic
    service_charges = await db_ops.get_all(Collections.SERVICE_CHARGES, filter_query=filter_query, skip=skip, limit=limit)
    return serialize_docs(service_charges)

@router.get("/{service_charge_id}", response_model=ServiceChargeResponse)
async def get_service_charge(service_charge_id: str, org_id: str = Depends(get_org_id)):
    service_charge = await db_ops.get_by_id(Collections.SERVICE_CHARGES, service_charge_id)
    if not service_charge or service_charge.get("organization_id") != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service charge not found")
    return serialize_doc(service_charge)

@router.put("/{service_charge_id}", response_model=ServiceChargeResponse)
async def update_service_charge(
    service_charge_id: str,
    service_charge_update: ServiceChargeUpdate,
    org_id: str = Depends(get_org_id),
):
    existing_charge = await db_ops.get_by_id(Collections.SERVICE_CHARGES, service_charge_id)
    if not existing_charge or existing_charge.get("organization_id") != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service charge not found")
    update_data = service_charge_update.model_dump(exclude_unset=True, mode='json')
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")
    new_applies_to = update_data.get("applies_to", existing_charge.get("applies_to"))
    new_charge_type = update_data.get("charge_type", existing_charge.get("charge_type"))
    if new_applies_to in ["packages", "hotels"] and new_charge_type != "fixed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Packages and Hotels can only have fixed service charges")
    updated_service_charge = await db_ops.update(Collections.SERVICE_CHARGES, service_charge_id, update_data)
    return serialize_doc(updated_service_charge)

@router.delete("/{service_charge_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_service_charge(service_charge_id: str, org_id: str = Depends(get_org_id)):
    sc = await db_ops.get_by_id(Collections.SERVICE_CHARGES, service_charge_id)
    if not sc or sc.get("organization_id") != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service charge not found")
    await db_ops.delete(Collections.SERVICE_CHARGES, service_charge_id)
    return None
