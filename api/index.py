"""
Vercel Serverless Entry Point
"""
import sys
import os

# Add the parent directory to path so we can import 'app' package
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Set environment to production
os.environ.setdefault('FLASK_ENV', 'production')

from app import create_app

# Vercel expects the app to be named 'app'
app = create_app()

# Handler for Vercel
def handler(request):
    return app(request)
