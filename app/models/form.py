"""
Form model and schemas for dynamic form builder
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class FieldType(str, Enum):
    TEXT = "text"
    EMAIL = "email"
    NUMBER = "number"
    SELECT = "select"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    TEXTAREA = "textarea"
    FILE = "file"

class FieldValidation(BaseModel):
    minLength: Optional[int] = None
    maxLength: Optional[int] = None
    pattern: Optional[str] = None
    fileTypes: Optional[List[str]] = None
    maxFileSize: Optional[int] = None

class FormField(BaseModel):
    id: str
    type: FieldType
    label: str
    name: str
    required: bool = False
    placeholder: Optional[str] = None
    options: Optional[List[str]] = Field(default_factory=list)  # For select, radio, checkbox
    validation: Optional[FieldValidation] = None

class ActionButton(BaseModel):
    id: str
    label: str
    action: str = "submit"  # submit, reset, custom
    type: str = "primary"  # primary, secondary, danger

class HelperNote(BaseModel):
    id: str
    text: str
    type: str = "info"  # info, warning, success, error

class SubmitButton(BaseModel):
    text: str = "Submit"
    styles: Optional[Dict[str, str]] = Field(default_factory=dict)

class FormSchema(BaseModel):
    fields: List[FormField] = Field(default_factory=list)
    submitButton: Optional[SubmitButton] = Field(default_factory=SubmitButton)
    buttons: Optional[List[ActionButton]] =Field(default_factory=list)
    notes: Optional[List[HelperNote]] = Field(default_factory=list)

class FormStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"

class FormBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    status: FormStatus = FormStatus.ACTIVE
    schema: FormSchema
    autoUrl: Optional[str] = None
    linkBlog: bool = False
    position: str = "End of Blog (Below Content)"  # Position for blog-linked forms

class FormCreate(FormBase):
    pass

class FormUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    status: Optional[FormStatus] = None
    schema: Optional[FormSchema] = None
    autoUrl: Optional[str] = None
    linkBlog: Optional[bool] = None
    position: Optional[str] = None

class FormResponse(BaseModel):
    id: str = Field(alias="_id")
    name: str
    status: FormStatus
    schema: FormSchema
    autoUrl: Optional[str] = None
    linkBlog: bool = False
    position: str = "End of Blog (Below Content)"
    submissions: int = 0
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
