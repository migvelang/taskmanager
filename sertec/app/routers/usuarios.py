"""Gestión de usuarios (solo administrador)."""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_admin
from ..models import User
from ..security import hash_password
from ..templating import templates

router = APIRouter()


@router.get("/usuarios")
def listar(
    request: Request,
    ok: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    usuarios = db.query(User).order_by(User.activo.desc(), User.email).all()
    return templates.TemplateResponse(
        "usuarios.html",
        {"request": request, "user": admin, "usuarios": usuarios, "ok": ok, "error": error},
    )


@router.post("/usuarios/nuevo")
def crear(
    request: Request,
    email: str = Form(...),
    nombre: str = Form(""),
    password: str = Form(...),
    rol: str = Form("visor"),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    email = email.lower().strip()
    if not email or not password:
        return RedirectResponse("/usuarios?error=Faltan+datos", status_code=303)
    if db.query(User).filter(User.email == email).first():
        return RedirectResponse("/usuarios?error=Ese+correo+ya+existe", status_code=303)
    db.add(User(
        email=email, nombre=nombre.strip() or None,
        hashed_password=hash_password(password),
        rol="admin" if rol == "admin" else "visor",
    ))
    db.commit()
    return RedirectResponse("/usuarios?ok=Usuario+creado", status_code=303)


@router.post("/usuarios/{user_id}/editar")
def editar(
    user_id: int,
    request: Request,
    nombre: str = Form(""),
    rol: str = Form("visor"),
    activo: str = Form(None),
    password: str = Form(""),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        return RedirectResponse("/usuarios?error=No+existe", status_code=303)

    u.nombre = nombre.strip() or None
    # No permitir que el admin se quite a sí mismo el acceso o el rol admin.
    if u.id == admin.id:
        u.rol = "admin"
        u.activo = True
    else:
        u.rol = "admin" if rol == "admin" else "visor"
        u.activo = activo == "on"
    if password.strip():
        u.hashed_password = hash_password(password.strip())
    db.commit()
    return RedirectResponse("/usuarios?ok=Usuario+actualizado", status_code=303)


@router.post("/usuarios/{user_id}/eliminar")
def eliminar(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if user_id == admin.id:
        return RedirectResponse("/usuarios?error=No+puedes+eliminar+tu+propia+cuenta", status_code=303)
    db.query(User).filter(User.id == user_id).delete()
    db.commit()
    return RedirectResponse("/usuarios?ok=Usuario+eliminado", status_code=303)
