"""
Vercel Entry Point (root level)
"""
import os
os.environ['FLASK_ENV'] = 'production'

from config import ProductionConfig
from app import create_app

app = create_app(ProductionConfig)
