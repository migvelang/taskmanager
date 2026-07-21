"""Construcción del texto (descripción) de cada ticket.

Todos los tickets comparten la misma "raíz"; lo único que cambia son los
valores OST, F11, GD y (opcionalmente) SN que se extraen del Excel.
"""

from __future__ import annotations

# Sufijo fijo de la descripción. Se puede sobrescribir desde config.json.
DEFAULT_SUFFIX = (
    "tiene autorización de facturación, favor informar RMA para poder facturar."
)


def build_description(
    ost: str,
    f11: str,
    gd: str,
    sn: str = "",
    suffix: str = DEFAULT_SUFFIX,
) -> str:
    """Arma la descripción de un ticket.

    Ejemplos::

        >>> build_description("12345", "678", "910", "ABC123")
        'OST 12345 F11 678 GD 910 SN ABC123 tiene autorización de ...'

        >>> build_description("12345", "678", "910")   # sin SN
        'OST 12345 F11 678 GD 910 tiene autorización de ...'

    El SN solo se incluye cuando viene con valor (columna D del Excel).
    """
    partes = [f"OST {ost}", f"F11 {f11}", f"GD {gd}"]
    if sn and sn.strip():
        partes.append(f"SN {sn.strip()}")
    base = " ".join(partes)
    return f"{base} {suffix}".strip()
