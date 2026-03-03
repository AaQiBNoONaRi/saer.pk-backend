import sys
import os

# Set Python path explicitly
INTERP = os.path.expanduser("~/virtualenv/app.saer.pk/3.12/bin/python")
if sys.executable != INTERP:
    try:
        os.execl(INTERP, INTERP, *sys.argv)
    except Exception:
        pass

# Add project root to module search path
sys.path.insert(0, os.path.dirname(__file__))

# Load environment variables explicitly for cPanel
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

from a2wsgi import ASGIMiddleware
from app.main import app

application = ASGIMiddleware(app)