"""Reglas de alerta por subestado (configurables) y su semilla por defecto.

Los valores por defecto reproducen el diccionario entregado por el negocio
(Excel DASHBOARD_ALERTAS). Se pueden editar desde la pestaña Configuración.
"""
from sqlalchemy.orm import Session

from ..models import ReglaAlerta

# Cada regla se identifica por la llave base del subestado (sin prefijo numérico).
# campos: nombre, activa, rango_min, dias_min, sev_alta_desde_rango,
#         gestion_prioridad, severidad, requiere_pu, mensaje
DEFAULTS = [
    dict(subestado="GESTION_FINALIZADA", nombre="Gestión finalizada", activa=True,
         rango_min=1, severidad="alta", requiere_pu=True,
         mensaje="OST abierta con gestión finalizada: generar PU para cerrar la OST."),
    dict(subestado="CANCELAR", nombre="Cancelar", activa=True, rango_min=1,
         severidad="media", mensaje="Se generó CANCELAR: revisar."),
    dict(subestado="PROBLEMAS_OST", nombre="Problemas OST", activa=True, rango_min=1,
         severidad="alta", mensaje="Problemas en la OST: revisar."),
    dict(subestado="ESPERA_RETIRO_CLIENTE", nombre="Espera retiro cliente", activa=True,
         rango_min=4, severidad="media",
         mensaje="Enviar correo al cliente para que retire el producto en tienda."),
    dict(subestado="PRODUCTO_CON_GUIA", nombre="Producto con guía", activa=True,
         dias_min=1, severidad="media",
         mensaje="Más de 1 día con guía: tomar acción."),
    dict(subestado="CON_RESPUESTA_ST", nombre="Con respuesta de ST", activa=True,
         rango_min=1, severidad="media", gestion_prioridad="RECHAZADO",
         mensaje="Con respuesta de ST: revisar (prioridad si está RECHAZADO)."),
    dict(subestado="RETORNANDO_A_TIENDA", nombre="Retornando a tienda", activa=True,
         rango_min=3, sev_alta_desde_rango=4, severidad="media", requiere_pu=True,
         mensaje="Posible incumplimiento: crear PU para solicitar información de la OST."),
    dict(subestado="PRODUCTO_EN_ST", nombre="Producto en ST", activa=True,
         rango_min=3, sev_alta_desde_rango=4, severidad="media", requiere_pu=True,
         mensaje="Posible incumplimiento: crear PU para solicitar información de la OST."),
    dict(subestado="PENDIENTE_DE_RETIRO_ASEGURADORA", nombre="Pendiente retiro aseguradora",
         activa=True, rango_min=4, severidad="media",
         mensaje="Pedir retiro de productos a la aseguradora."),
    dict(subestado="EN_TRANSITO_A_ST", nombre="En tránsito a ST", activa=True,
         rango_min=2, severidad="media",
         mensaje="En tránsito a ST sin avanzar a Producto en ST."),
    dict(subestado="INGRESADO", nombre="Ingresado", activa=True, dias_min=1,
         severidad="media", mensaje="Más de 1 día en Ingresado."),
    dict(subestado="DAR_SOLUCION_A_CLIENTE", nombre="Dar solución a cliente", activa=True,
         rango_min=1, severidad="media", mensaje="Dar solución a cliente: revisar."),
    dict(subestado="PRODUCTO_EN_TIENDA", nombre="Producto en tienda", activa=True,
         rango_min=1, severidad="media",
         mensaje="Actualizar estado a Espera Retiro Cliente y la gestión de producto."),
    dict(subestado="CON_RESPUESTA_ST_GC_1", nombre="Con respuesta ST GC", activa=True,
         rango_min=1, severidad="media", mensaje="Con respuesta de ST GC: revisar."),
    dict(subestado="CON_RESPUESTA_ST_GC_0", nombre="Con respuesta ST GC (0)", activa=True,
         rango_min=1, severidad="media", mensaje="Con respuesta de ST GC: revisar."),
    dict(subestado="SINIESTRO_TRANSPORTE", nombre="Siniestro transporte", activa=True,
         rango_min=1, severidad="media", mensaje="Siniestro de transporte: revisar."),
    dict(subestado="EMISION_DE_GUIA", nombre="Emisión de guía", activa=True, dias_min=1,
         severidad="media", requiere_pu=True,
         mensaje="Más de 1 día en Emisión de guía: generar PU."),
    # Sin alerta
    dict(subestado="PENDIENTE_AGENDAMIENTO_VISITA_TECNICA",
         nombre="Pendiente agendamiento visita técnica", activa=False, mensaje="No genera alerta."),
    dict(subestado="VISITA_TECNICA_AGENDADA", nombre="Visita técnica agendada", activa=False,
         mensaje="No genera alerta."),
    dict(subestado="VISITA_TECNICA_REALIZADA", nombre="Visita técnica realizada", activa=False,
         mensaje="No genera alerta."),
]


def seed_reglas(db: Session):
    """Crea las reglas por defecto si aún no existen (por subestado)."""
    existentes = {r.subestado for r in db.query(ReglaAlerta.subestado).all()}
    nuevas = 0
    for d in DEFAULTS:
        if d["subestado"] not in existentes:
            db.add(ReglaAlerta(**d))
            nuevas += 1
    if nuevas:
        db.commit()


def cargar_reglas(db: Session) -> dict[str, ReglaAlerta]:
    """Devuelve las reglas indexadas por subestado base."""
    return {r.subestado: r for r in db.query(ReglaAlerta).all()}
