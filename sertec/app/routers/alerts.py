"""Panel de alertas."""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_user
from ..models import Alerta, User
from ..services import stats
from ..templating import templates

router = APIRouter()

TIPOS = {
    "incumplimiento": "🔴 Nuevos incumplimientos",
    "cambio_estado": "🔄 Cambios de estado",
    "envejecimiento": "⏳ Envejecimiento",
    "sin_responsable": "⚠️ Sin responsable",
    "sf_no_cumple_matriz": "🧩 SF no cumple matriz",
    "sf_error_creacion": "✍️ SF error de creación",
}


@router.get("/alertas")
def alertas(
    request: Request,
    tipo: str | None = None,
    gestion: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    carga = stats.ultima_carga(db)
    ctx = {"request": request, "user": user, "carga": carga, "tipos": TIPOS,
           "tipo_sel": tipo, "gestion_sel": gestion}
    if not carga:
        return templates.TemplateResponse("alerts.html", {**ctx, "vacio": True})

    q = db.query(Alerta).filter(Alerta.carga_id == carga.id)
    if tipo:
        q = q.filter(Alerta.tipo == tipo)
    if gestion:
        q = q.filter(Alerta.gestion == gestion)

    orden = {"alta": 0, "media": 1, "baja": 2}
    items = q.all()
    items.sort(key=lambda a: (orden.get(a.severidad, 3), a.tipo))

    conteos = dict(
        db.query(Alerta.tipo, func.count(Alerta.id))
        .filter(Alerta.carga_id == carga.id)
        .group_by(Alerta.tipo)
        .all()
    )
    return templates.TemplateResponse(
        "alerts.html",
        {**ctx, "vacio": False, "items": items[:500], "total": len(items), "conteos": conteos},
    )


@router.post("/alertas/{alerta_id}/gestion")
def cambiar_gestion(
    alerta_id: int,
    estado: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    a = db.query(Alerta).filter(Alerta.id == alerta_id).first()
    if a and estado in ("nueva", "vista", "gestionada"):
        a.gestion = estado
        db.commit()
    return RedirectResponse("/alertas", status_code=303)
