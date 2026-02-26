from fastapi import APIRouter, Depends
from typing import List
from app.utils.auth import get_current_user
from app.database.db_operations import db_ops
from app.config.database import Collections

router = APIRouter(prefix="/debug", tags=["Debug"])


@router.get("/token")
async def debug_token(current_user: dict = Depends(get_current_user)):
    """Return the server-decoded token payload and a small sample of hotels visible to this user."""
    # Return the current_user payload
    result = {"current_user": current_user}

    # Attempt to show count of hotels visible to this user
    try:
        org_id = current_user.get("organization_id")
        is_super_admin = current_user.get("role") == 'super_admin'
        filter_q = {}
        if not is_super_admin:
            filter_q["organization_id"] = org_id
        hotels = await db_ops.get_all(Collections.HOTELS, filter_q, skip=0, limit=10)
        result["sample_hotels"] = [{"_id": str(h.get("_id")), "organization_id": h.get("organization_id"), "name": h.get("name")} for h in hotels]
        result["sample_count"] = len(result["sample_hotels"])
    except Exception as e:
        result["hotels_error"] = str(e)

    return result
