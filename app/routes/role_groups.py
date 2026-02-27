"""
Role Groups (Permissions) Routes
Org creates named permission groups using flat permission codes,
then assigns a group to an employee when creating / editing.
"""
from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional, List, Any
from datetime import datetime
from pydantic import BaseModel
from app.database.db_operations import db_ops
from app.utils.helpers import serialize_doc, serialize_docs
from app.utils.auth import get_current_user

router = APIRouter(prefix="/role-groups", tags=["Role Groups"])

# ---------------------------------------------------------------------------
# Enterprise RBAC Permission Catalogue
# Organization → Branch → Agency → Employee Hierarchy
# Each module supports: view, add, update, delete, all
# ---------------------------------------------------------------------------

def build_module_permissions(module_code, module_label):
    """Build standardized CRUD permissions for a module"""
    return [
        {"code": f"{module_code}.view", "label": f"View {module_label}"},
        {"code": f"{module_code}.add", "label": f"Add {module_label}"},
        {"code": f"{module_code}.update", "label": f"Update {module_label}"},
        {"code": f"{module_code}.delete", "label": f"Delete {module_label}"},
        {"code": f"{module_code}.all", "label": f"Full Access to {module_label}"},
    ]

def build_payments_permissions(module_code, module_label):
    """Build view+add only permissions for payments module"""
    return [
        {"code": f"{module_code}.view", "label": f"View {module_label}"},
        {"code": f"{module_code}.add", "label": f"Add {module_label}"},
    ]

