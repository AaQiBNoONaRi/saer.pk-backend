"""
Branch Authentication routes
"""
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr
from app.database.db_operations import db_ops
from app.config.database import Collections
from app.utils.auth import verify_password, create_access_token
from app.utils.helpers import serialize_doc

router = APIRouter(prefix="/branches", tags=["Branch Authentication"])

class BranchLogin(BaseModel):
    email: EmailStr
    password: str

@router.post("/login")
async def branch_login(credentials: BranchLogin):
    """
    Branch login endpoint
    Authenticates branch users and returns access token
    """
    try:
        # Find branch by email
        branch = await db_ops.get_one(Collections.BRANCHES, {"email": credentials.email})
        
        if not branch:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Check if branch is active
        if not branch.get("is_active", True):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Branch account is deactivated"
            )
        
        # Verify password (check both 'password' and legacy 'hashed_password' fields)
        stored_password = branch.get("password") or branch.get("hashed_password")
        if not stored_password:
             raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password" # No password set
            )

        try:
            if not verify_password(credentials.password, stored_password):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password"
                )
        except ValueError:
             # Handle "hash could not be identified" error from passlib
             print(f"Warning: Invalid password hash for branch {branch.get('email')}")
             raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password" # Treat as auth failure
            )
        
        # Create access token with branch-specific data
        token_data = {
            "sub": str(branch["_id"]),
            "email": branch["email"],
            "full_name": branch.get("full_name") or branch.get("name", ""),
            "name": branch.get("name") or branch.get("full_name", ""),
            "role": "branch",
            "branch_id": str(branch["_id"]),
            "organization_id": branch.get("organization_id"),
            "branch_name": branch.get("name")
        }
        access_token = create_access_token(data=token_data)
        
        # Prepare branch response (exclude password)
        branch_data = serialize_doc(branch)
        branch_data.pop("password", None)
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "branch": branch_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Branch login error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )
