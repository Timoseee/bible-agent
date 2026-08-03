"""Resolve bundled resources and writable application data paths."""

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def resource_path(relative_path):
    """Return a resource path in development or inside a PyInstaller bundle."""
    return Path(getattr(sys, "_MEIPASS", PROJECT_ROOT)) / relative_path


def writable_path(relative_path):
    """Return a path beside the executable for user-created files."""
    base_path = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else PROJECT_ROOT
    return base_path / relative_path
