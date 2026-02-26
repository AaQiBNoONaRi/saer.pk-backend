"""
Models for storing dynamic form submissions
"""
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from datetime import datetime

class FormSubmissionBase(BaseModel):
    form_id: str
    submitted_data: Dict[str, Any]
    source_url: Optional[str] = None

class FormSubmissionCreate(FormSubmissionBase):
    pass

class FormSubmissionResponse(FormSubmissionBase):
    id: str = Field(alias="_id")
    submitted_at: datetime
    
    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
