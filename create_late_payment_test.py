"""
Create a test booking and late payment to verify late payment detection
"""
import asyncio
from datetime import datetime, timedelta
from bson import ObjectId
from app.config.database import db_config, Collections
from app.database.db_operations import db_ops

async def create_test_late_payment():
    await db_config.connect_db()
    
    # Get the agency with existing bookings
    agency_id = "69907f1a1a2ed26ed3fc82ee"
    agency = await db_ops.get_by_id(Collections.AGENCIES, agency_id)
    
    if not agency:
        print("❌ Agency not found")
        return
    
    credit_limit_days = agency.get("credit_limit_days", 30)
    
    print("=" * 80)
    print("🧪 CREATING TEST BOOKING WITH LATE PAYMENT")
    print("=" * 80)
    print(f"🏢 Agency: {agency.get('name')}")
    print(f"   Credit Terms: {credit_limit_days} days")
    
    # Create booking with OLD date (45 days ago) so it's definitely past due
    booking_date = datetime.utcnow() - timedelta(days=45)
    due_date = booking_date + timedelta(days=credit_limit_days)
    
    # Payment date will be TODAY (15 days late)
    payment_date = datetime.utcnow()
    days_late = (payment_date - due_date).days
    
    print(f"\n📅 TIMELINE:")
    print(f"   Booking Created: {booking_date.strftime('%Y-%m-%d')} (45 days ago)")
    print(f"   Due Date: {due_date.strftime('%Y-%m-%d')} (after {credit_limit_days} days)")
    print(f"   Payment Date: {payment_date.strftime('%Y-%m-%d')} (TODAY)")
    print(f"   Days Late: {days_late} days ⏰")
    
    # Create test ticket booking
    test_booking = {
        "booking_reference": f"TB-TEST-{datetime.utcnow().strftime('%y%m%d-%H%M')}",
        "agency_id": agency_id,
        "branch_id": agency.get("branch_id"),
        "agent_name": "Test Agent",
        "ticket_id": str(ObjectId()),
        "booking_type": "ticket",
        "ticket_details": {
            "from": "LHE - Lahore",
            "to": "JED - Jeddah",
            "airline": "PIA",
            "flight_number": "PK-TEST123"
        },
        "passengers": [
            {
                "type": "Adult",
                "title": "Mr",
                "first_name": "Test",
                "last_name": "Passenger",
                "passport_number": "TEST12345",
                "date_of_birth": "1990-01-01",
                "passport_issue_date": "2020-01-01",
                "passport_expiry_date": "2030-01-01",
                "country": "Pakistan"
            }
        ],
        "total_passengers": 1,
        "base_price_per_person": 50000.0,
        "tax_per_person": 5000.0,
        "service_charge_per_person": 1000.0,
        "subtotal": 50000.0,
        "total_tax": 5000.0,
        "total_service_charge": 1000.0,
        "grand_total": 56000.0,
        "payment_method": None,
        "payment_status": "pending",
        "paid_amount": 0,
        "booking_status": "confirmed",
        "notes": "Test booking for late payment verification",
        "created_at": booking_date,
        "updated_at": booking_date,
        "created_by": agency_id
    }
    
    print(f"\n📋 Creating test booking...")
    created_booking = await db_ops.create(Collections.TICKET_BOOKINGS, test_booking)
    booking_id = str(created_booking["_id"])
    print(f"   ✅ Booking created: {booking_id}")
    print(f"   Ref: {test_booking['booking_reference']}")
    
    # Create late payment
    test_payment = {
        "booking_id": booking_id,
        "booking_type": "ticket",
        "payment_method": "bank",
        "amount": 56000.0,
        "payment_date": payment_date.strftime("%Y-%m-%d"),
        "note": "Test late payment for verification",
        "status": "approved",
        "agency_id": agency_id,
        "branch_id": agency.get("branch_id"),
        "agent_name": "Test Agent",
        "organization_id": agency.get("organization_id"),
        "created_by": agency_id,
        "created_at": payment_date,
        "updated_at": payment_date
    }
    
    print(f"\n💰 Creating late payment...")
    created_payment = await db_ops.create(Collections.PAYMENTS, test_payment)
    payment_id = str(created_payment["_id"])
    print(f"   ✅ Payment created: {payment_id}")
    print(f"   Amount: Rs. {test_payment['amount']:,.2f}")
    print(f"   Status: {test_payment['status']}")
    
    print("\n" + "=" * 80)
    print("✅ TEST DATA CREATED SUCCESSFULLY!")
    print("=" * 80)
    print(f"\n📊 Summary:")
    print(f"   Booking ID: {booking_id}")
    print(f"   Payment ID: {payment_id}")
    print(f"   Expected Result: LATE PAYMENT (⏰ {days_late} days late)")
    
    # Now test the API
    print(f"\n🧪 Testing API to verify late payment detection...")
    
    # Get updated stats
    ticket_bookings = await db_ops.get_all(Collections.TICKET_BOOKINGS, {"agency_id": agency_id})
    umrah_bookings = await db_ops.get_all(Collections.UMRAH_BOOKINGS, {"agency_id": agency_id})
    custom_bookings = await db_ops.get_all(Collections.CUSTOM_BOOKINGS, {"agency_id": agency_id})
    payments = await db_ops.get_all(Collections.PAYMENTS, {"agency_id": agency_id, "status": "approved"})
    
    print(f"\n📊 Current Agency Stats:")
    print(f"   Total Bookings: {len(ticket_bookings) + len(umrah_bookings) + len(custom_bookings)}")
    print(f"   Total Approved Payments: {len(payments)}")
    
    # Manually calculate late payments
    on_time = 0
    late = 0
    
    for payment in payments:
        if payment.get("payment_date"):
            booking = None
            bid = payment.get("booking_id")
            
            booking = await db_ops.get_by_id(Collections.TICKET_BOOKINGS, bid)
            if not booking:
                booking = await db_ops.get_by_id(Collections.UMRAH_BOOKINGS, bid)
            if not booking:
                booking = await db_ops.get_by_id(Collections.CUSTOM_BOOKINGS, bid)
            
            if booking and booking.get("created_at"):
                b_date = booking["created_at"]
                if isinstance(b_date, str):
                    b_date = datetime.fromisoformat(b_date.replace('Z', '+00:00'))
                
                d_date = b_date + timedelta(days=credit_limit_days)
                
                try:
                    p_date = datetime.strptime(payment["payment_date"], "%Y-%m-%d")
                except:
                    try:
                        p_date = datetime.fromisoformat(payment["payment_date"].replace('Z', '+00:00'))
                    except:
                        continue
                
                if p_date <= d_date:
                    on_time += 1
                else:
                    late += 1
    
    print(f"\n   ✅ On-Time Payments: {on_time}")
    print(f"   ⏰ Late Payments: {late}")
    
    if late > 0:
        print(f"\n🎉 SUCCESS! Late payment detection is working!")
        print(f"   The API should now show {late} late payment(s)")
    else:
        print(f"\n⚠️  WARNING: No late payments detected. Calculation may need adjustment.")
    
    print("\n" + "=" * 80)
    print("💡 To verify in the frontend:")
    print(f"   1. Refresh the organization portal")
    print(f"   2. View agency: {agency.get('name')}")
    print(f"   3. Check the 'Late Payments' card - should show {late}")
    print("=" * 80)
    
    await db_config.close_db()

if __name__ == "__main__":
    asyncio.run(create_test_late_payment())
