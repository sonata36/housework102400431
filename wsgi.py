"""Production WSGI entry point for a configured server process."""

from app import create_app


application = create_app()
