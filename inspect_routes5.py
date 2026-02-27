from app.main import app
import json

results = []
for r in app.routes:
    if not hasattr(r, 'path'):
        continue
    path = r.path
    if 'hotel' not in path.lower():
        continue
    endpoint = getattr(r, 'endpoint', None)
    module = getattr(endpoint, '__module__', 'unknown') if endpoint else 'unknown'
    name = getattr(endpoint, '__name__', 'unknown') if endpoint else 'unknown'
    methods = list(getattr(r, 'methods', set()) or set())
    results.append({"module": module, "name": name, "methods": methods, "path": path})

with open("routes_output.json", "w") as f:
    json.dump(results, f, indent=2)

print("Done. Check routes_output.json")
