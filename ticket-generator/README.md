# 🎫 Generador de Tickets · Facturación RMA

Aplicación **local** (corre en tu propio Mac) que lee un Excel con los datos de
cada caso y ayuda a crear los tickets en el portal
[Pantalla Única](https://pantallaunica.falabella.com/#/sac), escribiendo de
vuelta el número de ticket en el Excel.

Todos los tickets comparten la misma raíz; lo único que cambia es la descripción,
que se arma con los datos de cada fila:

```
OST <A> F11 <B> GD <C> SN <D> tiene autorización de facturación, favor informar RMA para poder facturar.
```

(el `SN` solo se agrega cuando la columna D trae valor).

## Estructura del Excel

| Columna | Contenido                       |
|---------|---------------------------------|
| **A**   | N° de OST                       |
| **B**   | N° de F11                       |
| **C**   | N° de guía de despacho (GD)     |
| **D**   | N° de serie (SN) — opcional     |
| **E**   | **N° de ticket** (lo escribe la app) |

La primera fila puede ser un encabezado (se detecta automáticamente).

---

## ¿Por qué corre localmente y no como página web pública?

Por tres razones de seguridad y acceso:

1. El portal de Falabella es **interno**: normalmente solo se accede desde tu
   equipo/red.
2. Tus **credenciales y el 2FA** no deben viajar a ningún servidor de terceros.
3. La automatización necesita un **navegador real** en tu máquina.

Por eso todo se ejecuta en `localhost`. Nada sale a internet salvo tu propia
navegación al portal.

### Sobre el login y la verificación en 2 pasos

En el **modo automático**, la app usa un perfil de navegador **persistente**:
la sesión (cookies) se guarda localmente, así que el login + 2FA se hace **una
sola vez** (o cuando la sesión caduque). El código 2FA, por diseño, siempre lo
ingresas tú a mano cuando el portal lo pida — nunca se guarda ni se automatiza.

---

## Instalación y uso (macOS)

Requisito: tener Python 3 (`python3 --version`). macOS moderno ya lo trae; si no,
instálalo desde [python.org](https://www.python.org/downloads/).

```bash
cd ticket-generator
chmod +x run.sh      # solo la primera vez
./run.sh
```

`run.sh` crea el entorno virtual, instala dependencias y abre
`http://127.0.0.1:8000` en tu navegador. Para detener: `Ctrl+C`.

Luego en la página:

1. **Cargar Excel** → verás la vista previa con el texto de cada ticket.
2. **Crear tickets** (dos modos, ver abajo).
3. **Descargar** el Excel con los N° de ticket en la columna E.

---

## Dos modos de creación

### Modo asistido (funciona de inmediato, sin configurar nada)

Para cada fila pendiente la app te muestra el texto exacto con un botón
**Copiar**. Abres el portal, creas el ticket pegando el texto, y pegas de vuelta
el número que devuelve. La app lo guarda en la columna E y avanza al siguiente.
Es el modo recomendado para empezar hoy mismo.

### Modo automático (Playwright)

La app abre un navegador controlado, tú inicias sesión + 2FA una vez, y luego
crea **todos** los tickets pendientes sola, leyendo el número que devuelve cada
uno. Requiere indicarle **dónde** están el campo de descripción, el botón de
enviar y el número resultante dentro del formulario (los "selectores"), porque
ese portal es interno y no conocemos su HTML de antemano.

#### Capturar los selectores (una sola vez)

1. Copia la plantilla de config:
   ```bash
   cp config.example.json config.json
   ```
2. Con la app instalada, lanza el inspector de Playwright sobre el portal:
   ```bash
   ./.venv/bin/python -m playwright codegen "https://pantallaunica.falabella.com/#/sac"
   ```
   Inicia sesión, ve al formulario de creación de ticket y haz clic en el campo
   de descripción y en el botón de enviar. Playwright te muestra el selector de
   cada elemento.
3. Pega esos selectores en `config.json`:
   ```json
   {
     "selectors": {
       "description_input": "textarea#descripcion",
       "submit_button": "button:has-text('Enviar')",
       "ticket_result": ".numero-ticket",
       "logged_in_marker": ""
     }
   }
   ```
   - `description_input`: el campo donde va el texto del ticket.
   - `submit_button`: el botón que envía/crea el ticket.
   - `ticket_result`: el elemento que muestra el N° de ticket tras enviar.
   - `logged_in_marker` (opcional): algo que solo aparece con sesión iniciada
     (permite detectar el login sin apretar «Ya inicié sesión»).
4. Reinicia la app. El **Modo automático** quedará habilitado.

> Si el portal cambia su diseño, basta con volver a capturar y actualizar
> `config.json`.

---

## Estructura del proyecto

```
ticket-generator/
├── app.py                # Servidor local (FastAPI) + API
├── run.sh                # Lanzador para macOS/Linux
├── requirements.txt
├── config.example.json   # Plantilla de configuración/selectores
├── static/index.html     # Interfaz de usuario
├── ticketgen/
│   ├── text.py           # Arma la descripción del ticket
│   ├── excel.py          # Lee/escribe el Excel (columna E = ticket)
│   ├── config.py         # Carga config.json
│   └── bot.py            # Automatización del navegador (Playwright)
└── tests/test_core.py    # Pruebas de la lógica (sin navegador)
```

Ejecutar las pruebas:

```bash
./.venv/bin/python tests/test_core.py
```

---

## Privacidad

- Todo corre en `127.0.0.1` (tu equipo).
- El Excel se procesa en memoria; solo se guarda cuando **tú** descargas.
- La sesión del navegador (modo automático) se guarda en la carpeta local
  `.browser-session/` — no la subas a git (ya está en `.gitignore`).
