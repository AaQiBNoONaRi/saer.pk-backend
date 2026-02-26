"""
Debug the late payment detection issue
"""
import asyncio
from datetime import datetime, timedelta
from app.config.database import db_config, Collections
from app.database.db_operations import db_ops

async def debug_late_payment():
    await db_config.connect_db()
    
    # Get the test payment we just created
    agency_id = "69907f1a1a2ed26ed3fc82ee"
    agency = await db_ops.get_by_id(Collections.AGENCIES, agency_id)
    credit_limit_days = agency.get("credit_limit_days", 30)
    
    # Get the last payment (our test one)
    payments = await db_ops.get_all(Collections.PAYMENTS, {"agency_id": agency_id, "status": "approved"})
    
    if payments:
        payment = payments[-1]  # Last payment (our test)
        
        print("=" * 80)
        print("🔍 DEBUGGING LATE PAYMENT DETECTION")
        print("=" * 80)
        
        booking_id = payment.get("booking_id")
        booking = await db_ops.get_by_id(Collections.TICKET_BOOKINGS, booking_id)
        
        if booking:
            print(f"\n📋 Booking Info:")
            print(f"   ID: {booking_id}")
            print(f"   Created At: {booking.get('created_at')}")
            print(f"   Type: {type(booking.get('created_at'))}")
            
            print(f"\n💰 Payment Info:")
            print(f"   Payment Date: {payment.get('payment_date')}")
            print(f"   Type: {type(payment.get('payment_date'))}")
            
            # Reproduce the logic from the API
            booking_date = booking["created_at"]
            print(f"\n🔧 STEP-BY-STEP CALCULATION:")
            print(f"   1. Raw booking_date: {booking_date} (type: {type(booking_date)})")
            
            if isinstance(booking_date, str):
                booking_date = datetime.fromisoformat(booking_date.replace('Z', '+00:00'))
                print(f"   2. Parsed booking_date: {booking_date}")
            else:
                print(f"   2. booking_date is already datetime: {booking_date}")
            
            due_date = booking_date + timedelta(days=credit_limit_days)
            print(f"   3. Due date: {due_date} (booking + {credit_limit_days} days)")
            
            payment_date_str = payment["payment_date"]
            print(f"   4. Raw payment_date: {payment_date_str} (type: {type(payment_date_str)})")
            
            try:
                payment_date = datetime.strptime(payment_date_str, "%Y-%m-%d")
                print(f"   5. Parsed payment_date: {payment_date}")
            except Exception as e:
                print(f"   5. Error parsing: {e}")
                try:
                    payment_date = datetime.fromisoformat(payment_date_str.replace('Z', '+00:00'))
                    print(f"   5. Parsed as ISO: {payment_date}")
                except Exception as e2:
                    print(f"   5. ISO parse error: {e2}")
            
            print(f"\n⚖️  COMPARISON:")
            print(f"   Payment Date: {payment_date}")
            print(f"   Due Date:     {due_date}")
            print(f"   Difference:   {(payment_date - due_date).days} days")
            
            if payment_date <= due_date:
                print(f"   Result: ✅ ON-TIME (payment <= due)")
            else:
                print(f"   Result: ⏰ LATE (payment > due)")
            
            # The issue: datetime comparison with time component
            print(f"\n💡 POTENTIAL ISSUE:")
            print(f"   Due date has time: {due_date.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   Payment date has time: {payment_date.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   Payment date time is: {payment_date.time()}")
            
            # Compare just dates
            if payment_date.date() > due_date.date():
                print(f"\n   ✅ When comparing DATES only: LATE")
            else:
                print(f"\n   ⚠️  When comparing DATES only: ON-TIME")
    
    await db_config.close_db()

if __name__ == "__main__":
    asyncio.run(debug_late_payment())
