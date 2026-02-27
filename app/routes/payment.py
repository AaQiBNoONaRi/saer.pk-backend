"""
Payment and Voucher API Routes for Kuickapay Integration
"""
from fastapi import APIRouter, HTTPException, Depends, Request, Header, status, UploadFile, File, Form
from typing import List, Optional
from datetime import datetime
from bson import ObjectId
import secrets
import hmac
import hashlib
import os
import shutil
import uuid
import asyncio
import inspect

from app.models.payment import Voucher, Transaction, Wallet, PaymentResponse
from app.config.database import db_config, Collections
from app.utils.auth import get_current_user
from app.database.db_operations import db_ops
from app.utils.helpers import serialize_doc, serialize_docs

router = APIRouter(prefix="/payments", tags=["payments"])


# Helper Functions
def generate_voucher_number():
    """
    Generate unique 18-digit voucher number for Kuickapay
    Format: 09571XXXXXXXXXXXXX (5-digit prefix + 13 digits)
    Prefix 09571 is assigned by Kuickapay to the institution
    """
    import time
    
    # Kuickapay assigned prefix (5 digits)
    prefix = "09571"
    
    # Generate 13 unique digits using timestamp + random
    # Use microseconds and random to ensure uniqueness
    timestamp_part = str(int(time.time() * 1000))[-9:]  # Last 9 digits of millisecond timestamp
    random_part = str(secrets.randbelow(10000)).zfill(4)  # 4 random digits
    
    # Combine to make 13 digits
    unique_suffix = (timestamp_part + random_part)[:13].zfill(13)
    
    # Return 18-digit consumer number
    voucher_number = prefix + unique_suffix
    
    return voucher_number


