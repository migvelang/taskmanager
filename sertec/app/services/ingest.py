"""Ingesta del Excel HISTORICO_SERTEC hacia la base de datos.

Lee las 3 hojas (Base SERTEC, Base SF, Resumen), valida el formato, crea la
`Carga` y guarda los snapshots de OST y SF. Al final dispara el motor de diffs.

Rendimiento:
  * La lectura del Excel usa python-calamine (lector en Rust), ~6x más rápido
    que openpyxl para 40k filas.
  * La inserción usa COPY en PostgreSQL (carga masiva), con caída a
    bulk_insert_mappings en SQLite (desarrollo local).
"""
import csv
import datetime as dt
import io
import re

from python_calamine import CalamineWorkbook
from sqlalchemy.orm import Session

from ..models import Carga, OstSnapshot, SfSnapshot
from . import sf_link

SHEET_SERTEC = "Base SERTEC"
SHEET_SF = "Base SF"
SHEET_RESUMEN = "Resumen"


class IngestError(Exception):
    pass


# --------------------------------------------------------------------------- #
# Carga masiva
# --------------------------------------------------------------------------- #
def _flush(db: Session, model, rows: list[dict]):
    """Inserta las filas de forma masiva (COPY en Postgres, bulk en otras)."""
    if not rows:
        return
    if db.bind.dialect.name == "postgresql":
        _copy_postgres(db, model.__tablename__, rows)
    else:
        db.bulk_insert_mappings(model, rows)


def _copy_postgres(db: Session, tabla: str, rows: list[dict]):
    """Carga masiva vía COPY ... FROM STDIN (formato CSV)."""
    cols = list(rows[0].keys())
    buf = io.StringIO()
    writer = csv.writer(buf)
    for r in rows:
        writer.writerow(["" if r[c] is None else r[c] for c in cols])
    buf.seek(0)
    collist = ", ".join(f'"{c}"' for c in cols)
    sql = f'COPY "{tabla}" ({collist}) FROM STDIN WITH (FORMAT csv, NULL \'\')'
    # Usa la conexión DBAPI de la sesión para participar en la misma transacción.
    dbapi_conn = db.connection().connection
    with dbapi_conn.cursor() as cur:
        cur.copy_expert(sql, buf)


# --------------------------------------------------------------------------- #
# Lectura del Excel (calamine)
# --------------------------------------------------------------------------- #
def _load_sheets(path: str) -> dict[str, list]:
    """Lee las 3 hojas obligatorias como listas de filas (rows[0] = encabezado)."""
    wb = CalamineWorkbook.from_path(path)
    disponibles = set(wb.sheet_names)
    for req in (SHEET_SERTEC, SHEET_SF, SHEET_RESUMEN):
        if req not in disponibles:
            raise IngestError(f"Falta la hoja obligatoria '{req}' en el archivo.")
    return {name: wb.get_sheet_by_name(name).to_python() for name in
            (SHEET_SERTEC, SHEET_SF, SHEET_RESUMEN)}


def _header_index(rows: list) -> dict:
    header = rows[0] if rows else []
    return {str(h).strip(): i for i, h in enumerate(header) if h not in (None, "")}


# --------------------------------------------------------------------------- #
# Conversores de valores (calamine entrega números como float, fechas como date)
# --------------------------------------------------------------------------- #
def _as_dt(v):
    if isinstance(v, dt.datetime):
        return v
    if isinstance(v, dt.date):
        return dt.datetime(v.year, v.month, v.day)
    return None


def _as_int(v):
    try:
        if v is None or v == "":
            return None
        return int(float(v))
    except (ValueError, TypeError):
        return None


def _as_float(v):
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (ValueError, TypeError):
        return None


def _s(v):
    """A texto normalizado. Los enteros que llegan como float (14405.0) se
    convierten a '14405' para no romper llaves como OST_NUM/SKU."""
    if v is None:
        return None
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    s = str(v).strip()
    return s or None


