"""Pestaña de Configuración (protegida con clave): edición de reglas de alerta."""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_user
from ..models import AppConfig, ReglaAlerta, User
from ..security import verify_password
from ..services import labels, reglas as reglas_mod
from ..templating import templates

router = APIRouter()


def _config_ok(request: Request) -> bool:
    return bool(request.session.get("config_ok"))


@router.get("/config")
def config_home(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    guardado: int | None = None,
):
    if not _config_ok(request):
        return templates.TemplateResponse(
            "config_login.html", {"request": request, "user": user, "error": None}
        )
    reglas = db.query(ReglaAlerta).order_by(ReglaAlerta.nombre).all()
    return templates.TemplateResponse(
        "config.html",
        {"request": request, "user": user, "reglas": reglas, "guardado": guardado,
         "estados": reglas_mod.ESTADOS, "subestados": reglas_mod.SUBESTADOS,
         "gestiones": reglas_mod.GESTIONES},
    )


@router.post("/config/acceso")
def config_acceso(
    request: Request,
    clave: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    cfg = db.query(AppConfig).filter(AppConfig.clave == "config_password_hash").first()
    if cfg and verify_password(clave, cfg.valor):
        request.session["config_ok"] = True
        return RedirectResponse("/config", status_code=303)
    return templates.TemplateResponse(
        "config_login.html",
        {"request": request, "user": user, "error": "Clave incorrecta."},
        status_code=401,
    )


@router.get("/config/salir")
def config_salir(request: Request, user: User = Depends(require_user)):
    request.session.pop("config_ok", None)
    return RedirectResponse("/config", status_code=303)


@router.post("/config/reglas")
async def guardar_reglas(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    if not _config_ok(request):
        return RedirectResponse("/config", status_code=303)

    # Los campos llegan como <campo>_<id>.
    form = await request.form()

    reglas = db.query(ReglaAlerta).all()
    for r in reglas:
        r.activa = form.get(f"activa_{r.id}") == "on"
        r.requiere_pu = form.get(f"requiere_pu_{r.id}") == "on"
        r.severidad = form.get(f"severidad_{r.id}") or r.severidad
        r.ost_estado = form.get(f"ost_estado_{r.id}") or None
        r.subestado = form.get(f"subestado_{r.id}") or None
        r.gestion_producto = form.get(f"gestion_producto_{r.id}") or None

        def _int(name):
            v = form.get(f"{name}_{r.id}")
            try:
                return int(v) if v not in (None, "") else None
            except ValueError:
                return None

        r.rango_min = _int("rango_min") or 1
        r.dias_min = _int("dias_min")
        mensaje = form.get(f"mensaje_{r.id}")
        if mensaje is not None:
            r.mensaje = mensaje.strip() or r.mensaje
    db.commit()
    return RedirectResponse("/config?guardado=1", status_code=303)


@router.post("/config/reglas/nueva")
async def crear_regla(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    if not _config_ok(request):
        return RedirectResponse("/config", status_code=303)
    form = await request.form()
    est = form.get("n_ost_estado") or None
    sub = form.get("n_subestado") or None
    ges = form.get("n_gestion_producto") or None
    if not (est or sub or ges):
        return RedirectResponse("/config", status_code=303)  # al menos una condición

    partes = [labels.estado(est) if est else None,
              labels.subestado(sub) if sub else None,
              labels.gestion(ges) if ges else None]
    nombre = " · ".join(p for p in partes if p) or "Regla"
    try:
        rango_min = int(form.get("n_rango_min") or 1)
    except ValueError:
        rango_min = 1
    dias_min = form.get("n_dias_min")
    try:
        dias_min = int(dias_min) if dias_min not in (None, "") else None
    except ValueError:
        dias_min = None

    db.add(ReglaAlerta(
        ost_estado=est, subestado=sub, gestion_producto=ges, nombre=nombre,
        activa=True, solo_abierta=False,
        rango_min=rango_min, dias_min=dias_min,
        severidad=form.get("n_severidad") or "media",
        requiere_pu=form.get("n_requiere_pu") == "on",
        mensaje=(form.get("n_mensaje") or "").strip() or "Revisar.",
    ))
    db.commit()
    return RedirectResponse("/config?guardado=1", status_code=303)


@router.post("/config/reglas/{regla_id}/eliminar")
def eliminar_regla(
    regla_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    if not _config_ok(request):
        return RedirectResponse("/config", status_code=303)
    db.query(ReglaAlerta).filter(ReglaAlerta.id == regla_id).delete()
    db.commit()
    return RedirectResponse("/config?guardado=1", status_code=303)
