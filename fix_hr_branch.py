import re

with open('app/routes/hr.py', 'r') as f:
    content = f.read()

# 1. Add helper function
helper_code = '''
async def get_allowed_emp_ids(current_user: dict, org_id: str) -> list:
    \"\"\"Get list of employee IDs the current user is allowed to see (branch or org)\"\"\"
    entity_id = current_user.get("branch_id") if current_user.get("role") == "branch" else org_id
    entity_type = "branch" if current_user.get("role") == "branch" else "organization"
    employees = await db_ops.get_all(
        Collections.EMPLOYEES,
        {"entity_id": entity_id, "entity_type": entity_type}
    )
    return [e["emp_id"] for e in employees if e.get("emp_id")]

# ===================== Dashboard Stats =====================
'''
content = content.replace('\n# ===================== Dashboard Stats =====================\n', '\n' + helper_code)

# 2. Fix get_hr_employees
old_employees = '''    # Query by entity_id and entity_type since employees are stored this way
    query = {
        "entity_id": org_id,
        "entity_type": "organization"
    }'''
new_employees = '''    # Query by entity_id and entity_type since employees are stored this way
    entity_id = current_user.get("branch_id") if current_user.get("role") == "branch" else org_id
    entity_type = "branch" if current_user.get("role") == "branch" else "organization"
    query = {
        "entity_id": entity_id,
        "entity_type": entity_type
    }'''
content = content.replace(old_employees, new_employees)

# 3. Fix get_attendance
old_attendance = '''        # Org-wide query: find all emp_ids for this org, then query attendance by those IDs.
        # This avoids the organization_id mismatch (records may have been created by employee
        # tokens whose entity_id differs from the admin's entity_id).
        org_employees = await db_ops.get_all(
            Collections.EMPLOYEES,
            {"entity_id": org_id, "entity_type": "organization"}
        )
        org_emp_ids = [e["emp_id"] for e in org_employees if e.get("emp_id")]
        if not org_emp_ids:
            return []
        query = {"emp_id": {"": org_emp_ids}}'''

new_attendance = '''        # Filter by branch or org
        allowed_emp_ids = await get_allowed_emp_ids(current_user, org_id)
        if not allowed_emp_ids:
            return []
        query = {"emp_id": {"": allowed_emp_ids}}'''
content = content.replace(old_attendance, new_attendance)

# 4. Fix get_movements
old_movements = '''    query = {"organization_id": org_id}
    if emp_id:
        query["emp_id"] = emp_id'''
new_movements = '''    allowed_emp_ids = await get_allowed_emp_ids(current_user, org_id)
    if not allowed_emp_ids: return []
    query = {"organization_id": org_id}
    if emp_id:
        if emp_id not in allowed_emp_ids: return []
        query["emp_id"] = emp_id
    else:
        query["emp_id"] = {"": allowed_emp_ids}'''
content = content.replace(old_movements, new_movements)

# 5. Fix get_leave_requests
old_leaves = '''    query = {"organization_id": org_id}
    if emp_id:
        query["emp_id"] = emp_id'''
content = content.replace(old_leaves, new_movements)

# 6. Fix get_punctuality
old_punctuality = '''    query = {"organization_id": org_id}
    if emp_id:
        query["emp_id"] = emp_id'''
content = content.replace(old_punctuality, new_movements)

# 7. Fix get_fines
old_fines = '''    query = {"organization_id": org_id}
    if emp_id:
        query["emp_id"] = emp_id'''
content = content.replace(old_fines, new_movements)

# 8. Fix get_salaries
old_salaries = '''    query = {"organization_id": org_id}
    if emp_id:
        query["emp_id"] = emp_id'''
content = content.replace(old_salaries, new_movements)

# 9. Fix get_dashboard_stats  - Wait, this is longer. Let's do it manually.
with open('app/routes/hr.py', 'w') as f:
    f.write(content)
print("Basic replacements done")
