"""Historial de cargas: listar, ver detalle y eliminar."""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_admin, require_user
from ..models import Carga, User
from ..templating import templates

router = APIRouter()


@router.get("/cargas")
def listar(
    request: Request,
    ok: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    cargas = db.query(Carga).order_by(Carga.fecha_extraccion.desc()).all()
    return templates.TemplateResponse(
        "cargas.html",
        {"request": request, "user": user, "cargas": cargas, "ok": ok},
    )


@router.post("/cargas/{carga_id}/eliminar")
def eliminar(
    carga_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    carga = db.query(Carga).filter(Carga.id == carga_id).first()
    if carga:
        db.delete(carga)
        db.commit()
    return RedirectResponse("/cargas", status_code=303)
