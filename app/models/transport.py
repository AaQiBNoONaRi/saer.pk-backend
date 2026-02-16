"""
Transport model and schemas
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime

class RoutePrice(BaseModel):
    route_name: str = Field(..., description="e.g. Jeddah to Makkah")
    price: float = Field(..., ge=0)

class TransportBase(BaseModel):
    vehicle_type: str = Field(..., description="Bus, Coaster, Car, GMC, etc.")
    capacity: int = Field(..., ge=1, description="Number of passengers")
    price_per_day: float = Field(..., ge=0)
    route_prices: List[RoutePrice] = Field(default=[])
    is_active: bool = True

class TransportCreate(TransportBase):
    pass

class TransportUpdate(BaseModel):
    vehicle_type: Optional[str] = None
    capacity: Optional[int] = Field(None, ge=1)
    price_per_day: Optional[float] = Field(None, ge=0)
    route_prices: Optional[List[RoutePrice]] = None
    is_active: Optional[bool] = None

class TransportResponse(TransportBase):
    id: str = Field(alias="_id")
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
