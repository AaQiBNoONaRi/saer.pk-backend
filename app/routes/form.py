"""
Form routes - CRUD operations
"""
from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from app.models.form import FormCreate, FormUpdate, FormResponse
from app.models.form_submission import FormSubmissionCreate, FormSubmissionResponse
from app.database.db_operations import db_ops
from app.config.database import Collections
from app.utils.helpers import serialize_doc, serialize_docs
from app.utils.auth import get_current_user
from datetime import datetime

router = APIRouter(prefix="/forms", tags=["Forms"])

@router.post("/", response_model=FormResponse, status_code=status.HTTP_201_CREATED)
async def create_form(
    form: FormCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new form"""
    form_dict = form.model_dump()
    form_dict['submissions'] = 0  # Initialize submission count
    
    created_form = await db_ops.create(Collections.FORMS, form_dict)
    return serialize_doc(created_form)

@router.get("/", response_model=List[FormResponse])
async def get_forms(
    skip: int = 0,
    limit: int = 20,
    current_user: dict = Depends(get_current_user)
):
    """Get all forms"""
    forms = await db_ops.get_all(Collections.FORMS, skip=skip, limit=limit)
    return serialize_docs(forms)

@router.get("/{form_id}", response_model=FormResponse)
async def get_form(
    form_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get form by ID"""
    form = await db_ops.get_by_id(Collections.FORMS, form_id)
    if not form:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Form not found"
        )
    return serialize_doc(form)

@router.put("/{form_id}", response_model=FormResponse)
async def update_form(
    form_id: str,
    form_update: FormUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update form"""
    update_data = form_update.model_dump(exclude_unset=True)
    
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )
    
    updated_form = await db_ops.update(Collections.FORMS, form_id, update_data)
    if not updated_form:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Form not found"
        )
    
    return serialize_doc(updated_form)

@router.delete("/{form_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_form(
    form_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete form"""
    deleted = await db_ops.delete(Collections.FORMS, form_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Form not found"
        )

# ─── Public Endpoints (No Auth Required) ──────────────────────────────────────

@router.get("/public/getByAutoUrl", response_model=FormResponse)
async def get_form_by_url(autoUrl: str):
    """Get active form by its autoUrl for standalone public pages"""
    form = await db_ops.get_one(Collections.FORMS, {"autoUrl": autoUrl, "status": "active"})
    if not form:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Form not found or is inactive"
        )
    return serialize_doc(form)

@router.get("/public/getByBlog/{blog_id}", response_model=List[FormResponse])
async def get_forms_by_blog(blog_id: str):
    """Get active forms linked to a specific blog post"""
    forms = await db_ops.get_all(Collections.FORMS, {"linked_blog_id": blog_id, "status": "active", "linkBlog": True})
    return serialize_docs(forms)

@router.post("/public/{form_id}/submit", response_model=FormSubmissionResponse, status_code=status.HTTP_201_CREATED)
async def submit_form(form_id: str, submission: FormSubmissionCreate):
    """Submit a form response"""
    # Verify form exists and is active
    form = await db_ops.get_by_id(Collections.FORMS, form_id)
    if not form or form.get("status") != "active":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Form not found or is inactive"
        )

    # Save submission
    sub_dict = submission.model_dump()
    sub_dict["submitted_at"] = datetime.utcnow()
    
    # Ensure form_id is correctly mapped from path if needed, though Pydantic should have it
    sub_dict["form_id"] = form_id

    created_sub = await db_ops.create(Collections.FORM_SUBMISSIONS, sub_dict)
    
    # Increment submission count on the form document
    current_count = form.get("submissions", 0)
    await db_ops.update(Collections.FORMS, form_id, {"submissions": current_count + 1})
    
    return serialize_doc(created_sub)

# ─── Admin Submissions View ───────────────────────────────────────────────────

@router.get("/{form_id}/submissions", response_model=List[FormSubmissionResponse])
async def get_form_submissions(
    form_id: str,
    skip: int = 0,
    limit: int = 50,
    current_user: dict = Depends(get_current_user)
):
    """Get submissions for a specific form (Admin only)"""
    subs = await db_ops.get_all(Collections.FORM_SUBMISSIONS, {"form_id": form_id}, skip=skip, limit=limit)
    # Sort newest first
    subs.sort(key=lambda x: x.get("submitted_at", ""), reverse=True)
    return serialize_docs(subs)
