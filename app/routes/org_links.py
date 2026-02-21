"""
Organization Link routes
Implements undirected org linking with normalized IDs (org_low_id, org_high_id)
"""
from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from datetime import datetime, timedelta
from app.models.org_link import (
    OrgLinkCreate, OrgLinkActionRequest, OrgLinkResponse,
    InventoryShareCreate, InventoryShareActionRequest, InventoryShareResponse
)
from app.database.db_operations import db_ops
from app.config.database import Collections, db_config
from app.utils.helpers import serialize_doc, serialize_docs
from app.utils.auth import get_current_user

router = APIRouter(prefix="/org-links", tags=["Shared Inventory: Links"])

COOLDOWN_HOURS = 24


def _normalize_ids(org_a: str, org_b: str):
    """Return (low, high) sorted IDs for undirected link storage"""
    return (min(org_a, org_b), max(org_a, org_b))


def _get_current_org_id(current_user: dict) -> str:
    org_id = current_user.get("organization_id")
    if not org_id:
        raise HTTPException(status_code=403, detail="No organization associated with this account")
    return org_id


def _make_audit(action: str, by_org_id: str, by_user_id: str, note: str = None) -> dict:
    return {
        "action": action,
        "by_org_id": by_org_id,
        "by_user_id": by_user_id,
        "timestamp": datetime.utcnow().isoformat(),
        "note": note
    }


# ─────────────────────────────────────────────────────────────────────────────
# LINK ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/request", status_code=status.HTTP_201_CREATED)
async def send_link_request(
    body: OrgLinkCreate,
    current_user: dict = Depends(get_current_user)
):
    """Send a link request to another organization"""
    from_org_id = _get_current_org_id(current_user)
    to_org_id = body.to_org_id

    if from_org_id == to_org_id:
        raise HTTPException(status_code=400, detail="Cannot link to your own organization")

    low, high = _normalize_ids(from_org_id, to_org_id)

    # Check for existing link
    existing = await db_ops.get_one(Collections.ORG_LINKS, {
        "org_low_id": low, "org_high_id": high, "is_active": True
    })

    if existing:
        if existing["status"] in ("pending", "accepted"):
            raise HTTPException(status_code=400, detail=f"A link already exists with status: {existing['status']}")

        if existing["status"] in ("rejected", "cancelled", "unlinked"):
            # Enforce cooldown
            updated_at = existing.get("updated_at", datetime.utcnow())
            if isinstance(updated_at, str):
                updated_at = datetime.fromisoformat(updated_at)
            cooldown_end = updated_at + timedelta(hours=COOLDOWN_HOURS)
            if datetime.utcnow() < cooldown_end:
                wait_mins = int((cooldown_end - datetime.utcnow()).total_seconds() / 60)
                raise HTTPException(
                    status_code=429,
                    detail=f"Please wait {wait_mins} minutes before re-requesting"
                )
            # Soft-delete old record and create fresh
            await db_ops.update(Collections.ORG_LINKS, str(existing["_id"]), {"is_active": False})

    now = datetime.utcnow()
    link_doc = {
        "org_low_id": low,
        "org_high_id": high,
        "requested_by_org_id": from_org_id,
        "status": "pending",
        "is_active": True,
        "deleted_at": None,
        "created_at": now,
        "updated_at": now,
        "audit_log": [_make_audit("created", from_org_id, current_user.get("sub", ""))]
    }
    created = await db_ops.create(Collections.ORG_LINKS, link_doc)
    return serialize_doc(created)


@router.get("/", response_model=List[dict])
async def get_my_links(current_user: dict = Depends(get_current_user)):
    """Get all links (sent and received) for the current organization"""
    org_id = _get_current_org_id(current_user)
    print(f"🔍 Fetching links for org_id: {org_id}")
    links = await db_ops.get_all(Collections.ORG_LINKS, {
        "$and": [
            {"$or": [{"org_low_id": org_id}, {"org_high_id": org_id}]},
            {"is_active": True}
        ]
    })
    print(f"🔍 Found {len(links)} links")
    return serialize_docs(links)


@router.get("/debug-me")
async def debug_me(current_user: dict = Depends(get_current_user)):
    """Debug endpoint: shows what org_id is extracted from the token"""
    org_id = current_user.get("organization_id")
    return {
        "organization_id": org_id,
        "user_type": current_user.get("user_type"),
        "sub": current_user.get("sub"),
        "username": current_user.get("username"),
    }


@router.patch("/{link_id}/action")
async def link_action(
    link_id: str,
    body: OrgLinkActionRequest,
    current_user: dict = Depends(get_current_user)
):
    """Perform accept | reject | cancel | unlink on a link"""
    org_id = _get_current_org_id(current_user)
    user_id = current_user.get("sub", "")

    link = await db_ops.get_by_id(Collections.ORG_LINKS, link_id)
    if not link or not link.get("is_active"):
        raise HTTPException(status_code=404, detail="Link not found")

    # Authorization: must be one of the two orgs
    if org_id not in (link["org_low_id"], link["org_high_id"]):
        raise HTTPException(status_code=403, detail="Not authorized to act on this link")

    action = body.action
    current_status = link["status"]

    # Validate transitions
    valid_transitions = {
        "accept": ["pending"],
        "reject": ["pending", "accepted"],
        "cancel": ["pending"],
        "unlink": ["accepted"],
    }
    if current_status not in valid_transitions.get(action, []):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot '{action}' a link with status '{current_status}'"
        )

    # For accept/reject on incoming: must be the non-requester
    if action in ("accept", "reject") and current_status == "pending":
        if org_id == link["requested_by_org_id"]:
            raise HTTPException(status_code=403, detail="Cannot accept/reject your own request. Use 'cancel' instead.")

    status_map = {
        "accept": "accepted",
        "reject": "rejected",
        "cancel": "cancelled",
        "unlink": "unlinked",
    }
    new_status = status_map[action]
    now = datetime.utcnow()

    update = {
        "status": new_status,
        "updated_at": now,
        "$push": {"audit_log": _make_audit(action, org_id, user_id)}
    }

    # If unlinking, also revoke all active inventory shares
    if action == "unlink":
        shares_col = db_config.get_collection(Collections.INVENTORY_SHARES)
        await shares_col.update_many(
            {"link_id": link_id, "status": "active"},
            {"$set": {"status": "revoked", "updated_at": now}}
        )

    links_col = db_config.get_collection(Collections.ORG_LINKS)
    await links_col.update_one(
        {"_id": link["_id"]},
        {"$set": {"status": new_status, "updated_at": now},
         "$push": {"audit_log": _make_audit(action, org_id, user_id)}}
    )

    updated = await db_ops.get_by_id(Collections.ORG_LINKS, link_id)
    return serialize_doc(updated)