def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify webhook signature using HMAC"""
    expected_signature = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected_signature)


# Voucher Endpoints
@router.post("/vouchers/", response_model=dict)
async def create_voucher(
    voucher_data: dict,
    current_user: dict = Depends(get_current_user)
):
    """
    Generate a new payment voucher (Kuickapay format)
    """
    try:
        db = db_config.database
        
        # Basic validation for required fields to provide clearer errors
        if not voucher_data:
            raise HTTPException(status_code=400, detail="Missing voucher data in request body")

        # Generate 18-digit consumer number (Kuickapay format)
        consumer_number = generate_voucher_number()
        
        # Convert expiry date to Kuickapay format (YYYYMMDD)
        expiry_date_str = voucher_data.get("expiry_date", "")
        if expiry_date_str:
            # Convert from YYYY-MM-DD to YYYYMMDD
            expiry_date_formatted = expiry_date_str.replace("-", "")
        else:
            # Default to 30 days from now
            from datetime import timedelta
            expiry_dt = datetime.utcnow() + timedelta(days=30)
            expiry_date_formatted = expiry_dt.strftime("%Y%m%d")
        
        # Generate billing month (YYMM format)
        billing_month = datetime.utcnow().strftime("%y%m")
        
        # Calculate amounts (Kuickapay format: 14 chars with 2 decimal places)
        amount_raw = voucher_data.get("amount")
        if amount_raw is None or amount_raw == "":
            raise HTTPException(status_code=400, detail="Amount is required")
        try:
            amount = float(amount_raw)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid amount; must be a number")
        amount_within_due = amount
        amount_after_due = amount * 1.05  # 5% late fee example
        
        # Prepare voucher document
        voucher = {
            "consumer_number": consumer_number,
            "user_name": voucher_data.get("user_name"),
            "user_email": voucher_data.get("user_email"),
            "contact_number": voucher_data.get("contact_number"),
            "reason": voucher_data.get("reason"),
            "amount": amount,
            "expiry_date": expiry_date_formatted,
            "currency": voucher_data.get("currency", "PKR"),
            "payment_method": voucher_data.get("payment_method", "wallet"),
            "status": "pending",
            "bill_status": "U",  # U = Unpaid
            "billing_month": billing_month,
            "amount_within_due_date": amount_within_due,
            "amount_after_due_date": amount_after_due,
            "date_paid": None,
            "amount_paid": None,
            "tran_auth_id": None,
            "transaction_id": None,
            "wallet_id": voucher_data.get("wallet_id"),
            "created_by": str(current_user.get("_id")),
            "organization_id": current_user.get("organization_id"),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "paid_at": None
        }
        
        # Insert voucher (debugging types to diagnose Future issue)
        try:
            print("[payments.create_voucher] insert_one callable:", callable(db.vouchers.insert_one))
            print("[payments.create_voucher] iscoroutinefunction:", asyncio.iscoroutinefunction(db.vouchers.insert_one))
            res_obj = db.vouchers.insert_one(voucher)
            print("[payments.create_voucher] res_obj type:", type(res_obj), "inspect.isawaitable:", inspect.isawaitable(res_obj))
            result = await res_obj
            voucher["_id"] = str(result.inserted_id)
        except Exception as ex:
            print("[payments.create_voucher] Insert failed:", repr(ex))
            raise
        
        return {
            **voucher,
            "created_at": voucher["created_at"].isoformat(),
            "updated_at": voucher["updated_at"].isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/vouchers/", response_model=List[dict])
async def list_vouchers(
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    List all vouchers for the current organization
    Also checks and updates expired vouchers
    """
    try:
        db = db_config.database
        
        # First, update any expired vouchers
        from datetime import date
        today = date.today().isoformat()
        await db.vouchers.update_many(
            {
                "status": "pending",
                "expiry_date": {"$lt": today}
            },
            {
                "$set": {
                    "status": "expired",
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        # Build query
        query = {"organization_id": current_user.get("organization_id")}
        if status:
            query["status"] = status
        
        # Fetch vouchers
        cursor = db.vouchers.find(query).sort("created_at", -1)
        vouchers = await cursor.to_list(length=100)
        
        # Format response
        for voucher in vouchers:
            voucher["_id"] = str(voucher["_id"])
            voucher["created_at"] = voucher["created_at"].isoformat() if voucher.get("created_at") else None
            voucher["updated_at"] = voucher["updated_at"].isoformat() if voucher.get("updated_at") else None
            voucher["paid_at"] = voucher["paid_at"].isoformat() if voucher.get("paid_at") else None
        
        return vouchers
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/vouchers/{voucher_id}", response_model=dict)
async def get_voucher(
    voucher_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get a specific voucher by ID
    """
    try:
        db = db_config.database
        
        voucher = await db.vouchers.find_one({"_id": ObjectId(voucher_id)})
        if not voucher:
            raise HTTPException(status_code=404, detail="Voucher not found")
        
        voucher["_id"] = str(voucher["_id"])
        voucher["created_at"] = voucher["created_at"].isoformat() if voucher.get("created_at") else None
        voucher["updated_at"] = voucher["updated_at"].isoformat() if voucher.get("updated_at") else None
        voucher["paid_at"] = voucher["paid_at"].isoformat() if voucher.get("paid_at") else None
        
        return voucher
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Payment Endpoints
@router.post("/topup/", response_model=dict)
async def initiate_topup(
    payment_data: dict,
    current_user: dict = Depends(get_current_user)
):
    """
    Initiate a payment/top-up (creates pending transaction and provider session)
    
    Based on Kuickapay documentation section 2.3
    """
    try:
        db = db_config.database
        
        # Create pending transaction
        transaction = {
            "wallet_id": payment_data.get("wallet_id"),
            "amount": float(payment_data.get("amount")),
            "currency": payment_data.get("currency", "PKR"),
            "type": "topup",
            "status": "pending",
            "provider": payment_data.get("provider", "local_gateway"),
            "provider_reference": None,
            "metadata": payment_data.get("metadata", {}),
            "created_by": str(current_user.get("_id")),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        result = await db.transactions.insert_one(transaction)
        transaction_id = str(result.inserted_id)
        
        # Simulate provider session creation
        # In production, this would call the actual payment gateway API
        provider_session = {
            "session_id": f"sess_{secrets.token_hex(16)}",
            "checkout_url": f"https://pay.example.com/checkout/sess_{secrets.token_hex(16)}",
            "reference": f"ref_{secrets.token_hex(12)}"
        }
        
        # Update transaction with provider reference
        await db.transactions.update_one(
            {"_id": ObjectId(transaction_id)},
            {"$set": {"provider_reference": provider_session["reference"]}}
        )
        
        # Update voucher if metadata contains voucher_id
        if payment_data.get("metadata", {}).get("voucher_id"):
            voucher_id = payment_data["metadata"]["voucher_id"]
            await db.vouchers.update_one(
                {"_id": ObjectId(voucher_id)},
                {"$set": {
                    "transaction_id": transaction_id,
                    "status": "processing",
                    "updated_at": datetime.utcnow()
                }}
            )
        
        return {
            "transaction_id": transaction_id,
            "status": "pending",
            "provider_session": provider_session
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/webhook/{provider}/")
async def payment_webhook(
    provider: str,
    request: Request,
    x_signature: Optional[str] = Header(None)
):
    """
    Handle payment provider webhooks
    
    Based on Kuickapay documentation section 5.2
    """
    try:
        db = db_config.database
        
        # Read raw body
        body = await request.body()
        payload = await request.json()
        
        # Verify signature (in production, verify against stored webhook secret)
        # For now, we skip verification in development
        
        # Get transaction by provider reference
        reference = payload.get("reference")
        transaction = await db.transactions.find_one({"provider_reference": reference})
        
        if not transaction:
            raise HTTPException(status_code=404, detail="Transaction not found")
        
        # Check if already processed (idempotency)
        if transaction["status"] in ("completed", "failed"):
            return {"status": "ok", "message": "Already processed"}
        
        # Process payment status
        if payload.get("status") == "paid":
            # Update transaction
            await db.transactions.update_one(
                {"_id": transaction["_id"]},
                {"$set": {
                    "status": "completed",
                    "updated_at": datetime.utcnow()
                }}
            )
            
            # Update wallet balance if wallet_id exists
            if transaction.get("wallet_id"):
                await db.wallets.update_one(
                    {"_id": ObjectId(transaction["wallet_id"])},
                    {
                        "$inc": {"balance": transaction["amount"]},
                        "$set": {"updated_at": datetime.utcnow()}
                    },
                    upsert=True
                )
            
            # Update voucher status if metadata contains voucher_id
            if transaction.get("metadata", {}).get("voucher_id"):
                await db.vouchers.update_one(
                    {"_id": ObjectId(transaction["metadata"]["voucher_id"])},
                    {"$set": {
                        "status": "paid",
                        "paid_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }}
                )
        else:
            # Mark as failed
            await db.transactions.update_one(
                {"_id": transaction["_id"]},
                {"$set": {
                    "status": "failed",
                    "updated_at": datetime.utcnow()
                }}
            )
            
            if transaction.get("metadata", {}).get("voucher_id"):
                await db.vouchers.update_one(
                    {"_id": ObjectId(transaction["metadata"]["voucher_id"])},
                    {"$set": {
                        "status": "failed",
                        "updated_at": datetime.utcnow()
                    }}
                )
        
        return {"status": "ok"}
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/transactions/", response_model=List[dict])
async def list_transactions(
    wallet_id: Optional[str] = None,
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    List transactions for wallet or user
    """
    try:
        db = db_config.database
        
        # Build query
        query = {"created_by": str(current_user.get("_id"))}
        if wallet_id:
            query["wallet_id"] = wallet_id
        if status:
            query["status"] = status
        
        # Fetch transactions
        cursor = db.transactions.find(query).sort("created_at", -1).limit(50)
        transactions = await cursor.to_list(length=50)
        
        # Format response
        for transaction in transactions:
            transaction["_id"] = str(transaction["_id"])
            transaction["created_at"] = transaction["created_at"].isoformat() if transaction.get("created_at") else None
            transaction["updated_at"] = transaction["updated_at"].isoformat() if transaction.get("updated_at") else None
        
        return transactions
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/refund/", response_model=dict)
async def create_refund(
    refund_data: dict,
    current_user: dict = Depends(get_current_user)
):
    """
    Issue a refund for a completed transaction
    
    Based on Kuickapay documentation section 5.3
    """
    try:
        db = db_config.database
        
        # Get original transaction
        transaction_id = refund_data.get("transaction_id")
        transaction = await db.transactions.find_one({"_id": ObjectId(transaction_id)})
        
        if not transaction:
            raise HTTPException(status_code=404, detail="Transaction not found")
        
        if transaction["status"] != "completed":
            raise HTTPException(status_code=400, detail="Can only refund completed transactions")
        
        refund_amount = float(refund_data.get("amount", transaction["amount"]))
        
        # Create refund transaction
        refund_transaction = {
            "wallet_id": transaction.get("wallet_id"),
            "amount": refund_amount,
            "currency": transaction["currency"],
            "type": "refund",
            "status": "completed",
            "provider": transaction.get("provider"),
            "provider_reference": f"refund_{secrets.token_hex(12)}",
            "metadata": {
                "original_transaction_id": transaction_id,
                "reason": refund_data.get("reason", "customer_request")
            },
            "created_by": str(current_user.get("_id")),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        result = await db.transactions.insert_one(refund_transaction)
        
        # Update wallet (if applicable)
        if transaction.get("wallet_id"):
            await db.wallets.update_one(
                {"_id": ObjectId(transaction["wallet_id"])},
                {
                    "$inc": {"balance": -refund_amount},
                    "$set": {"updated_at": datetime.utcnow()}
                }
            )
        
        # Update original transaction
        await db.transactions.update_one(
            {"_id": ObjectId(transaction_id)},
            {"$set": {"status": "refunded", "updated_at": datetime.utcnow()}}
        )
        
        return {
            "refund_transaction_id": str(result.inserted_id),
            "amount": refund_amount,
            "status": "completed"
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Wallet Endpoints
@router.get("/wallets/{wallet_id}", response_model=dict)
async def get_wallet(
    wallet_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get wallet details and recent transactions
    """
    try:
        db = db_config.database
        
        wallet = await db.wallets.find_one({"_id": ObjectId(wallet_id)})
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found")
        
        # Get recent transactions
        cursor = db.transactions.find({"wallet_id": wallet_id}).sort("created_at", -1).limit(10)
        transactions = await cursor.to_list(length=10)
        
        wallet["_id"] = str(wallet["_id"])
        wallet["transactions"] = [
            {**t, "_id": str(t["_id"])} for t in transactions
        ]
        
        return wallet
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Kuickapay Integration Endpoints
@router.post("/api/v1/BillInquiry", response_model=dict)
async def bill_inquiry(
    request: Request
):
    """
    Kuickapay Bill Inquiry Endpoint
    Check the validity and status of a voucher
    """
    try:
        db = db_config.database
        
        # Get credentials from headers
        username = request.headers.get("username")
        password = request.headers.get("password")
        
        # TODO: Validate username/password against stored credentials
        # For now, accepting any valid credentials
        
        # Get request body
        body = await request.json()
        consumer_number = body.get("consumer_number")
        bank_mnemonic = body.get("bank_mnemonic")
        reserved = body.get("reserved", "")
        
        if not consumer_number:
            return {
                "response_Code": "04",
                "consumer_Detail": "",
                "bill_status": "",
                "due_date": "",
                "amount_within_dueDate": "",
                "amount_after_dueDate": "",
                "email_address": "",
                "contact_number": "",
                "billing_month": "",
                "date_paid": "",
                "amount_paid": "",
                "tran_auth_Id": "",
                "reserved": "Invalid Data - Consumer number required"
            }
        
        # Find voucher by consumer_number
        voucher = await db.vouchers.find_one({"consumer_number": consumer_number})
        
        if not voucher:
            return {
                "response_Code": "01",
                "consumer_Detail": "",
                "bill_status": "",
                "due_date": "",
                "amount_within_dueDate": "",
                "amount_after_dueDate": "",
                "email_address": "",
                "contact_number": "",
                "billing_month": "",
                "date_paid": "",
                "amount_paid": "",
                "tran_auth_Id": "",
                "reserved": "Voucher Number does not exist"
            }
        
        # Check if voucher is blocked
        if voucher.get("status") == "blocked" or voucher.get("bill_status") == "B":
            return {
                "response_Code": "02",
                "consumer_Detail": voucher.get("user_name", "").ljust(30)[:30],
                "bill_status": "B",
                "due_date": voucher.get("expiry_date", ""),
                "amount_within_dueDate": "",
                "amount_after_dueDate": "",
                "email_address": voucher.get("user_email", ""),
                "contact_number": voucher.get("contact_number", ""),
                "billing_month": voucher.get("billing_month", ""),
                "date_paid": "",
                "amount_paid": "",
                "tran_auth_Id": "",
                "reserved": "Voucher Blocked or Inactive"
            }
        
        # Format amounts (14 chars: sign + 12 digits + 2 decimal places)
        def format_amount(amount):
            if amount is None:
                return "+00000000000000"
            amount_int = int(amount * 100)  # Convert to minor units
            sign = "+" if amount_int >= 0 else "-"
            return f"{sign}{abs(amount_int):012d}"
        
        # Build response based on bill status
        bill_status = voucher.get("bill_status", "U")
        
        response = {
            "response_Code": "00",
            "consumer_Detail": voucher.get("user_name", "").ljust(30)[:30],
            "bill_status": bill_status,
            "due_date": voucher.get("expiry_date", ""),
            "amount_within_dueDate": format_amount(voucher.get("amount_within_due_date", voucher.get("amount"))),
            "amount_after_dueDate": format_amount(voucher.get("amount_after_due_date", voucher.get("amount"))),
            "email_address": voucher.get("user_email", ""),
            "contact_number": voucher.get("contact_number", ""),
            "billing_month": voucher.get("billing_month", ""),
            "date_paid": voucher.get("date_paid", ""),
            "amount_paid": format_amount(voucher.get("amount_paid")).replace("+", "").replace("-", "") if voucher.get("amount_paid") else "",
            "tran_auth_Id": voucher.get("tran_auth_id", ""),
            "reserved": reserved
        }
        
        return response
        
    except Exception as e:
        return {
            "response_Code": "03",
            "consumer_Detail": "",
            "bill_status": "",
            "due_date": "",
            "amount_within_dueDate": "",
            "amount_after_dueDate": "",
            "email_address": "",
            "contact_number": "",
            "billing_month": "",
            "date_paid": "",
            "amount_paid": "",
            "tran_auth_Id": "",
            "reserved": f"Unknown Error: {str(e)}"
        }


@router.post("/api/v1/BillPayment", response_model=dict)
async def bill_payment(
    request: Request
):
    """
    Kuickapay Bill Payment Endpoint
    Process payment for a voucher
    """
    try:
        db = db_config.database
        
        # Get credentials from headers
        username = request.headers.get("username")
        password = request.headers.get("password")
        
        # TODO: Validate username/password against stored credentials
        
        # Get request body
        body = await request.json()
        consumer_number = body.get("consumer_number")
        tran_auth_id = body.get("tran_auth_id")
        transaction_amount = body.get("transaction_amount")
        tran_date = body.get("tran_date")
        tran_time = body.get("tran_time")
        bank_mnemonic = body.get("bank_mnemonic")
        reserved = body.get("reserved", "")
        
        if not all([consumer_number, tran_auth_id, transaction_amount, tran_date, tran_time]):
            return {
                "response_Code": "04",
                "Identification_parameter": "",
                "reserved": "Invalid Data - Missing required fields"
            }
        
        # Find voucher
        voucher = await db.vouchers.find_one({"consumer_number": consumer_number})
        
        if not voucher:
            return {
                "response_Code": "01",
                "Identification_parameter": "",
                "reserved": "Voucher Number does not exist"
            }
        
        # Check if already paid or blocked
        if voucher.get("bill_status") == "P":
            return {
                "response_Code": "03",
                "Identification_parameter": "",
                "reserved": "Duplicate Transaction - Already Paid"
            }
        
        if voucher.get("status") == "blocked" or voucher.get("bill_status") == "B":
            return {
                "response_Code": "02",
                "Identification_parameter": "",
                "reserved": "Voucher Blocked or Inactive"
            }
        
        # Process payment
        try:
            amount_paid = float(transaction_amount)
            
            # Update voucher
            await db.vouchers.update_one(
                {"consumer_number": consumer_number},
                {
                    "$set": {
                        "status": "paid",
                        "bill_status": "P",
                        "date_paid": tran_date,
                        "amount_paid": amount_paid,
                        "tran_auth_id": tran_auth_id,
                        "paid_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            # Create transaction record
            transaction = {
                "wallet_id": voucher.get("wallet_id"),
                "amount": amount_paid,
                "currency": voucher.get("currency", "PKR"),
                "type": "payment",
                "status": "completed",
                "provider": bank_mnemonic,
                "provider_reference": tran_auth_id,
                "metadata": {
                    "consumer_number": consumer_number,
                    "tran_date": tran_date,
                    "tran_time": tran_time,
                    "reserved": reserved
                },
                "created_by": voucher.get("created_by"),
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            result = await db.transactions.insert_one(transaction)
            
            # Return success
            receipt_id = str(result.inserted_id)[-20:].zfill(20)
            
            return {
                "response_Code": "00",
                "Identification_parameter": receipt_id,
                "reserved": reserved
            }
            
        except Exception as e:
            return {
                "response_Code": "05",
                "Identification_parameter": "",
                "reserved": f"Processing Failed: {str(e)}"
            }
        
    except Exception as e:
        return {
            "response_Code": "03",
            "Identification_parameter": "",
            "reserved": f"Unknown Error: {str(e)}"
        }

# Manual Payment & Deposit Endpoints

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
    transfer_account: Optional[str] = Form(None),
    transfer_account_name: Optional[str] = Form(None),
    transfer_phone: Optional[str] = Form(None),
    transfer_cnic: Optional[str] = Form(None),
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
        "transfer_account": transfer_account,
        "transfer_account_name": transfer_account_name,
        "transfer_phone": transfer_phone,
        "transfer_cnic": transfer_cnic,
    }
    
    # Resolve IDs from JWT
    role = current_user.get('role')
    payment_dict['agency_id'] = current_user.get('agency_id') or (current_user.get('sub') if role == 'agency' else None)
    payment_dict['branch_id'] = current_user.get('branch_id') or (current_user.get('sub') if role == 'branch' else None)
    payment_dict['organization_id'] = current_user.get('organization_id')
    payment_dict['sender_role'] = role
    payment_dict['agent_name'] = (
        current_user.get('agency_name') or
        current_user.get('branch_name') or
        current_user.get('email', 'Unknown')
    )
    payment_dict['created_by'] = current_user.get('email') or current_user.get('username')
    payment_dict['created_at'] = datetime.utcnow()
    payment_dict['updated_at'] = payment_dict['created_at']

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
        # Store the human-readable booking reference
        payment_dict['booking_reference'] = booking.get('booking_reference')
            
    # Make sure we don't save empty string fields
    payment_dict = {k: v for k, v in payment_dict.items() if v not in [None, ""]}
    
    # Logic for credit payment — handle inline, skip saving to payments collection
    if payment_method == "credit":
        agency_id = payment_dict.get('agency_id')
        if not agency_id:
            raise HTTPException(status_code=400, detail="Agency ID is required for credit payments")
        
        agency = await db_ops.get_by_id(Collections.AGENCIES, agency_id)
        if not agency:
            raise HTTPException(status_code=404, detail="Agency not found")
            
        limit = float(agency.get("credit_limit") or 0)
        used = float(agency.get("credit_used") or 0)
        amount_to_pay = float(amount)
        
        if (limit - used) < amount_to_pay:
            raise HTTPException(status_code=400, detail=f"Insufficient credit limit. Available: {limit - used}")
        
        # Deduct credit atomically
        await db_ops.update(Collections.AGENCIES, agency_id, {"credit_used": used + amount_to_pay})
        
        # Update booking status directly — no payment record stored
        if col_name:
            await db_ops.update(col_name, booking_id, {
                "payment_method": payment_method,
                "payment_status": "paid",
                "booking_status": "confirmed",
                "paid_amount": amount_to_pay
            })
        
        # Return a synthetic response (no DB record)
        return {
            "_id": "credit",
            "booking_id": booking_id,
            "booking_reference": payment_dict.get('booking_reference'),
            "booking_type": booking_type,
            "payment_method": "credit",
            "amount": amount_to_pay,
            "status": "approved",
            "sender_role": payment_dict.get('sender_role'),
            "agent_name": payment_dict.get('agent_name'),
            "payment_date": payment_dict.get('payment_date'),
            "created_at": payment_dict.get('created_at'),
            "updated_at": payment_dict.get('updated_at', payment_dict.get('created_at')),
        }

    # Allow manual deposits even if no booking ID exists natively.
    created_payment = await db_ops.create(Collections.PAYMENTS, payment_dict)
    
    # For non-credit: update booking with pending status
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
    exclude_credit: bool = False,
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
        # Branches should only see their own payments, not their sub-agencies
        query['agency_id'] = {"$exists": False}
        
    if status:
        query['status'] = status
    if booking_id:
        query['booking_id'] = booking_id
    if payment_method:
        query['payment_method'] = payment_method
    if exclude_credit:
        query['payment_method'] = {"$ne": "credit"}
        
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
        "updated_at": datetime.utcnow()
    }
    if note:
        update_data["note"] = f"{payment.get('note', '')}\n[ORG UPDATE]: {note}".strip()
        
    updated_payment = await db_ops.update(Collections.PAYMENTS, payment_id, update_data)
    
    # If payment is approved, we should also update the booking and create journal
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
            booking = await db_ops.get_by_id(col_name, payment.get('booking_id'))
            if booking:
                new_paid_amount = float(booking.get('paid_amount', 0)) + float(payment.get('amount', 0))
                total_amount = float(booking.get('grand_total') or booking.get('total_amount') or 0)
                
                payment_status = "paid" if new_paid_amount >= total_amount else "partial"
                
                await db_ops.update(col_name, payment.get('booking_id'), {
                    "payment_status": payment_status,
                    "paid_amount": new_paid_amount,
                    "booking_status": "confirmed" if payment_status == "paid" else "underprocess"
                })
                
                from app.finance.journal_engine import create_payment_received_journal
                try:
                    await create_payment_received_journal(
                        booking_reference=booking.get('booking_reference', payment.get('booking_id')),
                        amount=float(payment.get('amount', 0)),
                        payment_method=payment.get('payment_method', 'bank'),
                        agency_name=payment.get('agent_name', 'Agency'),
                        organization_id=payment.get('organization_id'),
                        branch_id=payment.get('branch_id'),
                        agency_id=payment.get('agency_id'),
                        created_by=current_user.get('email') or current_user.get('username') or "System"
                    )
                except Exception as je:
                    print(f"⚠️  Journal engine warning for payment approval {payment_id}: {je}")
            
    return serialize_doc(updated_payment)
