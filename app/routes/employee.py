"""
Employee routes
"""
from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from app.models.employee import (
    EmployeeCreate, EmployeeUpdate, EmployeeResponse,
    EmployeeLogin, EmployeeEmailLogin
)
from app.database.db_operations import db_ops
from app.config.database import Collections
from app.utils.helpers import serialize_doc, serialize_docs, generate_employee_id
from app.utils.auth import (
    get_current_user, require_org_admin, hash_password, 
    verify_password, create_access_token
)

router = APIRouter(prefix="/employees", tags=["Employees"])


@router.post("/login")
async def login(credentials: EmployeeLogin):
    """Employee login via emp_id (legacy)"""
    employee = await db_ops.get_one(Collections.EMPLOYEES, {"emp_id": credentials.emp_id})
    
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid employee ID or password"
        )
    
    if not verify_password(credentials.password, employee.get("hashed_password", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid employee ID or password"
        )
    
    if not employee.get("is_active", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Employee account is inactive"
        )
    
    # Get permissions (check group first if group_id exists)
    permissions = employee.get("permissions", ["crm"])
    if employee.get("group_id"):
        try:
            group = await db_ops.get_by_id('role_groups', employee.get('group_id'))
            if group:
                # New format: permissions is a list of permission codes
                if isinstance(group.get('permissions'), list):
                    permissions = group.get('permissions', [])
                # Legacy format: permissions is a dict of module -> actions
                elif isinstance(group.get('permissions'), dict):
                    perms = []
                    for mod, actions in group.get('permissions', {}).items():
                        try:
                            if any(actions.values()):
                                perms.append(mod)
                        except Exception:
                            continue
                    permissions = perms
        except Exception as e:
            print(f"Failed to fetch group permissions: {e}")
    
    # Include organization_id explicitly from DB (if present)
    org_id = employee.get("organization_id") if employee.get("organization_id") else None
    # Fallback: if entity_type is 'organization', derive from entity_id
    if not org_id and employee.get("entity_type", "").lower() == "organization":
        org_id = employee.get("entity_id") or None
    token_data = {
        "_id": str(employee["_id"]),
        "emp_id": employee["emp_id"],
        "full_name": employee.get("full_name") or employee.get("name", ""),
        "name": employee.get("name") or employee.get("full_name", ""),
        "entity_type": employee["entity_type"],
        "entity_id": employee["entity_id"],
        "role": employee["role"],
        "permissions": permissions,
        "user_type": "employee"
    }
    if org_id:
        token_data["organization_id"] = org_id
    access_token = create_access_token(token_data)

    
    employee_out = serialize_doc(employee)
    employee_out.pop("hashed_password", None)
    # Update employee_out with fresh permissions for the frontend
    employee_out["permissions"] = permissions
    
    return {
        "status": "success",
        "access_token": access_token,
        "token_type": "bearer",
        "employee": employee_out
    }


@router.post("/login-email")
async def login_with_email(credentials: EmployeeEmailLogin):
    """Employee login via email + password (for employee portal access)"""
    # Find employee by email
    employee = await db_ops.get_one(Collections.EMPLOYEES, {"email": credentials.email})
    
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Verify password
    if not verify_password(credentials.password, employee.get("hashed_password", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Check active status
    if not employee.get("is_active", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Employee account is inactive. Contact your administrator."
        )
    
    # Check portal access
    if not employee.get("portal_access_enabled", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Portal access is disabled for this account."
        )
    
    # Build JWT payload with full employee context
    permissions = employee.get("permissions", ["crm"])
    
    # If employee has a group_id, fetch fresh permissions from the group
    if employee.get("group_id"):
        try:
            group = await db_ops.get_by_id('role_groups', employee.get('group_id'))
            if group:
                # New format: permissions is a list of permission codes
                if isinstance(group.get('permissions'), list):
                    permissions = group.get('permissions', [])
                # Legacy format: permissions is a dict of module -> actions
                elif isinstance(group.get('permissions'), dict):
                    perms = []
                    for mod, actions in group.get('permissions', {}).items():
                        try:
                            if any(actions.values()):
                                perms.append(mod)
                        except Exception:
                            continue
                    permissions = perms
        except Exception as e:
            # If group fetch fails, use employee's stored permissions
            print(f"Failed to fetch group permissions: {e}")
    
    # Include organization_id explicitly from DB (if present)
    org_id = employee.get("organization_id") if employee.get("organization_id") else None
    # Fallback: if entity_type is 'organization', derive from entity_id
    if not org_id and employee.get("entity_type", "").lower() == "organization":
        org_id = employee.get("entity_id") or None
    token_data = {
        "_id": str(employee["_id"]),
        "emp_id": employee.get("emp_id", ""),
        "email": employee["email"],
        "full_name": employee.get("full_name") or employee.get("name", ""),
        "name": employee.get("name") or employee.get("full_name", ""),
        "entity_type": employee["entity_type"],
        "entity_id": employee["entity_id"],
        "branch_id": employee.get("branch_id", ""),
        "agency_id": employee.get("agency_id", ""),
        "role": employee["role"],
        "permissions": permissions,
        "user_type": "employee"
    }
    if org_id:
        token_data["organization_id"] = org_id
    access_token = create_access_token(token_data)

    
    employee_out = serialize_doc(employee)
    employee_out.pop("hashed_password", None)
    # Update employee_out with fresh permissions for the frontend
    employee_out["permissions"] = permissions
    
    return {
        "status": "success",
        "access_token": access_token,
        "token_type": "bearer",
        "employee": employee_out
    }


@router.get("/dashboard")
async def get_employee_dashboard(current_user: dict = Depends(get_current_user)):
    """Employee dashboard info — requires valid employee JWT"""
    # Support both emp_id and email based tokens
    emp_identifier = current_user.get("emp_id") or current_user.get("email")
    
    if not emp_identifier:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not an employee token"
        )
    
    # Fetch employee by emp_id or email
    employee = None
    if current_user.get("emp_id"):
        employee = await db_ops.get_one(Collections.EMPLOYEES, {"emp_id": current_user["emp_id"]})
    if not employee and current_user.get("email"):
        employee = await db_ops.get_one(Collections.EMPLOYEES, {"email": current_user["email"]})
    
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found"
        )
    
    employee_out = serialize_doc(employee)
    employee_out.pop("hashed_password", None)
    
    return {
        "employee": employee_out,
        "permissions": employee.get("permissions", ["crm"]),
        "entity_type": employee.get("entity_type"),
        "entity_id": employee.get("entity_id"),
    }


@router.post("/", response_model=EmployeeResponse, status_code=status.HTTP_201_CREATED)
async def create_employee(
    employee: EmployeeCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new employee"""
    # Verify entity exists
    if employee.entity_type == "organization":
        entity = await db_ops.get_by_id(Collections.ORGANIZATIONS, employee.entity_id)
    elif employee.entity_type == "branch":
        entity = await db_ops.get_by_id(Collections.BRANCHES, employee.entity_id)
    elif employee.entity_type == "agency":
        entity = await db_ops.get_by_id(Collections.AGENCIES, employee.entity_id)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid entity type"
        )
    
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{employee.entity_type.capitalize()} not found"
        )
    
    # Check if emp_id already exists
    existing = await db_ops.get_one(Collections.EMPLOYEES, {"emp_id": employee.emp_id})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Employee ID already exists"
        )
    
    # Check if email already exists
    existing_email = await db_ops.get_one(Collections.EMPLOYEES, {"email": employee.email})
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An employee with this email already exists"
        )
    
    # Validate permissions (unless group_id is provided)
    employee_dict = employee.model_dump()
    if not employee_dict.get('group_id'):
        valid_perms = {"crm", "employees"}
        invalid = [p for p in employee_dict.get('permissions', []) if p not in valid_perms]
        if invalid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid permissions: {invalid}. Valid options: {list(valid_perms)}"
            )

    # If a group_id is provided, resolve permissions from the role group
    if employee_dict.get('group_id'):
        group = await db_ops.get_by_id('role_groups', employee_dict['group_id'])
        if group:
            # New format: permissions is a list of permission codes
            if isinstance(group.get('permissions'), list):
                employee_dict['permissions'] = group.get('permissions', [])
            # Legacy format: permissions is a dict of module -> actions
            elif isinstance(group.get('permissions'), dict):
                perms = []
                for mod, actions in group.get('permissions', {}).items():
                    try:
                        if any(actions.values()):
                            perms.append(mod)
                    except Exception:
                        continue
                employee_dict['permissions'] = perms
    
    # Hash password
    password = employee_dict.pop("password")
    employee_dict["hashed_password"] = hash_password(password)
    
    created_employee = await db_ops.create(Collections.EMPLOYEES, employee_dict)
    return serialize_doc(created_employee)


@router.get("/", response_model=List[EmployeeResponse])
async def get_employees(
    entity_type: str = None,
    entity_id: str = None,
    skip: int = 0,
    limit: int = 20,
    current_user: dict = Depends(get_current_user)
):
    """Get all employees, optionally filtered by entity"""
    filter_query = {}
    if entity_type:
        filter_query["entity_type"] = entity_type
    if entity_id:
        filter_query["entity_id"] = entity_id
    
    employees = await db_ops.get_all(Collections.EMPLOYEES, filter_query, skip=skip, limit=limit)
    return serialize_docs(employees)


@router.get("/me", response_model=EmployeeResponse)
async def get_current_employee(current_user: dict = Depends(get_current_user)):
    """Get current logged-in employee"""
    employee = await db_ops.get_one(Collections.EMPLOYEES, {"emp_id": current_user["emp_id"]})
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found"
        )
    return serialize_doc(employee)


@router.get("/{emp_id}", response_model=EmployeeResponse)
async def get_employee(
    emp_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get employee by emp_id or MongoDB ObjectId"""
    from bson import ObjectId
    
    query = {"_id": ObjectId(emp_id)} if len(emp_id) == 24 and all(c in '0123456789abcdefABCDEF' for c in emp_id) else {"emp_id": emp_id}
    employee = await db_ops.get_one(Collections.EMPLOYEES, query)
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found"
        )
    return serialize_doc(employee)


@router.put("/{emp_id}", response_model=EmployeeResponse)
async def update_employee(
    emp_id: str,
    employee_update: EmployeeUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update employee"""
    from bson import ObjectId
    
    query = {"_id": ObjectId(emp_id)} if len(emp_id) == 24 and all(c in '0123456789abcdefABCDEF' for c in emp_id) else {"emp_id": emp_id}
    employee = await db_ops.get_one(Collections.EMPLOYEES, query)
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found"
        )
    
    update_data = employee_update.model_dump(exclude_unset=True)
    
    # Hash password if provided
    if "password" in update_data:
        password = update_data.pop("password")
        update_data["hashed_password"] = hash_password(password)
    
    # If group_id provided in update, resolve permissions from the group
    if "group_id" in update_data and update_data.get("group_id"):
        group = await db_ops.get_by_id('role_groups', update_data.get('group_id'))
        if group:
            # New format: permissions is a list of permission codes
            if isinstance(group.get('permissions'), list):
                update_data['permissions'] = group.get('permissions', [])
            # Legacy format: permissions is a dict of module -> actions
            elif isinstance(group.get('permissions'), dict):
                perms = []
                for mod, actions in group.get('permissions', {}).items():
                    try:
                        if any(actions.values()):
                            perms.append(mod)
                    except Exception:
                        continue
                update_data['permissions'] = perms
    # Validate permissions if provided and no group mapping
    if "permissions" in update_data and not update_data.get('group_id'):
        valid_perms = {"crm", "employees"}
        invalid = [p for p in update_data["permissions"] if p not in valid_perms]
        if invalid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid permissions: {invalid}. Valid options: {list(valid_perms)}"
            )
    
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )
    
    updated_employee = await db_ops.update(Collections.EMPLOYEES, str(employee["_id"]), update_data)
    return serialize_doc(updated_employee)


@router.delete("/{emp_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_employee(
    emp_id: str,
    current_user: dict = Depends(require_org_admin)
):
    """Delete employee (Org Admin only)"""
    from bson import ObjectId
    
    query = {"_id": ObjectId(emp_id)} if len(emp_id) == 24 and all(c in '0123456789abcdefABCDEF' for c in emp_id) else {"emp_id": emp_id}
    employee = await db_ops.get_one(Collections.EMPLOYEES, query)
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found"
        )
    
    deleted = await db_ops.delete(Collections.EMPLOYEES, str(employee["_id"]))
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found"
        )
