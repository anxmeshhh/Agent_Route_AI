"""
wsgi.py — Gunicorn entry point for Docker/production
Usage: gunicorn wsgi:app
"""
from app import create_app

app = create_app()
