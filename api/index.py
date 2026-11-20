"""Vercel entry point: serve the Flask app as a serverless function."""
import os
import sys

# The Flask app lives in the project root, one folder up.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import app  # noqa: E402,F401  (Vercel looks for "app")
