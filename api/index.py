"""
Vercel Serverless Entry Point
"""
import sys
import os

# Add the parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app

app = create_app()

# Vercel expects the app to be named 'app' or 'application'
application = app
