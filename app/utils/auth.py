"""
Authentication utilities - JWT, password hashing, and permission checks
"""
from datetime import datetime, timedelta
from typing import Optional, Dict
import bcrypt
from jose import JWTError, jwt
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config.settings import settings
from app.database.db_operations import db_ops
from app.config.database import Collections

# JWT Bearer token
security = HTTPBearer()

def hash_password(password: str) -> str:
    """Hash a password using bcrypt directly"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its bcrypt hash"""
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

def create_access_token(data: Dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Dict:
    """Decode and verify a JWT token"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError as e:
        import sys
        print(f"JWT Verification Failed: {str(e)}. Token: {token[:20]}...", file=sys.stderr)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict:
    """Get current authenticated user from JWT token"""
    token = credentials.credentials
    payload = decode_access_token(token)
    # Accept tokens that clearly identify a valid user or entity.
    # Support admin tokens ('sub'), employee tokens ('emp_id' or '_id' or 'email'),
    # agency tokens ('agency_id'), and tokens that include organization context ('organization_id').
    if payload.get("sub"):
        return payload

    if payload.get("emp_id") or payload.get("_id") or payload.get("email"):
        # If the token lacks organization context (missing or empty string),
        # try to enrich it from the employee record in DB.
        org_in_token = payload.get("organization_id") or ""  # treat empty string as missing
        if not org_in_token.strip():
            try:
                # Try emp_id lookup first, fall back to email
                emp_id_val = payload.get("emp_id") or ""
                email_val = payload.get("email") or ""
                employee = None
                if emp_id_val.strip():
                    employee = await db_ops.get_one(Collections.EMPLOYEES, {"emp_id": emp_id_val})
                if not employee and email_val.strip():
                    employee = await db_ops.get_one(Collections.EMPLOYEES, {"email": email_val})
                if employee:
                    # Try explicit organization_id field
                    found_org = (employee.get("organization_id") or "").strip()
                    # Fallback: derive from entity_id when entity_type is 'organization'
                    if not found_org and (employee.get("entity_type") or "").lower() == "organization":
                        found_org = (employee.get("entity_id") or "").strip()
                    elif not found_org and (employee.get("entity_type") or "").lower() == "branch":
                        branch = await db_ops.get_by_id(Collections.BRANCHES, employee.get("entity_id"))
                        if branch:
                            found_org = (branch.get("organization_id") or "").strip()
                    elif not found_org and (employee.get("entity_type") or "").lower() == "agency":
                        agency = await db_ops.get_by_id(Collections.AGENCIES, employee.get("entity_id"))
                        if agency:
                            found_org = (agency.get("organization_id") or "").strip()
                            
                    if found_org:
                        payload["organization_id"] = found_org
            except Exception as e:
                import sys
                print(f"Token enrichment failed: {e}", file=sys.stderr)
        return payload
    emp_id = payload.get("emp_id")


    if payload.get("agency_id"):
        return payload

    if payload.get("organization_id"):
        return payload

    # If none of the expected fields are present, reject the token
    import sys
    print(f"AUTH REJECTED: Invalid token payload format. Payload received: {payload}", file=sys.stderr)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials"
    )

def get_employee_type(emp_id: str) -> str:
    """Extract employee type from emp_id prefix"""
    if emp_id.startswith(settings.ORG_EMPLOYEE_PREFIX):
        return "organization"
    elif emp_id.startswith(settings.BRANCH_EMPLOYEE_PREFIX):
        return "branch"
    elif emp_id.startswith(settings.AGENCY_EMPLOYEE_PREFIX):
        return "agency"
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid employee ID format"
        )

def check_permission(current_user: Dict, required_type: str) -> bool:
    """Check if user has required permission based on employee type"""
    # Check if this is an admin token (has 'sub' field instead of 'emp_id')
    if current_user.get("sub"):
        # Admins have full access to everything
        return True
    
    # For employee tokens, check employee type
    emp_id = current_user.get("emp_id", "")
    if not emp_id:
        return False
    
    user_type = get_employee_type(emp_id)
    
    # Organization employees have access to everything
    if user_type == "organization":
        return True
    
    # Branch employees can access branch and agency data
    if user_type == "branch" and required_type in ["branch", "agency"]:
        return True
    
    # Agency employees can only access agency data
    if user_type == "agency" and required_type == "agency":
        return True
    
    return False

async def require_org_admin(current_user: Dict = Depends(get_current_user)) -> Dict:
    """Dependency to require organization admin access"""
    if not check_permission(current_user, "organization"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organization admins can perform this action"
        )
    return current_user

async def require_branch_admin(current_user: Dict = Depends(get_current_user)) -> Dict:
    """Dependency to require branch admin or higher access"""
    # Check if this is an admin token (has 'sub' field instead of 'emp_id')
    if current_user.get("sub"):
        # Admins have full access
        return current_user
    
    # For employee tokens, check employee type
    emp_id = current_user.get("emp_id", "")
    if not emp_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    emp_type = get_employee_type(emp_id)
    if emp_type not in ["organization", "branch"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    return current_user

def has_module_permission(current_user: Dict, module_code: str, action: str) -> bool:
    """Check whether the current_user has a specific module permission.

    Permission format: 'module.submodule.action' e.g. 'inventory.hotels.view'
    Admin tokens (with 'sub') implicitly have all permissions.
    """
    if not current_user:
        return False

    # Admin tokens
    if current_user.get("sub"):
        return True

    perms = current_user.get("permissions") or []
    if isinstance(perms, dict):
        # Some tokens may include structured permissions; flatten
        flat = []
        for k, v in perms.items():
            if isinstance(v, dict):
                for act, allowed in v.items():
                    if allowed:
                        flat.append(f"{k}.{act}")
        perms = flat

    # wildcard
    if "*" in perms:
        return True

    code = f"{module_code}.{action}"
    if code in perms:
        return True

    # also allow startswith checks for broader permissions
    return any(p.startswith(module_code) for p in perms)


# ─── Org-isolation helpers ────────────────────────────────────────────────────

def get_org_id(current_user: Dict = Depends(get_current_user)) -> str:
    """
    FastAPI dependency: extract organization_id from the JWT and return it.
    Raises HTTP 403 if the token has no organization_id (e.g. bare agency token).
    Use this on every endpoint that must be org-scoped.
    """
    org_id = current_user.get("organization_id") or current_user.get("sub")
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No organization associated with this account.",
        )
    return str(org_id)


async def get_shared_org_ids(org_id: str, inventory_type: str) -> list:
    """
    Return [org_id] + all other org IDs that have an *accepted* inventory_share
    link with this org covering the requested inventory_type.

    inventory_type values: 'hotels', 'packages', 'tickets'
    """
    from app.config.database import Collections as _C, db_config as _db

    # Find all active accepted links where this org is one of the two parties
    links_col = _db.get_collection(_C.ORG_LINKS)
    links = await links_col.find({
        "$or": [{"org_low_id": org_id}, {"org_high_id": org_id}],
        "status": "accepted",
        "is_active": True,
    }).to_list(length=100)

    linked_org_ids = []
    for link in links:
        other = link["org_high_id"] if link["org_low_id"] == org_id else link["org_low_id"]
        linked_org_ids.append(other)

    if not linked_org_ids:
        return [org_id]

    # Check which linked orgs have an accepted inventory_share for this type
    shares_col = _db.get_collection(_C.INVENTORY_SHARES)
    shared_orgs = []
    for other_id in linked_org_ids:
        share = await shares_col.find_one({
            "$or": [
                {"from_org_id": org_id, "to_org_id": other_id},
                {"from_org_id": other_id, "to_org_id": org_id},
            ],
            "status": "active",
            "is_active": True,
            "inventory_types": inventory_type,
        })
        if share:
            shared_orgs.append(other_id)

    return [org_id] + shared_orgs


# ─── Branch-level RBAC helpers ────────────────────────────────────────────────

async def has_branch_permission(current_user: Dict, permission_code: str) -> bool:
    """
    Async check using the full RBAC resolution chain:
      super admin → branch manager → override → role → deny

    Use this inside route handlers when you need a soft check (return bool).
    For a hard dependency (raise 403), use ``require_permission`` from
    app.rbac.service instead.
    """
    # Circular import guard – import here, not at module top
    from app.rbac.service import has_permission, _is_super_admin  # noqa: F401

    if _is_super_admin(current_user):
        return True

    emp_id = current_user.get("emp_id") or current_user.get("_id") or ""
    branch = current_user.get("branch_id") or current_user.get("entity_id") or ""
    org    = current_user.get("organization_id") or ""

    if not emp_id or not branch:
        return False

    return await has_permission(emp_id, branch, org, permission_code)


def get_branch_id(current_user: Dict) -> str:
    """
    Extract the branch_id from the JWT payload.
    Returns empty string if not a branch-scoped token.
    """
    return str(
        current_user.get("branch_id")
        or current_user.get("entity_id")
        or ""
    )


async def require_branch_permission(permission_code: str):
    """
    FastAPI dependency factory – raises HTTP 403 if permission not granted.

    Usage::

        @router.get("/payments")
        async def list_payments(
            _=Depends(require_branch_permission("payments.view")),
            current_user=Depends(get_current_user),
        ):
            ...
    """
    from app.rbac.service import require_permission  # noqa: F401
    return require_permission(permission_code)
