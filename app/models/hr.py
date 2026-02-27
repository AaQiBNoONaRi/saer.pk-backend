"""
HR Management models and schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, Literal, List
from datetime import datetime, date, time

# ===================== Employee HR Extensions =====================
class EmployeeHRBase(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=200)
    email: str
    phone: str
    whatsapp_number: Optional[str] = None
    other_contact_number: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    cnic: Optional[str] = None
    address: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    
    # Schedule
    office_check_in_time: str = Field(default="09:00", description="Expected check-in time (HH:MM)")
    office_check_out_time: str = Field(default="18:00", description="Expected check-out time (HH:MM)")
    grace_period_minutes: int = Field(default=15, description="Grace period in minutes")
    
    # Financial
    base_salary: float = Field(default=0.0, ge=0)
    currency: str = Field(default="PKR", description="Salary currency")
    bank_name: Optional[str] = None
    bank_account_number: Optional[str] = None
    bank_account_title: Optional[str] = None
    salary_payment_day: int = Field(default=25, ge=1, le=31, description="Day of month for salary payment")
    
    # Employment
    join_date: Optional[date] = None
    is_active: bool = True


class EmployeeHRCreate(EmployeeHRBase):
    emp_id: str
    entity_type: str
    entity_id: str
    organization_id: Optional[str] = None


class EmployeeHRUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    whatsapp_number: Optional[str] = None
    other_contact_number: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    role: Optional[str] = None
    cnic: Optional[str] = None
    address: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    office_check_in_time: Optional[str] = None
    office_check_out_time: Optional[str] = None
    grace_period_minutes: Optional[int] = None
    base_salary: Optional[float] = None
    currency: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account_number: Optional[str] = None
    bank_account_title: Optional[str] = None
    salary_payment_day: Optional[int] = None
    join_date: Optional[str] = None
    is_active: Optional[bool] = None
    
    class Config:
        extra = "ignore"  # Ignore extra fields


class EmployeeHRResponse(EmployeeHRBase):
    id: str = Field(alias="_id")
    emp_id: str
    entity_type: str
    entity_id: str
    organization_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True


# ===================== Attendance =====================
class AttendanceBase(BaseModel):
    emp_id: str
    date: date
    check_in: Optional[datetime] = None
    check_out: Optional[datetime] = None
    working_hours: Optional[float] = None
    status: Literal["on_time", "grace", "late", "absent", "half_day", "present"] = "present"
    notes: Optional[str] = None


class AttendanceCreate(AttendanceBase):
    organization_id: str


class AttendanceUpdate(BaseModel):
    check_in: Optional[datetime] = None
    check_out: Optional[datetime] = None
    working_hours: Optional[float] = None
    status: Optional[Literal["on_time", "grace", "late", "absent", "half_day", "present"]] = None
    notes: Optional[str] = None


class AttendanceResponse(AttendanceBase):
    id: str = Field(alias="_id")
    organization_id: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True


# ===================== Movement Log =====================
class MovementLogBase(BaseModel):
    emp_id: str
    date: date
    start_time: datetime
    end_time: Optional[datetime] = None
    reason: str = Field(..., min_length=1, max_length=500)
    destination: Optional[str] = None
    status: Literal["active", "completed", "cancelled"] = "active"


class MovementLogCreate(MovementLogBase):
    organization_id: str


class MovementLogUpdate(BaseModel):
    end_time: Optional[datetime] = None
    reason: Optional[str] = None
    destination: Optional[str] = None
    status: Optional[Literal["active", "completed", "cancelled"]] = None


class MovementLogResponse(MovementLogBase):
    id: str = Field(alias="_id")
    organization_id: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True


# ===================== Punctuality Record =====================
class PunctualityRecordBase(BaseModel):
    emp_id: str
    date: date
    violation_type: Literal["late_arrival", "early_leave", "absence", "incomplete_hours"]
    minutes_violated: int = 0
    auto_logged: bool = True
    notes: Optional[str] = None


class PunctualityRecordCreate(PunctualityRecordBase):
    organization_id: str


class PunctualityRecordResponse(PunctualityRecordBase):
    id: str = Field(alias="_id")
    organization_id: str
    created_at: datetime
    
    class Config:
        populate_by_name = True


# ===================== Leave Request =====================
class LeaveRequestBase(BaseModel):
    emp_id: str
    request_type: Literal["early_checkout", "full_day", "partial_day"]
    request_date: date
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    reason: str = Field(..., min_length=1)
    status: Literal["pending", "approved", "rejected"] = "pending"
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    approval_notes: Optional[str] = None


class LeaveRequestCreate(LeaveRequestBase):
    organization_id: str


class LeaveRequestUpdate(BaseModel):
    status: Optional[Literal["pending", "approved", "rejected"]] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    approval_notes: Optional[str] = None


class LeaveRequestResponse(LeaveRequestBase):
    id: str = Field(alias="_id")
    organization_id: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True


# ===================== Fine =====================
class FineBase(BaseModel):
    emp_id: str
    date: date
    amount: float = Field(..., ge=0)
    reason: str = Field(..., min_length=1)
    fine_type: Literal["punctuality", "manual", "policy_violation"] = "manual"
    applied_to_salary_month: Optional[str] = None  # Format: YYYY-MM


class FineCreate(FineBase):
    organization_id: str


class FineResponse(FineBase):
    id: str = Field(alias="_id")
    organization_id: str
    created_at: datetime
    
    class Config:
        populate_by_name = True


# ===================== Salary Payment =====================
class SalaryPaymentBase(BaseModel):
    emp_id: str
    month: str = Field(..., description="Format: YYYY-MM")
    base_salary: float = Field(..., ge=0)
    commission_total: float = Field(default=0.0, ge=0)
    fine_deductions: float = Field(default=0.0, ge=0)
    other_deductions: float = Field(default=0.0, ge=0)
    bonuses: float = Field(default=0.0, ge=0)
    net_salary: float = Field(..., ge=0)
    
    # Payment tracking
    status: Literal["pending", "paid", "cancelled"] = "pending"
    expected_payment_date: Optional[date] = None
    actual_payment_date: Optional[date] = None
    days_late: int = 0
    payment_method: Optional[str] = None
    payment_reference: Optional[str] = None
    notes: Optional[str] = None


class SalaryPaymentCreate(SalaryPaymentBase):
    organization_id: str


class SalaryPaymentUpdate(BaseModel):
    status: Optional[Literal["pending", "paid", "cancelled"]] = None
    actual_payment_date: Optional[date] = None
    days_late: Optional[int] = None
    payment_method: Optional[str] = None
    payment_reference: Optional[str] = None
    notes: Optional[str] = None
    commission_total: Optional[float] = None
    fine_deductions: Optional[float] = None
    other_deductions: Optional[float] = None
    bonuses: Optional[float] = None
    net_salary: Optional[float] = None


class SalaryPaymentResponse(SalaryPaymentBase):
    id: str = Field(alias="_id")
    organization_id: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True


# ===================== Request Models =====================
class CheckInRequest(BaseModel):
    emp_id: str
    check_in_time: Optional[datetime] = None  # If None, use current time


class CheckOutRequest(BaseModel):
    emp_id: str
    check_out_time: Optional[datetime] = None  # If None, use current time
    reason: Optional[str] = None  # Required for early checkout


class StartMovementRequest(BaseModel):
    emp_id: str
    reason: str
    destination: Optional[str] = None
    start_time: Optional[datetime] = None  # If None, use current time


class EndMovementRequest(BaseModel):
    movement_id: str
    end_time: Optional[datetime] = None  # If None, use current time


class ApproveLeaveRequest(BaseModel):
    approved_by: str
    approval_notes: Optional[str] = None


class GenerateSalariesRequest(BaseModel):
    month: str = Field(..., description="Format: YYYY-MM")
    year: int = Field(..., ge=2000, le=2100)
    
class GenerateSalariesJobRequest(BaseModel):
    month: str = Field(..., description="Month number (1-12)")
    year: str = Field(..., description="Year (YYYY)")
