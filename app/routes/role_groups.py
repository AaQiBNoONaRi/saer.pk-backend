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
# Full Permission Catalogue
# ---------------------------------------------------------------------------
PERMISSION_CATALOGUE = [
    {
        "category": "Login Access", "icon": "??",
        "permissions": [
            {"code": "admin_portal_access", "label": "Can access admin portal"},
        ],
    },
    {
        "category": "Booking History", "icon": "??",
        "permissions": [
            {"code": "view_agent_bookings_admin",    "label": "Can view agent bookings"},
            {"code": "view_booking_history_admin",   "label": "Can view booking history"},
            {"code": "view_branch_bookings_admin",   "label": "Can view branch bookings"},
            {"code": "view_employee_bookings_admin", "label": "Can view employee bookings"},
            {"code": "view_org_bookings_admin",      "label": "Can view organization bookings"},
        ],
    },
    {
        "category": "Blogs", "icon": "??",
        "permissions": [
            {"code": "add_blog_admin",    "label": "Can add blogs"},
            {"code": "delete_blog_admin", "label": "Can delete blogs"},
            {"code": "edit_blog_admin",   "label": "Can edit blogs"},
            {"code": "view_blog_admin",   "label": "Can view blogs"},
        ],
    },
    {
        "category": "CRM", "icon": "??",
        "subcategories": [
            {"label": "Leads", "icon": "??", "permissions": [
                {"code": "add_leads_admin",  "label": "Can add leads"},
                {"code": "edit_leads_admin", "label": "Can edit leads"},
                {"code": "view_leads_admin", "label": "Can view leads"},
            ]},
            {"label": "Loan", "icon": "??", "permissions": [
                {"code": "add_loan_admin",  "label": "Can add loan"},
                {"code": "edit_loan_admin", "label": "Can edit loan"},
                {"code": "view_loan_admin", "label": "Can view loan"},
            ]},
            {"label": "Tasks", "icon": "?", "permissions": [
                {"code": "add_tasks_admin",  "label": "Can add tasks"},
                {"code": "edit_tasks_admin", "label": "Can edit tasks"},
                {"code": "view_tasks_admin", "label": "Can view tasks"},
            ]},
            {"label": "Closed Leads", "icon": "??", "permissions": [
                {"code": "view_closed_leads_admin", "label": "Can view closed leads"},
            ]},
            {"label": "Instant", "icon": "?", "permissions": [
                {"code": "view_instant_admin", "label": "Can view instant"},
            ]},
            {"label": "Passport Leads", "icon": "??", "permissions": [
                {"code": "add_passport_leads_admin",    "label": "Can add passport leads"},
                {"code": "delete_passport_leads_admin", "label": "Can delete passport leads"},
                {"code": "edit_passport_leads_admin",   "label": "Can edit passport leads"},
                {"code": "view_passport_leads_admin",   "label": "Can view passport leads"},
            ]},
            {"label": "Walking Customer", "icon": "??", "permissions": [
                {"code": "add_walking_customer_admin",    "label": "Can add walking customer"},
                {"code": "delete_walking_customer_admin", "label": "Can delete walking customer"},
                {"code": "edit_walking_customer_admin",   "label": "Can edit walking customer"},
                {"code": "view_walking_customer_admin",   "label": "Can view walking customer"},
            ]},
            {"label": "Customer Database", "icon": "??", "permissions": [
                {"code": "add_customer_database_admin",    "label": "Can add customer database"},
                {"code": "delete_customer_database_admin", "label": "Can delete customer database"},
                {"code": "edit_customer_database_admin",   "label": "Can edit customer database"},
                {"code": "view_customer_database_admin",   "label": "Can view customer database"},
            ]},
        ],
    },
    {
        "category": "Daily Operations", "icon": "??",
        "subcategories": [
            {"label": "Hotel Check-in/Check-out", "icon": "??", "permissions": [
                {"code": "update_hotel_checkin_admin", "label": "Can update hotel check-in/check-out"},
                {"code": "view_hotel_checkin_admin",   "label": "Can view hotel check-in/check-out"},
            ]},
            {"label": "Ziyarat", "icon": "??", "permissions": [
                {"code": "update_ziyarat_operations_admin", "label": "Can update ziyarat"},
                {"code": "view_ziyarat_operations_admin",   "label": "Can view ziyarat"},
            ]},
            {"label": "Transport", "icon": "??", "permissions": [
                {"code": "update_transport_operations_admin", "label": "Can update transport"},
                {"code": "view_transport_operations_admin",   "label": "Can view transport"},
            ]},
            {"label": "Airport", "icon": "??", "permissions": [
                {"code": "update_airport_operations_admin", "label": "Can update airport"},
                {"code": "view_airport_operations_admin",   "label": "Can view airport"},
            ]},
            {"label": "Food", "icon": "???", "permissions": [
                {"code": "update_food_operations_admin", "label": "Can update food"},
                {"code": "view_food_operations_admin",   "label": "Can view food"},
            ]},
            {"label": "Pax Details", "icon": "??", "permissions": [
                {"code": "update_pax_details_admin", "label": "Can update pax details"},
                {"code": "view_pax_details_admin",   "label": "Can view pax details"},
            ]},
        ],
    },
    {
        "category": "Finance", "icon": "??",
        "subcategories": [
            {"label": "Recent Transactions", "icon": "??", "permissions": [
                {"code": "view_recent_transactions_admin", "label": "Can view recent transactions"},
            ]},
            {"label": "Profit & Loss Reports", "icon": "??", "permissions": [
                {"code": "view_profit_loss_reports_admin", "label": "Can view profit & loss reports"},
            ]},
            {"label": "Financial Ledger", "icon": "??", "permissions": [
                {"code": "view_financial_ledger_admin", "label": "Can view financial ledger"},
            ]},
            {"label": "Expense Management", "icon": "??", "permissions": [
                {"code": "add_expense_management_admin",    "label": "Can add expense management"},
                {"code": "delete_expense_management_admin", "label": "Can delete expense management"},
                {"code": "edit_expense_management_admin",   "label": "Can edit expense management"},
                {"code": "view_expense_management_admin",   "label": "Can view expense management"},
            ]},
            {"label": "Manual Posting", "icon": "??", "permissions": [
                {"code": "add_manual_posting_admin",    "label": "Can add manual posting"},
                {"code": "delete_manual_posting_admin", "label": "Can delete manual posting"},
                {"code": "edit_manual_posting_admin",   "label": "Can edit manual posting"},
                {"code": "view_manual_posting_admin",   "label": "Can view manual posting"},
            ]},
            {"label": "Tax Reports (FBR)", "icon": "???", "permissions": [
                {"code": "view_tax_reports_fbr_admin", "label": "Can view tax reports (FBR)"},
            ]},
            {"label": "Balance Sheet", "icon": "??", "permissions": [
                {"code": "view_balance_sheet_admin", "label": "Can view balance sheet"},
            ]},
            {"label": "Audit Trail", "icon": "??", "permissions": [
                {"code": "view_audit_trail_admin", "label": "Can view audit trail"},
            ]},
        ],
    },
    {
        "category": "Form Management", "icon": "??",
        "permissions": [
            {"code": "add_form_admin",    "label": "Can add forms"},
            {"code": "delete_form_admin", "label": "Can delete forms"},
            {"code": "edit_form_admin",   "label": "Can edit forms"},
            {"code": "view_form_admin",   "label": "Can view forms"},
        ],
    },
    {
        "category": "Hotels", "icon": "??",
        "subcategories": [
            {"label": "Main Hotel Permissions", "icon": "??", "permissions": [
                {"code": "add_hotel_admin",    "label": "Can add hotels"},
                {"code": "delete_hotel_admin", "label": "Can delete hotels"},
                {"code": "edit_hotel_admin",   "label": "Can edit hotels"},
                {"code": "view_hotel_admin",   "label": "Can view hotels"},
            ]},
            {"label": "Hotel Availability", "icon": "??", "permissions": [
                {"code": "add_availability_admin",    "label": "Can add hotel availability"},
                {"code": "delete_availability_admin", "label": "Can delete hotel availability"},
                {"code": "edit_availability_admin",   "label": "Can edit hotel availability"},
                {"code": "view_availability_admin",   "label": "Can view hotel availability"},
            ]},
            {"label": "Hotel Outsourcing", "icon": "??", "permissions": [
                {"code": "add_outsourcing_admin",    "label": "Can add hotel outsourcing"},
                {"code": "delete_outsourcing_admin", "label": "Can delete hotel outsourcing"},
                {"code": "edit_outsourcing_admin",   "label": "Can edit hotel outsourcing"},
                {"code": "view_outsourcing_admin",   "label": "Can view hotel outsourcing"},
            ]},
            {"label": "Hotel Floor Management", "icon": "??", "permissions": [
                {"code": "add_floor_management_admin",    "label": "Can add hotel floor management"},
                {"code": "delete_floor_management_admin", "label": "Can delete hotel floor management"},
                {"code": "edit_floor_management_admin",   "label": "Can edit hotel floor management"},
                {"code": "view_floor_management_admin",   "label": "Can view hotel floor management"},
            ]},
        ],
    },
    {
        "category": "HR", "icon": "??",
        "subcategories": [
            {"label": "Employees", "icon": "??", "permissions": [
                {"code": "add_employees_admin",    "label": "Can add employees"},
                {"code": "delete_employees_admin", "label": "Can delete employees"},
                {"code": "edit_employees_admin",   "label": "Can edit employees"},
                {"code": "view_employees_admin",   "label": "Can view employees"},
            ]},
            {"label": "Attendance", "icon": "??", "permissions": [
                {"code": "add_attendance_admin",    "label": "Can add attendance"},
                {"code": "delete_attendance_admin", "label": "Can delete attendance"},
                {"code": "edit_attendance_admin",   "label": "Can edit attendance"},
                {"code": "view_attendance_admin",   "label": "Can view attendance"},
            ]},
            {"label": "Movements", "icon": "??", "permissions": [
                {"code": "add_movements_admin",    "label": "Can add movements"},
                {"code": "delete_movements_admin", "label": "Can delete movements"},
                {"code": "edit_movements_admin",   "label": "Can edit movements"},
                {"code": "view_movements_admin",   "label": "Can view movements"},
            ]},
            {"label": "Commission", "icon": "??", "permissions": [
                {"code": "add_hr_commission_admin",    "label": "Can add commission"},
                {"code": "delete_hr_commission_admin", "label": "Can delete commission"},
                {"code": "edit_hr_commission_admin",   "label": "Can edit commission"},
                {"code": "view_hr_commission_admin",   "label": "Can view commission"},
            ]},
            {"label": "Punctuality", "icon": "?", "permissions": [
                {"code": "add_punctuality_admin",    "label": "Can add punctuality"},
                {"code": "delete_punctuality_admin", "label": "Can delete punctuality"},
                {"code": "edit_punctuality_admin",   "label": "Can edit punctuality"},
                {"code": "view_punctuality_admin",   "label": "Can view punctuality"},
            ]},
            {"label": "Approvals", "icon": "?", "permissions": [
                {"code": "add_approvals_admin",    "label": "Can add approvals"},
                {"code": "delete_approvals_admin", "label": "Can delete approvals"},
                {"code": "edit_approvals_admin",   "label": "Can edit approvals"},
                {"code": "view_approvals_admin",   "label": "Can view approvals"},
            ]},
            {"label": "Payments", "icon": "??", "permissions": [
                {"code": "add_hr_payments_admin",    "label": "Can add HR payments"},
                {"code": "delete_hr_payments_admin", "label": "Can delete HR payments"},
                {"code": "edit_hr_payments_admin",   "label": "Can edit HR payments"},
                {"code": "view_hr_payments_admin",   "label": "Can view HR payments"},
            ]},
        ],
    },
    {
        "category": "Order Delivery", "icon": "??",
        "permissions": [
            {"code": "update_order_delivery_admin", "label": "Can update order delivery"},
            {"code": "view_order_delivery_admin",   "label": "Can view order delivery"},
        ],
    },
    {
        "category": "Packages", "icon": "??",
        "permissions": [
            {"code": "add_package_admin",    "label": "Can add packages"},
            {"code": "delete_package_admin", "label": "Can delete packages"},
            {"code": "edit_package_admin",   "label": "Can edit packages"},
            {"code": "view_package_admin",   "label": "Can view packages"},
        ],
    },
    {
        "category": "Partners", "icon": "??",
        "subcategories": [
            {"label": "Add Users", "icon": "??", "permissions": [
                {"code": "assign_agency_admin",       "label": "Can assign agency"},
                {"code": "assign_branches_admin",     "label": "Can assign branches"},
                {"code": "assign_groups_admin",       "label": "Can assign groups"},
                {"code": "assign_organization_admin", "label": "Can assign organization"},
                {"code": "view_add_users_admin",      "label": "Can view add users"},
                {"code": "view_users_admin",          "label": "Can view users"},
            ]},
            {"label": "Organization", "icon": "??", "permissions": [
                {"code": "add_organization_admin",    "label": "Can add organization"},
                {"code": "delete_organization_admin", "label": "Can delete organization"},
                {"code": "edit_organization_admin",   "label": "Can edit organization"},
                {"code": "view_organization_admin",   "label": "Can view organization"},
            ]},
            {"label": "Groups", "icon": "??", "permissions": [
                {"code": "add_groups_admin",                   "label": "Can add groups"},
                {"code": "assign_permissions_to_groups_admin", "label": "Can assign permissions to groups"},
                {"code": "delete_groups_admin",                "label": "Can delete groups"},
                {"code": "edit_groups_admin",                  "label": "Can edit groups"},
                {"code": "view_groups_admin",                  "label": "Can view groups"},
            ]},
            {"label": "Agency", "icon": "???", "permissions": [
                {"code": "add_agency_admin",    "label": "Can add agency"},
                {"code": "delete_agency_admin", "label": "Can delete agency"},
                {"code": "edit_agency_admin",   "label": "Can edit agency"},
                {"code": "view_agency_admin",   "label": "Can view agency"},
            ]},
            {"label": "Branch", "icon": "??", "permissions": [
                {"code": "add_branch_admin",    "label": "Can add branch"},
                {"code": "delete_branch_admin", "label": "Can delete branch"},
                {"code": "edit_branch_admin",   "label": "Can edit branch"},
                {"code": "view_branch_admin",   "label": "Can view branch"},
            ]},
            {"label": "Discount", "icon": "??", "permissions": [
                {"code": "add_discount_groups_admin",                  "label": "Can add discount groups"},
                {"code": "assign_commission_to_discount_groups_admin", "label": "Can assign commission to discount groups"},
                {"code": "delete_discount_groups_admin",               "label": "Can delete discount groups"},
                {"code": "edit_discount_groups_admin",                 "label": "Can edit discount groups"},
                {"code": "view_discount_groups_admin",                 "label": "Can view discount groups"},
            ]},
            {"label": "Org Links", "icon": "??", "permissions": [
                {"code": "add_create_link_org_admin",         "label": "Can create link org"},
                {"code": "add_create_resell_request_admin",   "label": "Can create resell request"},
                {"code": "delete_create_link_org_admin",      "label": "Can delete link org"},
                {"code": "delete_create_resell_request_admin","label": "Can delete resell request"},
                {"code": "edit_create_link_org_admin",        "label": "Can edit link org"},
                {"code": "edit_create_resell_request_admin",  "label": "Can edit resell request"},
                {"code": "view_create_link_org_admin",        "label": "Can view link org"},
                {"code": "view_create_resell_request_admin",  "label": "Can view resell request"},
            ]},
            {"label": "Markup Rules", "icon": "??", "permissions": [
                {"code": "add_markup_add_group_admin",       "label": "Can add markup group"},
                {"code": "add_markup_assign_value_admin",    "label": "Can assign markup value"},
                {"code": "delete_markup_add_group_admin",    "label": "Can delete markup group"},
                {"code": "delete_markup_assign_value_admin", "label": "Can delete markup value"},
                {"code": "edit_markup_add_group_admin",      "label": "Can edit markup group"},
                {"code": "edit_markup_assign_value_admin",   "label": "Can edit markup value"},
                {"code": "view_markup_add_group_admin",      "label": "Can view markup group"},
                {"code": "view_markup_assign_value_admin",   "label": "Can view markup value"},
            ]},
            {"label": "Commission Rules", "icon": "??", "permissions": [
                {"code": "add_commission_add_group_admin",       "label": "Can add commission group"},
                {"code": "add_commission_assign_value_admin",    "label": "Can assign commission value"},
                {"code": "delete_commission_add_group_admin",    "label": "Can delete commission group"},
                {"code": "delete_commission_assign_value_admin", "label": "Can delete commission value"},
                {"code": "edit_commission_add_group_admin",      "label": "Can edit commission group"},
                {"code": "edit_commission_assign_value_admin",   "label": "Can edit commission value"},
                {"code": "view_commission_add_group_admin",      "label": "Can view commission group"},
                {"code": "view_commission_assign_value_admin",   "label": "Can view commission value"},
            ]},
            {"label": "Super Admin", "icon": "??", "permissions": [
                {"code": "add_super_admin_admin",    "label": "Can add super admin"},
                {"code": "delete_super_admin_admin", "label": "Can delete super admin"},
                {"code": "edit_super_admin_admin",   "label": "Can edit super admin"},
            ]},
            {"label": "Admin", "icon": "??", "permissions": [
                {"code": "add_admin_admin",    "label": "Can add admin"},
                {"code": "delete_admin_admin", "label": "Can delete admin"},
                {"code": "edit_admin_admin",   "label": "Can edit admin"},
            ]},
            {"label": "Agent", "icon": "??", "permissions": [
                {"code": "add_agent_admin",    "label": "Can add agent"},
                {"code": "delete_agent_admin", "label": "Can delete agent"},
                {"code": "edit_agent_admin",   "label": "Can edit agent"},
            ]},
            {"label": "Area Agent", "icon": "??", "permissions": [
                {"code": "add_area_agent_admin",    "label": "Can add area agent"},
                {"code": "delete_area_agent_admin", "label": "Can delete area agent"},
                {"code": "edit_area_agent_admin",   "label": "Can edit area agent"},
            ]},
            {"label": "Employee", "icon": "?????", "permissions": [
                {"code": "add_employee_admin",    "label": "Can add employee"},
                {"code": "delete_employee_admin", "label": "Can delete employee"},
                {"code": "edit_employee_admin",   "label": "Can edit employee"},
            ]},
            {"label": "Branch Users", "icon": "???????????", "permissions": [
                {"code": "add_branch_users_admin",    "label": "Can add branch users"},
                {"code": "delete_branch_users_admin", "label": "Can delete branch users"},
                {"code": "edit_branch_users_admin",   "label": "Can edit branch users"},
            ]},
        ],
    },
    {
        "category": "Pax Movement & Intimation", "icon": "??",
        "subcategories": [
            {"label": "All Passengers", "icon": "??", "permissions": [
                {"code": "view_pax_all_passengers_admin", "label": "Can view all passengers"},
            ]},
        ],
    },
    {
        "category": "Payments", "icon": "??",
        "subcategories": [
            {"label": "Ledger", "icon": "??", "permissions": [
                {"code": "view_ledger_admin", "label": "Can view ledger"},
            ]},
            {"label": "Payments", "icon": "??", "permissions": [
                {"code": "add_payments_finance_admin", "label": "Can add payments"},
                {"code": "approve_payments_admin",     "label": "Can approve payments"},
                {"code": "reject_payments_admin",      "label": "Can reject payments"},
            ]},
            {"label": "Bank Account", "icon": "??", "permissions": [
                {"code": "add_bank_account_admin",    "label": "Can add bank account"},
                {"code": "delete_bank_account_admin", "label": "Can delete bank account"},
                {"code": "edit_bank_account_admin",   "label": "Can edit bank account"},
                {"code": "view_bank_account_admin",   "label": "Can view bank account"},
            ]},
            {"label": "Pending Payments", "icon": "?", "permissions": [
                {"code": "add_remarks_pending_payments_admin", "label": "Can add remarks to pending payments"},
                {"code": "view_pending_payments_admin",        "label": "Can view pending payments"},
            ]},
        ],
    },
    {
        "category": "Rules Management", "icon": "??",
        "permissions": [
            {"code": "add_rule_admin",    "label": "Can add rules"},
            {"code": "delete_rule_admin", "label": "Can delete rules"},
            {"code": "edit_rule_admin",   "label": "Can edit rules"},
            {"code": "view_rule_admin",   "label": "Can view rules"},
        ],
    },
    {
        "category": "Tickets", "icon": "??",
        "permissions": [
            {"code": "add_ticket_admin",    "label": "Can add tickets"},
            {"code": "delete_ticket_admin", "label": "Can delete tickets"},
            {"code": "edit_ticket_admin",   "label": "Can edit tickets"},
            {"code": "view_ticket_admin",   "label": "Can view tickets"},
        ],
    },
    {
        "category": "Visa and Other Permissions", "icon": "??",
        "subcategories": [
            {"label": "Riyal Rate", "icon": "??", "permissions": [
                {"code": "edit_riyal_rate_admin", "label": "Can edit riyal rate"},
            ]},
            {"label": "Shirka", "icon": "??", "permissions": [
                {"code": "add_shirka_admin",    "label": "Can add shirka"},
                {"code": "delete_shirka_admin", "label": "Can delete shirka"},
                {"code": "edit_shirka_admin",   "label": "Can edit shirka"},
            ]},
            {"label": "Sector", "icon": "??", "permissions": [
                {"code": "add_sector_admin",    "label": "Can add sector"},
                {"code": "delete_sector_admin", "label": "Can delete sector"},
                {"code": "edit_sector_admin",   "label": "Can edit sector"},
            ]},
            {"label": "Big Sector", "icon": "???", "permissions": [
                {"code": "add_big_sector_admin",    "label": "Can add big sector"},
                {"code": "delete_big_sector_admin", "label": "Can delete big sector"},
                {"code": "edit_big_sector_admin",   "label": "Can edit big sector"},
            ]},
            {"label": "Visa and Transport Rate", "icon": "??", "permissions": [
                {"code": "add_visa_transport_rate_admin",    "label": "Can add visa and transport rate"},
                {"code": "delete_visa_transport_rate_admin", "label": "Can delete visa and transport rate"},
                {"code": "edit_visa_transport_rate_admin",   "label": "Can edit visa and transport rate"},
            ]},
            {"label": "Only Visa Rates", "icon": "??", "permissions": [
                {"code": "edit_long_term_visa_rate_admin", "label": "Can edit long term visa rate"},
                {"code": "edit_only_visa_rate_admin",      "label": "Can edit only visa rate"},
            ]},
            {"label": "Transport Prices", "icon": "??", "permissions": [
                {"code": "add_transport_price_admin",    "label": "Can add transport price"},
                {"code": "delete_transport_price_admin", "label": "Can delete transport price"},
                {"code": "edit_transport_price_admin",   "label": "Can edit transport price"},
            ]},
            {"label": "Food Prices", "icon": "???", "permissions": [
                {"code": "add_food_price_admin",    "label": "Can add food price"},
                {"code": "delete_food_price_admin", "label": "Can delete food price"},
                {"code": "edit_food_price_admin",   "label": "Can edit food price"},
            ]},
            {"label": "Ziarat Prices", "icon": "??", "permissions": [
                {"code": "add_ziarat_price_admin",    "label": "Can add ziarat price"},
                {"code": "delete_ziarat_price_admin", "label": "Can delete ziarat price"},
                {"code": "edit_ziarat_price_admin",   "label": "Can edit ziarat price"},
            ]},
            {"label": "Flight", "icon": "??", "permissions": [
                {"code": "add_flight_admin",    "label": "Can add flight"},
                {"code": "delete_flight_admin", "label": "Can delete flight"},
                {"code": "edit_flight_admin",   "label": "Can edit flight"},
            ]},
            {"label": "City", "icon": "???", "permissions": [
                {"code": "add_city_admin",    "label": "Can add city"},
                {"code": "delete_city_admin", "label": "Can delete city"},
                {"code": "edit_city_admin",   "label": "Can edit city"},
            ]},
            {"label": "Booking Settings", "icon": "??", "permissions": [
                {"code": "edit_booking_expire_time_admin", "label": "Can set time for booking expire"},
            ]},
        ],
    },
]

# Flat set of all valid permission codes for validation
ALL_CODES: set = set()
for _cat in PERMISSION_CATALOGUE:
    for _p in _cat.get("permissions", []):
        ALL_CODES.add(_p["code"])
    for _sub in _cat.get("subcategories", []):
        for _p in _sub.get("permissions", []):
            ALL_CODES.add(_p["code"])


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
