"""Motor de alertas: compara la carga actual contra la anterior.

Genera alertas de dos naturalezas:
  * De cambio (requieren carga previa): incumplimiento nuevo, cambio de estado,
    envejecimiento.
  * De estado (se evalúan sobre la foto actual): reglas configurables por
    subestado, facturación a proveedor, PU que no cumple matriz / error creación.
"""
import re

from sqlalchemy.orm import Session

from ..models import Alerta, Carga, OstSnapshot, SfSnapshot
from . import labels, reglas as reglas_mod


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
    reglas_map = reglas_mod.cargar_reglas(db)

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

        # Reglas configurables por subestado (estado actual)
        _evaluar_regla(alertas, carga.id, o, reglas_map)
        # Facturación a proveedor por revisar (estado actual)
        _evaluar_facturacion(alertas, carga.id, o)

        if not p:
            continue  # el resto requiere carga anterior

        # Nuevo incumplimiento
        if o.flag_plazo == "Fuera de plazo" and p["flag_plazo"] != "Fuera de plazo" and _abierta(o.ost_estado):
            alertas.append(Alerta(
                carga_id=carga.id, tipo="incumplimiento", severidad="alta",
                ost_num=o.ost_num, cruce_tienda=o.cruce_tienda,
                titulo=f"OST {o.ost_num} cruzó a FUERA DE PLAZO",
                detalle=f"{o.prod_nombre or ''} · {labels.subestado(o.ost_subestado) or ''}",
                valor_anterior=p["flag_plazo"] or "—", valor_actual="Fuera de plazo",
            ))

        # Cambio de estado / subestado / gestión de producto
        # (campo, valor_ant, valor_act, etiquetador)
        cambios = []
        if o.ost_estado != p["estado"]:
            cambios.append(("Estado", p["estado"], o.ost_estado, labels.estado))
        if o.ost_subestado != p["subestado"]:
            cambios.append(("Subestado", p["subestado"], o.ost_subestado, labels.subestado))
        if o.ost_estado_gestion_producto != p["gestion"]:
            cambios.append(("Gestión producto", p["gestion"], o.ost_estado_gestion_producto, labels.gestion))
        if cambios:
            escalado = any(
                x[2] and ("PROBLEMAS" in str(x[2]).upper() or "RECHAZ" in str(x[2]).upper()
                          or "CANCELAR" in str(x[2]).upper())
                for x in cambios
            )
            detalle = " | ".join(
                f"{c}: {fn(a) or '—'} → {fn(b) or '—'}" for c, a, b, fn in cambios
            )
            _, va, vb, fn0 = cambios[0]
            alertas.append(Alerta(
                carga_id=carga.id, tipo="cambio_estado",
                severidad="alta" if escalado else "media",
                ost_num=o.ost_num, cruce_tienda=o.cruce_tienda,
                titulo=f"OST {o.ost_num}: cambio de estado",
                detalle=detalle,
                valor_anterior=fn0(va), valor_actual=fn0(vb),
            ))

        # Envejecimiento: subió de tramo de días
        if _abierta(o.ost_estado) and _tramo(o.rango_sertec) > _tramo(p["rango"]) > 0:
            alertas.append(Alerta(
                carga_id=carga.id, tipo="envejecimiento", severidad="media",
                ost_num=o.ost_num, cruce_tienda=o.cruce_tienda,
                titulo=f"OST {o.ost_num} aumentó de antigüedad",
                detalle=f"{o.prod_nombre or ''} · {labels.subestado(o.ost_subestado) or ''}",
                valor_anterior=p["rango"], valor_actual=o.rango_sertec,
            ))

    # --- Alertas de casos Salesforce (estado actual) ---
    for s in db.query(SfSnapshot).filter(SfSnapshot.carga_id == carga.id).yield_per(1000):
        cerrado = bool(s.fecha_cierre) or (s.estado or "").lower() in ("cerrado", "closed")
        if s.validacion_matriz and "NO_CUMPLE" in s.validacion_matriz.upper():
            alertas.append(Alerta(
                carga_id=carga.id, tipo="sf_no_cumple_matriz", severidad="media",
                ss_nro=s.ss_nro, ost_num=s.ost_parseada, cruce_tienda=s.tienda_origen,
                titulo=f"Caso PU {s.ss_nro} no cumple validación de matriz",
                detalle=s.motivo_no_cumple or s.nivel_3,
                valor_actual=s.validacion_matriz,
            ))
        if s.link_status == "error_creacion" and not cerrado:
            alertas.append(Alerta(
                carga_id=carga.id, tipo="sf_error_creacion", severidad="media",
                ss_nro=s.ss_nro, cruce_tienda=s.tienda_origen,
                titulo=f"Caso PU {s.ss_nro} sin F11/OST (posible error de creación)",
                detalle=(s.descripcion or "")[:200],
                valor_actual=s.estado,
            ))

    db.bulk_save_objects(alertas)
    db.flush()
    return len(alertas)


def _evaluar_regla(alertas: list, carga_id: int, o: OstSnapshot, reglas_map: dict):
    """Aplica la regla configurable del subestado de la OST, si corresponde."""
    if not o.ost_subestado:
        return
    r = reglas_map.get(labels.base(o.ost_subestado))
    if not r or not r.activa:
        return
    if r.solo_abierta and not _abierta(o.ost_estado):
        return

    tramo = _tramo(o.rango_sertec)
    dias = o.dias_sertec or 0
    if r.dias_min is not None:
        if dias < r.dias_min:
            return
    elif tramo < (r.rango_min or 1):
        return

    sev = r.severidad or "media"
    if r.sev_alta_desde_rango and tramo >= r.sev_alta_desde_rango:
        sev = "alta"
    if r.gestion_prioridad and labels.base(o.ost_estado_gestion_producto) == r.gestion_prioridad:
        sev = "alta"
    if o.f11_tipo_cliente == "Cliente":  # los clientes son prioridad
        sev = "alta"

    alertas.append(Alerta(
        carga_id=carga_id, tipo="regla", severidad=sev, requiere_pu=bool(r.requiere_pu),
        ost_num=o.ost_num, cruce_tienda=o.cruce_tienda,
        titulo=f"OST {o.ost_num} · {labels.subestado(o.ost_subestado)}",
        detalle=r.mensaje,
        valor_actual=o.rango_sertec,
    ))


def _evaluar_facturacion(alertas: list, carga_id: int, o: OstSnapshot):
    """Revisar facturación a proveedor: gestión FACTURACION_PROVEEDOR, transacción
    DEVOLUCION/CAMBIO y sin F3 generado."""
    if (labels.base(o.ost_estado_gestion_producto) == "FACTURACION_PROVEEDOR"
            and (o.xtransac_full or "").upper() in ("DEVOLUCION", "CAMBIO")
            and o.f11srx_status_f03 == "NO F3"):
        alertas.append(Alerta(
            carga_id=carga_id, tipo="facturacion", severidad="media",
            ost_num=o.ost_num, cruce_tienda=o.cruce_tienda,
            titulo=f"OST {o.ost_num} · Revisar facturación a proveedor",
            detalle=f"{o.xtransac_full} · sin F3 · {o.prod_nombre or ''}",
            valor_actual="NO F3",
        ))
