"""Instancia compartida de plantillas Jinja2 + helpers de formato."""
from pathlib import Path

from fastapi.templating import Jinja2Templates

from .services import labels

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _miles(v):
    try:
        return f"{int(v):,}".replace(",", ".")
    except (ValueError, TypeError):
        return v


templates.env.filters["miles"] = _miles
# Etiquetas legibles de estados
templates.env.filters["disp_estado"] = labels.estado
templates.env.filters["disp_subestado"] = labels.subestado
templates.env.filters["disp_gestion"] = labels.gestion
