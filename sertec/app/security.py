"""Autenticación por sesión (cookie firmada) y hashing de contraseñas."""
import bcrypt
from fastapi import Request
from sqlalchemy.orm import Session

from .models import User


def hash_password(password: str) -> str:
    # bcrypt admite máximo 72 bytes; se trunca de forma segura.
    return bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8")[:72], hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = db.query(User).filter(User.email == email.lower().strip(), User.activo == True).first()  # noqa: E712
    if user and verify_password(password, user.hashed_password):
        return user
    return None


def current_user(request: Request, db: Session) -> User | None:
    """Devuelve el usuario de la sesión, o None si no ha iniciado sesión."""
    uid = request.session.get("uid")
    if not uid:
        return None
    return db.query(User).filter(User.id == uid, User.activo == True).first()  # noqa: E712
