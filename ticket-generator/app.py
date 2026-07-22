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

import json
import queue
import threading
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
import os

from ticketgen.config import load_config, Config, CONFIG_PATH
from ticketgen.excel import TicketWorkbook
from ticketgen.history import HistoryStore
from ticketgen import bot as botmod

BASE_DIR = os.path.dirname(__file__)
history = HistoryStore(os.path.join(BASE_DIR, "historial.json"))

# Nombre de campo (UI) -> clave en config.selectors
FIELD_MAP = {
    "description": "description_input",
    "submit": "submit_button",
    "result": "ticket_result",
}

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
        # --- estado del detector de campos (configuración de selectores) ---
        self.setup_thread: Optional[threading.Thread] = None
        self.setup_status: dict = {"running": False}
        self.setup_continue = threading.Event()
        self.setup_cancel = False
        self.setup_queue: "queue.Queue[str]" = queue.Queue()

    def reset_data(self):
        """Olvida el Excel cargado para empezar de cero con otro archivo."""
        self.wb = None
        self.filename = "tickets.xlsx"


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
@app.post("/api/row")
async def add_row(
    ost: str = Form(""),
    f11: str = Form(""),
    gd: str = Form(""),
    sn: str = Form(""),
):
    """Agrega un caso nuevo (OST/F11/GD/SN) al Excel desde la página."""
    ost, f11, gd, sn = ost.strip(), f11.strip(), gd.strip(), sn.strip()
    if not any([ost, f11, gd]):
        raise HTTPException(400, "Ingresa al menos OST, F11 o GD.")
    if state.wb is None:
        # Sin archivo cargado: empezamos un Excel nuevo en blanco.
        state.wb = TicketWorkbook.blank(
            output_column=state.config.output_column, suffix=state.config.suffix
        )
        state.filename = "tickets.xlsx"
    state.wb.add_row(ost, f11, gd, sn)
    rows = [r.to_dict() for r in state.wb.rows()]
    # Aviso de duplicado: ¿esta OST ya tiene ticket en el historial?
    dup = history.find_by_ost(ost) if ost else []
    return {
        "count": len(rows),
        "pending": sum(1 for r in rows if not r["ticket"]),
        "rows": rows,
        "filename": state.filename,
        "output_column": state.wb.output_column,
        "duplicate": [{"ost": d["ost"], "ticket": d["ticket"]} for d in dup],
    }


# ------------------------------------------------------------------ historial
@app.get("/api/history")
def history_list(q: str = ""):
    return {"items": history.list(q)}


@app.post("/api/history/delete")
def history_delete(id: str = Form(...)):
    ok = history.delete(id)
    return {"ok": ok}


@app.post("/api/ticket")
async def set_ticket(excel_row: int = Form(...), ticket_number: str = Form(...)):
    if state.wb is None:
        raise HTTPException(400, "No hay Excel cargado.")
    ticket_number = ticket_number.strip()
    if not ticket_number:
        raise HTTPException(400, "El número de ticket está vacío.")
    state.wb.set_ticket(excel_row, ticket_number)
    # Registrar en el historial persistente.
    vals = state.wb.row_values(excel_row)
    history.add(ticket=ticket_number, **vals)
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
                ticket = bot.create_ticket(
                    row["description"], should_cancel=lambda: state.cancel_flag
                )
                state.wb.set_ticket(row["excel_row"], ticket)
                history.add(
                    ost=row.get("ost", ""), f11=row.get("f11", ""),
                    gd=row.get("gd", ""), sn=row.get("sn", ""),
                    ticket=ticket, description=row.get("description", ""),
                )
                st.setdefault("results", []).append(
                    {"excel_row": row["excel_row"], "ticket": ticket, "ok": True}
                )
                print(f"[auto] fila {row['excel_row']}: OK -> {ticket}")
            except Exception as exc:
                msg = str(exc).splitlines()[0] if str(exc) else repr(exc)
                # Guardar una captura del primer fallo para poder diagnosticar.
                if not st.get("screenshot"):
                    shot = os.path.join(BASE_DIR, "ultimo-error.png")
                    if bot.save_screenshot(shot):
                        st["screenshot"] = True
                st.setdefault("results", []).append(
                    {"excel_row": row["excel_row"], "ok": False, "error": msg}
                )
                print(f"[auto] fila {row['excel_row']}: ERROR -> {msg}")
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
    if state.setup_status.get("running"):
        raise HTTPException(409, "El detector de campos está abierto. Ciérralo con «Cerrar detector» antes de iniciar.")

    pending = [r.to_dict() for r in state.wb.rows() if not r.ticket]
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


@app.get("/api/auto/error-screenshot")
def auto_error_screenshot():
    path = os.path.join(BASE_DIR, "ultimo-error.png")
    if not os.path.exists(path):
        raise HTTPException(404, "No hay captura de error.")
    with open(path, "rb") as fh:
        data = fh.read()
    return Response(content=data, media_type="image/png")


# ------------------------------------------------------------------ reiniciar
@app.post("/api/reset")
def reset():
    state.reset_data()
    return {"ok": True}


