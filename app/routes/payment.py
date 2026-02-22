import os
import shutil
import uuid
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File, Form

from app.database.db_operations import db_ops
from app.config.database import Collections
from app.utils.auth import get_current_user
from app.utils.helpers import serialize_doc, serialize_docs
from app.models.payment import PaymentResponse

router = APIRouter(prefix="/payments", tags=["Payments"])

UPLOAD_DIR = "uploads/payments"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(
    booking_id: str = Form(...),
    booking_type: str = Form(...),
    payment_method: str = Form(...),
    amount: float = Form(...),
    payment_date: str = Form(...),
    note: Optional[str] = Form(None),
    beneficiary_account: Optional[str] = Form(None),
    agent_account: Optional[str] = Form(None),
    bank_name: Optional[str] = Form(None),
    depositor_name: Optional[str] = Form(None),
    depositor_cnic: Optional[str] = Form(None),
    slip_file: Optional[UploadFile] = File(None),
    current_user: dict = Depends(get_current_user)
):
    """Create a new payment request, optionally uploading a slip file."""
    
    # Save the file if provided
    slip_url = None
    if slip_file:
        file_ext = os.path.splitext(slip_file.filename)[1]
        unique_filename = f"{uuid.uuid4().hex}{file_ext}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(slip_file.file, buffer)
            
        slip_url = f"/{UPLOAD_DIR}/{unique_filename}"
        
    payment_dict = {
        "booking_id": booking_id,
        "booking_type": booking_type,
        "payment_method": payment_method,
        "amount": amount,
        "payment_date": payment_date,
        "note": note,
        "status": "pending",
        "slip_url": slip_url,
        "beneficiary_account": beneficiary_account,
        "agent_account": agent_account,
        "bank_name": bank_name,
        "depositor_name": depositor_name,
        "depositor_cnic": depositor_cnic,
    }
    
    # Resolve IDs from JWT
    role = current_user.get('role')
    payment_dict['agency_id'] = current_user.get('agency_id') or (current_user.get('sub') if role == 'agency' else None)
    payment_dict['branch_id'] = current_user.get('branch_id') or (current_user.get('sub') if role == 'branch' else None)
    payment_dict['organization_id'] = current_user.get('organization_id')
    payment_dict['agent_name'] = (
        current_user.get('agency_name') or
        current_user.get('branch_name') or
        current_user.get('email', 'Unknown')
    )
    payment_dict['created_by'] = current_user.get('email') or current_user.get('username')
    payment_dict['created_at'] = datetime.utcnow().isoformat()
    payment_dict['updated_at'] = payment_dict['created_at']

    # Make sure we don't save empty string fields
    payment_dict = {k: v for k, v in payment_dict.items() if v not in [None, ""]}
    
    # Check if booking exists (either ticket, umrah, or custom)
    col_name = None
    if booking_type == "ticket":
        col_name = Collections.TICKET_BOOKINGS
    elif booking_type == "umrah":
        col_name = Collections.UMRAH_BOOKINGS
    elif booking_type == "custom":
        col_name = Collections.CUSTOM_BOOKINGS
        
    if col_name:
        booking = await db_ops.get_by_id(col_name, booking_id)
        if not booking:
            raise HTTPException(status_code=404, detail="Related booking not found")
            
    # Allow manual deposits even if no booking ID exists natively.
    created_payment = await db_ops.create(Collections.PAYMENTS, payment_dict)
    
    # If booking exists, update its payment_status and payment method without confirming paid
    # Let the Organization manually confirm and mark it as 'paid'
    if col_name:
        await db_ops.update(col_name, booking_id, {
            "payment_method": payment_method,
            "payment_status": "pending"
        })
        
    return serialize_doc(created_payment)

@router.get("/", response_model=List[PaymentResponse])
async def get_payments(
    status: Optional[str] = None,
    booking_id: Optional[str] = None,
    payment_method: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: dict = Depends(get_current_user)
):
    """Get payments with optional filtering."""
    query = {}
    
    # If Agency or Branch, only see their own
    role = current_user.get('role')
    if role == 'agency':
        query['agency_id'] = current_user.get('agency_id') or current_user.get('sub')
    elif role == 'branch':
        query['branch_id'] = current_user.get('branch_id') or current_user.get('sub')
        
    if status:
        query['status'] = status
    if booking_id:
        query['booking_id'] = booking_id
    if payment_method:
        query['payment_method'] = payment_method
        
    payments = await db_ops.get_all(Collections.PAYMENTS, query, skip=skip, limit=limit)
    return serialize_docs(payments)

@router.put("/{payment_id}/status", response_model=PaymentResponse)
async def update_payment_status(
    payment_id: str,
    new_status: str = Form(...),
    note: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user)
):
    """
    Update payment status (accessible mainly by Organization to approve/reject).
    """
    print(f"DEBUG PAYMENT AUTH: {current_user}")
    
    role = current_user.get('role', '')
    emp_id = current_user.get('emp_id', '')
    entity_type = current_user.get('entity_type', '')
    user_type = current_user.get('user_type', '')
    
    # Check if user is organization or admin
    is_org = role in ['organization', 'admin', 'super_admin']
    if not is_org and emp_id.startswith('ORG-'):
        is_org = True
    if not is_org and entity_type == 'organization':
        is_org = True
    if not is_org and user_type == 'organization':
        is_org = True
        
    if not is_org:
        print(f"REJECTED: role={role}, emp_id={emp_id}, entity_type={entity_type}, user_type={user_type}")
        raise HTTPException(status_code=403, detail="Not authorized to update payment status")
        
    payment = await db_ops.get_by_id(Collections.PAYMENTS, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
        
    update_data = {
        "status": new_status,
        "updated_at": datetime.utcnow().isoformat()
    }
    if note:
        update_data["note"] = f"{payment.get('note', '')}\n[ORG UPDATE]: {note}".strip()
        
    updated_payment = await db_ops.update(Collections.PAYMENTS, payment_id, update_data)
    
    # If payment is approved, we should also update the booking
    if new_status == 'approved':
        col_name = None
        b_type = payment.get('booking_type')
        if b_type == "ticket":
            col_name = Collections.TICKET_BOOKINGS
        elif b_type == "umrah":
            col_name = Collections.UMRAH_BOOKINGS
        elif b_type == "custom":
            col_name = Collections.CUSTOM_BOOKINGS
            
        if col_name:
            await db_ops.update(col_name, payment.get('booking_id'), {
                "payment_status": "paid",
                "paid_amount": payment.get('amount')
            })
            
    return serialize_doc(updated_payment)
