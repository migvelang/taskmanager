"""Etiquetas legibles para los estados crudos (según diccionario oficial).

Convierte los valores técnicos que vienen en el Excel a la forma "MOSTRAR COMO"
definida por el negocio. La regla general es: quitar el prefijo numérico
("8. "), reemplazar guiones bajos por espacios y pasar a mayúsculas. Los casos
que no siguen esa regla se listan como excepciones explícitas.

Solo afecta la *presentación*: los valores crudos se siguen guardando tal cual en
la base, de modo que la lógica (detección de abiertas, comparaciones, etc.) no
cambia.
"""
import re

_PREFIX = re.compile(r"^\s*\d+\.\s*")


def _base(v) -> str | None:
    """Quita el prefijo numérico y espacios; deja la forma con guiones bajos."""
    if v is None:
        return None
    return _PREFIX.sub("", str(v)).strip()


def base(v) -> str | None:
    """Llave normalizada de un estado/subestado (sin prefijo numérico).

    Ej: '8. PRODUCTO_EN_ST' -> 'PRODUCTO_EN_ST'. Sirve como clave estable para
    las reglas de alerta.
    """
    return _base(v)


def _generic(v) -> str | None:
    b = _base(v)
    if b is None:
        return None
    return b.replace("_", " ").upper()


# --- Excepciones que no salen de la regla general ---
_SUBESTADO = {
    "CON_RESPUESTA_ST": "CON RESPUESTA DE ST",
    "CON_RESPUESTA_ST_GC_0": "CON RESPUESTA DE ST GC",
    "CON_RESPUESTA_ST_GC_1": "CON RESPUESTA DE ST GC",
    "PENDIENTE_DE_RETIRO_ASEGURADORA": "PENDIENTE RETIRO ASEGURADORA",
}

_GESTION = {
    "En gestión postventa tienda": "EN GESTIÓN POSVENTA TIENDA",
}


def estado(v) -> str | None:
    """OST_ESTADO / F11_ESTADO: solo quita prefijo y normaliza."""
    return _generic(v)


def subestado(v) -> str | None:
    b = _base(v)
    if b is None:
        return None
    return _SUBESTADO.get(b, b.replace("_", " ").upper())


def gestion(v) -> str | None:
    if v is None:
        return None
    if str(v) in _GESTION:
        return _GESTION[str(v)]
    return _generic(v)