# ------------------------------------------------------------------ detector de campos (config del modo automático)
def _setup_worker():
    """Abre el portal y captura los selectores que el usuario va marcando."""
    st = state.setup_status
    try:
        bot = botmod.PortalBot(state.config)
    except Exception as exc:
        st.update(running=False, error=str(exc))
        return
    try:
        bot.start()
        st.update(phase="login", message="Inicia sesión y completa el 2FA en la ventana, luego presiona «Ya inicié sesión».")
        while not state.setup_continue.is_set():
            if state.setup_cancel:
                st.update(phase="cancelado")
                bot.close()
                st.update(running=False)
                return
            if bot.is_logged_in():
                break
            state.setup_continue.wait(timeout=0.5)

        st.update(phase="ready", message="Sesión lista. Marca cada campo cuando la app te lo pida.")
        st.setdefault("selectors", {})
        while True:
            if state.setup_cancel:
                break
            try:
                cmd = state.setup_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if cmd == "stop":
                break
            if cmd == "record_start":
                bot.start_recording()
                st.update(recording=True, message="Grabando el formulario fijo… llena todos los campos en el navegador.")
                continue
            if cmd == "record_stop":
                steps = bot.stop_recording()
                st["form_steps"] = steps
                st.update(recording=False, message=f"Formulario grabado: {len(steps)} pasos.")
                continue
            if cmd.startswith("capture:"):
                field = cmd.split(":", 1)[1]
                st.update(capturing=field, message=f"Haz clic en el elemento en el navegador…")
                try:
                    bot.arm_capture()
                    sel = bot.wait_capture()
                    st["selectors"][field] = sel
                    st.update(capturing=None, message=f"Capturado «{field}»: {sel}")
                except Exception as exc:
                    st.update(capturing=None, message=f"No se pudo capturar «{field}»: {exc}")
    except Exception as exc:
        st.update(error=str(exc))
    finally:
        bot.close()
        st.update(running=False, phase="closed")


@app.post("/api/auto/setup/start")
def setup_start():
    if not botmod.PLAYWRIGHT_AVAILABLE:
        raise HTTPException(400, "Playwright no está instalado. Revisa el README.")
    if state.setup_status.get("running") or state.auto_status.get("running"):
        raise HTTPException(409, "Ya hay un proceso de navegador en curso.")
    state.setup_continue.clear()
    state.setup_cancel = False
    state.setup_queue = queue.Queue()
    state.setup_status = {"running": True, "phase": "starting", "selectors": {}, "form_steps": []}
    state.setup_thread = threading.Thread(target=_setup_worker, daemon=True)
    state.setup_thread.start()
    return {"ok": True}


@app.post("/api/auto/setup/record/start")
def setup_record_start():
    if not state.setup_status.get("running"):
        raise HTTPException(400, "El detector no está activo.")
    state.setup_queue.put("record_start")
    return {"ok": True}


@app.post("/api/auto/setup/record/stop")
def setup_record_stop():
    if not state.setup_status.get("running"):
        raise HTTPException(400, "El detector no está activo.")
    state.setup_queue.put("record_stop")
    return {"ok": True}


@app.post("/api/auto/setup/continue")
def setup_continue():
    state.setup_continue.set()
    return {"ok": True}


@app.post("/api/auto/setup/capture")
def setup_capture(field: str = Form(...)):
    key = FIELD_MAP.get(field)
    if not key:
        raise HTTPException(400, f"Campo desconocido: {field}")
    if not state.setup_status.get("running"):
        raise HTTPException(400, "El detector no está activo.")
    state.setup_queue.put(f"capture:{key}")
    return {"ok": True, "field": key}


@app.post("/api/auto/setup/save")
def setup_save():
    sels = state.setup_status.get("selectors", {})
    if not all(sels.get(k) for k in ("description_input", "submit_button", "ticket_result")):
        raise HTTPException(400, "Faltan campos por capturar (descripción, enviar y número de ticket).")
    # Escribir/actualizar config.json conservando el resto de la config.
    data = {
        "portal_url": state.config.portal_url,
        "suffix": state.config.suffix,
        "output_column": state.config.output_column,
        "user_data_dir": state.config.user_data_dir,
        "selectors": {
            "description_input": sels.get("description_input", ""),
            "submit_button": sels.get("submit_button", ""),
            "ticket_result": sels.get("ticket_result", ""),
            "logged_in_marker": sels.get("logged_in_marker", ""),
        },
        "form_steps": state.setup_status.get("form_steps", []),
    }
    with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    # Cerrar el detector y recargar la config.
    state.setup_queue.put("stop")
    state.config = load_config()
    return {"ok": True, "automatic_ready": state.config.automatic_ready, "selectors": data["selectors"]}


@app.post("/api/auto/setup/cancel")
def setup_cancel():
    state.setup_cancel = True
    state.setup_queue.put("stop")
    return {"ok": True}


@app.get("/api/auto/setup/status")
def setup_status():
    return JSONResponse(state.setup_status)


if __name__ == "__main__":
    import uvicorn

    print("\n  Generador de Tickets ->  http://127.0.0.1:8000\n")
    uvicorn.run(app, host="127.0.0.1", port=8000)
