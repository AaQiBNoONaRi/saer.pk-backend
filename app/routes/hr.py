"""
HR Management routes
"""
from fastapi import APIRouter, HTTPException, status, Depends, Query
from fastapi.responses import JSONResponse
from typing import List, Optional
from datetime import datetime, date, timedelta
from bson import ObjectId
import pytz
import calendar

from app.models.hr import (
    EmployeeHRCreate, EmployeeHRUpdate, EmployeeHRResponse,
    AttendanceCreate, AttendanceUpdate, AttendanceResponse,
    MovementLogCreate, MovementLogUpdate, MovementLogResponse,
    PunctualityRecordCreate, PunctualityRecordResponse,
    LeaveRequestCreate, LeaveRequestUpdate, LeaveRequestResponse,
    FineCreate, FineResponse,
    SalaryPaymentCreate, SalaryPaymentUpdate, SalaryPaymentResponse,
    CheckInRequest, CheckOutRequest, StartMovementRequest, EndMovementRequest,
    ApproveLeaveRequest, GenerateSalariesRequest, GenerateSalariesJobRequest
)
from app.database.db_operations import db_ops
from app.config.database import Collections
from app.utils.helpers import serialize_doc, serialize_docs
from app.utils.auth import get_current_user, require_org_admin

router = APIRouter(prefix="/hr", tags=["HR Management"])

# Pakistan Standard Time
PKT = pytz.timezone('Asia/Karachi')


def get_pkt_now():
    """Get current time in PKT"""
    return datetime.now(PKT)


def parse_time(time_str: str) -> tuple:
    """Parse time string HH:MM to hour, minute"""
    try:
        parts = time_str.split(':')
        return int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        # Default to 18:00 if parsing fails
        return 18, 0



async def get_allowed_emp_ids(current_user: dict, org_id: str) -> list:
    """Get list of employee IDs the current user is allowed to see (branch or org)"""
    entity_id = current_user.get("branch_id") if current_user.get("role") == "branch" else org_id
    entity_type = "branch" if current_user.get("role") == "branch" else "organization"
    employees = await db_ops.get_all(
        Collections.EMPLOYEES,
        {"entity_id": entity_id, "entity_type": entity_type}
    )
    return [e["emp_id"] for e in employees if e.get("emp_id")]

# ===================== Dashboard Stats =====================
@router.get("/dashboard/stats")
async def get_dashboard_stats(current_user: dict = Depends(get_current_user)):
    """Get HR dashboard statistics"""
    org_id = current_user.get("organization_id") or current_user.get("entity_id")
    if not org_id:
        raise HTTPException(status_code=400, detail="Organization ID not found")
    
    today = date.today()
    current_month = today.strftime("%Y-%m")
    
    # Filter by branch or org
    allowed_emp_ids = await get_allowed_emp_ids(current_user, org_id)
    if not allowed_emp_ids:
        return {
            "total_employees": 0, "present_today": 0, "late_today": 0, "absent_today": 0,
            "salaries_paid_this_month": 0, "pending_salaries": 0, "pending_leave_requests": 0,
            "total_movements_today": 0, "total_commissions_this_month": 0, "avg_checkin_time": "--:--",
            "punctuality_score": 0
        }

    # Total employees
    total_employees = await db_ops.count(Collections.EMPLOYEES, {
        "emp_id": {"$in": allowed_emp_ids},
        "is_active": True
    })
    
    # Today's attendance
    today_attendance = await db_ops.get_all(Collections.HR_ATTENDANCE, {
        "emp_id": {"$in": allowed_emp_ids},
        "date": today.isoformat()
    })
    
    present_today = len([a for a in today_attendance if a.get("status") != "absent"])
    late_today = len([a for a in today_attendance if a.get("status") in ["late", "grace"]])
    absent_today = len([a for a in today_attendance if a.get("status") == "absent"])
    
    # Financial stats
    salaries_this_month = await db_ops.get_all(Collections.HR_SALARY_PAYMENTS, {
        "emp_id": {"$in": allowed_emp_ids},
        "month": current_month
    })
    
    total_salaries_paid = sum(s.get("net_salary", 0) for s in salaries_this_month if s.get("status") == "paid")
    pending_salaries = sum(s.get("net_salary", 0) for s in salaries_this_month if s.get("status") == "pending")
    
    # Pending approvals
    pending_leave_requests = await db_ops.count(Collections.HR_LEAVE_REQUESTS, {
        "emp_id": {"$in": allowed_emp_ids},
        "status": "pending"
    })
    
    # Total movements today
    total_movements_today = await db_ops.count(Collections.HR_MOVEMENT_LOGS, {
        "emp_id": {"$in": allowed_emp_ids},
        "date": today.isoformat()
    })
    
    # Total commissions this month
    commissions_this_month = await db_ops.get_all(Collections.HR_SALARY_PAYMENTS, {
        "emp_id": {"$in": allowed_emp_ids},
        "month": current_month
    })
    total_commissions = sum(s.get("commission_total", 0) for s in commissions_this_month)
    
    # Average check-in time
    avg_checkin_time = None
    if today_attendance:
        valid_checkins = [a for a in today_attendance if a.get("check_in")]
        if valid_checkins:
            total_minutes = 0
            count = 0
            for att in valid_checkins:
                try:
                    checkin = att.get("check_in")
                    if isinstance(checkin, str):
                        checkin_dt = datetime.fromisoformat(checkin.replace('Z', '+00:00'))
                    elif isinstance(checkin, datetime):
                        checkin_dt = checkin
                    else:
                        continue
                    total_minutes += checkin_dt.hour * 60 + checkin_dt.minute
                    count += 1
                except Exception as e:
                    print(f"Error parsing check-in time: {e}")
                    pass
            if count > 0:
                avg_minutes = total_minutes // count
                avg_checkin_time = f"{avg_minutes // 60:02d}:{avg_minutes % 60:02d}"
    
    # Punctuality score (percentage of on-time check-ins)
    punctuality_score = 0
    if today_attendance:
        on_time = len([a for a in today_attendance if a.get("status") in ["on_time", "grace", "present"]])
        punctuality_score = int((on_time / len(today_attendance)) * 100) if len(today_attendance) > 0 else 0

    # Build employee lookup for names
    emps = await db_ops.get_all(Collections.EMPLOYEES, {"emp_id": {"$in": allowed_emp_ids}})
    emp_lookup = {e["emp_id"]: (e.get("full_name") or e.get("name") or e["emp_id"]) for e in emps}

    # Gather recent activities
    checkins = [{"type": "attendance", "action": "Checked in", "time": a.get("check_in"), "emp_id": a.get("emp_id"), "emp_name": emp_lookup.get(a.get("emp_id"), a.get("emp_id"))} for a in today_attendance if a.get("check_in")]
    checkouts = [{"type": "attendance", "action": "Checked out", "time": a.get("check_out"), "emp_id": a.get("emp_id"), "emp_name": emp_lookup.get(a.get("emp_id"), a.get("emp_id"))} for a in today_attendance if a.get("check_out")]
    
    today_movements = await db_ops.get_all(Collections.HR_MOVEMENT_LOGS, {"emp_id": {"$in": allowed_emp_ids}, "date": today.isoformat()})
    movements = [{"type": "movement", "action": "Started movement", "time": m.get("start_time"), "emp_id": m.get("emp_id"), "emp_name": emp_lookup.get(m.get("emp_id"), m.get("emp_id"))} for m in today_movements]
    
    pending_requests_full = await db_ops.get_all(Collections.HR_LEAVE_REQUESTS, {"emp_id": {"$in": allowed_emp_ids}, "status": "pending"})
    leaves = [{"type": "leave", "action": "Requested leave", "time": l.get("created_at") or datetime.now().isoformat(), "emp_id": l.get("emp_id"), "emp_name": emp_lookup.get(l.get("emp_id"), l.get("emp_id"))} for l in pending_requests_full]

    all_activities = checkins + checkouts + movements + leaves
    
    def get_time_str(val):
        if isinstance(val, datetime): return val.isoformat()
        if isinstance(val, str): return val
        return ""

    all_activities.sort(key=lambda x: get_time_str(x.get("time")), reverse=True)
    recent_activities = all_activities[:6]

    # Process pending requests for notifications array
    approval_notifications = []
    from app.utils.helpers import serialize_docs
    serialized_reqs = serialize_docs(pending_requests_full)
    for req in serialized_reqs:
        req["emp_name"] = emp_lookup.get(req.get("emp_id"), req.get("emp_id"))
        approval_notifications.append(req)
        
    # Sort notifications newest first
    approval_notifications.sort(key=lambda x: get_time_str(x.get("created_at")), reverse=True)

    return {
        "total_employees": total_employees,
        "present_today": present_today,
        "late_today": late_today,
        "absent_today": absent_today,
        "salaries_paid_this_month": total_salaries_paid,
        "pending_salaries": pending_salaries,
        "pending_leave_requests": pending_leave_requests,
        "total_movements_today": total_movements_today,
        "total_commissions_this_month": total_commissions,
        "avg_checkin_time": avg_checkin_time or "--:--",
        "punctuality_score": punctuality_score,
        "recent_activities": recent_activities,
        "approval_notifications": approval_notifications
    }