# --------------------------------------------------------------------------- #
# Metadatos de la hoja Resumen
# --------------------------------------------------------------------------- #
def _parse_fecha_extraccion(rows: list) -> dt.datetime:
    """Lee 'Fecha extracción' de la hoja Resumen (formato dd-mm-YYYY HH:MM)."""
    for row in rows:
        if row and row[0] and "extrac" in str(row[0]).lower():
            raw = row[1] if len(row) > 1 else None
            if isinstance(raw, dt.datetime):
                return raw
            m = re.search(r"(\d{2})-(\d{2})-(\d{4})[ T]+(\d{1,2}):(\d{2})", str(raw))
            if m:
                d, mo, y, h, mi = map(int, m.groups())
                return dt.datetime(y, mo, d, h, mi)
    raise IngestError("No se encontró 'Fecha extracción' en la hoja Resumen.")


def _parse_resumen_totales(rows: list) -> dict:
    tot = {}
    for row in rows:
        if row and len(row) > 1 and row[0] not in (None, "") and row[1] not in (None, ""):
            tot[str(row[0]).strip()] = row[1]
    return tot


def parse_workbook_meta(path: str) -> dict:
    """Lee solo metadatos (fecha y totales) para validar y detectar duplicados."""
    sheets = _load_sheets(path)
    resumen = sheets[SHEET_RESUMEN]
    return {
        "fecha_extraccion": _parse_fecha_extraccion(resumen),
        "totales": _parse_resumen_totales(resumen),
    }


# --------------------------------------------------------------------------- #
# Ingesta principal
# --------------------------------------------------------------------------- #
def ingest_file(db: Session, path: str, archivo_nombre: str, usuario: str) -> Carga:
    """Procesa el Excel y crea la Carga con sus snapshots. Devuelve la Carga."""
    sheets = _load_sheets(path)
    fecha = _parse_fecha_extraccion(sheets[SHEET_RESUMEN])
    totales = _parse_resumen_totales(sheets[SHEET_RESUMEN])

    existente = db.query(Carga).filter(Carga.fecha_extraccion == fecha).first()
    if existente:
        raise IngestError(
            f"Ya existe una carga con fecha de extracción {fecha:%d-%m-%Y %H:%M} "
            f"(carga #{existente.id}). Elimínala primero si quieres reprocesarla."
        )

    carga = Carga(
        fecha_extraccion=fecha,
        archivo_nombre=archivo_nombre,
        subido_por=usuario,
        estado="procesando",
        totales=totales,
    )
    db.add(carga)
    db.flush()  # obtener carga.id

    carga.n_ost = _ingest_sertec(db, sheets[SHEET_SERTEC], carga.id)
    carga.n_sf = _ingest_sf(db, sheets[SHEET_SF], carga.id)
    carga.estado = "listo"
    db.flush()

    # Motor de alertas (import diferido para evitar ciclo de imports).
    from .diff import generar_alertas
    carga.n_alertas = generar_alertas(db, carga)

    db.commit()
    db.refresh(carga)
    return carga


