"""Dependencias comunes: guard de autenticación."""
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .db import get_db
from .models import User
from .security import current_user


def require_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Exige sesión iniciada. Si no hay, lanza 401 (redirigido a /login)."""
    user = current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="No autenticado")
    return user


def require_admin(user: User = Depends(require_user)) -> User:
    if user.rol != "admin":
        raise HTTPException(status_code=403, detail="Requiere rol admin")
    return user


def resolve_tienda(request: Request, tienda_param: str | None) -> str | None:
    """Filtro de tienda persistente en la sesión.

    Si el usuario eligió explícitamente en el selector (`tienda_param` presente),
    se guarda o limpia en la sesión. Si no vino parámetro (navegación normal), se
    conserva la última tienda elegida. Así el filtro se mantiene entre pantallas.
    """
    if tienda_param is not None:
        if tienda_param.strip():
            request.session["tienda"] = tienda_param
        else:
            request.session.pop("tienda", None)
    return request.session.get("tienda")