PERMISSION_CATALOGUE = [
    # 🗂 INVENTORY MODULE
    {
        "category": "Inventory",
        "icon": "📦",
        "description": "Manage stock items (Packages, Hotels, Tickets, Flights, Others)",
        "subcategories": [
            {"label": "Packages", "permissions": build_module_permissions("inventory.packages", "Packages")},
            {"label": "Hotels", "permissions": build_module_permissions("inventory.hotels", "Hotels")},
            {"label": "Tickets", "permissions": build_module_permissions("inventory.tickets", "Tickets")},
            {"label": "Flights", "permissions": build_module_permissions("inventory.flights", "Flights")},
            {"label": "Others", "permissions": build_module_permissions("inventory.others", "Other Items")},
        ],
    },
    
    # 💰 PRICING MODULE
    {
        "category": "Pricing",
        "icon": "💰",
        "description": "Manage discounts, commissions, and service charges",
        "subcategories": [
            {"label": "Discounts", "permissions": build_module_permissions("pricing.discounts", "Discounts")},
            {"label": "Commissions", "permissions": build_module_permissions("pricing.commissions", "Commissions")},
            {"label": "Service Charges", "permissions": build_module_permissions("pricing.service_charges", "Service Charges")},
        ],
    },
    
    # 📊 FINANCE MODULE
    {
        "category": "Finance",
        "icon": "📊",
        "description": "Financial management & accounting",
        "subcategories": [
            {"label": "Dashboard", "permissions": [
                {"code": "finance.dashboard.view", "label": "View Finance Dashboard"},
            ]},
            {"label": "Chart of Accounts", "permissions": [
                {"code": "finance.coa.view", "label": "View Chart of Accounts"},
                {"code": "finance.coa.add", "label": "Add Chart of Accounts"},
            ]},
            {"label": "Journal Entries", "permissions": [
                {"code": "finance.journals.view", "label": "View Journal Entries"},
            ]},
            {"label": "Manual Posting", "permissions": [
                {"code": "finance.manual_posting.view", "label": "View Manual Posting"},
                {"code": "finance.manual_posting.add", "label": "Add Manual Posting"},
            ]},
            {"label": "Profit & Loss", "permissions": [
                {"code": "finance.profit_loss.view", "label": "View Profit & Loss Reports"},
            ]},
            {"label": "Balance Sheet", "permissions": [
                {"code": "finance.balance_sheet.view", "label": "View Balance Sheet"},
            ]},
            {"label": "Trial Balance", "permissions": [
                {"code": "finance.trial_balance.view", "label": "View Trial Balance"},
            ]},
            {"label": "Ledger", "permissions": [
                {"code": "finance.ledger.view", "label": "View Financial Ledger"},
            ]},
            {"label": "Audit Trail", "permissions": [
                {"code": "finance.audit_trail.view", "label": "View Audit Trail"},
            ]},
        ],
    },
    
    # 💳 PAYMENTS MODULE
    {
        "category": "Payments",
        "icon": "💳",
        "description": "Payment processing & management",
        "subcategories": [
            {"label": "Add Payment", "permissions": build_payments_permissions("payments.add_payment", "Add Payment")},
            {"label": "Pending Payments", "permissions": build_payments_permissions("payments.pending", "Pending Payments")},
            {"label": "Vouchers", "permissions": build_payments_permissions("payments.vouchers", "Vouchers")},
            {"label": "Bank Accounts", "permissions": build_payments_permissions("payments.bank_accounts", "Bank Accounts")},
        ],
    },
    
    # 👥 CUSTOMERS MODULE
    {
        "category": "Customers",
        "icon": "👥",
        "description": "Customer relationship management",
        "subcategories": [
            {"label": "Customers", "permissions": build_module_permissions("customers.customers", "Customers")},
            {"label": "Leads", "permissions": build_module_permissions("customers.leads", "Leads")},
            {"label": "Passport Leads", "permissions": build_module_permissions("customers.passport_leads", "Passport Leads")},
        ],
    },
    
    # 🧑‍💼 HR MODULE
    {
        "category": "HR",
        "icon": "🧑‍💼",
        "description": "Human resources management",
        "subcategories": [
            {"label": "Employees", "permissions": build_module_permissions("hr.employees", "HR Employees")},
            {"label": "Attendance", "permissions": build_module_permissions("hr.attendance", "Attendance")},
            {"label": "Movements", "permissions": build_module_permissions("hr.movements", "Movements")},
            {"label": "Commissions", "permissions": build_module_permissions("hr.commissions", "HR Commissions")},
            {"label": "Punctuality", "permissions": build_module_permissions("hr.punctuality", "Punctuality")},
            {"label": "Approvals", "permissions": build_module_permissions("hr.approvals", "Approvals")},
        ],
    },
    
    # 🏢 ENTITIES MODULE
    {
        "category": "Entities",
        "icon": "🏢",
        "description": "Organizational structure management",
        "subcategories": [
            {"label": "Organization", "permissions": build_module_permissions("entities.organization", "Organization")},
            {"label": "Branch", "permissions": build_module_permissions("entities.branch", "Branch")},
            {"label": "Agencies", "permissions": build_module_permissions("entities.agencies", "Agencies")},
            {"label": "Roles & Permissions", "permissions": build_module_permissions("entities.roles_permissions", "Roles & Permissions")},
            {"label": "Employees", "permissions": build_module_permissions("entities.employees", "Entity Employees")},
        ],
    },
    
    # 📝 SINGLE MODULES (Independent)
    {
        "category": "Content & Operations",
        "icon": "📝",
        "description": "Independent operational modules",
        "subcategories": [
            {"label": "Blogs", "permissions": build_module_permissions("content.blogs", "Blogs")},
            {"label": "Forms", "permissions": build_module_permissions("content.forms", "Forms")},
            {"label": "Pax Movement", "permissions": build_module_permissions("operations.pax_movement", "Pax Movement")},
            {"label": "Daily Operations", "permissions": build_module_permissions("operations.daily", "Daily Operations")},
            {"label": "Order Delivery", "permissions": build_module_permissions("operations.order_delivery", "Order Delivery")},
        ],
    },
    
    # 🏪 AGENCY MODULES (For Agency Portal)
    {
        "category": "Agency",
        "icon": "🏪",
        "description": "Agency-specific modules (controlled by Organization)",
        "subcategories": [
            {"label": "Dashboard", "permissions": build_module_permissions("agency.dashboard", "Agency Dashboard")},
            {"label": "Bookings", "permissions": build_module_permissions("agency.bookings", "Agency Bookings")},
            {"label": "Custom Umrah", "permissions": build_module_permissions("agency.custom_umrah", "Custom Umrah")},
            {"label": "Umrah Package", "permissions": build_module_permissions("agency.umrah_package", "Umrah Package")},
            {"label": "Ticket", "permissions": build_module_permissions("agency.ticket", "Agency Ticket")},
            {"label": "Flight Search", "permissions": build_module_permissions("agency.flight_search", "Flight Search")},
            {"label": "Hotels", "permissions": build_module_permissions("agency.hotels", "Agency Hotels")},
            {"label": "Payments", "permissions": build_module_permissions("agency.payments", "Agency Payments")},
            {"label": "Booking History", "permissions": build_module_permissions("agency.booking_history", "Agency Booking History")},
        ],
    },
]

