import re

with open('e:/saer.pk/backend/app/routes/others.py', 'r', encoding='utf-8') as f:
    text = f.read()

pattern = r'(\w+_dict)\s*=\s*(\w+)\.model_dump\(.*\)\["organization_id"\]\s*=\s*org_id'
replacement = r'\1 = \2.model_dump()\n    \1["organization_id"] = org_id'
text = re.sub(pattern, replacement, text)

with open('e:/saer.pk/backend/app/routes/others.py', 'w', encoding='utf-8') as f:
    f.write(text)
    
print("Fixed others.py")
