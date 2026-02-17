from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional

class BedTypeBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    is_room_price: bool = False
    is_active: bool = True

class BedTypeCreate(BedTypeBase):
    pass

class BedTypeUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    is_active: Optional[bool] = None
    # is_room_price is intentionally excluded to prevent updates

class BedTypeResponse(BedTypeBase):
    id: str = Field(alias="_id")
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True
        json_encoders = {datetime: lambda v: v.isoformat()}
