"""Carga del Excel diario."""
import tempfile

from fastapi import APIRouter, Depends, Request, UploadFile
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

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=True) as tmp:
        tmp.write(await archivo.read())
        tmp.flush()
        try:
            carga = ingest.ingest_file(db, tmp.name, archivo.filename, user.email)
        except ingest.IngestError as e:
            db.rollback()
            return templates.TemplateResponse(
                "upload.html",
                {"request": request, "user": user, "error": str(e), "ok": None},
                status_code=400,
            )
        except Exception as e:  # noqa: BLE001
            db.rollback()
            return templates.TemplateResponse(
                "upload.html",
                {"request": request, "user": user, "error": f"Error procesando el archivo: {e}", "ok": None},
                status_code=500,
            )

    return RedirectResponse(f"/cargas?ok={carga.id}", status_code=303)
