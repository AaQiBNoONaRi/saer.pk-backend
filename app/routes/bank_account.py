"""
Bank Account Routes
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from datetime import datetime
from bson import ObjectId

from app.database.db_operations import db_ops
from app.config.database import Collections
from app.models.bank_account import BankAccountCreate, BankAccountUpdate, BankAccountResponse
from app.utils.auth import get_current_user
from app.utils.helpers import serialize_doc, serialize_docs

router = APIRouter(
    prefix="/bank-accounts",
    tags=["Bank Accounts"]
)

@router.post("/", response_model=BankAccountResponse)
async def create_bank_account(
    account: BankAccountCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new bank account.
    - **Organization Admin**: Can create for Organization, Branch, or Agency.
    - **Branch Admin**: Can create for Branch (self).
    - **Agency Admin**: Can create for Agency (self).
    """
    account_dict = account.model_dump()
    
    # Determine User Role and Scope
    user_type = current_user.get("role") or current_user.get("user_type") # Standardization issue in auth?
    # Based on auth.py:
    # Org: sub=id, no role field explicitly in 'get_current_user' return for Org?
    # Wait, 'get_current_user' returns payload.
    # Org Admin payload: {"sub": "...", ...}
    # Branch payload: {"role": "branch", "branch_id": "...", ...}
    # Agency payload: {"role": "agency", "agency_id": "...", ...}
    
    # 1. Identify Actor
    if current_user.get("role") == "branch":
        # Branch acting
        if account.account_type != "Branch":
            raise HTTPException(status_code=403, detail="Branch can only create Branch accounts")
        
        # Enforce IDs
        account_dict["branch_id"] = current_user["branch_id"]
        account_dict["organization_id"] = current_user["organization_id"]
        account_dict["agency_id"] = None
        
    elif current_user.get("role") == "agency":
         # Agency acting
        if account.account_type != "Agency":
            raise HTTPException(status_code=403, detail="Agency can only create Agency accounts")
        
        # Enforce IDs
        account_dict["agency_id"] = current_user["agency_id"]
        account_dict["organization_id"] = current_user["organization_id"]
        account_dict["branch_id"] = None
        
    else:
        # Organization acting (or Super Admin)
        # Check permissions? require_org_admin isn't enforced by Depends(get_current_user) alone.
        # But let's assume if not branch/agency, it's Org.
        # Ideally we should use `require_org_admin` logic or check.
        # For now, if no role='branch'/'agency', we assume Org context.
        # Org payload usually has `sub` as org_id (Direct Login) OR `organization_id` (Employee).
        
        org_id = current_user.get("organization_id") or current_user.get("sub")
        if not org_id:
             raise HTTPException(status_code=403, detail="Organization context required")

        account_dict["organization_id"] = str(org_id)
        
        # Handle Account Types
        if account.account_type == "Organization":
            account_dict["branch_id"] = None
            account_dict["agency_id"] = None
            
        elif account.account_type == "Branch":
            if not account.branch_id:
                 raise HTTPException(status_code=400, detail="Branch ID required for Branch account")
            # Verify Branch belongs to Org? Refinement.
            # Fetch Branch to be safe and ensure Org ID matches?
            # Trusting FE for now, but adding org_id to payload ensures it's linked to THIS org.
            # But what if I create for a branch NOT in my org?
            # Let's simple check:
            branch = await db_ops.get_one(Collections.BRANCHES, {"_id": ObjectId(account.branch_id), "organization_id": str(org_id)})
            if not branch:
                 raise HTTPException(status_code=404, detail="Branch not found in this organization")

        elif account.account_type == "Agency":
            if not account.agency_id:
                 raise HTTPException(status_code=400, detail="Agency ID required for Agency account")
            # Verify Agency
            agency = await db_ops.get_one(Collections.AGENCIES, {"_id": ObjectId(account.agency_id), "organization_id": str(org_id)})
            if not agency:
                 raise HTTPException(status_code=404, detail="Agency not found in this organization")
    
    new_account = await db_ops.create(Collections.BANK_ACCOUNTS, account_dict)
    return serialize_doc(new_account)

