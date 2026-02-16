
import os
import sys

# Ensure usage of the current directory for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.utils.auth import hash_password

try:
    print("Testing hash_password...")
    pwd = "password123"
    print(f"Password length: {len(pwd)}")
    hashed = hash_password(pwd)
    print(f"Hash success: {hashed}")
except Exception as e:
    print(f"Error: {e}")
