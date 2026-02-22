"""
Payment and Voucher Models for Kuickapay Integration
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class Wallet(BaseModel):
    """Wallet model for storing user balance"""
    id: Optional[str] = Field(None, alias="_id")
    user_id: str
    currency: str = "PKR"
    balance: float = 0.0
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "user_id": "699a2404c592bdf4d29edd0f",
                "currency": "PKR",
                "balance": 15000.00,
                "is_active": True
            }
        }


class Transaction(BaseModel):
    """Transaction model for payments, top-ups, and refunds"""
    id: Optional[str] = Field(None, alias="_id")
    wallet_id: Optional[str] = None
    amount: float
    currency: str = "PKR"
    type: str  # topup|payment|refund
    status: str = "pending"  # pending|completed|failed|refunded
    provider: Optional[str] = None
    provider_reference: Optional[str] = None
    metadata: Optional[dict] = None
    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "wallet_id": "60a1b2c3d4e5f6g7h8i9j0k1",
                "amount": 5000.00,
                "currency": "PKR",
                "type": "topup",
                "status": "pending",
                "provider": "local_gateway"
            }
        }


class Voucher(BaseModel):
    """Payment voucher model for Kuickapay integration"""
    id: Optional[str] = Field(None, alias="_id")
    consumer_number: str  # 18-digit Kuickapay voucher number (09571XXXXXXXXXXXXX)
    user_name: str  # Consumer detail / title
    user_email: str
    contact_number: str
    reason: str
    amount: float
    expiry_date: str  # Due date (YYYYMMDD format for Kuickapay)
    currency: str = "PKR"
    payment_method: str = "wallet"
    status: str = "pending"  # pending|paid|cancelled|failed|expired|blocked
    bill_status: str = "U"  # U=Unpaid, P=Paid, B=Blocked, T=Top-up (Kuickapay format)
    billing_month: Optional[str] = None  # YYMM format
    amount_within_due_date: Optional[float] = None
    amount_after_due_date: Optional[float] = None
    date_paid: Optional[str] = None  # YYYYMMDD format
    amount_paid: Optional[float] = None
    tran_auth_id: Optional[str] = None  # 6-digit transaction authorization ID
    transaction_id: Optional[str] = None
    wallet_id: Optional[str] = None
    created_by: Optional[str] = None
    organization_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    paid_at: Optional[datetime] = None

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "consumer_number": "095719876543210123",
                "user_name": "Abdul Rafay",
                "user_email": "abdulrafay@gmail.com",
                "contact_number": "+923132858290",
                "reason": "Umrah package payment",
                "amount": 10000.00,
                "expiry_date": "20260315",
                "currency": "PKR",
                "payment_method": "wallet",
                "status": "pending",
                "bill_status": "U"
            }
        }


class ProviderConfig(BaseModel):
    """Payment provider configuration"""
    id: Optional[str] = Field(None, alias="_id")
    name: str
    api_key: str
    webhook_secret: str
    active: bool = True
    settings: Optional[dict] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
