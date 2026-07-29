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
# Etiquetas legibles de estados (como filtro |disp_x y como función disp_x())
templates.env.filters["disp_estado"] = labels.estado
templates.env.filters["disp_subestado"] = labels.subestado
templates.env.filters["disp_gestion"] = labels.gestion
templates.env.globals["disp_estado"] = labels.estado
templates.env.globals["disp_subestado"] = labels.subestado
templates.env.globals["disp_gestion"] = labels.gestion
