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
