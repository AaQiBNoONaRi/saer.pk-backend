"""
Package routes
"""
from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from app.models.package import PackageCreate, PackageUpdate, PackageResponse
from app.database.db_operations import db_ops
from app.config.database import Collections
from app.utils.helpers import serialize_doc, serialize_docs
from app.utils.auth import get_current_user, get_org_id, get_shared_org_ids

router = APIRouter(prefix="/packages", tags=["Packages"])

@router.post("/", response_model=PackageResponse, status_code=status.HTTP_201_CREATED)
async def create_package(
    package: PackageCreate,
    org_id: str = Depends(get_org_id),
    current_user: dict = Depends(get_current_user)
):
    """Create a new package – stamped with calling org's ID"""
    package_dict = package.model_dump()
    package_dict["organization_id"] = org_id
    created_package = await db_ops.create(Collections.PACKAGES, package_dict)
    return serialize_doc(created_package)

@router.get("/", response_model=List[PackageResponse])
async def get_packages(
    is_active: bool = None,
    skip: int = 0,
    limit: int = 100,
    org_id: str = Depends(get_org_id),
):
    """Get packages – own org + orgs that have an active packages inventory share"""
    visible_orgs = await get_shared_org_ids(org_id, "packages")
    filter_query: dict = {"organization_id": {"$in": visible_orgs}}
    if is_active is not None:
        filter_query["is_active"] = is_active
    packages = await db_ops.get_all(Collections.PACKAGES, filter_query, skip=skip, limit=limit)
    return serialize_docs(packages)

@router.get("/{package_id}", response_model=PackageResponse)
async def get_package(
    package_id: str,
    org_id: str = Depends(get_org_id),
):
    """Get package by ID – ownership or shared-inventory check"""
    package = await db_ops.get_by_id(Collections.PACKAGES, package_id)
    if not package:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Package not found")
    visible_orgs = await get_shared_org_ids(org_id, "packages")
    if package.get("organization_id") not in visible_orgs:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Package not found")
    return serialize_doc(package)

@router.put("/{package_id}", response_model=PackageResponse)
async def update_package(
    package_id: str,
    package_update: PackageUpdate,
    org_id: str = Depends(get_org_id),
):
    """Update package – only own-org packages"""
    package = await db_ops.get_by_id(Collections.PACKAGES, package_id)
    if not package or package.get("organization_id") != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Package not found")
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
    org_id: str = Depends(get_org_id),
):
    """Delete package – only own-org packages"""
    package = await db_ops.get_by_id(Collections.PACKAGES, package_id)
    if not package or package.get("organization_id") != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Package not found")
    await db_ops.delete(Collections.PACKAGES, package_id)