# Flatten all permission codes for validation
ALL_CODES: set = set()
for category in PERMISSION_CATALOGUE:
    for perm in category.get("permissions", []):
        ALL_CODES.add(perm["code"])
    for sub in category.get("subcategories", []):
        for perm in sub.get("permissions", []):
            ALL_CODES.add(perm["code"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------
class RoleGroupCreate(BaseModel):
    name: str
    description: Optional[str] = None
    organization_id: Optional[str] = None
    permissions: Optional[Any] = None   # either dict (module->actions) or list of permission codes


class RoleGroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    permissions: Optional[Any] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/catalogue", summary="Get full permission catalogue")
async def get_catalogue():
    """Returns the complete permission catalogue for the frontend."""
    return PERMISSION_CATALOGUE


@router.get("/", summary="List role groups")
async def list_role_groups(
    organization_id: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    filters = {}
    if organization_id:
        filters["organization_id"] = organization_id
    else:
        token_org = current_user.get("organization_id") or current_user.get("entity_id")
        if token_org:
            filters["organization_id"] = str(token_org)
    groups = await db_ops.get_all("role_groups", filters)
    return serialize_docs(groups)


@router.post("/", summary="Create role group", status_code=status.HTTP_201_CREATED)
async def create_role_group(
    body: RoleGroupCreate,
    current_user: dict = Depends(get_current_user),
):
    data = body.model_dump()
    if not data.get("organization_id"):
        data["organization_id"] = str(
            current_user.get("organization_id") or current_user.get("entity_id") or ""
        )
    raw = data.get("permissions") or []
    # Accept either a dict mapping module->actions (frontend style) or a list of codes
    if isinstance(raw, dict):
        data["permissions"] = raw
    else:
        data["permissions"] = [c for c in raw if c in ALL_CODES]
    data["created_at"] = datetime.utcnow().isoformat()
    data["updated_at"] = datetime.utcnow().isoformat()
    created = await db_ops.create("role_groups", data)
    return serialize_doc(created)


@router.get("/by-org/{org_id}", summary="List groups by org")
async def get_groups_by_org(org_id: str, current_user: dict = Depends(get_current_user)):
    groups = await db_ops.get_all("role_groups", {"organization_id": org_id})
    return serialize_docs(groups)


@router.get("/{group_id}", summary="Get single role group")
async def get_role_group(group_id: str, current_user: dict = Depends(get_current_user)):
    group = await db_ops.get_by_id("role_groups", group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Role group not found")
    return serialize_doc(group)


@router.put("/{group_id}", summary="Update role group")
async def update_role_group(
    group_id: str,
    body: RoleGroupUpdate,
    current_user: dict = Depends(get_current_user),
):
    group = await db_ops.get_by_id("role_groups", group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Role group not found")
    update_data = {k: v for k, v in body.model_dump().items() if v is not None}
    if "permissions" in update_data:
        # Accept dict (module->actions) or list of codes
        if isinstance(update_data["permissions"], dict):
            update_data["permissions"] = update_data["permissions"]
        else:
            update_data["permissions"] = [c for c in update_data["permissions"] if c in ALL_CODES]
    update_data["updated_at"] = datetime.utcnow().isoformat()
    updated = await db_ops.update("role_groups", group_id, update_data)
    return serialize_doc(updated)


@router.delete("/{group_id}", summary="Delete role group")
async def delete_role_group(group_id: str, current_user: dict = Depends(get_current_user)):
    group = await db_ops.get_by_id("role_groups", group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Role group not found")
    await db_ops.delete("role_groups", group_id)
    return {"message": "Role group deleted"}
