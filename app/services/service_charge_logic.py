"""
Service charge calculation logic for branches
"""
from app.database.db_operations import db_ops
from app.config.database import Collections
from app.utils.helpers import serialize_doc
from typing import Optional, Dict, Any

async def get_branch_service_charge(branch_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetch the active service charge rule for a branch.
    """
    if not branch_id:
        return None
    
    branch = await db_ops.get_by_id(Collections.BRANCHES, branch_id)
    if not branch or not branch.get("service_charge_group_id"):
        return None
    
    rule = await db_ops.get_by_id(Collections.SERVICE_CHARGES, branch["service_charge_group_id"])
    if not rule or not rule.get("is_active", True):
        return None
        
    return serialize_doc(rule)

def apply_ticket_charge(base_price: float, rule: Dict[str, Any]) -> float:
    """
    Calculate final ticket price based on service charge rule.
    """
    if not rule:
        return base_price
        
    charge = rule.get("ticket_charge", 0)
    charge_type = rule.get("ticket_charge_type", "fixed")
    
    if charge_type == "percentage":
        return base_price + (base_price * (charge / 100))
    else:
        return base_price + charge

def apply_package_charge(base_price: float, rule: Dict[str, Any]) -> float:
    """
    Calculate final package price based on service charge rule.
    """
    if not rule:
        return base_price
        
    charge = rule.get("package_charge", 0)
    charge_type = rule.get("package_charge_type", "fixed")
    
    if charge_type == "percentage":
        return base_price + (base_price * (charge / 100))
    else:
        return base_price + charge

def apply_hotel_charge(base_price: float, rule: Dict[str, Any], hotel_id: str, room_type: str) -> float:
    """
    Calculate final hotel price based on service charge rule overrides.
    room_type should be one of: quint, quad, triple, double, sharing
    """
    if not rule:
        return base_price
        
    hotel_charges = rule.get("hotel_charges", [])
    
    # normalize room_type to match keys like 'quint_charge'
    key_suffix = room_type.lower()
    if not key_suffix.endswith('_charge'):
        key_suffix = f"{key_suffix}_charge"
    
    # Find override for this specific hotel
    for period in hotel_charges:
        if hotel_id in period.get("hotels", []):
            override_val = period.get(key_suffix, 0)
            return base_price + override_val
            
    # If no specific hotel override is found, the user's plan implies we don't add anything extra
    # for hotels beyond the package_charge (which is usually applied at the package level).
    return base_price
