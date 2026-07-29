"""Motor de alertas: compara la carga actual contra la anterior.

Genera alertas de dos naturalezas:
  * De cambio (requieren carga previa): incumplimiento nuevo, cambio de estado,
    envejecimiento.
  * De estado (se evalúan sobre la foto actual): sin responsable, SF que no
    cumple matriz, SF con error de creación.
"""
import re

from sqlalchemy.orm import Session

from ..config import settings
from ..models import Alerta, Carga, OstSnapshot, SfSnapshot


def _abierta(estado: str | None) -> bool:
    return bool(estado) and ("ABIERTA" in estado.upper())


def _tramo(rango: str | None) -> int:
    """Número de tramo de RANGO_SERTEC (ej: '6) 31 y más' -> 6). 0 si no aplica."""
    if not rango:
        return 0
    m = re.match(r"\s*(\d)", rango)
    return int(m.group(1)) if m else 0


def _carga_anterior(db: Session, carga: Carga) -> Carga | None:
    return (
        db.query(Carga)
        .filter(Carga.fecha_extraccion < carga.fecha_extraccion, Carga.estado == "listo")
        .order_by(Carga.fecha_extraccion.desc())
        .first()
    )


def generar_alertas(db: Session, carga: Carga) -> int:
    """Genera y persiste las alertas de la carga. Devuelve la cantidad creada."""
    # Limpia alertas previas de esta carga (por si se reprocesa).
    db.query(Alerta).filter(Alerta.carga_id == carga.id).delete()

    alertas: list[Alerta] = []
    prev = _carga_anterior(db, carga)

    # --- Índice de la carga anterior (solo campos necesarios) ---
    prev_map: dict[str, dict] = {}
    if prev:
        cols = (
            OstSnapshot.ost_num, OstSnapshot.ost_estado, OstSnapshot.ost_subestado,
            OstSnapshot.ost_estado_gestion_producto, OstSnapshot.flag_plazo,
            OstSnapshot.rango_sertec,
        )
        for r in db.query(*cols).filter(OstSnapshot.carga_id == prev.id).all():
            prev_map[r.ost_num] = {
                "estado": r.ost_estado, "subestado": r.ost_subestado,
                "gestion": r.ost_estado_gestion_producto, "flag_plazo": r.flag_plazo,
                "rango": r.rango_sertec,
            }

    # --- Recorre las OST de la carga actual ---
    for o in db.query(OstSnapshot).filter(OstSnapshot.carga_id == carga.id).yield_per(2000):
        p = prev_map.get(o.ost_num)

        # Sin responsable (estado actual, solo abiertas)
        if _abierta(o.ost_estado) and (not o.flag_responsable or o.flag_responsable == "Sin responsable"):
            alertas.append(Alerta(
                carga_id=carga.id, tipo="sin_responsable", severidad="media",
                ost_num=o.ost_num, cruce_tienda=o.cruce_tienda,
                titulo=f"OST {o.ost_num} sin responsable asignado",
                detalle=o.prod_nombre, valor_actual=o.flag_responsable or "Sin responsable",
            ))

        if not p:
            continue  # el resto requiere carga anterior

        # Nuevo incumplimiento
        if o.flag_plazo == "Fuera de plazo" and p["flag_plazo"] != "Fuera de plazo" and _abierta(o.ost_estado):
            alertas.append(Alerta(
                carga_id=carga.id, tipo="incumplimiento", severidad="alta",
                ost_num=o.ost_num, cruce_tienda=o.cruce_tienda,
                titulo=f"OST {o.ost_num} cruzó a FUERA DE PLAZO",
                detalle=f"{o.prod_nombre or ''} · {o.ost_subestado or ''}",
                valor_anterior=p["flag_plazo"] or "—", valor_actual="Fuera de plazo",
            ))

        # Cambio de estado / subestado / gestión de producto
        cambios = []
        if o.ost_estado != p["estado"]:
            cambios.append(("Estado", p["estado"], o.ost_estado))
        if o.ost_subestado != p["subestado"]:
            cambios.append(("Subestado", p["subestado"], o.ost_subestado))
        if o.ost_estado_gestion_producto != p["gestion"]:
            cambios.append(("Gestión producto", p["gestion"], o.ost_estado_gestion_producto))
        if cambios:
            escalado = any(
                x[2] and ("PROBLEMAS" in str(x[2]).upper() or "RECHAZ" in str(x[2]).upper()
                          or "CANCELAR" in str(x[2]).upper())
                for x in cambios
            )
            detalle = " | ".join(f"{c}: {a or '—'} → {b or '—'}" for c, a, b in cambios)
            alertas.append(Alerta(
                carga_id=carga.id, tipo="cambio_estado",
                severidad="alta" if escalado else "media",
                ost_num=o.ost_num, cruce_tienda=o.cruce_tienda,
                titulo=f"OST {o.ost_num}: cambio de estado",
                detalle=detalle,
                valor_anterior=cambios[0][1], valor_actual=cambios[0][2],
            ))

        # Envejecimiento: subió de tramo de días
        if _abierta(o.ost_estado) and _tramo(o.rango_sertec) > _tramo(p["rango"]) > 0:
            alertas.append(Alerta(
                carga_id=carga.id, tipo="envejecimiento", severidad="media",
                ost_num=o.ost_num, cruce_tienda=o.cruce_tienda,
                titulo=f"OST {o.ost_num} envejeció de tramo",
                detalle=f"{o.prod_nombre or ''} · {o.ost_subestado or ''}",
                valor_anterior=p["rango"], valor_actual=o.rango_sertec,
            ))

    # --- Alertas de casos Salesforce (estado actual) ---
    for s in db.query(SfSnapshot).filter(SfSnapshot.carga_id == carga.id).yield_per(1000):
        cerrado = bool(s.fecha_cierre) or (s.estado or "").lower() in ("cerrado", "closed")
        if s.validacion_matriz and "NO_CUMPLE" in s.validacion_matriz.upper():
            alertas.append(Alerta(
                carga_id=carga.id, tipo="sf_no_cumple_matriz", severidad="media",
                ss_nro=s.ss_nro, ost_num=s.ost_parseada, cruce_tienda=s.tienda_origen,
                titulo=f"Caso SF {s.ss_nro} no cumple validación de matriz",
                detalle=s.motivo_no_cumple or s.nivel_3,
                valor_actual=s.validacion_matriz,
            ))
        if s.link_status == "error_creacion" and not cerrado:
            alertas.append(Alerta(
                carga_id=carga.id, tipo="sf_error_creacion", severidad="media",
                ss_nro=s.ss_nro, cruce_tienda=s.tienda_origen,
                titulo=f"Caso SF {s.ss_nro} sin F11/OST (posible error de creación)",
                detalle=(s.descripcion or "")[:200],
                valor_actual=s.estado,
            ))

    db.bulk_save_objects(alertas)
    db.flush()
    return len(alertas)
