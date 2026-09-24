"""Run from the repository root: python -m uvicorn main.main:app."""
from .api import create_app

app = create_app()
