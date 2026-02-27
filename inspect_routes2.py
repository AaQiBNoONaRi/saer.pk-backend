from app.main import app
print("=== All routes matching /api/hotels/ ===")
for r in app.routes:
    if hasattr(r, 'path') and r.path == '/api/hotels/':
        print(f"Methods: {r.methods}, path: {r.path}")

print("\n=== Routes for /api/hotels ===")
for r in app.routes:
    if hasattr(r, 'path') and r.path == '/api/hotels':
        print(f"Methods: {r.methods}, path: {r.path}")
