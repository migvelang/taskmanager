"""Pestaña de Configuración (protegida con clave): edición de reglas de alerta."""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_user
from ..models import AppConfig, ReglaAlerta, User
from ..security import verify_password
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
        {"request": request, "user": user, "reglas": reglas, "guardado": guardado},
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
