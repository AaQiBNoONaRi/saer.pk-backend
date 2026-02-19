"""
Blog model and schemas for block-based content editor
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class BlockType(str, Enum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    IMAGE = "image"
    VIDEO = "video"
    BUTTON = "button"
    QUOTE = "quote"

class ContentBlock(BaseModel):
    id: str
    type: BlockType
    order: int
    content: Dict[str, Any] = Field(default_factory=dict)  # Flexible content based on type
    styles: Optional[Dict[str, str]] = Field(default_factory=dict)  # CSS properties

class SEOMeta(BaseModel):
    description: Optional[str] = None
    keywords: Optional[List[str]] = Field(default_factory=list)
    ogImage: Optional[str] = None

class BlogStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"

class BlogBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    slug: Optional[str] = None
    blocks: List[ContentBlock] = Field(default_factory=list)
    seoMeta: Optional[SEOMeta] = Field(default_factory=SEOMeta)
    status: BlogStatus = BlogStatus.DRAFT
    views: int = 0
    autoPage: bool = False

class BlogCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    blocks: Optional[List[ContentBlock]] = Field(default_factory=list)
    seoMeta: Optional[SEOMeta] = None

class BlogUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    slug: Optional[str] = None
    blocks: Optional[List[ContentBlock]] = None
    seoMeta: Optional[SEOMeta] = None
    status: Optional[BlogStatus] = None
    views: Optional[int] = None
    autoPage: Optional[bool] = None

class BlogResponse(BaseModel):
    id: str = Field(alias="_id")
    title: str
    slug: Optional[str] = None
    previewUuid: Optional[str] = None
    status: BlogStatus
    blocks: List[ContentBlock]
    seoMeta: Optional[SEOMeta] = None
    views: int = 0
    autoPage: bool = False
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime] = None
    
    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
