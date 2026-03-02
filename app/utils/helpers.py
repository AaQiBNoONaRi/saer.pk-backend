"""
Helper utility functions
"""
from bson import ObjectId
from typing import Any, Dict, List
from datetime import datetime
import pytz

PKT = pytz.timezone('Asia/Karachi')

def serialize_doc(doc: Dict) -> Dict:
    """Convert MongoDB document to JSON-serializable format"""
    if doc is None:
        return None
    
    if "_id" in doc and isinstance(doc["_id"], ObjectId):
        doc["_id"] = str(doc["_id"])
    
    # Convert any nested ObjectIds or datetimes
    for key, value in doc.items():
        if isinstance(value, ObjectId):
            doc[key] = str(value)
        elif isinstance(value, datetime):
            if value.tzinfo is None:
                utc_dt = pytz.utc.localize(value)
                doc[key] = utc_dt.astimezone(PKT).isoformat()
            else:
                doc[key] = value.astimezone(PKT).isoformat()
        elif isinstance(value, str) and key in ("check_in", "check_out", "start_time", "end_time", "created_at", "updated_at"):
            # Attempt to parse ISO strings that might be naive UTC from DB
            try:
                # If it already has an offset, we leave it alone or just parse it
                if '+' in value or value.endswith('Z'):
                    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    doc[key] = dt.astimezone(PKT).isoformat()
                else:
                    # Naive string from DB is assumed UTC
                    dt = datetime.fromisoformat(value)
                    utc_dt = pytz.utc.localize(dt)
                    doc[key] = utc_dt.astimezone(PKT).isoformat()
            except ValueError:
                pass  # Not a valid isoformat string, leave as is
        elif isinstance(value, list):
            doc[key] = [serialize_doc(item) if isinstance(item, dict) else item for item in value]
        elif isinstance(value, dict):
            doc[key] = serialize_doc(value)
    
    return doc

def serialize_docs(docs: List[Dict]) -> List[Dict]:
    """Convert list of MongoDB documents to JSON-serializable format"""
    return [serialize_doc(doc) for doc in docs]

def generate_employee_id(entity_type: str, count: int) -> str:
    """Generate employee ID based on entity type and count"""
    from app.config.settings import settings
    
    if entity_type == "organization":
        prefix = settings.ORG_EMPLOYEE_PREFIX
    elif entity_type == "branch":
        prefix = settings.BRANCH_EMPLOYEE_PREFIX
    elif entity_type == "agency":
        prefix = settings.AGENCY_EMPLOYEE_PREFIX
    else:
        raise ValueError(f"Invalid entity type: {entity_type}")
    
    return f"{prefix}{count + 1:03d}"

def calculate_available_credit(credit_limit: float, credit_used: float) -> float:
    """Calculate available credit for an agency"""
    return max(0, credit_limit - credit_used)
