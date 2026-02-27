from app.main import app

print("=== All /hotels routes with their source ===")
for r in app.routes:
    if not hasattr(r, 'path'):
        continue
    path = r.path
    if 'hotel' not in path:
        continue
    endpoint = getattr(r, 'endpoint', None)
    module = getattr(endpoint, '__module__', 'unknown') if endpoint else 'unknown'
    name = getattr(endpoint, '__name__', 'unknown') if endpoint else 'unknown'
    methods = getattr(r, 'methods', set())
    print(f"[{module}.{name}] Methods: {methods}, Path: {path}")
