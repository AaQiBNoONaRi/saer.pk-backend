"""
employee tasks tracking
"""
from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field
from app.database.db_operations import db_ops
from app.config.database import Collections
from app.utils.helpers import serialize_doc, serialize_docs
from app.utils.auth import get_current_user

router = APIRouter(prefix="/tasks", tags=["Task Management"])

# ─── Models ───────────────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    task_type: str = Field(..., description="'customer' or 'internal'")
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    contact_number: Optional[str] = None
    whatsapp_number: Optional[str] = None
    address: Optional[str] = None
    follow_up_date: str
    follow_up_time: str
    description: str

class TaskUpdate(BaseModel):
    task_type: Optional[str] = None
    customer_name: Optional[str] = None
    contact_number: Optional[str] = None
    whatsapp_number: Optional[str] = None
    address: Optional[str] = None
    follow_up_date: Optional[str] = None
    follow_up_time: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None

class RemarkCreate(BaseModel):
    text: str = Field(..., min_length=1, description="Remark content")


# ─── API Routes ───────────────────────────────────────────────────────────────

@router.post("/", summary="Create a new task", status_code=status.HTTP_201_CREATED)
async def create_task(task: TaskCreate, current_user: dict = Depends(get_current_user)):
    """Create a new task (Customer or Internal)"""
    if task.task_type not in ["customer", "internal"]:
        raise HTTPException(status_code=400, detail="Invalid task type")

    # If customer task, validate required fields loosely
    if task.task_type == "customer":
        if not task.customer_name and not task.customer_id:
            raise HTTPException(status_code=400, detail="Customer selection required for Customer Tasks")

    task_dict = task.model_dump()
    task_dict["status"] = "pending"
    task_dict["created_at"] = datetime.utcnow().isoformat()
    task_dict["updated_at"] = datetime.utcnow().isoformat()
    task_dict["remarks"] = []   # chat-style remarks list
    
    # Save user info
    task_dict["created_by"] = str(current_user.get("_id") or current_user.get("sub") or current_user.get("emp_id") or "")
    if current_user.get("user_type") == "employee" and current_user.get("_id"):
         task_dict["employee_id"] = current_user.get("_id")

    # Scope
    entity_type = current_user.get("entity_type")
    entity_id = current_user.get("entity_id")
    if entity_type == "organization":
        task_dict["organization_id"] = entity_id
    elif entity_type == "branch":
        task_dict["branch_id"] = entity_id
    elif entity_type == "agency":
        task_dict["agency_id"] = entity_id

    # Fallbacks from user object if multi-level
    if not task_dict.get("organization_id") and current_user.get("organization_id"):
        task_dict["organization_id"] = str(current_user["organization_id"])
    if not task_dict.get("branch_id") and current_user.get("branch_id"):
        task_dict["branch_id"] = str(current_user["branch_id"])
    if not task_dict.get("agency_id") and current_user.get("agency_id"):
        task_dict["agency_id"] = str(current_user["agency_id"])

    created = await db_ops.create(Collections.TASKS, task_dict)
    return serialize_doc(created)


@router.get("/", summary="Get tasks")
async def get_tasks(
    organization_id: Optional[str] = Query(None),
    branch_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    task_type: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500)
):
    """Retrieve tasks with filtering"""
    filters = {}
    if organization_id:
        filters["organization_id"] = organization_id
    if branch_id:
        filters["branch_id"] = branch_id
    if status:
        filters["status"] = status
    if task_type:
        filters["task_type"] = task_type

    tasks = await db_ops.get_all(Collections.TASKS, filters, skip=skip, limit=limit)
    return serialize_docs(tasks)


