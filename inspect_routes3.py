from app.main import app

print("=== All /hotels routes with their source ===")
for r in app.routes:
    if hasattr(r, 'path') and 'hotels' in r.path:
        endpoint = getattr(r, 'endpoint', None)
        module = getattr(endpoint, '__module__', 'unknown') if endpoint else 'unknown'
        print(f"[{module}] Methods: {r.methods}, Path: {r.path}")
