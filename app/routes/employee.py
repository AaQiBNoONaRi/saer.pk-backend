"""
Employee routes
"""
from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from app.models.employee import EmployeeCreate, EmployeeUpdate, EmployeeResponse, EmployeeLogin
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
    """Employee login"""
    # Find employee by emp_id
    employee = await db_ops.get_one(Collections.EMPLOYEES, {"emp_id": credentials.emp_id})
    
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid employee ID or password"
        )
    
    # Verify password
    if not verify_password(credentials.password, employee.get("hashed_password", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid employee ID or password"
        )
    
    # Check if employee is active
    if not employee.get("is_active", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Employee account is inactive"
        )
    
    # Create access token
    token_data = {
        "emp_id": employee["emp_id"],
        "entity_type": employee["entity_type"],
        "entity_id": employee["entity_id"],
        "role": employee["role"]
    }
    access_token = create_access_token(token_data)
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "employee": serialize_doc(employee)
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
    
    # Hash password
    employee_dict = employee.model_dump()
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
    """Get employee by emp_id"""
    employee = await db_ops.get_one(Collections.EMPLOYEES, {"emp_id": emp_id})
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
    # Find employee
    employee = await db_ops.get_one(Collections.EMPLOYEES, {"emp_id": emp_id})
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
    
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )
    
    # Update using _id
    updated_employee = await db_ops.update(Collections.EMPLOYEES, str(employee["_id"]), update_data)
    return serialize_doc(updated_employee)

@router.delete("/{emp_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_employee(
    emp_id: str,
    current_user: dict = Depends(require_org_admin)
):
    """Delete employee (Org Admin only)"""
    employee = await db_ops.get_one(Collections.EMPLOYEES, {"emp_id": emp_id})
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