@router.put("/{task_id}", summary="Update a task")
async def update_task(task_id: str, updates: TaskUpdate, current_user: dict = Depends(get_current_user)):
    """Update a task's details or status"""
    existing = await db_ops.get_by_id(Collections.TASKS, task_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Task not found")

    update_data = {k: v for k, v in updates.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.utcnow().isoformat()

    updated = await db_ops.update(Collections.TASKS, task_id, update_data)
    return serialize_doc(updated)


@router.post("/{task_id}/remarks", summary="Add a remark to a task")
async def add_task_remark(task_id: str, remark: RemarkCreate, current_user: dict = Depends(get_current_user)):
    """Append a chat-style remark to a task"""
    existing = await db_ops.get_by_id(Collections.TASKS, task_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Task not found")

    # Build author display name
    author_name = await _get_author_name(current_user)
    author_type = current_user.get("user_type", "unknown")

    remark_entry = {
        "text": remark.text.strip(),
        "author_name": author_name,
        "author_type": author_type,
        "entity_type": author_type,   # use user_type (employee/organization) not token's entity_type
        "entity_name": _get_entity_name(current_user),
        "created_at": datetime.utcnow().isoformat(),
    }

    # Push to remarks array
    existing_remarks = existing.get("remarks", [])
    if not isinstance(existing_remarks, list):
        existing_remarks = []
    existing_remarks.append(remark_entry)

    await db_ops.update(Collections.TASKS, task_id, {
        "remarks": existing_remarks,
        "updated_at": datetime.utcnow().isoformat()
    })

    return {"success": True, "remark": remark_entry}


@router.delete("/{task_id}", summary="Delete a task")
async def delete_task(task_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a task permanently"""
    existing = await db_ops.get_by_id(Collections.TASKS, task_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Task not found")
    
    await db_ops.delete(Collections.TASKS, task_id)
    return {"message": "Task deleted successfully"}


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _get_author_name(current_user: dict) -> str:
    """Get a human-readable name for the logged-in user dynamically from the database."""
    from app.database.db_operations import db_ops
    from app.config.database import Collections
    try:
        if current_user.get("user_type") == "employee":
            emp_id = current_user.get("_id") or current_user.get("emp_id")
            if emp_id:
                emp = await db_ops.get_by_id(Collections.EMPLOYEES, emp_id)
                if not emp and current_user.get("emp_id"):
                    emp = await db_ops.get_one(Collections.EMPLOYEES, {"emp_id": current_user["emp_id"]})
                if emp:
                    return emp.get("full_name") or emp.get("name") or emp.get("email") or emp.get("emp_id") or "Employee"
        
        if current_user.get("user_type") in ["admin", "organization"]:
            coll = Collections.ADMINS if current_user.get("user_type") == "admin" else Collections.ORGANIZATIONS
            sub_id = current_user.get("sub") or current_user.get("_id")
            if sub_id:
                user = await db_ops.get_by_id(coll, sub_id)
                if user:
                    return user.get("full_name") or user.get("name") or user.get("username") or user.get("email") or current_user.get("user_type", "").title()

        role = current_user.get("role", "")
        if role in ["branch", "agency"]:
            coll = Collections.BRANCHES if role == "branch" else Collections.AGENCIES
            sub_id = current_user.get("sub") or current_user.get("_id")
            if sub_id:
                user = await db_ops.get_by_id(coll, sub_id)
                if user:
                    return user.get("full_name") or user.get("name") or user.get("email") or role.title()
    except Exception as e:
        print(f"Error fetching live author name: {e}")

    # Fallback to token payload if DB lookup fails
    return (
        current_user.get("full_name")
        or current_user.get("name")
        or current_user.get("username")
        or current_user.get("email")
        or "User"
    )


def _get_entity_name(current_user: dict) -> str:
    """Get a descriptive label - role for employees, org/branch/agency name for portal admins."""
    user_type = current_user.get("user_type", "")
    if user_type == "employee":
        return (
            current_user.get("role")
            or current_user.get("designation")
            or current_user.get("entity_type", "").title()
            or "Employee"
        )
    entity_type = current_user.get("entity_type", "")
    if entity_type == "organization":
        return current_user.get("org_name") or current_user.get("organization_name") or current_user.get("username") or "Organization"
    if entity_type == "branch":
        return current_user.get("branch_name") or current_user.get("branch_city") or "Branch"
    if entity_type == "agency":
        return current_user.get("agency_name") or "Agency"
    return current_user.get("role") or current_user.get("user_type") or ""


