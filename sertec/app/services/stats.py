"""Agregaciones para el dashboard a partir de la última carga."""
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import Alerta, Carga, OstSnapshot, SfSnapshot


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


def dashboard_data(db: Session, carga: Carga, tienda: str | None = None) -> dict:
    base = db.query(OstSnapshot).filter(OstSnapshot.carga_id == carga.id)
    if tienda:
        base = base.filter(OstSnapshot.cruce_tienda == tienda)

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

    # Casos SF abiertos (sin fecha de cierre)
    sf_q = db.query(func.count(SfSnapshot.id)).filter(
        SfSnapshot.carga_id == carga.id, SfSnapshot.fecha_cierre.is_(None)
    )
    kpis["sf_abiertos"] = sf_q.scalar() or 0

    def agrupar(col, q=None, limite=None):
        qq = (q or base).with_entities(col, func.count(OstSnapshot.id)).group_by(col).order_by(func.count(OstSnapshot.id).desc())
        if limite:
            qq = qq.limit(limite)
        return [(k if k is not None else "Sin dato", v) for k, v in qq.all()]

    por_rango = agrupar(OstSnapshot.rango_sertec, abiertas_q)
    # ordenar por número de tramo
    por_rango = sorted(por_rango, key=lambda x: x[0])
    por_subestado = agrupar(OstSnapshot.ost_subestado, abiertas_q)[:8]
    por_garantia = agrupar(OstSnapshot.prod_tipo_garantia)
    top_tiendas = agrupar(OstSnapshot.cruce_tienda, abiertas_q, limite=10) if not tienda else []
    por_marca = agrupar(OstSnapshot.prod_marca, abiertas_q, limite=10)

    # Resumen de alertas por tipo
    alertas_por_tipo = dict(
        db.query(Alerta.tipo, func.count(Alerta.id))
        .filter(Alerta.carga_id == carga.id)
        .group_by(Alerta.tipo)
        .all()
    )

    return {
        "kpis": kpis,
        "por_rango": por_rango,
        "por_subestado": por_subestado,
        "por_garantia": por_garantia,
        "top_tiendas": top_tiendas,
        "por_marca": por_marca,
        "alertas_por_tipo": alertas_por_tipo,
    }
