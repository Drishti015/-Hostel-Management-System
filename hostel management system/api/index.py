import os
import sys
from pathlib import Path

# Ensure application root is in Python module search path
PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from app import create_app

# Vercel looks for a WSGI callable named 'app'
app = create_app(os.environ.get('FLASK_ENV', 'production'))
