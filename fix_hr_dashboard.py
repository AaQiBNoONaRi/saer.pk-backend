import sys

with open('app/routes/hr.py', 'r') as f:
    content = f.read()

# Replace total employees query
old_total_emp = '''    # Total employees
    total_employees = await db_ops.count(Collections.EMPLOYEES, {
        "entity_id": org_id,
        "entity_type": "organization",
        "is_active": True
    })'''
new_total_emp = '''    # Filter by branch or org
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
    })'''
content = content.replace(old_total_emp, new_total_emp)

# Replace today_attendance
old_att = '''    # Today's attendance
    today_attendance = await db_ops.get_all(Collections.HR_ATTENDANCE, {
        "organization_id": org_id,
        "date": today.isoformat()
    })'''
new_att = '''    # Today's attendance
    today_attendance = await db_ops.get_all(Collections.HR_ATTENDANCE, {
        "emp_id": {"$in": allowed_emp_ids},
        "date": today.isoformat()
    })'''
content = content.replace(old_att, new_att)

# Replace financial stats
old_fin = '''    # Financial stats
    salaries_this_month = await db_ops.get_all(Collections.HR_SALARY_PAYMENTS, {
        "organization_id": org_id,
        "month": current_month
    })'''
new_fin = '''    # Financial stats
    salaries_this_month = await db_ops.get_all(Collections.HR_SALARY_PAYMENTS, {
        "emp_id": {"$in": allowed_emp_ids},
        "month": current_month
    })'''
content = content.replace(old_fin, new_fin)

# Replace pending approvals
old_pending = '''    # Pending approvals
    pending_leave_requests = await db_ops.count(Collections.HR_LEAVE_REQUESTS, {
        "organization_id": org_id,
        "status": "pending"
    })'''
new_pending = '''    # Pending approvals
    pending_leave_requests = await db_ops.count(Collections.HR_LEAVE_REQUESTS, {
        "emp_id": {"$in": allowed_emp_ids},
        "status": "pending"
    })'''
content = content.replace(old_pending, new_pending)

# Replace movements
old_movements = '''    # Total movements today
    total_movements_today = await db_ops.count(Collections.HR_MOVEMENT_LOGS, {
        "organization_id": org_id,
        "date": today.isoformat()
    })'''
new_movements = '''    # Total movements today
    total_movements_today = await db_ops.count(Collections.HR_MOVEMENT_LOGS, {
        "emp_id": {"$in": allowed_emp_ids},
        "date": today.isoformat()
    })'''
content = content.replace(old_movements, new_movements)

# Replace commissions
old_comm = '''    # Total commissions this month
    commissions_this_month = await db_ops.get_all(Collections.HR_SALARY_PAYMENTS, {
        "organization_id": org_id,
        "month": current_month
    })'''
new_comm = '''    # Total commissions this month
    commissions_this_month = await db_ops.get_all(Collections.HR_SALARY_PAYMENTS, {
        "emp_id": {"$in": allowed_emp_ids},
        "month": current_month
    })'''
content = content.replace(old_comm, new_comm)

with open('app/routes/hr.py', 'w') as f:
    f.write(content)

print("Dashboard stats replacements done")
