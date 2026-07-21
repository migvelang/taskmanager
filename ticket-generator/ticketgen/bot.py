"""Automatización del navegador (MODO AUTOMÁTICO) con Playwright.

Puntos clave del diseño:

* Usa un **contexto persistente** (`launch_persistent_context`) apuntando a una
  carpeta local. Ahí se guardan las cookies/sesión, de modo que el login +
  verificación en 2 pasos solo se hace la PRIMERA vez (o cuando la sesión
  caduca). En corridas siguientes el portal ya reconoce la sesión.

* El navegador se abre **visible** (headless=False) para que el usuario pueda
  completar manualmente el 2FA cuando haga falta. El 2FA, por seguridad, nunca
  se almacena ni se automatiza.

* Playwright (API síncrona) se ejecuta en su propio hilo; no comparte el loop
  asíncrono de FastAPI.
"""

from __future__ import annotations

from typing import Optional

from .config import Config

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    PLAYWRIGHT_AVAILABLE = True
except Exception:  # pragma: no cover - Playwright es opcional
    PLAYWRIGHT_AVAILABLE = False


class PortalBot:
    """Controla una sesión de navegador contra el portal Pantalla Única."""

    def __init__(self, config: Config):
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError(
                "Playwright no está instalado. Instálalo con:\n"
                "  pip install playwright && python -m playwright install chromium"
            )
        self.config = config
        self._pw = None
        self._ctx = None
        self._page = None

    # ---------- ciclo de vida ----------
    def start(self):
        self._pw = sync_playwright().start()
        # Contexto persistente => la sesión sobrevive entre corridas.
        self._ctx = self._pw.chromium.launch_persistent_context(
            user_data_dir=self.config.user_data_dir,
            headless=False,
            viewport={"width": 1280, "height": 900},
        )
        self._page = self._ctx.pages[0] if self._ctx.pages else self._ctx.new_page()
        self._page.goto(self.config.portal_url, wait_until="domcontentloaded")
        return self._page

    def is_logged_in(self) -> bool:
        """True si detecta el marcador de sesión iniciada (si está configurado)."""
        marker = self.config.selectors.logged_in_marker
        if not marker:
            return False  # sin marcador no podemos saberlo automáticamente
        try:
            return self._page.locator(marker).first.is_visible(timeout=1500)
        except Exception:
            return False

    def close(self):
        try:
            if self._ctx:
                self._ctx.close()
        finally:
            if self._pw:
                self._pw.stop()
            self._ctx = None
            self._page = None
            self._pw = None

    # ---------- creación de un ticket ----------
    def create_ticket(self, description: str, timeout_ms: int = 30000) -> str:
        """Rellena la descripción, envía y devuelve el número de ticket.

        Requiere que los selectores estén configurados en config.json.
        Lanza una excepción si algo falla (la orquestación la captura).
        """
        sel = self.config.selectors
        if not self.config.automatic_ready:
            raise RuntimeError(
                "Selectores incompletos: configura description_input, "
                "submit_button y ticket_result en config.json."
            )

        page = self._page
        page.wait_for_selector(sel.description_input, timeout=timeout_ms)
        field = page.locator(sel.description_input).first
        field.click()
        field.fill(description)

        page.locator(sel.submit_button).first.click()

        # Esperar a que aparezca el número de ticket resultante.
        page.wait_for_selector(sel.ticket_result, timeout=timeout_ms)
        text = page.locator(sel.ticket_result).first.inner_text().strip()
        return text

    def goto_new_ticket(self):
        """Vuelve a la pantalla base para crear el siguiente ticket."""
        self._page.goto(self.config.portal_url, wait_until="domcontentloaded")

    # ---------- detector de campos (para configurar los selectores) ----------
    def arm_capture(self):
        """Deja el próximo clic del usuario "armado" para capturar su selector.

        Instala un listener en fase de captura que intercepta el siguiente clic
        (sin dejar que dispare la acción real: evita enviar el formulario al
        capturar el botón), calcula un selector CSS del elemento y lo deja en
        `window.__capturedSelector`.
        """
        self._page.evaluate(
            """() => {
              window.__captured = false;
              window.__capturedSelector = '';
              function cssPath(el){
                if(!(el instanceof Element)) return '';
                // Atributos estables preferidos (típicos en portales Angular).
                function stable(node){
                  const tag = node.tagName.toLowerCase();
                  if(node.id) return '#' + CSS.escape(node.id);
                  for(const a of ['formcontrolname','data-testid','name']){
                    const v = node.getAttribute && node.getAttribute(a);
                    if(v) return tag + '[' + a + '="' + v + '"]';
                  }
                  return null;
                }
                const own = stable(el);
                if(own) return own;
                const parts = [];
                while(el && el.nodeType === 1 && el.tagName.toLowerCase() !== 'html'){
                  const s = stable(el);
                  if(s){ parts.unshift(s); break; }
                  let sel = el.tagName.toLowerCase();
                  const parent = el.parentNode;
                  if(parent){
                    const sibs = Array.from(parent.children).filter(c => c.tagName === el.tagName);
                    if(sibs.length > 1){ sel += ':nth-of-type(' + (sibs.indexOf(el) + 1) + ')'; }
                  }
                  parts.unshift(sel);
                  el = el.parentElement;
                }
                return parts.join(' > ');
              }
              const handler = (e) => {
                e.preventDefault();
                e.stopPropagation();
                window.__capturedSelector = cssPath(e.target);
                window.__captured = true;
                window.removeEventListener('click', handler, true);
              };
              window.addEventListener('click', handler, true);
            }"""
        )

    def wait_capture(self, timeout_ms: int = 120000) -> str:
        """Espera a que el usuario haga clic y devuelve el selector capturado."""
        self._page.wait_for_function("window.__captured === true", timeout=timeout_ms)
        return self._page.evaluate("window.__capturedSelector")
