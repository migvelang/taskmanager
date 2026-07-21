"""Generador de Tickets — servidor local.

Se ejecuta en tu propio computador (localhost). Nada sale a internet salvo
tu navegación normal al portal de Falabella. Sirve una UI para:

  1. Cargar el Excel (columnas A=OST, B=F11, C=GD, D=SN).
  2. Previsualizar el texto de cada ticket.
  3. Crear los tickets en modo ASISTIDO (siempre disponible) o AUTOMÁTICO
     (Playwright, requiere selectores configurados).
  4. Escribir el N° de ticket en la columna E y descargar el Excel actualizado.
"""

from __future__ import annotations

import threading
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
import os

from ticketgen.config import load_config, Config
from ticketgen.excel import TicketWorkbook
from ticketgen import bot as botmod

BASE_DIR = os.path.dirname(__file__)

app = FastAPI(title="Generador de Tickets")


# ------------------------------------------------------------------ estado
class AppState:
    def __init__(self):
        self.config: Config = load_config()
        self.wb: Optional[TicketWorkbook] = None
        self.filename: str = "tickets.xlsx"
        # --- estado del modo automático ---
        self.auto_thread: Optional[threading.Thread] = None
        self.auto_status: dict = {"running": False}
        self.continue_event = threading.Event()
        self.cancel_flag = False


state = AppState()


# ------------------------------------------------------------------ UI
@app.get("/", response_class=HTMLResponse)
def index():
    with open(os.path.join(BASE_DIR, "static", "index.html"), encoding="utf-8") as fh:
        return fh.read()


# ------------------------------------------------------------------ carga
@app.post("/api/upload")
async def upload(
    file: UploadFile = File(...),
    has_header: Optional[str] = Form(None),
):
    data = await file.read()
    hh: Optional[bool]
    if has_header is None or has_header == "auto":
        hh = None
    else:
        hh = has_header == "true"
    try:
        wb = TicketWorkbook(
            data,
            has_header=hh,
            output_column=state.config.output_column,
            suffix=state.config.suffix,
        )
    except Exception as exc:
        raise HTTPException(400, f"No se pudo leer el Excel: {exc}")

    state.wb = wb
    state.filename = file.filename or "tickets.xlsx"
    rows = [r.to_dict() for r in wb.rows()]
    return {
        "filename": state.filename,
        "has_header": wb.has_header,
        "output_column": wb.output_column,
        "count": len(rows),
        "pending": sum(1 for r in rows if not r["ticket"]),
        "rows": rows,
        "automatic_ready": state.config.automatic_ready,
    }


# ------------------------------------------------------------------ guardar ticket (modo asistido)
@app.post("/api/ticket")
async def set_ticket(excel_row: int = Form(...), ticket_number: str = Form(...)):
    if state.wb is None:
        raise HTTPException(400, "No hay Excel cargado.")
    ticket_number = ticket_number.strip()
    if not ticket_number:
        raise HTTPException(400, "El número de ticket está vacío.")
    state.wb.set_ticket(excel_row, ticket_number)
    return {"ok": True, "excel_row": excel_row, "ticket_number": ticket_number}


# ------------------------------------------------------------------ descargar
@app.get("/api/download")
def download():
    if state.wb is None:
        raise HTTPException(400, "No hay Excel cargado.")
    data = state.wb.to_bytes()
    headers = {
        "Content-Disposition": f'attachment; filename="{state.filename}"'
    }
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


# ------------------------------------------------------------------ modo automático
def _auto_worker(rows: list[dict]):
    """Corre en un hilo aparte: abre navegador, espera login, crea tickets."""
    st = state.auto_status
    try:
        bot = botmod.PortalBot(state.config)
    except Exception as exc:
        st.update(running=False, error=str(exc))
        return

    try:
        bot.start()
        st.update(phase="login", message="Inicia sesión y completa el 2FA en la ventana del navegador, luego presiona «Ya inicié sesión».")
        # Esperar a que el usuario confirme el login (o auto-detección).
        while not state.continue_event.is_set():
            if state.cancel_flag:
                st.update(running=False, phase="cancelado")
                bot.close()
                return
            if bot.is_logged_in():
                break
            state.continue_event.wait(timeout=1.0)

        st.update(phase="working", message="Creando tickets…")
        for i, row in enumerate(rows):
            if state.cancel_flag:
                st.update(phase="cancelado")
                break
            st.update(current=i + 1, total=len(rows), current_row=row["excel_row"])
            try:
                bot.goto_new_ticket()
                ticket = bot.create_ticket(row["description"])
                state.wb.set_ticket(row["excel_row"], ticket)
                st.setdefault("results", []).append(
                    {"excel_row": row["excel_row"], "ticket": ticket, "ok": True}
                )
            except Exception as exc:
                st.setdefault("results", []).append(
                    {"excel_row": row["excel_row"], "ok": False, "error": str(exc)}
                )
        st.update(phase="done", message="Proceso finalizado.")
    except Exception as exc:
        st.update(error=str(exc))
    finally:
        bot.close()
        st.update(running=False)


@app.post("/api/auto/start")
def auto_start():
    if state.wb is None:
        raise HTTPException(400, "No hay Excel cargado.")
    if not botmod.PLAYWRIGHT_AVAILABLE:
        raise HTTPException(400, "Playwright no está instalado. Usa el modo asistido o revisa el README.")
    if not state.config.automatic_ready:
        raise HTTPException(400, "Faltan selectores en config.json. Usa el modo asistido o revisa el README.")
    if state.auto_status.get("running"):
        raise HTTPException(409, "Ya hay un proceso automático en curso.")

    pending = [r.to_dict() for r in state.wb.rows() if not r["ticket"]]
    state.continue_event.clear()
    state.cancel_flag = False
    state.auto_status = {"running": True, "phase": "starting", "total": len(pending), "current": 0, "results": []}
    state.auto_thread = threading.Thread(target=_auto_worker, args=(pending,), daemon=True)
    state.auto_thread.start()
    return {"ok": True, "pending": len(pending)}


@app.post("/api/auto/continue")
def auto_continue():
    state.continue_event.set()
    return {"ok": True}


@app.post("/api/auto/cancel")
def auto_cancel():
    state.cancel_flag = True
    state.continue_event.set()
    return {"ok": True}


@app.get("/api/auto/status")
def auto_status():
    return JSONResponse(state.auto_status)


if __name__ == "__main__":
    import uvicorn

    print("\n  Generador de Tickets ->  http://127.0.0.1:8000\n")
    uvicorn.run(app, host="127.0.0.1", port=8000)
