"""
Authentication utilities - JWT, password hashing, and permission checks
"""
from datetime import datetime, timedelta
from typing import Optional, Dict
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config.settings import settings

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Bearer token
security = HTTPBearer()

def hash_password(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)

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
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict:
    """Get current authenticated user from JWT token"""
    token = credentials.credentials
    payload = decode_access_token(token)
    
    # Check for admin token (has 'sub' field)
    if payload.get("sub"):
        return payload
    
    # Check for employee token (has 'emp_id' field)
    emp_id = payload.get("emp_id")
    if emp_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
    
    return payload

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
    emp_type = get_employee_type(current_user.get("emp_id", ""))
    if emp_type not in ["organization", "branch"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    return current_user