# ===================== Employee HR Management =====================
@router.get("/employees")
async def get_hr_employees(
    current_user: dict = Depends(get_current_user),
    is_active: Optional[bool] = None,
    department: Optional[str] = None
):
    """Get all employees with HR details"""
    org_id = current_user.get("organization_id") or current_user.get("entity_id")
    if not org_id:
        raise HTTPException(status_code=400, detail="Organization ID not found")
    
    # Query by entity_id and entity_type since employees are stored this way
    entity_id = current_user.get("branch_id") if current_user.get("role") == "branch" else org_id
    entity_type = "branch" if current_user.get("role") == "branch" else "organization"
    query = {
        "entity_id": entity_id,
        "entity_type": entity_type
    }
    if is_active is not None:
        query["is_active"] = is_active
    if department:
        query["department"] = department
    
    employees = await db_ops.get_all(Collections.EMPLOYEES, query)
    return serialize_docs(employees)


@router.get("/employees/{emp_id}")
async def get_hr_employee(emp_id: str, current_user: dict = Depends(get_current_user)):
    """Get employee details"""
    employee = await db_ops.get_one(Collections.EMPLOYEES, {"emp_id": emp_id})
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    return serialize_doc(employee)


@router.put("/employees/{emp_id}")
async def update_hr_employee(
    emp_id: str,
    employee_data: EmployeeHRUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update employee HR details"""
    employee = await db_ops.get_one(Collections.EMPLOYEES, {"emp_id": emp_id})
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    update_data = employee_data.dict(exclude_unset=True)
    if update_data:
        update_data["updated_at"] = get_pkt_now()
        await db_ops.update_one(
            Collections.EMPLOYEES,
            {"emp_id": emp_id},
            update_data
        )
    
    updated_employee = await db_ops.get_one(Collections.EMPLOYEES, {"emp_id": emp_id})
    return serialize_doc(updated_employee)


# ===================== Attendance Management =====================
@router.post("/attendance/check-in")
async def check_in(request: CheckInRequest, current_user: dict = Depends(get_current_user)):
    """Employee check-in"""
    org_id = current_user.get("organization_id") or current_user.get("entity_id")
    if not org_id:
        raise HTTPException(status_code=400, detail="Organization ID not found")
    
    # Get employee
    employee = await db_ops.get_one(Collections.EMPLOYEES, {"emp_id": request.emp_id})
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    check_in_time = request.check_in_time or get_pkt_now()
    today = check_in_time.date()
    
    # Check if already checked in
    existing = await db_ops.get_one(Collections.HR_ATTENDANCE, {
        "emp_id": request.emp_id,
        "date": today.isoformat()
    })
    
    if existing and existing.get("check_in"):
        raise HTTPException(status_code=400, detail="Already checked in today")
    
    # Determine status based on check-in time
    expected_time_str = employee.get("office_check_in_time", "09:00")
    grace_minutes = employee.get("grace_period_minutes", 15)
    
    expected_hour, expected_min = parse_time(expected_time_str)
    expected_dt = check_in_time.replace(hour=expected_hour, minute=expected_min, second=0, microsecond=0)
    grace_limit = expected_dt + timedelta(minutes=grace_minutes)
    
    if check_in_time <= expected_dt:
        status = "on_time"
    elif check_in_time <= grace_limit:
        status = "grace"
    else:
        status = "late"
        # Log punctuality violation
        minutes_late = int((check_in_time - expected_dt).total_seconds() / 60)
        await db_ops.create(Collections.HR_PUNCTUALITY_RECORDS, {
            "organization_id": org_id,
            "emp_id": request.emp_id,
            "date": today.isoformat(),
            "violation_type": "late_arrival",
            "minutes_violated": minutes_late,
            "auto_logged": True,
            "created_at": get_pkt_now()
        })
    
    # Create or update attendance
    if existing:
        await db_ops.update_one(
            Collections.HR_ATTENDANCE,
            {"_id": existing["_id"]},
            {
                "check_in": check_in_time,
                "status": status,
                "updated_at": get_pkt_now()
            }
        )
        result = await db_ops.get_by_id(Collections.HR_ATTENDANCE, str(existing["_id"]))
    else:
        result = await db_ops.create(Collections.HR_ATTENDANCE, {
            "organization_id": org_id,
            "emp_id": request.emp_id,
            "date": today.isoformat(),
            "check_in": check_in_time,
            "check_out": None,
            "working_hours": None,
            "status": status,
            "created_at": get_pkt_now(),
            "updated_at": get_pkt_now()
        })
    
    return serialize_doc(result)


@router.post("/attendance/check-out")
async def check_out(request: CheckOutRequest, current_user: dict = Depends(get_current_user)):
    """Employee check-out"""
    org_id = current_user.get("organization_id") or current_user.get("entity_id")
    if not org_id:
        raise HTTPException(status_code=400, detail="Organization ID not found")
    
    check_out_time = request.check_out_time or get_pkt_now()
    today = check_out_time.date()
    
    # Get today's attendance
    attendance = await db_ops.get_one(Collections.HR_ATTENDANCE, {
        "emp_id": request.emp_id,
        "date": today.isoformat()
    })
    
    if not attendance:
        raise HTTPException(status_code=404, detail="No check-in record found for today")
    
    if attendance.get("check_out"):
        raise HTTPException(status_code=400, detail="Already checked out today")
    
    check_in_time = attendance.get("check_in")
    if isinstance(check_in_time, str):
        check_in_time = datetime.fromisoformat(check_in_time.replace('Z', '+00:00'))
    
    # Ensure check_in_time is timezone-aware (PKT)
    if check_in_time.tzinfo is None:
        check_in_time = PKT.localize(check_in_time)
    else:
        check_in_time = check_in_time.astimezone(PKT)
    
    # Get employee expected checkout time
    employee = await db_ops.get_one(Collections.EMPLOYEES, {"emp_id": request.emp_id})
    if not employee:
        # If employee not found, proceed with checkout without early checkout validation
        expected_out_str = "18:00"
    else:
        expected_out_str = employee.get("office_check_out_time", "18:00")
    
    expected_out_hour, expected_out_min = parse_time(expected_out_str)
    expected_out_dt = check_out_time.replace(hour=expected_out_hour, minute=expected_out_min, second=0, microsecond=0)
    
    # Check if checking out early
    if check_out_time < expected_out_dt:
        minutes_early = int((expected_out_dt - check_out_time).total_seconds() / 60)
        if minutes_early > 15:  # More than 15 minutes early
            # Check if there's a pending or approved early checkout request for today
            existing_request = await db_ops.get_one(Collections.HR_LEAVE_REQUESTS, {
                "emp_id": request.emp_id,
                "request_type": "early_checkout",
                "request_date": today.isoformat()
            })
            
            if not existing_request:
                # Need to request approval first
                if not request.reason or not request.reason.strip():
                    raise HTTPException(
                        status_code=400, 
                        detail=f"Early checkout detected ({minutes_early} min early). Please provide a reason for approval."
                    )
                
                # Create early checkout request
                leave_request = await db_ops.create(Collections.HR_LEAVE_REQUESTS, {
                    "organization_id": org_id,
                    "emp_id": request.emp_id,
                    "request_type": "early_checkout",
                    "request_date": today.isoformat(),
                    "start_time": check_out_time,
                    "reason": request.reason.strip(),
                    "status": "pending",
                    "created_at": get_pkt_now(),
                    "updated_at": get_pkt_now()
                })
                
                # Return success response for approval request creation
                return JSONResponse(
                    status_code=202,
                    content={
                        "status": "approval_required",
                        "message": f"Early checkout request submitted for approval. You are checking out {minutes_early} minutes early.",
                        "request_id": str(leave_request.get("_id")),
                        "minutes_early": minutes_early
                    }
                )
            
            elif existing_request.get("status") == "pending":
                return JSONResponse(
                    status_code=202,
                    content={
                        "status": "approval_pending",
                        "message": "Your early checkout request is pending approval. Please wait for manager approval.",
                        "request_id": str(existing_request.get("_id"))
                    }
                )
            
            elif existing_request.get("status") == "rejected":
                raise HTTPException(
                    status_code=400,
                    detail="Your early checkout request was rejected. You cannot check out early."
                )
            
            # If approved, allow checkout and log punctuality violation
            if existing_request.get("status") == "approved":
                await db_ops.create(Collections.HR_PUNCTUALITY_RECORDS, {
                    "organization_id": org_id,
                    "emp_id": request.emp_id,
                    "date": today.isoformat(),
                    "violation_type": "early_leave",
                    "minutes_violated": minutes_early,
                    "auto_logged": True,
                    "notes": f"Approved early checkout. Reason: {existing_request.get('reason')}",
                    "created_at": get_pkt_now()
                })
    
    # Calculate working hours
    working_duration = check_out_time - check_in_time
    working_hours = working_duration.total_seconds() / 3600
    
    # Determine final status
    status = attendance.get("status", "present")
    if working_hours < 4:
        status = "half_day"
    
    # Update attendance
    await db_ops.update_one(
        Collections.HR_ATTENDANCE,
        {"_id": attendance["_id"]},
        {
            "check_out": check_out_time,
            "working_hours": round(working_hours, 2),
            "status": status,
            "updated_at": get_pkt_now()
        }
    )
    
    result = await db_ops.get_by_id(Collections.HR_ATTENDANCE, str(attendance["_id"]))
    return serialize_doc(result)


@router.get("/attendance")
async def get_attendance(
    current_user: dict = Depends(get_current_user),
    emp_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    status: Optional[str] = None
):
    """Get attendance records"""
    org_id = current_user.get("organization_id") or current_user.get("entity_id")
    if not org_id:
        raise HTTPException(status_code=400, detail="Organization ID not found")

    if emp_id:
        # Single employee: query by emp_id only — no org filter needed
        query = {"emp_id": emp_id}
    else:
        # Filter by branch or org
        allowed_emp_ids = await get_allowed_emp_ids(current_user, org_id)
        if not allowed_emp_ids:
            return []
        query = {"emp_id": {"$in": allowed_emp_ids}}

    if start_date and end_date:
        query["date"] = {"$gte": start_date, "$lte": end_date}
    elif start_date:
        query["date"] = {"$gte": start_date}
    elif end_date:
        query["date"] = {"$lte": end_date}
    if status:
        query["status"] = status

    records = await db_ops.get_all(Collections.HR_ATTENDANCE, query)
    return serialize_docs(records)



@router.get("/attendance/today/{emp_id}")
async def get_today_attendance(emp_id: str, current_user: dict = Depends(get_current_user)):
    """Get today's attendance record for a specific employee.
    Queries only by emp_id + today's date — no organization_id filter —
    so it works regardless of which token (admin or employee) created the record.
    """
    today = date.today().isoformat()
    record = await db_ops.get_one(Collections.HR_ATTENDANCE, {
        "emp_id": emp_id,
        "date": today
    })
    if not record:
        return {"status": "not_checked_in", "check_in": None, "check_out": None, "date": today}
    return serialize_doc(record)




# ===================== Movement Management =====================
@router.post("/movements/start")
async def start_movement(request: StartMovementRequest, current_user: dict = Depends(get_current_user)):
    """Start employee movement"""
    org_id = current_user.get("organization_id") or current_user.get("entity_id")
    if not org_id:
        raise HTTPException(status_code=400, detail="Organization ID not found")
    
    start_time = request.start_time or get_pkt_now()
    
    # Check for active movement
    active_movement = await db_ops.get_one(Collections.HR_MOVEMENT_LOGS, {
        "emp_id": request.emp_id,
        "status": "active"
    })
    
    if active_movement:
        raise HTTPException(status_code=400, detail="Employee has an active movement")
    
    movement = await db_ops.create(Collections.HR_MOVEMENT_LOGS, {
        "organization_id": org_id,
        "emp_id": request.emp_id,
        "date": start_time.date().isoformat(),
        "start_time": start_time,
        "end_time": None,
        "reason": request.reason,
        "destination": request.destination,
        "status": "active",
        "created_at": get_pkt_now(),
        "updated_at": get_pkt_now()
    })
    
    return serialize_doc(movement)


@router.post("/movements/end")
async def end_movement(request: EndMovementRequest, current_user: dict = Depends(get_current_user)):
    """End employee movement"""
    movement = await db_ops.get_by_id(Collections.HR_MOVEMENT_LOGS, request.movement_id)
    if not movement:
        raise HTTPException(status_code=404, detail="Movement not found")
    
    if movement.get("status") != "active":
        raise HTTPException(status_code=400, detail="Movement is not active")
    
    end_time = request.end_time or get_pkt_now()
    
    await db_ops.update_one(
        Collections.HR_MOVEMENT_LOGS,
        {"_id": ObjectId(request.movement_id)},
        {
            "end_time": end_time,
            "status": "completed",
            "updated_at": get_pkt_now()
        }
    )
    
    result = await db_ops.get_by_id(Collections.HR_MOVEMENT_LOGS, request.movement_id)
    return serialize_doc(result)


@router.get("/movements")
async def get_movements(
    current_user: dict = Depends(get_current_user),
    emp_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    status: Optional[str] = None
):
    """Get movement logs"""
    org_id = current_user.get("organization_id") or current_user.get("entity_id")
    if not org_id:
        raise HTTPException(status_code=400, detail="Organization ID not found")
    
    allowed_emp_ids = await get_allowed_emp_ids(current_user, org_id)
    if not allowed_emp_ids: return []
    query = {"organization_id": org_id}
    if emp_id:
        if emp_id not in allowed_emp_ids: return []
        query["emp_id"] = emp_id
    else:
        query["emp_id"] = {"$in": allowed_emp_ids}
    if start_date and end_date:
        query["date"] = {"$gte": start_date, "$lte": end_date}
    if status:
        query["status"] = status
    
    records = await db_ops.get_all(Collections.HR_MOVEMENT_LOGS, query)
    
    # Populate employee information for each movement
    for record in records:
        if record.get("emp_id"):
            employee = await db_ops.get_one(Collections.EMPLOYEES, {"emp_id": record["emp_id"]})
            if employee:
                record["employee"] = {
                    "emp_id": employee.get("emp_id"),
                    "full_name": employee.get("full_name") or employee.get("name"),
                    "name": employee.get("name"),
                    "phone": employee.get("phone"),
                    "designation": employee.get("designation"),
                    "role": employee.get("role")
                }
    
    return serialize_docs(records)


# ===================== Leave Requests =====================
@router.post("/leave-requests")
async def create_leave_request(
    request: LeaveRequestCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create leave request"""
    leave_request = await db_ops.create(Collections.HR_LEAVE_REQUESTS, {
        **request.dict(),
        "created_at": get_pkt_now(),
        "updated_at": get_pkt_now()
    })
    return serialize_doc(leave_request)


@router.get("/leave-requests")
async def get_leave_requests(
    current_user: dict = Depends(get_current_user),
    emp_id: Optional[str] = None,
    status: Optional[str] = None,
    request_type: Optional[str] = None
):
    """Get leave requests"""
    org_id = current_user.get("organization_id") or current_user.get("entity_id")
    if not org_id:
        raise HTTPException(status_code=400, detail="Organization ID not found")
    
    allowed_emp_ids = await get_allowed_emp_ids(current_user, org_id)
    if not allowed_emp_ids: return []
    query = {"organization_id": org_id}
    if emp_id:
        if emp_id not in allowed_emp_ids: return []
        query["emp_id"] = emp_id
    else:
        query["emp_id"] = {"$in": allowed_emp_ids}
    if status:
        query["status"] = status
    if request_type:
        query["request_type"] = request_type
    
    records = await db_ops.get_all(Collections.HR_LEAVE_REQUESTS, query)
    return serialize_docs(records)


@router.post("/leave-requests/{request_id}/approve")
async def approve_leave_request(
    request_id: str,
    approval: ApproveLeaveRequest,
    current_user: dict = Depends(get_current_user)
):
    """Approve leave request"""
    leave_request = await db_ops.get_by_id(Collections.HR_LEAVE_REQUESTS, request_id)
    if not leave_request:
        raise HTTPException(status_code=404, detail="Leave request not found")
    
    if leave_request.get("status") != "pending":
        raise HTTPException(status_code=400, detail="Leave request is not pending")
    
    # Update leave request
    await db_ops.update_one(
        Collections.HR_LEAVE_REQUESTS,
        {"_id": ObjectId(request_id)},
        {
            "status": "approved",
            "approved_by": approval.approved_by,
            "approved_at": get_pkt_now(),
            "approval_notes": approval.approval_notes,
            "updated_at": get_pkt_now()
        }
    )
    
    # If early checkout, update attendance
    if leave_request.get("request_type") == "early_checkout":
        request_date = leave_request.get("request_date")
        if isinstance(request_date, str):
            request_date = datetime.fromisoformat(request_date).date()
        
        attendance = await db_ops.get_one(Collections.HR_ATTENDANCE, {
            "emp_id": leave_request.get("emp_id"),
            "date": request_date.isoformat() if hasattr(request_date, 'isoformat') else request_date
        })
        
        if attendance and not attendance.get("check_out"):
            # Auto check-out at the requested time or current time
            checkout_time = leave_request.get("start_time") or get_pkt_now()
            if isinstance(checkout_time, str):
                checkout_time = datetime.fromisoformat(checkout_time)
            
            check_in = attendance.get("check_in")
            if isinstance(check_in, str):
                check_in = datetime.fromisoformat(check_in)
            
            # Ensure both datetimes are timezone-aware
            if check_in.tzinfo is None:
                check_in = PKT.localize(check_in)
            if checkout_time.tzinfo is None:
                checkout_time = PKT.localize(checkout_time)
            
            working_hours = (checkout_time - check_in).total_seconds() / 3600
            
            await db_ops.update_one(
                Collections.HR_ATTENDANCE,
                {"_id": attendance["_id"]},
                {
                    "check_out": checkout_time,
                    "working_hours": round(working_hours, 2),
                    "status": "half_day" if working_hours < 4 else "present",
                    "updated_at": get_pkt_now()
                }
            )
    
    result = await db_ops.get_by_id(Collections.HR_LEAVE_REQUESTS, request_id)
    return serialize_doc(result)


@router.post("/leave-requests/{request_id}/reject")
async def reject_leave_request(
    request_id: str,
    approval: ApproveLeaveRequest,
    current_user: dict = Depends(get_current_user)
):
    """Reject leave request"""
    leave_request = await db_ops.get_by_id(Collections.HR_LEAVE_REQUESTS, request_id)
    if not leave_request:
        raise HTTPException(status_code=404, detail="Leave request not found")
    
    if leave_request.get("status") != "pending":
        raise HTTPException(status_code=400, detail="Leave request is not pending")
    
    await db_ops.update_one(
        Collections.HR_LEAVE_REQUESTS,
        {"_id": ObjectId(request_id)},
        {
            "status": "rejected",
            "approved_by": approval.approved_by,
            "approved_at": get_pkt_now(),
            "approval_notes": approval.approval_notes,
            "updated_at": get_pkt_now()
        }
    )
    
    result = await db_ops.get_by_id(Collections.HR_LEAVE_REQUESTS, request_id)
    return serialize_doc(result)


# ===================== Punctuality =====================
@router.get("/punctuality")
async def get_punctuality(
    current_user: dict = Depends(get_current_user),
    emp_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """Get punctuality records"""
    org_id = current_user.get("organization_id") or current_user.get("entity_id")
    if not org_id:
        raise HTTPException(status_code=400, detail="Organization ID not found")
    
    allowed_emp_ids = await get_allowed_emp_ids(current_user, org_id)
    if not allowed_emp_ids: return []
    query = {"organization_id": org_id}
    if emp_id:
        if emp_id not in allowed_emp_ids: return []
        query["emp_id"] = emp_id
    else:
        query["emp_id"] = {"$in": allowed_emp_ids}
    if start_date and end_date:
        query["date"] = {"$gte": start_date, "$lte": end_date}
    
    records = await db_ops.get_all(Collections.HR_PUNCTUALITY_RECORDS, query)
    return serialize_docs(records)


# ===================== Fines =====================
@router.post("/fines")
async def create_fine(fine: FineCreate, current_user: dict = Depends(get_current_user)):
    """Create a fine"""
    result = await db_ops.create(Collections.HR_FINES, {
        **fine.dict(),
        "created_at": get_pkt_now()
    })
    return serialize_doc(result)


@router.get("/fines")
async def get_fines(
    current_user: dict = Depends(get_current_user),
    emp_id: Optional[str] = None,
    month: Optional[str] = None
):
    """Get fines"""
    org_id = current_user.get("organization_id") or current_user.get("entity_id")
    if not org_id:
        raise HTTPException(status_code=400, detail="Organization ID not found")
    
    allowed_emp_ids = await get_allowed_emp_ids(current_user, org_id)
    if not allowed_emp_ids: return []
    query = {"organization_id": org_id}
    if emp_id:
        if emp_id not in allowed_emp_ids: return []
        query["emp_id"] = emp_id
    else:
        query["emp_id"] = {"$in": allowed_emp_ids}
    if month:
        query["applied_to_salary_month"] = month
    
    records = await db_ops.get_all(Collections.HR_FINES, query)
    return serialize_docs(records)


# ===================== Salary Payments =====================
@router.post("/salaries/auto-generate")
async def auto_generate_due_salaries(current_user: dict = Depends(get_current_user)):
    """Auto-generate salaries for employees based on their join date"""
    org_id = current_user.get("organization_id") or current_user.get("entity_id")
    if not org_id:
        raise HTTPException(status_code=400, detail="Organization ID not found")
    
    today = date.today()
    current_day = today.day
    current_month_str = today.strftime("%Y-%m")
    
    # Get all active employees mapped accurately to branch/org
    entity_id = current_user.get("branch_id") if current_user.get("role") == "branch" else org_id
    entity_type = "branch" if current_user.get("role") == "branch" else "organization"
    employees = await db_ops.get_all(Collections.EMPLOYEES, {
        "entity_id": entity_id,
        "entity_type": entity_type,
        "is_active": True
    })
    
    generated_count = 0
    skipped_count = 0
    
    for emp in employees:
        emp_id = emp.get("emp_id")
        if not emp_id:
            continue
        
        # Get employee's join date
        join_date = emp.get("join_date")
        if not join_date:
            skipped_count += 1
            continue
        
        # Parse join date
        if isinstance(join_date, str):
            try:
                join_date = datetime.fromisoformat(join_date).date()
            except:
                skipped_count += 1
                continue
        
        # Determine salary payment day (day of month from join date)
        salary_day = join_date.day
        
        # Check if salary is due (current day >= salary day)
        if current_day < salary_day:
            # Salary not due yet this month
            continue
        
        # Check if salary already generated for current month
        existing = await db_ops.get_one(Collections.HR_SALARY_PAYMENTS, {
            "emp_id": emp_id,
            "month": current_month_str
        })
        
        if existing:
            # Already generated
            continue
        
        # Check if employee has been with company for at least a month
        months_employed = (today.year - join_date.year) * 12 + (today.month - join_date.month)
        if months_employed < 1:
            # Employee joined this month, skip first month
            continue
        
        # Get base salary
        base_salary = emp.get("base_salary", 0)
        
        # Calculate commissions (from separate commission system if exists)
        commission_total = 0.0
        
        # Calculate fines for this month
        fines = await db_ops.get_all(Collections.HR_FINES, {
            "emp_id": emp_id,
            "applied_to_salary_month": current_month_str
        })
        fine_deductions = sum(f.get("amount", 0) for f in fines)
        
        # Calculate net salary
        net_salary = base_salary + commission_total - fine_deductions
        
        # Expected payment date is the salary day of current month
        try:
            expected_payment_date = date(today.year, today.month, salary_day)
        except ValueError:
            # Handle case where salary_day > days in current month
            # Use last day of month
            import calendar
            last_day = calendar.monthrange(today.year, today.month)[1]
            expected_payment_date = date(today.year, today.month, last_day)
        
        # Create salary payment record
        await db_ops.create(Collections.HR_SALARY_PAYMENTS, {
            "organization_id": org_id,
            "emp_id": emp_id,
            "month": current_month_str,
            "base_salary": base_salary,
            "commission_total": commission_total,
            "fine_deductions": fine_deductions,
            "other_deductions": 0.0,
            "bonuses": 0.0,
            "net_salary": net_salary,
            "status": "pending",
            "expected_payment_date": expected_payment_date.isoformat(),
            "actual_payment_date": None,
            "days_late": 0,
            "salary_day": salary_day,
            "created_at": get_pkt_now(),
            "updated_at": get_pkt_now()
        })
        generated_count += 1
    
    return {
        "status": "success",
        "generated_count": generated_count,
        "skipped_count": skipped_count,
        "month": current_month_str,
        "message": f"Auto-generated {generated_count} salaries for {current_month_str}"
    }


@router.get("/salaries")
async def get_salaries(
    current_user: dict = Depends(get_current_user),
    emp_id: Optional[str] = None,
    month: Optional[str] = None,
    status: Optional[str] = None
):
    """Get salary payments"""
    org_id = current_user.get("organization_id") or current_user.get("entity_id")
    if not org_id:
        raise HTTPException(status_code=400, detail="Organization ID not found")
    
    allowed_emp_ids = await get_allowed_emp_ids(current_user, org_id)
    if not allowed_emp_ids: return []
    query = {"organization_id": org_id}
    if emp_id:
        if emp_id not in allowed_emp_ids: return []
        query["emp_id"] = emp_id
    else:
        query["emp_id"] = {"$in": allowed_emp_ids}
    if month:
        query["month"] = month
    if status:
        query["status"] = status
    
    records = await db_ops.get_all(Collections.HR_SALARY_PAYMENTS, query)
    return serialize_docs(records)


@router.post("/salaries/{salary_id}/mark-paid")
async def mark_salary_paid(
    salary_id: str,
    payment_date: Optional[str] = None,
    payment_method: Optional[str] = None,
    payment_reference: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Mark salary as paid"""
    salary = await db_ops.get_by_id(Collections.HR_SALARY_PAYMENTS, salary_id)
    if not salary:
        raise HTTPException(status_code=404, detail="Salary record not found")
    
    actual_payment_date = payment_date or date.today().isoformat()
    
    # Calculate days late
    expected_date = salary.get("expected_payment_date")
    if expected_date:
        if isinstance(expected_date, str):
            expected_date = datetime.fromisoformat(expected_date).date()
        actual_date = datetime.fromisoformat(actual_payment_date).date()
        days_late = max(0, (actual_date - expected_date).days)
    else:
        days_late = 0
    
    await db_ops.update_one(
        Collections.HR_SALARY_PAYMENTS,
        {"_id": ObjectId(salary_id)},
        {
            "status": "paid",
            "actual_payment_date": actual_payment_date,
            "days_late": days_late,
            "payment_method": payment_method,
            "payment_reference": payment_reference,
            "updated_at": get_pkt_now()
        }
    )
    
    result = await db_ops.get_by_id(Collections.HR_SALARY_PAYMENTS, salary_id)
    return serialize_doc(result)


@router.put("/salaries/{salary_id}")
async def update_salary(
    salary_id: str,
    salary_data: SalaryPaymentUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update salary payment details"""
    salary = await db_ops.get_by_id(Collections.HR_SALARY_PAYMENTS, salary_id)
    if not salary:
        raise HTTPException(status_code=404, detail="Salary record not found")
    
    update_data = salary_data.dict(exclude_unset=True)
    if update_data:
        update_data["updated_at"] = get_pkt_now()
        
        # Recalculate net salary if components changed
        if any(k in update_data for k in ["commission_total", "fine_deductions", "other_deductions", "bonuses"]):
            base_salary = salary.get("base_salary", 0)
            commission = update_data.get("commission_total", salary.get("commission_total", 0))
            fines = update_data.get("fine_deductions", salary.get("fine_deductions", 0))
            other_ded = update_data.get("other_deductions", salary.get("other_deductions", 0))
            bonuses = update_data.get("bonuses", salary.get("bonuses", 0))
            update_data["net_salary"] = base_salary + commission + bonuses - fines - other_ded
        
        await db_ops.update_one(
            Collections.HR_SALARY_PAYMENTS,
            {"_id": ObjectId(salary_id)},
            update_data
        )
    
    result = await db_ops.get_by_id(Collections.HR_SALARY_PAYMENTS, salary_id)
    return serialize_doc(result)


# ===================== Employee Ledger =====================
@router.get("/employees/{emp_id}/ledger")
async def get_employee_ledger(
    emp_id: str,
    current_user: dict = Depends(get_current_user),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """Get employee financial ledger"""
    # Get all salary payments
    query = {"emp_id": emp_id}
    if start_date and end_date:
        # Filter by month if dates provided
        pass
    
    salaries = await db_ops.get_all(Collections.HR_SALARY_PAYMENTS, query)
    
    # Build ledger entries
    ledger = []
    running_balance = 0.0
    
    for salary in sorted(salaries, key=lambda x: x.get("month", "")):
        month = salary.get("month")
        
        # Credit: Salary accrual
        accrual_entry = {
            "date": f"{month}-01",
            "type": "credit",
            "category": "salary_accrual",
            "description": f"Salary for {month}",
            "amount": salary.get("base_salary", 0),
            "balance": 0
        }
        running_balance += accrual_entry["amount"]
        accrual_entry["balance"] = running_balance
        ledger.append(accrual_entry)
        
        # Credit: Commission
        if salary.get("commission_total", 0) > 0:
            comm_entry = {
                "date": f"{month}-01",
                "type": "credit",
                "category": "commission",
                "description": f"Commission for {month}",
                "amount": salary.get("commission_total", 0),
                "balance": 0
            }
            running_balance += comm_entry["amount"]
            comm_entry["balance"] = running_balance
            ledger.append(comm_entry)
        
        # Debit: Fines
        if salary.get("fine_deductions", 0) > 0:
            fine_entry = {
                "date": f"{month}-01",
                "type": "debit",
                "category": "fine",
                "description": f"Fines for {month}",
                "amount": salary.get("fine_deductions", 0),
                "balance": 0
            }
            running_balance -= fine_entry["amount"]
            fine_entry["balance"] = running_balance
            ledger.append(fine_entry)
        
        # Debit: Payment
        if salary.get("status") == "paid":
            payment_entry = {
                "date": salary.get("actual_payment_date") or f"{month}-01",
                "type": "debit",
                "category": "payment",
                "description": f"Salary payment for {month}",
                "amount": salary.get("net_salary", 0),
                "balance": 0
            }
            running_balance -= payment_entry["amount"]
            payment_entry["balance"] = running_balance
            ledger.append(payment_entry)
    
    return {
        "emp_id": emp_id,
        "ledger": ledger,
        "current_balance": running_balance
    }


# ===================== Punctuality Analytics =====================
@router.get("/punctuality/analytics")
async def get_punctuality_analytics(
    current_user: dict = Depends(get_current_user),
    emp_id: Optional[str] = Query(None, description="Filter by specific employee"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)")
):
    """Get punctuality analytics with statistics and employee-wise breakdown"""
    org_id = current_user.get("organization_id") or current_user.get("entity_id")
    if not org_id:
        raise HTTPException(status_code=400, detail="Organization ID not found")
    
    # Set default date range to last 30 days if not provided
    if not end_date:
        end_date = date.today().isoformat()
    if not start_date:
        start_date = (date.today() - timedelta(days=30)).isoformat()
    
    allowed_emp_ids = await get_allowed_emp_ids(current_user, org_id)
    if not allowed_emp_ids:
        return {
            "statistics": {
                "total_late_arrivals": 0, "total_grace_usage": 0,
                "total_absences": 0, "total_early_leaves": 0,
                "overall_punctuality_score": 0
            },
            "employees": []
        }

    # Build query using allowed_emp_ids for isolation
    attendance_query = {
        "emp_id": {"$in": allowed_emp_ids},
        "date": {"$gte": start_date, "$lte": end_date}
    }
    punctuality_query = {
        "emp_id": {"$in": allowed_emp_ids},
        "date": {"$gte": start_date, "$lte": end_date}
    }
    
    if emp_id:
        if emp_id not in allowed_emp_ids:
            return {"statistics": {}, "employees": []}
        attendance_query["emp_id"] = emp_id
        punctuality_query["emp_id"] = emp_id
    
    # Get all attendance and punctuality records
    attendance_records = await db_ops.get_all(Collections.HR_ATTENDANCE, attendance_query)
    punctuality_records = await db_ops.get_all(Collections.HR_PUNCTUALITY_RECORDS, punctuality_query)
    
    # Get all employees accurately mapped to branch/org
    entity_id = current_user.get("branch_id") if current_user.get("role") == "branch" else org_id
    entity_type = "branch" if current_user.get("role") == "branch" else "organization"
    emp_query = {
        "entity_id": entity_id,
        "entity_type": entity_type,
        "is_active": True
    }
    if emp_id:
        emp_query["emp_id"] = emp_id
    
    employees = await db_ops.get_all(Collections.EMPLOYEES, emp_query)
    
    # Calculate overall statistics
    total_late_arrivals = len([r for r in punctuality_records if r.get("violation_type") == "late_arrival"])
    total_grace_usage = len([a for a in attendance_records if a.get("status") == "grace"])
    total_absences = len([r for r in punctuality_records if r.get("violation_type") == "absence"])
    total_early_leaves = len([r for r in punctuality_records if r.get("violation_type") == "early_leave"])
    
    # Calculate employee-wise data
    employee_data = []
    total_punctuality_score = 0
    employees_with_score = 0
    
    for emp in employees:
        emp_id_val = emp.get("emp_id")
        
        # Get attendance for this employee
        emp_attendance = [a for a in attendance_records if a.get("emp_id") == emp_id_val]
        working_days = len([a for a in emp_attendance if a.get("status") != "absent"])
        
        # Get violations for this employee
        emp_violations = [v for v in punctuality_records if v.get("emp_id") == emp_id_val]
        
        # Count violation types
        late_count = len([v for v in emp_violations if v.get("violation_type") == "late_arrival"])
        early_leave_count = len([v for v in emp_violations if v.get("violation_type") == "early_leave"])
        absence_count = len([v for v in emp_violations if v.get("violation_type") == "absence"])
        grace_count = len([a for a in emp_attendance if a.get("status") == "grace"])
        
        total_violations = late_count + early_leave_count + absence_count
        
        # Calculate punctuality score
        # Formula: Max(0, 100 - (late*5 + early_leave*5 + absence*10 + grace*1))
        # Or simpler: (working_days - violations) / max(working_days, 1) * 100
        total_days = len(emp_attendance)
        if total_days > 0:
            punctuality_score = max(0, ((total_days - total_violations) / total_days) * 100)
            total_punctuality_score += punctuality_score
            employees_with_score += 1
        else:
            punctuality_score = 0
        
        # Build violations summary
        violations_summary = []
        if late_count > 0:
            violations_summary.append(f"{late_count} Late")
        if early_leave_count > 0:
            violations_summary.append(f"{early_leave_count} Early Leave")
        if absence_count > 0:
            violations_summary.append(f"{absence_count} Absent")
        if grace_count > 0:
            violations_summary.append(f"{grace_count} Grace")
        
        violations_text = ", ".join(violations_summary) if violations_summary else "No violations"
        
        employee_data.append({
            "emp_id": emp_id_val,
            "full_name": emp.get("full_name") or emp.get("name") or "Unknown",
            "designation": emp.get("designation", ""),
            "working_days": working_days,
            "total_days": total_days,
            "violations": {
                "late": late_count,
                "early_leave": early_leave_count,
                "absence": absence_count,
                "grace": grace_count,
                "total": total_violations,
                "summary": violations_text
            },
            "punctuality_score": round(punctuality_score, 1)
        })
    
    # Calculate average punctuality
    avg_punctuality = round(total_punctuality_score / employees_with_score, 1) if employees_with_score > 0 else 0
    
    return {
        "statistics": {
            "violation_rate": total_late_arrivals + total_early_leaves,
            "grace_usage": total_grace_usage,
            "absenteeism": total_absences,
            "average_punctuality": avg_punctuality
        },
        "date_range": {
            "start_date": start_date,
            "end_date": end_date
        },
        "employees": employee_data
    }


# ===================== Salary Statistics =====================
@router.get("/salaries/statistics")
async def get_salary_statistics(
    current_user: dict = Depends(get_current_user),
    month: Optional[str] = Query(None, description="Filter by specific month (YYYY-MM)")
):
    """Get salary payment statistics"""
    org_id = current_user.get("organization_id") or current_user.get("entity_id")
    if not org_id:
        raise HTTPException(status_code=400, detail="Organization ID not found")
    
    allowed_emp_ids = await get_allowed_emp_ids(current_user, org_id)
    if not allowed_emp_ids:
        return {
            "total_pending": 0, "total_paid": 0, "total_records": 0,
            "overdue_count": 0, "pending_count": 0, "paid_count": 0
        }

    query = {"emp_id": {"$in": allowed_emp_ids}}
    if month:
        query["month"] = month
    
    # Get all salary records
    all_salaries = await db_ops.get_all(Collections.HR_SALARY_PAYMENTS, query)
    
    # Calculate statistics
    total_pending_amount = 0
    total_paid_amount = 0
    overdue_count = 0
    today = date.today()
    
    for salary in all_salaries:
        net_salary = salary.get("net_salary", 0)
        status = salary.get("status", "pending")
        
        if status == "paid":
            total_paid_amount += net_salary
        elif status == "pending":
            total_pending_amount += net_salary
            
            # Check if overdue
            expected_date_str = salary.get("expected_payment_date")
            if expected_date_str:
                try:
                    if isinstance(expected_date_str, str):
                        expected_date = datetime.fromisoformat(expected_date_str).date()
                    else:
                        expected_date = expected_date_str
                    
                    if today > expected_date:
                        overdue_count += 1
                except (ValueError, AttributeError):
                    pass
    
    return {
        "total_pending": total_pending_amount,
        "total_paid": total_paid_amount,
        "total_records": len(all_salaries),
        "overdue_count": overdue_count,
        "pending_count": len([s for s in all_salaries if s.get("status") == "pending"]),
        "paid_count": len([s for s in all_salaries if s.get("status") == "paid"])
    }

