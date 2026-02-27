from app.main import app
for route in app.routes:
    if hasattr(route, 'path') and '/hotels' in route.path:
        methods = getattr(route, 'methods', None)
        print(f"Path: {route.path}, Methods: {methods}")
