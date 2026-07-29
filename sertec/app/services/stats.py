"""Agregaciones para el dashboard a partir de la última carga."""
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import Alerta, Carga, OstSnapshot, SfSnapshot
from . import labels


def ultima_carga(db: Session) -> Carga | None:
    return (
        db.query(Carga)
        .filter(Carga.estado == "listo")
        .order_by(Carga.fecha_extraccion.desc())
        .first()
    )


def lista_tiendas(db: Session, carga_id: int) -> list[str]:
    rows = (
        db.query(OstSnapshot.cruce_tienda)
        .filter(OstSnapshot.carga_id == carga_id, OstSnapshot.cruce_tienda.isnot(None))
        .distinct()
        .order_by(OstSnapshot.cruce_tienda)
        .all()
    )
    return [r[0] for r in rows]


def _agregar_por_etiqueta(pares: list[tuple], fn) -> list[tuple]:
    """Aplica `fn` a la categoría y suma los conteos que comparten etiqueta."""
    acc: dict[str, int] = {}
    for k, v in pares:
        etiqueta = fn(k) if k not in (None, "Sin dato") else "Sin dato"
        acc[etiqueta] = acc.get(etiqueta, 0) + v
    return sorted(acc.items(), key=lambda x: x[1], reverse=True)


def lista_garantias(db: Session, carga_id: int) -> list[str]:
    rows = (
        db.query(OstSnapshot.prod_tipo_garantia)
        .filter(OstSnapshot.carga_id == carga_id, OstSnapshot.prod_tipo_garantia.isnot(None))
        .distinct()
        .order_by(OstSnapshot.prod_tipo_garantia)
        .all()
    )
    return [r[0] for r in rows]


def dashboard_data(db: Session, carga: Carga, tienda: str | None = None,
                   garantia: str | None = None) -> dict:
    base = db.query(OstSnapshot).filter(OstSnapshot.carga_id == carga.id)
    if tienda:
        base = base.filter(OstSnapshot.cruce_tienda == tienda)
    if garantia:
        base = base.filter(OstSnapshot.prod_tipo_garantia == garantia)

    def contar(q):
        return q.with_entities(func.count(OstSnapshot.id)).scalar() or 0

    abiertas_q = base.filter(OstSnapshot.ost_estado.like("%ABIERTA%"))
    kpis = {
        "abiertas": contar(abiertas_q),
        "en_plazo": contar(base.filter(OstSnapshot.flag_plazo == "Dentro de plazo")),
        "fuera_plazo": contar(base.filter(OstSnapshot.flag_plazo == "Fuera de plazo")),
        "cerradas": contar(base.filter(OstSnapshot.ost_estado.like("%CERRADA%"))),
        "canceladas": contar(base.filter(OstSnapshot.ost_estado.like("%CANCELADA%"))),
    }

    # Casos PU (Salesforce) abiertos (sin fecha de cierre), filtrados por tienda
    sf_q = db.query(func.count(SfSnapshot.id)).filter(
        SfSnapshot.carga_id == carga.id, SfSnapshot.fecha_cierre.is_(None)
    )
    if tienda:
        sf_q = sf_q.filter(SfSnapshot.tienda_origen == tienda)
    kpis["sf_abiertos"] = sf_q.scalar() or 0

    def agrupar(col, q=None, limite=None):
        qq = (q or base).with_entities(col, func.count(OstSnapshot.id)).group_by(col).order_by(func.count(OstSnapshot.id).desc())
        if limite:
            qq = qq.limit(limite)
        return [(k if k is not None else "Sin dato", v) for k, v in qq.all()]

    por_rango = agrupar(OstSnapshot.rango_sertec, abiertas_q)
    # ordenar por número de tramo
    por_rango = sorted(por_rango, key=lambda x: x[0])
    # subestado con etiqueta legible, agregando los que comparten etiqueta
    por_subestado = _agregar_por_etiqueta(agrupar(OstSnapshot.ost_subestado, abiertas_q), labels.subestado)[:8]
    por_garantia = agrupar(OstSnapshot.prod_tipo_garantia)
    top_tiendas = agrupar(OstSnapshot.cruce_tienda, abiertas_q, limite=10) if not tienda else []
    por_marca = agrupar(OstSnapshot.prod_marca, abiertas_q, limite=10)

    # Resumen de alertas por tipo (respetando el filtro de tienda)
    alertas_q = db.query(Alerta.tipo, func.count(Alerta.id)).filter(Alerta.carga_id == carga.id)
    if tienda:
        alertas_q = alertas_q.filter(Alerta.cruce_tienda == tienda)
    alertas_por_tipo = dict(alertas_q.group_by(Alerta.tipo).all())

    return {
        "kpis": kpis,
        "por_rango": por_rango,
        "por_subestado": por_subestado,
        "por_garantia": por_garantia,
        "top_tiendas": top_tiendas,
        "por_marca": por_marca,
        "alertas_por_tipo": alertas_por_tipo,
    }
