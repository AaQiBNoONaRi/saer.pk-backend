"""
Inventory Share Request routes
Only linked (accepted) organizations can share inventory
"""
from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from datetime import datetime
from app.models.org_link import (
    InventoryShareCreate, InventoryShareActionRequest, InventoryShareResponse
)
from app.database.db_operations import db_ops
from app.config.database import Collections, db_config
from app.utils.helpers import serialize_doc, serialize_docs
from app.utils.auth import get_current_user

router = APIRouter(prefix="/inventory-shares", tags=["Shared Inventory: Shares"])


def _get_current_org_id(current_user: dict) -> str:
    org_id = current_user.get("organization_id")
    if not org_id:
        raise HTTPException(status_code=403, detail="No organization associated with this account")
    return org_id


def _make_audit(action: str, by_org_id: str, by_user_id: str) -> dict:
    return {
        "action": action,
        "by_org_id": by_org_id,
        "by_user_id": by_user_id,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.post("/request", status_code=status.HTTP_201_CREATED)
async def send_share_request(
    body: InventoryShareCreate,
    current_user: dict = Depends(get_current_user)
):
    """Send an inventory share request to a linked organization"""
    from_org_id = _get_current_org_id(current_user)

    # Validate the link exists and is accepted
    link = await db_ops.get_by_id(Collections.ORG_LINKS, body.link_id)
    if not link or link.get("status") != "accepted":
        raise HTTPException(status_code=400, detail="No active accepted link found")

    # Validate current org is part of this link
    if from_org_id not in (link["org_low_id"], link["org_high_id"]):
        raise HTTPException(status_code=403, detail="Not authorized for this link")

    # Validate target org is the other party
    other_org = link["org_high_id"] if from_org_id == link["org_low_id"] else link["org_low_id"]
    if body.to_org_id != other_org:
        raise HTTPException(status_code=400, detail="Target org does not match link")

    now = datetime.utcnow()
    share_doc = {
        "link_id": body.link_id,
        "from_org_id": from_org_id,
        "to_org_id": body.to_org_id,
        "inventory_types": body.inventory_types,
        "scope": body.scope.model_dump(),
        "status": "pending",
        "is_active": True,
        "deleted_at": None,
        "created_at": now,
        "updated_at": now,
        "audit_log": [_make_audit("created", from_org_id, current_user.get("sub", ""))]
    }
    created = await db_ops.create(Collections.INVENTORY_SHARES, share_doc)
    return serialize_doc(created)


@router.get("/", response_model=List[dict])
async def get_my_shares(current_user: dict = Depends(get_current_user)):
    """Get all inventory share requests (sent and received)"""
    org_id = _get_current_org_id(current_user)
    shares = await db_ops.get_all(Collections.INVENTORY_SHARES, {
        "$or": [{"from_org_id": org_id}, {"to_org_id": org_id}],
        "is_active": True
    })
    return serialize_docs(shares)


@router.patch("/{share_id}/action")
async def share_action(
    share_id: str,
    body: InventoryShareActionRequest,
    current_user: dict = Depends(get_current_user)
):
    """Perform accept | reject | revoke on a share request"""
    org_id = _get_current_org_id(current_user)
    user_id = current_user.get("sub", "")

    share = await db_ops.get_by_id(Collections.INVENTORY_SHARES, share_id)
    if not share or not share.get("is_active"):
        raise HTTPException(status_code=404, detail="Share request not found")

    # Authorization
    if org_id not in (share["from_org_id"], share["to_org_id"]):
        raise HTTPException(status_code=403, detail="Not authorized")

    action = body.action
    current_status = share["status"]

    valid_transitions = {
        "accept": ["pending"],
        "reject": ["pending", "active"],
        "revoke": ["active", "pending"],
    }
    if current_status not in valid_transitions.get(action, []):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot '{action}' a share with status '{current_status}'"
        )

    # Only recipient can accept/reject incoming
    if action in ("accept", "reject") and org_id == share["from_org_id"]:
        if action == "reject":
            pass  # sender can reject/revoke their own
        else:
            raise HTTPException(status_code=403, detail="Only recipient can accept")

    status_map = {"accept": "active", "reject": "rejected", "revoke": "revoked"}
    new_status = status_map[action]
    now = datetime.utcnow()

    shares_col = db_config.get_collection(Collections.INVENTORY_SHARES)
    await shares_col.update_one(
        {"_id": share["_id"]},
        {"$set": {"status": new_status, "updated_at": now},
         "$push": {"audit_log": _make_audit(action, org_id, user_id)}}
    )

    updated = await db_ops.get_by_id(Collections.INVENTORY_SHARES, share_id)
    return serialize_doc(updated)
