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
    limit: int = 20,
    current_user: dict = Depends(get_current_user)
):
    """Get all packages with optional filtering"""
    filter_query = {}
    if is_active is not None:
        filter_query["is_active"] = is_active
        
    packages = await db_ops.get_all(Collections.PACKAGES, filter_query, skip=skip, limit=limit)
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
