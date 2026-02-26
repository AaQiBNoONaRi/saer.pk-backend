"""
Show detailed payment timing analysis
"""
import asyncio
from datetime import datetime, timedelta
from app.config.database import db_config, Collections
from app.database.db_operations import db_ops

async def analyze_payments():
    await db_config.connect_db()
    
    # Get agency with payments
    agency = await db_ops.get_by_id(Collections.AGENCIES, "69907f1a1a2ed26ed3fc82ee")
    
    if not agency:
        print("Agency not found")
        return
    
    print(f"\n{'='*80}")
    print(f"🏢 Agency: {agency.get('name')}")
    print(f"   Credit Limit Days: {agency.get('credit_limit_days', 30)} days")
    print(f"{'='*80}\n")
    
    # Get all approved payments
    payments = await db_ops.get_all(Collections.PAYMENTS, {
        "agency_id": "69907f1a1a2ed26ed3fc82ee",
        "status": "approved"
    })
    
    print(f"📊 Found {len(payments)} approved payments\n")
    
    credit_limit_days = agency.get("credit_limit_days", 30)
    on_time = 0
    late = 0
    
    for i, payment in enumerate(payments, 1):
        print(f"{'─'*80}")
        print(f"💰 Payment #{i}")
        print(f"   Payment ID: {payment.get('_id')}")
        print(f"   Booking ID: {payment.get('booking_id')}")
        print(f"   Amount: Rs. {payment.get('amount')}")
        print(f"   Payment Date: {payment.get('payment_date')}")
        
        # Find the related booking
        booking_id = payment.get("booking_id")
        booking = None
        booking_type = None
        
        booking = await db_ops.get_by_id(Collections.TICKET_BOOKINGS, booking_id)
        if booking:
            booking_type = "Ticket Booking"
        
        if not booking:
            booking = await db_ops.get_by_id(Collections.UMRAH_BOOKINGS, booking_id)
            if booking:
                booking_type = "Umrah Booking"
        
        if not booking:
            booking = await db_ops.get_by_id(Collections.CUSTOM_BOOKINGS, booking_id)
            if booking:
                booking_type = "Custom Booking"
        
        if booking and booking.get("created_at"):
            print(f"\n   📋 Related {booking_type}")
            print(f"      Booking Ref: {booking.get('booking_reference')}")
            
            # Calculate due date
            booking_date = booking["created_at"]
            if isinstance(booking_date, str):
                booking_date = datetime.fromisoformat(booking_date.replace('Z', '+00:00'))
            
            due_date = booking_date + timedelta(days=credit_limit_days)
            
            print(f"      Booking Created: {booking_date.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"      Due Date: {due_date.strftime('%Y-%m-%d %H:%M:%S')} ({credit_limit_days} days credit)")
            
            # Parse payment date
            payment_date_str = payment["payment_date"]
            try:
                payment_date = datetime.strptime(payment_date_str, "%Y-%m-%d")
            except:
                try:
                    payment_date = datetime.fromisoformat(payment_date_str.replace('Z', '+00:00'))
                except:
                    print("      ❌ Could not parse payment date")
                    continue
            
            # Calculate days difference
            days_diff = (payment_date - due_date).days
            
            if payment_date <= due_date:
                status = "✅ ON-TIME"
                on_time += 1
                if days_diff == 0:
                    print(f"      {status} (paid on due date)")
                else:
                    print(f"      {status} (paid {abs(days_diff)} days early)")
            else:
                status = "⏰ LATE"
                late += 1
                print(f"      {status} (paid {days_diff} days after due date)")
        else:
            print(f"   ❌ Booking not found - cannot calculate due date")
        
        print()
    
    print(f"{'='*80}")
    print(f"📊 SUMMARY")
    print(f"{'='*80}")
    print(f"   ✅ On-Time Payments: {on_time}")
    print(f"   ⏰ Late Payments: {late}")
    print(f"   📝 Total Analyzed: {on_time + late}")
    print(f"\n💡 HOW IT WORKS:")
    print(f"   Due Date = Booking Created Date + {credit_limit_days} days")
    print(f"   If Payment Date ≤ Due Date → On-Time ✅")
    print(f"   If Payment Date > Due Date → Late ⏰")
    print(f"{'='*80}\n")
    
    await db_config.close_db()

if __name__ == "__main__":
    asyncio.run(analyze_payments())
