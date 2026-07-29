"""Panel de alertas."""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_user, resolve_tienda
from ..models import Alerta, GestionOst, User
from ..services import stats
from ..templating import templates

router = APIRouter()

# Categorías (tipos) del panel, en orden de aparición.
TIPOS = {
    "incumplimiento": "🔴 Incumplimientos",
    "posible_incumplimiento": "🟠 Posibles incumplimientos",
    "facturacion": "🧾 Facturación a proveedor",
    "pendiente_gestion": "📋 Pendientes de gestión",
}


@router.get("/alertas")
def alertas(
    request: Request,
    tipo: str | None = None,
    prioridad: str | None = None,
    gestion: str | None = None,
    tienda: str | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    tienda = resolve_tienda(request, tienda)
    carga = stats.ultima_carga(db)
    ctx = {"request": request, "user": user, "carga": carga, "tipos": TIPOS,
           "tipo_sel": tipo, "prioridad_sel": prioridad, "gestion_sel": gestion,
           "tienda": tienda, "q": q or "", "tiendas": []}
    if not carga:
        return templates.TemplateResponse("alerts.html", {**ctx, "vacio": True})

    ctx["tiendas"] = stats.lista_tiendas(db, carga.id)

    base = db.query(Alerta).filter(Alerta.carga_id == carga.id)
    if tienda:
        base = base.filter(Alerta.cruce_tienda == tienda)

    q_alertas = base
    if tipo:
        q_alertas = q_alertas.filter(Alerta.tipo == tipo)
    if prioridad:
        q_alertas = q_alertas.filter(Alerta.severidad == prioridad)
    if gestion:
        q_alertas = q_alertas.filter(Alerta.gestion == gestion)
    if q:
        term = f"%{q.strip()}%"
        q_alertas = q_alertas.filter(or_(Alerta.ost_num.ilike(term), Alerta.ss_nro.ilike(term)))

    orden = {"alta": 0, "media": 1, "baja": 2}
    items = q_alertas.all()
    items.sort(key=lambda a: (orden.get(a.severidad, 3), a.tipo))

    # Auditoría: quién gestionó cada OST (desde la memoria persistente).
    ctx["gestion_por"] = dict(
        db.query(GestionOst.ost_num, GestionOst.actualizado_por)
        .filter(GestionOst.actualizado_por.isnot(None)).all()
    )

    # Conteos por tipo (respetando tienda), para las pestañas.
    conteos_q = db.query(Alerta.tipo, func.count(Alerta.id)).filter(Alerta.carga_id == carga.id)
    if tienda:
        conteos_q = conteos_q.filter(Alerta.cruce_tienda == tienda)
    conteos = dict(conteos_q.group_by(Alerta.tipo).all())
    return templates.TemplateResponse(
        "alerts.html",
        {**ctx, "vacio": False, "items": items[:500], "total": len(items), "conteos": conteos},
    )


def _upsert_gestion(db: Session, ost_num: str, email: str, *, gestion=None, pu=None):
    g = db.query(GestionOst).filter(GestionOst.ost_num == ost_num).first()
    if not g:
        g = GestionOst(ost_num=ost_num)
        db.add(g)
    if gestion is not None:
        g.gestion = gestion
    if pu is not None:
        g.pu_manual = pu or None
    g.actualizado_por = email
    return g


@router.post("/alertas/{alerta_id}/gestion")
def cambiar_gestion(
    alerta_id: int,
    request: Request,
    estado: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    a = db.query(Alerta).filter(Alerta.id == alerta_id).first()
    if a and estado in ("nueva", "vista", "gestionada"):
        a.gestion = estado
        if a.ost_num:  # recordar la gestión entre cargas
            _upsert_gestion(db, a.ost_num, user.email, gestion=estado)
        db.commit()
    return RedirectResponse(request.headers.get("referer") or "/alertas", status_code=303)


@router.post("/alertas/{alerta_id}/pu")
def registrar_pu(
    alerta_id: int,
    request: Request,
    pu: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    a = db.query(Alerta).filter(Alerta.id == alerta_id).first()
    if a and a.ost_num:
        pu = pu.strip()
        a.ss_nro = pu or a.ss_nro
        _upsert_gestion(db, a.ost_num, user.email, pu=pu)
        db.commit()
    return RedirectResponse(request.headers.get("referer") or "/alertas", status_code=303)
