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
    def create_ticket(self, description: str, timeout_ms: int = 30000, should_cancel=None) -> str:
        """Rellena el formulario completo, envía y devuelve el número de ticket.

        1) Reproduce los pasos grabados del formulario fijo (form_steps): campos
           de texto y listas desplegables que son iguales en todos los tickets.
        2) Escribe la descripción (lo único que varía por fila).
        3) Presiona enviar y lee el número de ticket.
        """
        sel = self.config.selectors
        if not self.config.automatic_ready:
            raise RuntimeError(
                "Selectores incompletos: configura description_input, "
                "submit_button y ticket_result en config.json."
            )

        page = self._page
        # 1) Formulario fijo (incluye pestañas y desplegables).
        if self.config.form_steps:
            self.replay_steps(self.config.form_steps, should_cancel=should_cancel)

        # 2) Descripción.
        try:
            page.wait_for_selector(sel.description_input, timeout=12000)
        except Exception:
            raise RuntimeError(
                f"No encontré el campo de descripción (selector '{sel.description_input}'). "
                "Puede que el formulario no haya quedado abierto tras el paso anterior."
            )
        field = page.locator(sel.description_input).first
        field.click()
        field.fill(description)

        # 3) Enviar y leer el número resultante.
        try:
            page.locator(sel.submit_button).first.click(timeout=12000)
        except Exception:
            raise RuntimeError(f"No pude presionar enviar (selector '{sel.submit_button}').")
        try:
            page.wait_for_selector(sel.ticket_result, timeout=timeout_ms)
        except Exception:
            raise RuntimeError(
                f"Envié pero no apareció el número de ticket (selector '{sel.ticket_result}')."
            )
        text = page.locator(sel.ticket_result).first.inner_text().strip()

        # 4) Cerrar el modal de confirmación ("Entendido") para dejar el
        #    formulario limpio y poder crear el siguiente ticket.
        self._dismiss_confirmation()
        return text

    def _dismiss_confirmation(self):
        """Cierra el modal de éxito tras enviar (best-effort, no falla la corrida).

        Primero intenta un selector configurado (opcional) y luego botones
        comunes por texto: «Entendido», «Aceptar», «OK», «Cerrar».
        """
        page = self._page
        configurado = getattr(self.config.selectors, "confirm_button", "") or ""
        if configurado:
            try:
                page.locator(configurado).first.click(timeout=5000)
                page.wait_for_timeout(600)
                return
            except Exception:
                pass
        for etiqueta in ("Entendido", "Aceptar", "Aceptar ", "OK", "Cerrar"):
            try:
                page.get_by_role("button", name=etiqueta, exact=False).first.click(timeout=1500)
                page.wait_for_timeout(600)
                return
            except Exception:
                try:
                    page.get_by_text(etiqueta, exact=True).first.click(timeout=1200)
                    page.wait_for_timeout(600)
                    return
                except Exception:
                    continue

    def save_screenshot(self, path: str):
        """Guarda una captura de la página actual (para diagnosticar fallos)."""
        try:
            self._page.screenshot(path=path, full_page=True)
            return True
        except Exception:
            return False

    # ---------- reproducción de pasos grabados (formulario fijo) ----------
    def replay_steps(self, steps: list, step_wait_ms: int = 450, should_cancel=None):
        """Ejecuta en orden los pasos grabados del formulario fijo.

        Tipos de paso:
          - fill:   escribir texto en un input/textarea.
          - select: elegir opción en un <select> nativo (por su texto).
          - check:  marcar/desmarcar un checkbox/radio.
          - click:  hacer clic (abrir desplegable personalizado y elegir opción).
        Los clics usan primero el selector CSS y, si falla, caen a buscar por
        el texto visible (más robusto para opciones de menús Angular).

        Si un paso falla, lanza un error que dice EXACTAMENTE qué paso fue.
        """
        page = self._page
        for i, st in enumerate(steps):
            if should_cancel and should_cancel():
                raise RuntimeError("Cancelado por el usuario.")
            kind = st.get("kind")
            sel = st.get("selector", "")
            text = st.get("text", "") or ""
            etiqueta = f"paso {i + 1} de {len(steps)} [{kind}] «{text or sel}»"
            try:
                if kind == "fill":
                    page.fill(sel, st.get("value", ""), timeout=8000)
                elif kind == "select":
                    page.select_option(sel, label=st.get("value", ""), timeout=8000)
                elif kind == "check":
                    loc = page.locator(sel).first
                    loc.check(timeout=8000) if st.get("value") else loc.uncheck(timeout=8000)
                elif kind == "click":
                    self._click_step(st)
            except Exception as exc:
                primera = str(exc).splitlines()[0] if str(exc) else repr(exc)
                raise RuntimeError(f"Falló el {etiqueta}: {primera}")
            page.wait_for_timeout(step_wait_ms)

    def _click_step(self, st: dict, force_text: bool = False):
        page = self._page
        sel = st.get("selector", "")
        text = (st.get("text") or "").strip()
        if not force_text and sel:
            try:
                page.locator(sel).first.click(timeout=8000)
                return
            except Exception:
                pass
        if text:
            page.get_by_text(text, exact=True).first.click(timeout=8000)
            return
        if sel:
            page.locator(sel).first.click(timeout=8000)

    # ---------- grabador del formulario fijo ----------
    def start_recording(self):
        """Empieza a grabar lo que el usuario hace en el formulario.

        Registra en orden: textos escritos, selects nativos, checkboxes y clics
        (incluye abrir desplegables personalizados y elegir su opción). NO
        interfiere con la navegación: los clics funcionan normalmente para que
        el usuario pueda llenar el formulario de verdad.
        """
        self._page.evaluate(
            """() => {
              window.__rec = [];
              function cssPath(el){
                if(!(el instanceof Element)) return '';
                function stable(node){
                  const tag = node.tagName.toLowerCase();
                  if(node.id) return '#' + CSS.escape(node.id);
                  for(const a of ['formcontrolname','data-testid','name']){
                    const v = node.getAttribute && node.getAttribute(a);
                    if(v) return tag + '[' + a + '="' + v + '"]';
                  }
                  return null;
                }
                const own = stable(el); if(own) return own;
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
                  parts.unshift(sel); el = el.parentElement;
                }
                return parts.join(' > ');
              }
              const textOf = (el) => (el.innerText || el.textContent || '').trim().replace(/\\s+/g,' ').slice(0,80);
              window.__recInput = (e) => {
                const el = e.target, tag = el.tagName.toLowerCase();
                if((tag === 'input' || tag === 'textarea') && el.type !== 'checkbox' && el.type !== 'radio'){
                  // No grabar "fill" en inputs de solo lectura/deshabilitados
                  // (suelen ser el disparador de un desplegable): al reproducir
                  // no se pueden escribir y darían error.
                  if(el.readOnly || el.disabled) return;
                  window.__rec.push({kind:'fill', selector: cssPath(el), value: el.value});
                }
              };
              window.__recChange = (e) => {
                const el = e.target, tag = el.tagName.toLowerCase();
                if(tag === 'select'){
                  const opt = el.options[el.selectedIndex];
                  window.__rec.push({kind:'select', selector: cssPath(el), value: opt ? opt.text.trim() : el.value});
                } else if((tag === 'input' || tag === 'textarea') && (el.type === 'checkbox' || el.type === 'radio')){
                  window.__rec.push({kind:'check', selector: cssPath(el), value: el.checked});
                }
              };
              window.__recClick = (e) => {
                const el = e.target, tag = el.tagName.toLowerCase();
                // Los <select> nativos se registran por su cambio de valor.
                if(tag === 'select') return;
                // OJO: SÍ registramos clics sobre <input>/<textarea>, porque muchos
                // desplegables de Angular se abren al hacer clic en un input (de solo
                // lectura). Si no, se perdería el paso que abre la lista.
                window.__rec.push({kind:'click', selector: cssPath(el), text: textOf(el)});
              };
              document.addEventListener('input', window.__recInput, true);
              document.addEventListener('change', window.__recChange, true);
              document.addEventListener('click', window.__recClick, true);
            }"""
        )

    def stop_recording(self) -> list:
        """Detiene la grabación y devuelve la lista de pasos (colapsando fills
        repetidos del mismo campo para quedarse con el último valor)."""
        steps = self._page.evaluate(
            """() => {
              try {
                document.removeEventListener('input', window.__recInput, true);
                document.removeEventListener('change', window.__recChange, true);
                document.removeEventListener('click', window.__recClick, true);
              } catch(e) {}
              return window.__rec || [];
            }"""
        )
        # Colapsar 'fill'/'select'/'check' consecutivos sobre el mismo selector.
        cleaned = []
        for st in steps:
            if (
                st.get("kind") in ("fill", "select", "check")
                and cleaned
                and cleaned[-1].get("kind") == st.get("kind")
                and cleaned[-1].get("selector") == st.get("selector")
            ):
                cleaned[-1] = st
            else:
                cleaned.append(st)
        return cleaned

    def goto_new_ticket(self):
        """Prepara el siguiente ticket SIN recargar la página.

        Recargar el portal (SPA de Angular) volvía a la pestaña por defecto y
        podía perder la sesión. En vez de eso, la navegación a «Formulario
        tienda» se reproduce como primer paso grabado (form_steps), que hace
        clic en esa pestaña. Aquí solo damos un pequeño respiro entre tickets.
        """
        self._page.wait_for_timeout(800)

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
