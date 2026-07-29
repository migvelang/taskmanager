"""Dashboard principal."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_user
from ..models import User
from ..services import stats
from ..templating import templates

router = APIRouter()


@router.get("/")
def dashboard(
    request: Request,
    tienda: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    carga = stats.ultima_carga(db)
    ctx = {"request": request, "user": user, "carga": carga, "tienda": tienda}
    if not carga:
        return templates.TemplateResponse("dashboard.html", {**ctx, "vacio": True})

    data = stats.dashboard_data(db, carga, tienda)
    tiendas = stats.lista_tiendas(db, carga.id)
    return templates.TemplateResponse(
        "dashboard.html",
        {**ctx, "vacio": False, "data": data, "tiendas": tiendas},
    )