def _ingest_sertec(db: Session, rows: list, carga_id: int) -> int:
    h = _header_index(rows)

    def g(row, name):
        i = h.get(name)
        return row[i] if i is not None and i < len(row) else None

    batch = []
    for row in rows[1:]:
        ost_num = _s(g(row, "OST_NUM"))
        if not ost_num:
            continue
        batch.append({
            "carga_id": carga_id,
            "ost_num": ost_num,
            "f11_num": _s(g(row, "F11_NUM")),
            "f11_estado": _s(g(row, "F11_ESTADO")),
            "ost_estado": _s(g(row, "OST_ESTADO")),
            "ost_subestado": _s(g(row, "OST_SUBESTADO")),
            "ost_estado_gestion_producto": _s(g(row, "OST_ESTADO_GESTION_PRODUCTO")),
            "sub_estado_externo": _s(g(row, "SUB_ESTADO_EXTERNO")),
            "flag_plazo": _s(g(row, "FLAG_PLAZO")),
            "dias_sertec": _as_int(g(row, "DIAS_SERTEC")),
            "rango_sertec": _s(g(row, "RANGO_SERTEC")),
            "flag_responsable": _s(g(row, "FLAG_RESPONSABLE")),
            "responsable_sac": _s(g(row, "RESPONSABLE_SAC")),
            "responsable_mini_big_ticket": _s(g(row, "RESPONSABLE_MINI_BIG_TICKET")),
            "fecha_creacion": _as_dt(g(row, "OST_FECHA_CREACION")),
            "fecha_compromiso": _as_dt(g(row, "OST_FECHA_COMPROMISO")),
            "fecha_cierre": _as_dt(g(row, "OST_FECHA_CIERRE")),
            "prod_nombre": _s(g(row, "PROD_NOMBRE")),
            "prod_sku": _s(g(row, "PROD_SKU")),
            "prod_marca": _s(g(row, "PROD_MARCA")),
            "prod_modelo": _s(g(row, "PROD_MODELO")),
            "prod_numero_serie": _s(g(row, "PROD_NUMERO_SERIE")),
            "prod_garantia_modalidad": _s(g(row, "PROD_GARANTIA_MODALIDAD")),
            "prod_tipo_garantia": _s(g(row, "PROD_TIPO_GARANTIA")),
            "desc_falla": _s(g(row, "OST_DESC_FALLA")),
            "cruce_tienda": _s(g(row, "CRUCE_TIENDA")),
            "codigo_tienda": _s(g(row, "CODIGO_TIENDA")),
            "region": _s(g(row, "F11SRX_REGION")),
            "comuna": _s(g(row, "F11SRX_COMUNA")),
            "desc_linea": _s(g(row, "F11SRX_DESC_LINEA")),
            "desc_sublinea": _s(g(row, "F11SRX_DESC_SUBLINEA")),
            "precio_vta": _as_float(g(row, "F11SRX_PRECIO_VTA")),
        })
    _flush(db, OstSnapshot, batch)
    return len(batch)


def _ingest_sf(db: Session, rows: list, carga_id: int) -> int:
    h = _header_index(rows)

    def g(row, name):
        i = h.get(name)
        return row[i] if i is not None and i < len(row) else None

    batch = []
    for row in rows[1:]:
        ss_nro = _s(g(row, "SS_NRO"))
        if not ss_nro:
            continue
        descripcion = _s(g(row, "DESCRIPCION"))
        f11, ost = sf_link.parse_descripcion(descripcion)
        batch.append({
            "carga_id": carga_id,
            "ss_nro": ss_nro,
            "id_regulatorio": _s(g(row, "ID_REGULATORIO")),
            "estado": _s(g(row, "ESTADO")),
            "nivel_1": _s(g(row, "NIVEL_1")),
            "nivel_2": _s(g(row, "NIVEL_2")),
            "nivel_3": _s(g(row, "NIVEL_3")),
            "nivel_4": _s(g(row, "NIVEL_4")),
            "descripcion": descripcion,
            "fecha_creacion": _as_dt(g(row, "FECHA_CREACION")),
            "fecha_cierre": _as_dt(g(row, "FECHA_CIERRE")),
            "tipo_cierre": _s(g(row, "TIPO_CIERRE")),
            "nombre_propietario": _s(g(row, "NOMBRE_PROPIETARIO")),
            "tienda_origen": _s(g(row, "TIENDA_ORIGEN")),
            "validacion_matriz": _s(g(row, "VALIDACION_MATRIZ")),
            "motivo_no_cumple": _s(g(row, "MOTIVO_NO_CUMPLE_VALIDACION")),
            "f11_parseado": f11,
            "ost_parseada": ost,
            "link_status": sf_link.link_status(f11, ost),
        })
    _flush(db, SfSnapshot, batch)
    return len(batch)
