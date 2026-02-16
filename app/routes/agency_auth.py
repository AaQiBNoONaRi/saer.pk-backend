"""
Agency Authentication routes
"""
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr
from app.database.db_operations import db_ops
from app.config.database import Collections
from app.utils.auth import verify_password, create_access_token
from app.utils.helpers import serialize_doc

router = APIRouter(prefix="/agencies", tags=["Agency Authentication"])

class AgencyLogin(BaseModel):
    email: EmailStr
    password: str

@router.post("/login")
async def agency_login(credentials: AgencyLogin):
    """
    Agency login endpoint
    Authenticates agency users and returns access token
    """
    try:
        # Find agency by email
        agency = await db_ops.get_one(Collections.AGENCIES, {"email": credentials.email})
        
        if not agency:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Check if agency is active
        if not agency.get("is_active", True):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Agency account is deactivated"
            )
        
        # Verify password (check both 'password' and legacy 'hashed_password' fields)
        stored_password = agency.get("password") or agency.get("hashed_password")
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
             print(f"Warning: Invalid password hash for agency {agency.get('email')}")
             raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password" # Treat as auth failure
            )
        
        # Create access token with agency-specific data
        token_data = {
            "sub": str(agency["_id"]),
            "email": agency["email"],
            "role": "agency",
            "agency_id": str(agency["_id"]),
            "branch_id": agency.get("branch_id"),
            "organization_id": agency.get("organization_id"),
            "agency_name": agency.get("name")
        }
        access_token = create_access_token(data=token_data)
        
        # Prepare agency response (exclude password)
        agency_data = serialize_doc(agency)
        agency_data.pop("password", None)
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "agency": agency_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Agency login error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )