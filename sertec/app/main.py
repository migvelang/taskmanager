"""Punto de entrada de la app SERTEC (FastAPI)."""
import logging

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from .config import settings
from .db import Base, SessionLocal, engine
from .models import User
from .routers import alerts, auth, cargas, cases, dashboard, upload
from .security import hash_password
from .templating import TEMPLATES_DIR, templates  # noqa: F401

app = FastAPI(title=settings.APP_NAME)
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY, max_age=60 * 60 * 12)

app.mount("/static", StaticFiles(directory=str(TEMPLATES_DIR.parent / "static")), name="static")

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(upload.router)
app.include_router(alerts.router)
app.include_router(cases.router)
app.include_router(cargas.router)


@app.exception_handler(StarletteHTTPException)
async def auth_redirect(request: Request, exc: StarletteHTTPException):
    """Redirige a /login cuando falta autenticación en vistas HTML."""
    if exc.status_code == 401:
        return RedirectResponse("/login")
    return templates.TemplateResponse(
        "error.html",
        {"request": request, "code": exc.status_code, "detail": exc.detail},
        status_code=exc.status_code,
    )


logger = logging.getLogger("sertec")


@app.on_event("startup")
def startup():
    # Nunca se hace drop_all: create_all solo crea tablas que falten, así que los
    # datos ya cargados sobreviven a cada redeploy.
    Base.metadata.create_all(bind=engine)
    _seed_admin()
    _avisar_backend_datos()


def _avisar_backend_datos():
    """Avisa en los logs qué base se está usando y alerta si es efímera.

    Con SQLite dentro del contenedor los datos se pierden en cada redeploy; con
    Postgres persisten. Este aviso permite detectar de inmediato una mala
    configuración de DATABASE_URL antes de perder cargas.
    """
    url = settings.DATABASE_URL
    if url.startswith("sqlite"):
        logger.warning(
            "⚠️  SERTEC está usando SQLite (%s). Los datos se BORRAN en cada "
            "redeploy. En producción define DATABASE_URL apuntando a Postgres.",
            url,
        )
    else:
        # Oculta credenciales al registrar el host.
        host = url.split("@")[-1] if "@" in url else url
        logger.info("SERTEC usando base persistente: %s", host)


def _seed_admin():
    """Garantiza el usuario admin definido por ADMIN_EMAIL/ADMIN_PASSWORD.

    Es idempotente: en cada arranque asegura que exista un admin con ese correo
    y sincroniza su contraseña con la variable de entorno. Así, cambiar
    ADMIN_PASSWORD y redeployar siempre deja credenciales válidas, sin importar
    el orden en que se configuraron las variables la primera vez.
    """
    db = SessionLocal()
    try:
        email = settings.ADMIN_EMAIL.lower().strip()
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.hashed_password = hash_password(settings.ADMIN_PASSWORD)
            user.rol = "admin"
            user.activo = True
        else:
            db.add(User(
                email=email,
                nombre="Administrador",
                hashed_password=hash_password(settings.ADMIN_PASSWORD),
                rol="admin",
            ))
        db.commit()
    finally:
        db.close()
