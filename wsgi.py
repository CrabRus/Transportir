"""WSGI entry point (PythonAnywhere, flask CLI)."""
from app import create_app

application = create_app()
app = application
