"""Instancia compartida de plantillas Jinja2 + helpers de formato."""
from pathlib import Path

from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _miles(v):
    try:
        return f"{int(v):,}".replace(",", ".")
    except (ValueError, TypeError):
        return v


templates.env.filters["miles"] = _miles
