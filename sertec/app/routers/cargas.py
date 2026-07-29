"""Historial de cargas: listar, ver detalle y eliminar."""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import require_admin, require_user
from ..models import Alerta, Carga, OstSnapshot, SfSnapshot, User
from ..templating import templates

router = APIRouter()


@router.get("/cargas")
def listar(
    request: Request,
    ok: int | None = None,
    procesando: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    cargas = db.query(Carga).order_by(Carga.subido_en.desc()).all()
    persistente = not settings.DATABASE_URL.startswith("sqlite")
    hay_procesando = any(c.estado == "procesando" for c in cargas)
    return templates.TemplateResponse(
        "cargas.html",
        {"request": request, "user": user, "cargas": cargas, "ok": ok,
         "procesando": procesando, "hay_procesando": hay_procesando,
         "persistente": persistente},
    )


@router.post("/cargas/{carga_id}/eliminar")
def eliminar(
    carga_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    # Borrado masivo (una sentencia por tabla) para que sea rápido incluso con
    # ~40k filas; el ORM fila a fila era muy lento.
    for modelo in (Alerta, OstSnapshot, SfSnapshot):
        db.query(modelo).filter(modelo.carga_id == carga_id).delete(synchronize_session=False)
    db.query(Carga).filter(Carga.id == carga_id).delete(synchronize_session=False)
    db.commit()
    return RedirectResponse("/cargas", status_code=303)
