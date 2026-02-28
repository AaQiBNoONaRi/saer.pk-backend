"""
Package routes
"""
from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from app.models.package import PackageCreate, PackageUpdate, PackageResponse
from app.database.db_operations import db_ops
from app.config.database import Collections
from app.utils.helpers import serialize_doc, serialize_docs
from app.utils.auth import get_current_user
from app.services.service_charge_logic import get_branch_service_charge, apply_ticket_charge, apply_package_charge, apply_hotel_charge

router = APIRouter(prefix="/packages", tags=["Packages"])

@router.post("/", response_model=PackageResponse, status_code=status.HTTP_201_CREATED)
async def create_package(
    package: PackageCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new package"""
    package_dict = package.model_dump()
    created_package = await db_ops.create(Collections.PACKAGES, package_dict)
    return serialize_doc(created_package)

@router.get("/", response_model=List[PackageResponse])
async def get_packages(
    is_active: bool = None,
    skip: int = 0,
    limit: int = 100,
    current_user: dict = Depends(get_current_user)
):
    """Get all packages with optional filtering"""
    filter_query = {}
    if is_active is not None:
        filter_query["is_active"] = is_active
        
    packages = await db_ops.get_all(Collections.PACKAGES, filter_query, skip=skip, limit=limit)
    
    # Apply service charges for branch users
    role = current_user.get("role")
    entity_type = current_user.get("entity_type")
    branch_id = current_user.get("branch_id")
    
    # Identify portal users (branch admin, branch employee, or area agency)
    agency_type = current_user.get("agency_type")
    is_portal_user = (role == "branch") or (role == "agency" and agency_type == "area") or (entity_type == "branch")
    
    if is_portal_user and branch_id:
        rule = await get_branch_service_charge(branch_id)
        if rule:
            for pkg in packages:
                # Apply ONLY to main package prices (not individual components for fixed packages)
                if pkg.get("package_prices"):
                    for room_type, price in pkg["package_prices"].items():
                        if isinstance(price, dict) and "selling" in price:
                            # Apply to the nested selling price if it exists
                            original_val = price.get("selling", 0)
                            price["selling"] = apply_package_charge(original_val, rule)
                        elif isinstance(price, (int, float)):
                            pkg["package_prices"][room_type] = {"selling": apply_package_charge(price, rule)}

    return serialize_docs(packages)

@router.get("/{package_id}", response_model=PackageResponse)
async def get_package(
    package_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get package by ID"""
    package = await db_ops.get_by_id(Collections.PACKAGES, package_id)
    if not package:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Package not found"
        )
        
    # Apply service charges for branch users
    role = current_user.get("role")
    entity_type = current_user.get("entity_type")
    branch_id = current_user.get("branch_id")
    
    agency_type = current_user.get("agency_type")
    is_portal_user = (role == "branch") or (role == "agency" and agency_type == "area") or (entity_type == "branch")
    
    if is_portal_user and branch_id:
        rule = await get_branch_service_charge(branch_id)
        if rule:
            # Apply ONLY to main package prices
            if package.get("package_prices"):
                for room_type, price in package["package_prices"].items():
                    if isinstance(price, dict) and "selling" in price:
                        original_val = price.get("selling", 0)
                        price["selling"] = apply_package_charge(original_val, rule)
                    elif isinstance(price, (int, float)):
                        package["package_prices"][room_type] = {"selling": apply_package_charge(price, rule)}

    return serialize_doc(package)

@router.put("/{package_id}", response_model=PackageResponse)
async def update_package(
    package_id: str,
    package_update: PackageUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update package"""
    update_data = package_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
        
    updated_package = await db_ops.update(Collections.PACKAGES, package_id, update_data)
    if not updated_package:
        raise HTTPException(status_code=404, detail="Package not found")
        
    return serialize_doc(updated_package)

@router.delete("/{package_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_package(
    package_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete package"""
    deleted = await db_ops.delete(Collections.PACKAGES, package_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Package not found")
