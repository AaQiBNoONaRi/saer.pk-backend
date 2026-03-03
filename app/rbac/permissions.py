"""
RBAC Permission Catalogue
=========================
Naming convention:  <module>.<submodule>.<action>
All codes are flat strings stored in MongoDB lists.

Branch-level permission check order:
  1. employee_permission_overrides.revoked  → deny
  2. employee_permission_overrides.granted  → allow
  3. branch_role.permissions                → allow / deny
  4. default                                → deny
"""
from typing import Dict, List

# ─── Action shortcuts ────────────────────────────────────────────────────────
def _crud(base: str) -> List[str]:
    return [f"{base}.view", f"{base}.create", f"{base}.edit", f"{base}.delete"]

def _crud_approve(base: str) -> List[str]:
    return _crud(base) + [f"{base}.approve"]

def _crud_approve_cancel(base: str) -> List[str]:
    return _crud_approve(base) + [f"{base}.cancel"]

# ─── Full catalogue (grouped for frontend checkbox rendering) ─────────────────
PERMISSION_CATALOGUE: List[Dict] = [

    # ── 1. DASHBOARD ──────────────────────────────────────────────────────────
    {
        "module": "dashboard",
        "label": "Dashboard",
        "subcategories": [
            {
                "key": "dashboard.analytics",
                "label": "Analytics",
                "permissions": [
                    {"code": "dashboard.analytics.view", "label": "View Analytics"},
                ],
            },
            {
                "key": "dashboard.branch_summary",
                "label": "Branch Summary",
                "permissions": [
                    {"code": "dashboard.branch_summary.view", "label": "View Branch Summary"},
                ],
            },
        ],
    },

    # ── 2. BOOKINGS ───────────────────────────────────────────────────────────
    {
        "module": "bookings",
        "label": "Bookings",
        "subcategories": [
            {
                "key": "bookings.custom_umrah",
                "label": "Custom Umrah",
                "permissions": [
                    {"code": "bookings.custom_umrah.view",    "label": "View Custom Umrah"},
                    {"code": "bookings.custom_umrah.create",  "label": "Create Custom Umrah"},
                    {"code": "bookings.custom_umrah.edit",    "label": "Edit Custom Umrah"},
                    {"code": "bookings.custom_umrah.delete",  "label": "Delete Custom Umrah"},
                    {"code": "bookings.custom_umrah.approve", "label": "Approve Custom Umrah"},
                    {"code": "bookings.custom_umrah.cancel",  "label": "Cancel Custom Umrah"},
                ],
            },
            {
                "key": "bookings.umrah_package",
                "label": "Umrah Package",
                "permissions": [
                    {"code": "bookings.umrah_package.view",    "label": "View Umrah Package"},
                    {"code": "bookings.umrah_package.create",  "label": "Create Umrah Package"},
                    {"code": "bookings.umrah_package.edit",    "label": "Edit Umrah Package"},
                    {"code": "bookings.umrah_package.delete",  "label": "Delete Umrah Package"},
                    {"code": "bookings.umrah_package.approve", "label": "Approve Umrah Package"},
                    {"code": "bookings.umrah_package.cancel",  "label": "Cancel Umrah Package"},
                ],
            },
            {
                "key": "bookings.ticket",
                "label": "Ticket Booking",
                "permissions": [
                    {"code": "bookings.ticket.view",    "label": "View Ticket Booking"},
                    {"code": "bookings.ticket.create",  "label": "Create Ticket Booking"},
                    {"code": "bookings.ticket.edit",    "label": "Edit Ticket Booking"},
                    {"code": "bookings.ticket.delete",  "label": "Delete Ticket Booking"},
                    {"code": "bookings.ticket.approve", "label": "Approve Ticket Booking"},
                    {"code": "bookings.ticket.cancel",  "label": "Cancel Ticket Booking"},
                ],
            },
        ],
    },

    # ── 3. BOOKING HISTORY ────────────────────────────────────────────────────
    {
        "module": "booking_history",
        "label": "Booking History",
        "subcategories": [
            {
                "key": "booking_history",
                "label": "Booking History",
                "permissions": [
                    {"code": "booking_history.view",   "label": "View Booking History"},
                    {"code": "booking_history.export", "label": "Export Booking History"},
                ],
            },
        ],
    },

    # ── 4. ENTITIES ───────────────────────────────────────────────────────────
    {
        "module": "entities",
        "label": "Entities",
        "subcategories": [
            {
                "key": "entities.agency",
                "label": "Agency",
                "permissions": [
                    {"code": "entities.agency.view",   "label": "View Agency"},
                    {"code": "entities.agency.create", "label": "Create Agency"},
                    {"code": "entities.agency.edit",   "label": "Edit Agency"},
                    {"code": "entities.agency.delete", "label": "Delete Agency"},
                ],
            },
            {
                "key": "entities.employee",
                "label": "Employee",
                "permissions": [
                    {"code": "entities.employee.view",   "label": "View Employee"},
                    {"code": "entities.employee.create", "label": "Create Employee"},
                    {"code": "entities.employee.edit",   "label": "Edit Employee"},
                    {"code": "entities.employee.delete", "label": "Delete Employee"},
                ],
            },
            {
                "key": "entities.hr",
                "label": "HR Management",
                "permissions": [
                    {"code": "entities.hr.view",   "label": "View HR"},
                    {"code": "entities.hr.create", "label": "Create HR Record"},
                    {"code": "entities.hr.edit",   "label": "Edit HR Record"},
                    {"code": "entities.hr.delete", "label": "Delete HR Record"},
                ],
            },
        ],
    },

    # ── 5. COMMISSION & EARNINGS ──────────────────────────────────────────────
    {
        "module": "commission",
        "label": "Commission & Earnings",
        "subcategories": [
            {
                "key": "commission",
                "label": "Commission",
                "permissions": [
                    {"code": "commission.view",      "label": "View Commission"},
                    {"code": "commission.calculate", "label": "Calculate Commission"},
                    {"code": "commission.edit",      "label": "Edit Commission"},
                    {"code": "commission.approve",   "label": "Approve Commission"},
                ],
            },
        ],
    },

    # ── 6. HOTELS ─────────────────────────────────────────────────────────────
    {
        "module": "hotels",
        "label": "Hotels",
        "subcategories": [
            {
                "key": "hotels",
                "label": "Hotels",
                "permissions": [
                    {"code": "hotels.view",   "label": "View Hotels"},
                    {"code": "hotels.add",    "label": "Add Hotel"},
                    {"code": "hotels.edit",   "label": "Edit Hotel"},
                    {"code": "hotels.delete", "label": "Delete Hotel"},
                ],
            },
        ],
    },

    # ── 7. PAYMENTS ───────────────────────────────────────────────────────────
    {
        "module": "payments",
        "label": "Payments",
        "subcategories": [
            {
                "key": "payments",
                "label": "Payments",
                "permissions": [
                    {"code": "payments.view",   "label": "View Payments"},
                    {"code": "payments.create", "label": "Create Payment"},
                    {"code": "payments.verify", "label": "Verify Payment"},
                    {"code": "payments.refund", "label": "Process Refund"},
                ],
            },
        ],
    },

    # ── 8. PAX MOVEMENTS ──────────────────────────────────────────────────────
    {
        "module": "pax_movements",
        "label": "Pax Movements",
        "subcategories": [
            {
                "key": "pax_movements",
                "label": "Pax Movements",
                "permissions": [
                    {"code": "pax_movements.view",   "label": "View Pax Movements"},
                    {"code": "pax_movements.add",    "label": "Add Pax Movement"},
                    {"code": "pax_movements.edit",   "label": "Edit Pax Movement"},
                    {"code": "pax_movements.delete", "label": "Delete Pax Movement"},
                ],
            },
        ],
    },
]

