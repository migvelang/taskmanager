"""Panel de alertas."""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_user, resolve_tienda
from ..models import Alerta, User
from ..services import stats
from ..templating import templates

router = APIRouter()

TIPOS = {
    "regla": "📋 Gestión (reglas)",
    "incumplimiento": "🔴 Nuevos incumplimientos",
    "facturacion": "🧾 Facturación proveedor",
    "cambio_estado": "🔄 Cambios de estado",
    "envejecimiento": "⏳ Antigüedad",
    "sf_no_cumple_matriz": "🧩 PU no cumple matriz",
    "sf_error_creacion": "✍️ PU error de creación",
}


@router.get("/alertas")
def alertas(
    request: Request,
    tipo: str | None = None,
    gestion: str | None = None,
    tienda: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    tienda = resolve_tienda(request, tienda)
    carga = stats.ultima_carga(db)
    ctx = {"request": request, "user": user, "carga": carga, "tipos": TIPOS,
           "tipo_sel": tipo, "gestion_sel": gestion, "tienda": tienda, "tiendas": []}
    if not carga:
        return templates.TemplateResponse("alerts.html", {**ctx, "vacio": True})

    ctx["tiendas"] = stats.lista_tiendas(db, carga.id)

    base = db.query(Alerta).filter(Alerta.carga_id == carga.id)
    if tienda:
        base = base.filter(Alerta.cruce_tienda == tienda)

    q = base
    if tipo:
        q = q.filter(Alerta.tipo == tipo)
    if gestion:
        q = q.filter(Alerta.gestion == gestion)

    orden = {"alta": 0, "media": 1, "baja": 2}
    items = q.all()
    items.sort(key=lambda a: (orden.get(a.severidad, 3), a.tipo))

    conteos_q = db.query(Alerta.tipo, func.count(Alerta.id)).filter(Alerta.carga_id == carga.id)
    if tienda:
        conteos_q = conteos_q.filter(Alerta.cruce_tienda == tienda)
    conteos = dict(conteos_q.group_by(Alerta.tipo).all())
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
