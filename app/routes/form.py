"""
Form routes - CRUD operations
"""
from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from app.models.form import FormCreate, FormUpdate, FormResponse
from app.database.db_operations import db_ops
from app.config.database import Collections
from app.utils.helpers import serialize_doc, serialize_docs
from app.utils.auth import get_current_user

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