# ─── Flat set of all valid codes (for validation) ─────────────────────────────
ALL_PERMISSION_CODES: set = set()
for _cat in PERMISSION_CATALOGUE:
    for _sub in _cat.get("subcategories", []):
        for _p in _sub.get("permissions", []):
            ALL_PERMISSION_CODES.add(_p["code"])


# ─── Predefined Role Templates ────────────────────────────────────────────────
# Each value is the list of permission codes auto-granted to that role.
# Branch Admin / Super Admin bypass permission checks entirely (handled in middleware).

PREDEFINED_ROLES: Dict[str, List[str]] = {

    "branch_manager": list(ALL_PERMISSION_CODES),  # full access within branch

    "admin": [
        # dashboard
        "dashboard.analytics.view", "dashboard.branch_summary.view",
        # bookings - full
        *[c for c in ALL_PERMISSION_CODES if c.startswith("bookings.")],
        "booking_history.view", "booking_history.export",
        # entities - full
        *[c for c in ALL_PERMISSION_CODES if c.startswith("entities.")],
        # commission
        *[c for c in ALL_PERMISSION_CODES if c.startswith("commission.")],
        # hotels
        *[c for c in ALL_PERMISSION_CODES if c.startswith("hotels.")],
        # payments
        *[c for c in ALL_PERMISSION_CODES if c.startswith("payments.")],
        # pax
        *[c for c in ALL_PERMISSION_CODES if c.startswith("pax_movements.")],
    ],

    "sales": [
        "dashboard.analytics.view",
        "dashboard.branch_summary.view",
        "bookings.custom_umrah.view",
        "bookings.custom_umrah.create",
        "bookings.custom_umrah.edit",
        "bookings.umrah_package.view",
        "bookings.umrah_package.create",
        "bookings.umrah_package.edit",
        "bookings.ticket.view",
        "bookings.ticket.create",
        "bookings.ticket.edit",
        "booking_history.view",
        "payments.view",
        "payments.create",
        "hotels.view",
        "pax_movements.view",
    ],

    "accountant": [
        "dashboard.analytics.view",
        "dashboard.branch_summary.view",
        "booking_history.view",
        "booking_history.export",
        "commission.view",
        "commission.calculate",
        "commission.approve",
        "payments.view",
        "payments.create",
        "payments.verify",
        "payments.refund",
    ],

    "hr": [
        "dashboard.branch_summary.view",
        "entities.employee.view",
        "entities.employee.create",
        "entities.employee.edit",
        "entities.employee.delete",
        "entities.hr.view",
        "entities.hr.create",
        "entities.hr.edit",
        "entities.hr.delete",
        "pax_movements.view",
        "pax_movements.add",
        "pax_movements.edit",
        "pax_movements.delete",
    ],
}

# Deduplicate
for _role in PREDEFINED_ROLES:
    PREDEFINED_ROLES[_role] = sorted(set(PREDEFINED_ROLES[_role]))
