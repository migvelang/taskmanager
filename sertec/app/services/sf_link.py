"""Parseo de la descripción de casos Salesforce para vincularlos con las OST.

En la hoja Base SF el F11 y/o la OST vienen embebidos en texto libre, con
formatos muy variados, por ejemplo:
    "F11: 1162463382  OST Nº 50315"
    "OST: 37149 Y F1162339847"
    "ost;48385 ... sku:16900650"
    "FOLIO 1162356875 OST 38857"

Estrategia:
  * F11: los folios F11 son números que empiezan en 11 y tienen 10 dígitos
    (ej: 1162463382). Se buscan con prioridad los precedidos por F11/FOLIO/F,
    y como respaldo cualquier 11xxxxxxxx suelto.
  * OST: número precedido por las palabras OST / OST Nº / ost;. Se evita
    confundirlo con SKU/boletas exigiendo la palabra clave OST.
Si no se encuentra ni F11 ni OST => el caso se marca como "error_creacion".
"""
import re

# F11: 10 dígitos comenzando en 11, opcionalmente precedido por F/F11/FOLIO.
_F11_KEYED = re.compile(r"(?:F\s*11|F11|FOLIO|F)\s*[:\-;.]?\s*(11\d{8})", re.IGNORECASE)
_F11_LOOSE = re.compile(r"\b(11\d{8})\b")

# OST: exige la palabra OST cerca del número (2 a 7 dígitos).
_OST_KEYED = re.compile(r"OST\s*(?:N[º°ro.]*)?\s*[:\-;.#]?\s*(\d{2,7})", re.IGNORECASE)


def parse_descripcion(texto: str | None) -> tuple[str | None, str | None]:
    """Devuelve (f11, ost) extraídos de la descripción, o (None, None)."""
    if not texto:
        return None, None
    t = str(texto)

    f11 = None
    m = _F11_KEYED.search(t)
    if m:
        f11 = m.group(1)
    else:
        m = _F11_LOOSE.search(t)
        if m:
            f11 = m.group(1)

    ost = None
    m = _OST_KEYED.search(t)
    if m:
        ost = m.group(1).lstrip("0") or m.group(1)  # normaliza ceros a la izquierda

    return f11, ost


def link_status(f11: str | None, ost: str | None) -> str:
    """Un caso está 'vinculado' si trae F11 u OST; si no, es 'error_creacion'."""
    return "vinculado" if (f11 or ost) else "error_creacion"