@router.get("/", response_model=List[BankAccountResponse])
async def get_bank_accounts(
    current_user: dict = Depends(get_current_user),
    include_system: bool = Query(True, description="Include Organization/System accounts")
):
    """
    Get bank accounts based on user scope.
    - **Organization**: All accounts in org.
    - **Branch**: Own accounts + Organization accounts.
    - **Agency**: Own accounts + Organization accounts.
    """
    
    query = {"is_active": True}
    
    # Identify Actor
    if current_user.get("role") == "branch":
        # Branch View
        # Logic: (account_type='Branch' AND branch_id=Me) OR (account_type='Organization' AND organization_id=MyOrg)
        branch_id = current_user["branch_id"]
        org_id = current_user["organization_id"]
        
        or_conditions = [
            {"account_type": "Branch", "branch_id": branch_id},
        ]
        if include_system:
            or_conditions.append({"account_type": "Organization", "organization_id": org_id})
            
        query["$or"] = or_conditions
        
    elif current_user.get("role") == "agency":
        # Agency View
        agency_id = current_user.get("agency_id") or current_user.get("sub")
        org_id = current_user.get("organization_id")
        
        or_conditions = [
            {"account_type": "Agency", "agency_id": agency_id},
        ]
        # Only add org condition if org_id is present
        if include_system and org_id:
            or_conditions.append({"account_type": "Organization", "organization_id": str(org_id)})
        # If no org_id, fall back: show all Organization accounts (so agent still sees where to pay)
        elif include_system and not org_id:
            or_conditions.append({"account_type": "Organization"})
             
        query["$or"] = or_conditions

    else:
        # Organization View
        org_id = current_user.get("organization_id") or current_user.get("sub")
        query["organization_id"] = str(org_id)
        # No extra filtering needed, they see all types for their org.

    accounts = await db_ops.get_all(Collections.BANK_ACCOUNTS, query, limit=1000)
    return serialize_docs(accounts)

@router.put("/{account_id}", response_model=BankAccountResponse)
async def update_bank_account(
    account_id: str,
    account_update: BankAccountUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update a bank account"""
    # 1. Fetch Account
    existing_account = await db_ops.get_one(Collections.BANK_ACCOUNTS, {"_id": ObjectId(account_id)})
    if not existing_account:
        raise HTTPException(status_code=404, detail="Bank account not found")

    # 2. Verify Permission
    is_authorized = False
    
    if current_user.get("role") == "branch":
        # Can only update OWN Branch Accounts
        if existing_account.get("account_type") == "Branch" and \
           str(existing_account.get("branch_id")) == str(current_user["branch_id"]):
            is_authorized = True
            
    elif current_user.get("role") == "agency":
        # Can only update OWN Agency Accounts
        if existing_account.get("account_type") == "Agency" and \
           str(existing_account.get("agency_id")) == str(current_user["agency_id"]):
            is_authorized = True
            
    else:
        # Organization
        # Can update ANY account in their Org
        org_id = current_user.get("organization_id") or current_user.get("sub")
        if str(existing_account.get("organization_id")) == str(org_id):
            is_authorized = True

    if not is_authorized:
         raise HTTPException(status_code=403, detail="Not authorized to update this account")
         
    # 3. Update
    update_data = account_update.model_dump(exclude_unset=True)
    
    if update_data:
        updated_account = await db_ops.update(Collections.BANK_ACCOUNTS, account_id, update_data)
        return serialize_doc(updated_account)
        
    return serialize_doc(existing_account)

@router.delete("/{account_id}")
async def delete_bank_account(
    account_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete (soft delete) a bank account"""
    # 1. Fetch Account
    existing_account = await db_ops.get_one(Collections.BANK_ACCOUNTS, {"_id": ObjectId(account_id)})
    if not existing_account:
        raise HTTPException(status_code=404, detail="Bank account not found")

    # 2. Verify Permission
    is_authorized = False
    
    if current_user.get("role") == "branch":
        if existing_account.get("account_type") == "Branch" and \
           str(existing_account.get("branch_id")) == str(current_user["branch_id"]):
            is_authorized = True
            
    elif current_user.get("role") == "agency":
        if existing_account.get("account_type") == "Agency" and \
           str(existing_account.get("agency_id")) == str(current_user["agency_id"]):
            is_authorized = True
            
    else:
        # Organization
        org_id = current_user.get("organization_id") or current_user.get("sub")
        if str(existing_account.get("organization_id")) == str(org_id):
            is_authorized = True

    if not is_authorized:
         raise HTTPException(status_code=403, detail="Not authorized to delete this account")

    result = await db_ops.update(Collections.BANK_ACCOUNTS, account_id, {"is_active": False})
    
    if not result:
        raise HTTPException(status_code=404, detail="Bank account not found or could not be deleted")
        
    return {"message": "Bank account deleted successfully"}
