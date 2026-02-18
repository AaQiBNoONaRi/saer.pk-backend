from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer
from app.models.admin import AdminCreate, AdminResponse, AdminLogin, AdminLoginResponse
from app.utils.auth import hash_password, verify_password, create_access_token, get_current_user
from app.database.db_operations import db_ops
from app.config.database import Collections
from datetime import datetime
from bson import ObjectId

router = APIRouter(prefix="/admin", tags=["Admin"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/admin/login")

@router.post("/login", response_model=AdminLoginResponse)
async def admin_login(credentials: AdminLogin):
    """
    Authenticate admin user and return JWT token
    Supports login from both admins and organizations collections
    """
    user = None
    user_type = None
    
    # First, try to find in admins collection by username
    admin = await db_ops.get_one(Collections.ADMINS, {"username": credentials.username})
    if admin:
        user = admin
        user_type = "admin"
    
    # If not found in admins, try organizations collection
    # Check by email or username
    if not user:
        org = await db_ops.get_one(Collections.ORGANIZATIONS, {
            "$or": [
                {"email": credentials.username},
                {"username": credentials.username}
            ]
        })
        if org and org.get("portal_access_enabled", False):
            user = org
            user_type = "organization"
    
    # If user not found in either collection
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
    
    # Verify password
    if not verify_password(credentials.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
    
    # Check if user is active
    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated"
        )
    
    # Create access token
    token_data = {
        "sub": str(user["_id"]),
        "username": user.get("username") or user.get("email"),
        "role": user.get("role", "organization" if user_type == "organization" else "admin"),
        "organization_id": str(user["_id"]) if user_type == "organization" else user.get("organization_id"),
        "user_type": user_type
    }
    access_token = create_access_token(data=token_data)
    
    # Prepare admin response
    admin_response = AdminResponse(
        _id=str(user["_id"]),
        username=user.get("username") or user.get("email"),
        email=user["email"],
        full_name=user.get("full_name") or user.get("name", ""),
        organization_id=str(user["_id"]) if user_type == "organization" else user.get("organization_id", ""),
        role=user.get("role", "organization" if user_type == "organization" else "admin"),
        is_active=user.get("is_active", True),
        created_at=user.get("created_at", datetime.utcnow()),
        updated_at=user.get("updated_at", datetime.utcnow())
    )
    
    return AdminLoginResponse(
        access_token=access_token,
        admin=admin_response
    )

@router.get("/me", response_model=AdminResponse)
async def get_current_admin(current_user: dict = Depends(get_current_user)):
    """
    Get current authenticated admin information
    """
    admin = await db_ops.get_by_id(Collections.ADMINS, current_user["sub"])
    
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin not found"
        )
    
    return AdminResponse(
        _id=str(admin["_id"]),
        username=admin["username"],
        email=admin["email"],
        full_name=admin["full_name"],
        organization_id=admin["organization_id"],
        role=admin.get("role", "admin"),
        is_active=admin.get("is_active", True),
        created_at=admin.get("created_at", datetime.utcnow()),
        updated_at=admin.get("updated_at", datetime.utcnow())
    )

@router.post("/create", response_model=AdminResponse, status_code=status.HTTP_201_CREATED)
async def create_admin(admin_data: AdminCreate, current_user: dict = Depends(get_current_user)):
    """
    Create a new admin user (requires super_admin role)
    """
    # Check if current user is super_admin
    if current_user.get("role") != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admins can create new admins"
        )
    
    # Check if username already exists
    existing_admin = await db_ops.get_one(Collections.ADMINS, {"username": admin_data.username})
    if existing_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )
    
    # Check if email already exists
    existing_email = await db_ops.get_one(Collections.ADMINS, {"email": admin_data.email})
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists"
        )
    
    # Hash password
    hashed_password = hash_password(admin_data.password)
    
    # Prepare admin document
    admin_doc = {
        "username": admin_data.username,
        "email": admin_data.email,
        "full_name": admin_data.full_name,
        "organization_id": admin_data.organization_id,
        "role": admin_data.role,
        "is_active": admin_data.is_active,
        "password": hashed_password,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    # Insert admin
    created_admin = await db_ops.create(Collections.ADMINS, admin_doc)
    
    return AdminResponse(
        _id=str(created_admin["_id"]),
        username=created_admin["username"],
        email=created_admin["email"],
        full_name=created_admin["full_name"],
        organization_id=created_admin["organization_id"],
        role=created_admin["role"],
        is_active=created_admin["is_active"],
        created_at=created_admin["created_at"],
        updated_at=created_admin["updated_at"]
    )
