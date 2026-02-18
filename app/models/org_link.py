"""
Organization Link and Inventory Share Request models
Implements the Shared Inventory module with normalized org IDs (undirected links)
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime

# --- Enums ---
LinkStatus = Literal["pending", "accepted", "rejected", "cancelled", "unlinked"]
ShareStatus = Literal["pending", "active", "rejected", "revoked"]
InventoryType = Literal["tickets", "hotels", "packages"]
LinkAction = Literal["accept", "reject", "cancel", "unlink"]
ShareAction = Literal["accept", "reject", "revoke"]


# --- Audit Log Entry ---
class AuditEntry(BaseModel):
    action: str
    by_org_id: str
    by_user_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    note: Optional[str] = None


# --- Organization Link ---
class OrgLinkCreate(BaseModel):
    """Send a link request to another organization"""
    to_org_id: str = Field(..., description="Target organization ID")


class OrgLinkActionRequest(BaseModel):
    """Perform an action on an existing link"""
    action: LinkAction


class OrgLinkResponse(BaseModel):
    id: str = Field(alias="_id")
    org_low_id: str
    org_high_id: str
    requested_by_org_id: str
    status: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    audit_log: List[dict] = []

    class Config:
        populate_by_name = True


# --- Inventory Share Request ---
class ShareScope(BaseModel):
    all: bool = True
    filters: Optional[dict] = Field(default_factory=dict)


class InventoryShareCreate(BaseModel):
    """Send an inventory share request to a linked organization"""
    link_id: str
    to_org_id: str
    inventory_types: List[InventoryType] = Field(..., min_length=1)
    scope: ShareScope = Field(default_factory=ShareScope)


class InventoryShareActionRequest(BaseModel):
    action: ShareAction


class InventoryShareResponse(BaseModel):
    id: str = Field(alias="_id")
    link_id: str
    from_org_id: str
    to_org_id: str
    inventory_types: List[str]
    scope: dict
    status: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    audit_log: List[dict] = []

    class Config:
        populate_by_name = True
