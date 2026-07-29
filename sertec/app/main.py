"""Punto de entrada de la app SERTEC (FastAPI)."""
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


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    _seed_admin()


def _seed_admin():
    """Crea el usuario administrador inicial si la tabla está vacía."""
    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            db.add(User(
                email=settings.ADMIN_EMAIL.lower(),
                nombre="Administrador",
                hashed_password=hash_password(settings.ADMIN_PASSWORD),
                rol="admin",
            ))
            db.commit()
    finally:
        db.close()
