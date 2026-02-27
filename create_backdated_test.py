"""
Create a proper test with backdated booking for late payment
"""
import asyncio
from datetime import datetime, timedelta
from bson import ObjectId
from app.config.database import db_config, Collections

async def create_late_payment_test():
    await db_config.connect_db()
    
    agency_id = "69907f1a1a2ed26ed3fc82ee"
    collection = db_config.get_collection(Collections.AGENCIES)
    agency = await collection.find_one({"_id": ObjectId(agency_id)})
    
    if not agency:
        print("❌ Agency not found")
        return
    
    credit_limit_days = agency.get("credit_limit_days", 30)
    
    print("=" * 80)
    print("🧪 CREATING BACKDATED BOOKING WITH LATE PAYMENT")
    print("=" * 80)
    print(f"🏢 Agency: {agency.get('name')}")
    print(f"   Credit Terms: {credit_limit_days} days\n")
    
    # Create booking 45 days in the past
    booking_date = datetime.now() - timedelta(days=45)
    due_date = booking_date + timedelta(days=credit_limit_days)
    payment_date = datetime.now()  # Today
    days_late = (payment_date - due_date).days
    
    print(f"📅 TIMELINE:")
    print(f"   Booking Date: {booking_date.strftime('%Y-%m-%d')} (45 days ago)")
    print(f"   Due Date:     {due_date.strftime('%Y-%m-%d')} (booking + {credit_limit_days} days)")
    print(f"   Payment Date: {payment_date.strftime('%Y-%m-%d')} (TODAY)")
    print(f"   Expected:     ⏰ LATE by {days_late} days\n")
    
    # Create booking directly with old date
    bookings_collection = db_config.get_collection(Collections.TICKET_BOOKINGS)
    
    booking_doc = {
        "booking_reference": f"TB-LATE-TEST-{datetime.now().strftime('%H%M%S')}",
        "agency_id": agency_id,
        "branch_id": agency.get("branch_id"),
        "agent_name": "Test Agent",
        "ticket_id": str(ObjectId()),
        "booking_type": "ticket",
        "ticket_details": {
            "from": "LHE - Lahore",
            "to": "JED - Jeddah",
            "airline": "PIA",
            "flight_number": "PK-999"
        },
        "passengers": [{
            "type": "Adult",
            "title": "Mr",
            "first_name": "Late",
            "last_name": "Payment",
            "passport_number": "LATE99999",
            "date_of_birth": "1990-01-01",
            "passport_issue_date": "2020-01-01",
            "passport_expiry_date": "2030-01-01",
            "country": "Pakistan"
        }],
        "total_passengers": 1,
        "base_price_per_person": 60000.0,
        "tax_per_person": 6000.0,
        "service_charge_per_person": 1200.0,
        "subtotal": 60000.0,
        "total_tax": 6000.0,
        "total_service_charge": 1200.0,
        "grand_total": 67200.0,
        "payment_status": "pending",
        "paid_amount": 0,
        "booking_status": "confirmed",
        "notes": "Test booking backdated for late payment testing",
        "created_at": booking_date,  # BACKDATED
        "updated_at": booking_date
    }
    
    result = await bookings_collection.insert_one(booking_doc)
    booking_id = str(result.inserted_id)
    
    print(f"📋 Created Booking:")
    print(f"   ID: {booking_id}")
    print(f"   Ref: {booking_doc['booking_reference']}")
    
    # Verify the date was saved correctly
    saved_booking = await bookings_collection.find_one({"_id": result.inserted_id})
    print(f"   Saved created_at: {saved_booking['created_at']}")
    
    # Create payment for TODAY (late)
    payments_collection = db_config.get_collection(Collections.PAYMENTS)
    
    payment_doc = {
        "booking_id": booking_id,
        "booking_type": "ticket",
        "payment_method": "bank",
        "amount": 67200.0,
        "payment_date": payment_date.strftime("%Y-%m-%d"),  # TODAY
        "note": "Test late payment - paid after due date",
        "status": "approved",
        "agency_id": agency_id,
        "branch_id": agency.get("branch_id"),
        "agent_name": "Test Agent",
        "organization_id": agency.get("organization_id"),
        "created_at": payment_date,
        "updated_at": payment_date
    }
    
    result = await payments_collection.insert_one(payment_doc)
    payment_id = str(result.inserted_id)
    
    print(f"\n💰 Created Payment:")
    print(f"   ID: {payment_id}")
    print(f"   Amount: Rs. {payment_doc['amount']:,.2f}")
    print(f"   Date: {payment_doc['payment_date']}")
    print(f"   Status: {payment_doc['status']}\n")
    
    print("=" * 80)
    print("✅ TEST DATA CREATED!")
    print("=" * 80)
    
    # Test the calculation manually
    print(f"\n🧪 MANUAL VERIFICATION:")
    b_date = saved_booking["created_at"]
    d_date = b_date + timedelta(days=credit_limit_days)
    p_date = datetime.strptime(payment_doc["payment_date"], "%Y-%m-%d")
    
    print(f"   Booking: {b_date.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Due:     {d_date.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Payment: {p_date.strftime('%Y-%m-%d %H:%M:%S')}")
    
    if p_date > d_date:
        days = (p_date - d_date).days
        print(f"   Result:  ⏰ LATE by {days} days")
    else:
        print(f"   Result:  ✅ ON-TIME")
    
    print(f"\n💡 Now test the API:")
    print(f"   GET /api/agencies/{agency_id}/stats")
    print(f"   Should show at least 1 late payment!")
    
    await db_config.close_db()

if __name__ == "__main__":
    asyncio.run(create_late_payment_test())
