"""
wsgi.py — Gunicorn entry point for Docker/production
Usage: gunicorn wsgi:application
"""
from app import create_app

app = create_app()
application = app  # gunicorn alias
