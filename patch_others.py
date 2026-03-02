import re

def patch_others():
    with open('app/routes/others.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # Add get_org_id import
    if 'get_org_id' not in content:
        content = content.replace(
            'from app.utils.auth import get_current_user',
            'from app.utils.auth import get_current_user, get_org_id'
        )

    # 1. Add org_id to all endpoint signatures
    # Find def ...(\n ... current_user: dict = Depends(get_current_user)\n):
    # and replace with current_user..., org_id: str = Depends(get_org_id)
    content = re.sub(
        r'(current_user:\s*dict\s*=\s*Depends\(get_current_user\))',
        r'\1,\n    org_id: str = Depends(get_org_id)',
        content
    )

    # 2. Patch create endpoints
    # Look for _dict = *.model_dump()
    # Replace with _dict = *.model_dump()\n    _dict["organization_id"] = org_id
    content = re.sub(
        r'(\w+_dict\s*=\s*\w+\.model_dump\(\))',
        r'\1\n    \g<1>["organization_id"] = org_id',
        content
    )
    content = re.sub(
        r'(\w+_dict\s*=\s*\w+\.model_dump\(exclude_unset=True\))',
        r'\1\n    # exclude_unset handles updates, no org_id injected here',
        content
    )

    # 3. Patch get_all endpoints
    # Look for filter_query = {} or filter_query = {"is_active":.+}
    # Ensure they add organization_id: org_id filtering
    # Wait, some have filter_query = {}
    content = re.sub(
        r'(filter_query\s*=\s*\{\})',
        r'filter_query = {"organization_id": org_id} if org_id else {}',
        content
    )
    
    # 4. Patch single fetches / updates / deletes for ownership
    # We need to find places where it checks `if not <var>:` right after db_ops.get_by_id
    # e.g.:
    # record = await db_ops.get_by_id(...)
    # if not record: ...
    #
    # We can use regex:
    # (\w+)\s*=\s*await db_ops\.get_by_id\([^)]+\)\s*if not \1:\s*raise HTTPException\([^)]+\)
    
    ownership_check = r"""
    is_super = current_user.get("role") in ("admin", "super_admin")
    if org_id and \2.get("organization_id") != org_id and not is_super:
        raise HTTPException(status_code=403, detail="Access denied")"""

    content = re.sub(
        r'((\w+)\s*=\s*await db_ops\.get_by_id\([^\)]+\)\n\s*if not \2:\n\s*raise HTTPException\([^\)]+\))',
        r'\1' + ownership_check,
        content
    )

    with open('app/routes/others_patched.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("Patched successfully to others_patched.py")

if __name__ == '__main__':
    patch_others()
