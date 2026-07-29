"""Carga del Excel diario (procesamiento en segundo plano)."""
import os
import tempfile

from fastapi import APIRouter, BackgroundTasks, Depends, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_user
from ..models import User
from ..services import ingest
from ..templating import templates

router = APIRouter()


@router.get("/cargar")
def cargar_form(request: Request, user: User = Depends(require_user)):
    return templates.TemplateResponse(
        "upload.html", {"request": request, "user": user, "error": None, "ok": None}
    )


@router.post("/cargar")
async def cargar_submit(
    request: Request,
    background_tasks: BackgroundTasks,
    archivo: UploadFile,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    if not archivo.filename.lower().endswith((".xlsx", ".xlsm")):
        return templates.TemplateResponse(
            "upload.html",
            {"request": request, "user": user, "error": "El archivo debe ser .xlsx", "ok": None},
            status_code=400,
        )

    # Guarda el archivo en un temporal persistente (lo borra la tarea de fondo).
    fd, path = tempfile.mkstemp(suffix=".xlsx")
    with os.fdopen(fd, "wb") as f:
        f.write(await archivo.read())

    # Validación rápida + creación de la carga (estado "procesando").
    try:
        carga = ingest.crear_carga(db, path, archivo.filename, user.email)
    except ingest.IngestError as e:
        db.rollback()
        os.remove(path)
        return templates.TemplateResponse(
            "upload.html",
            {"request": request, "user": user, "error": str(e), "ok": None},
            status_code=400,
        )
    except Exception as e:  # noqa: BLE001
        db.rollback()
        os.remove(path)
        return templates.TemplateResponse(
            "upload.html",
            {"request": request, "user": user, "error": f"Error leyendo el archivo: {e}", "ok": None},
            status_code=500,
        )

    # El trabajo pesado (insertar 40k filas + alertas) corre en segundo plano.
    background_tasks.add_task(ingest.procesar_carga_bg, carga.id, path)
    return RedirectResponse(f"/cargas?procesando={carga.id}", status_code=303)
