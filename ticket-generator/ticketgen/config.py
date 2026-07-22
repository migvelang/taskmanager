"""Carga de configuración (plantilla de texto y selectores del portal).

Los SELECTORES sirven solo para el MODO AUTOMÁTICO. Como el portal de
Falabella es interno y no conocemos su HTML de antemano, estos valores hay
que ajustarlos una vez usando el navegador (ver README, sección "Capturar
selectores"). Mientras estén vacíos, el modo automático queda deshabilitado y
se usa el modo asistido.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from .text import DEFAULT_SUFFIX

CONFIG_PATH = os.environ.get(
    "TICKETGEN_CONFIG",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json"),
)


@dataclass
class Selectors:
    # Selector CSS del campo de descripción/comentario del ticket.
    description_input: str = ""
    # Selector del botón "Enviar" / "Crear".
    submit_button: str = ""
    # Selector del elemento que muestra el número de ticket tras enviar.
    ticket_result: str = ""
    # (Opcional) selector que solo aparece cuando la sesión está iniciada,
    # para detectar si hay que pedir login + 2FA.
    logged_in_marker: str = ""


@dataclass
class Config:
    portal_url: str = "https://pantallaunica.falabella.com/#/sac"
    suffix: str = DEFAULT_SUFFIX
    output_column: str = "E"
    # Carpeta donde Playwright guarda la sesión (cookies) para no repetir login.
    user_data_dir: str = ".browser-session"
    selectors: Selectors = field(default_factory=Selectors)
    # Pasos grabados del formulario fijo (textos, desplegables, pestañas…).
    # Se reproducen antes de escribir la descripción de cada ticket.
    form_steps: list = field(default_factory=list)

    @property
    def automatic_ready(self) -> bool:
        s = self.selectors
        return bool(s.description_input and s.submit_button and s.ticket_result)


def load_config(path: str = CONFIG_PATH) -> Config:
    if not os.path.exists(path):
        return Config()
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    sel = Selectors(**raw.pop("selectors", {}))
    return Config(selectors=sel, **raw)
