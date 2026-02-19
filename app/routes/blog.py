"""
Blog routes - CRUD operations and preview support
"""
from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
import uuid
from app.models.blog import BlogCreate, BlogUpdate, BlogResponse
from app.database.db_operations import db_ops
from app.config.database import Collections
from app.utils.helpers import serialize_doc, serialize_docs
from app.utils.auth import get_current_user

router = APIRouter(prefix="/blogs", tags=["Blogs"])

def generate_slug(title: str) -> str:
    """Generate URL-friendly slug from title"""
    slug = title.lower().strip()
    slug = slug.replace(" ", "-")
    # Remove special characters
    slug = "".join(c for c in slug if c.isalnum() or c == "-")
    return slug

@router.post("/", response_model=BlogResponse, status_code=status.HTTP_201_CREATED)
async def create_blog(
    blog: BlogCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new blog"""
    blog_dict = blog.model_dump()
    
    # Generate preview UUID for draft mode
    blog_dict['previewUuid'] = str(uuid.uuid4())
    blog_dict['status'] = 'draft'  # Always start as draft
    blog_dict['slug'] = None  # No slug until published
    blog_dict['published_at'] = None
    
    created_blog = await db_ops.create(Collections.BLOGS, blog_dict)
    return serialize_doc(created_blog)

@router.get("/", response_model=List[BlogResponse])
async def get_blogs(
    skip: int = 0,
    limit: int = 20,
    status: str = None,  # Filter by status
    current_user: dict = Depends(get_current_user)
):
    """Get all blogs with optional status filter"""
    filter_query = {}
    if status:
        filter_query['status'] = status
    
    blogs = await db_ops.get_all(Collections.BLOGS, filter_query, skip, limit)
    return serialize_docs(blogs)

@router.get("/preview/{preview_uuid}", response_model=BlogResponse)
async def get_blog_preview(
    preview_uuid: str,
    current_user: dict = Depends(get_current_user)
):
    """Get blog by preview UUID (for draft preview)"""
    blog = await db_ops.get_one(Collections.BLOGS, {"previewUuid": preview_uuid})
    if not blog:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blog not found"
        )
    return serialize_doc(blog)

@router.get("/{blog_id}", response_model=BlogResponse)
async def get_blog(
    blog_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get blog by ID"""
    blog = await db_ops.get_by_id(Collections.BLOGS, blog_id)
    if not blog:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blog not found"
        )
    return serialize_doc(blog)

@router.put("/{blog_id}", response_model=BlogResponse)
async def update_blog(
    blog_id: str,
    blog_update: BlogUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update blog"""
    update_data = blog_update.model_dump(exclude_unset=True)
    
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )
    
    updated_blog = await db_ops.update(Collections.BLOGS, blog_id, update_data)
    if not updated_blog:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blog not found"
        )
    
    return serialize_doc(updated_blog)

@router.patch("/{blog_id}/publish", response_model=BlogResponse)
async def publish_blog(
    blog_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Publish blog - generates slug and sets status"""
    blog = await db_ops.get_by_id(Collections.BLOGS, blog_id)
    if not blog:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blog not found"
        )
    
    # Generate slug from title
    base_slug = generate_slug(blog['title'])
    slug = base_slug
    counter = 1
    
    # Ensure slug is unique
    while await db_ops.get_one(Collections.BLOGS, {"slug": slug}):
        slug = f"{base_slug}-{counter}"
        counter += 1
    
    from datetime import datetime
    update_data = {
        'slug': slug,
        'status': 'published',
        'published_at': datetime.utcnow()
    }
    
    updated_blog = await db_ops.update(Collections.BLOGS, blog_id, update_data)
    return serialize_doc(updated_blog)

@router.delete("/{blog_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_blog(
    blog_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete blog"""
    deleted = await db_ops.delete(Collections.BLOGS, blog_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blog not found"
        )
