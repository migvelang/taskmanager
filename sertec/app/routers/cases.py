"""Pantalla única de caso: une la OST (SERTEC) con su caso Salesforce."""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_user
from ..models import Carga, OstSnapshot, SfSnapshot, User
from ..services import stats
from ..templating import templates

router = APIRouter()


@router.get("/caso")
def buscar(
    request: Request,
    q: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    carga = stats.ultima_carga(db)
    ctx = {"request": request, "user": user, "carga": carga, "q": q}
    if not q or not carga:
        return templates.TemplateResponse("case_search.html", ctx)

    term = q.strip()
    # 1) OST directa
    ost = (
        db.query(OstSnapshot)
        .filter(OstSnapshot.carga_id == carga.id, OstSnapshot.ost_num == term)
        .first()
    )
    if not ost:
        ost = (
            db.query(OstSnapshot)
            .filter(OstSnapshot.carga_id == carga.id, OstSnapshot.f11_num == term)
            .first()
        )
    if ost:
        return RedirectResponse(f"/caso/ost/{ost.ost_num}", status_code=303)

    # 2) Caso SF por número
    sf = (
        db.query(SfSnapshot)
        .filter(SfSnapshot.carga_id == carga.id, SfSnapshot.ss_nro == term)
        .first()
    )
    if sf and sf.ost_parseada:
        return RedirectResponse(f"/caso/ost/{sf.ost_parseada}", status_code=303)
    if sf:
        return RedirectResponse(f"/caso/sf/{sf.ss_nro}", status_code=303)

    return templates.TemplateResponse("case_search.html", {**ctx, "no_result": True})


@router.get("/caso/ost/{ost_num}")
def detalle_ost(
    request: Request,
    ost_num: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    carga = stats.ultima_carga(db)
    actual = (
        db.query(OstSnapshot)
        .filter(OstSnapshot.carga_id == carga.id, OstSnapshot.ost_num == ost_num)
        .first()
    )
    # Línea de tiempo: la OST en todas las cargas
    timeline = (
        db.query(OstSnapshot, Carga.fecha_extraccion)
        .join(Carga, OstSnapshot.carga_id == Carga.id)
        .filter(OstSnapshot.ost_num == ost_num)
        .order_by(Carga.fecha_extraccion.asc())
        .all()
    )
    # Casos SF vinculados en la última carga
    sf_links = []
    if actual:
        filtros = [SfSnapshot.ost_parseada == ost_num]
        if actual.f11_num:
            filtros.append(SfSnapshot.f11_parseado == actual.f11_num)
        from sqlalchemy import or_
        sf_links = (
            db.query(SfSnapshot)
            .filter(SfSnapshot.carga_id == carga.id, or_(*filtros))
            .all()
        )
    return templates.TemplateResponse(
        "case_ost.html",
        {"request": request, "user": user, "carga": carga, "ost_num": ost_num,
         "actual": actual, "timeline": timeline, "sf_links": sf_links},
    )


@router.get("/caso/sf/{ss_nro}")
def detalle_sf(
    request: Request,
    ss_nro: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    carga = stats.ultima_carga(db)
    sf = (
        db.query(SfSnapshot)
        .filter(SfSnapshot.carga_id == carga.id, SfSnapshot.ss_nro == ss_nro)
        .first()
    )
    return templates.TemplateResponse(
        "case_sf.html",
        {"request": request, "user": user, "carga": carga, "sf": sf, "ss_nro": ss_nro},
    )
