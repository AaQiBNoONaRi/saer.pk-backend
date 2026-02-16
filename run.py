import uvicorn
import os
import sys

if __name__ == "__main__":
    # Ensure usage of the current directory for imports
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    
    print("🚀 Starting Saerpk 2.0 Backend...")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
