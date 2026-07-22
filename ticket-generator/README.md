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

### Atajo: ícono en el Escritorio (doble clic, sin Terminal)

Para no volver a escribir rutas, crea un acceso directo en el Escritorio con
este comando (una sola vez):

```bash
DIR="$(dirname "$(find ~ -name run.sh -path '*ticket-generator*' 2>/dev/null | head -1)")"; printf '#!/bin/bash\ncd "%s"\n./run.sh\n' "$DIR" > ~/Desktop/Iniciar-Generador-Tickets.command; chmod +x ~/Desktop/Iniciar-Generador-Tickets.command; open ~/Desktop
```

Aparecerá `Iniciar-Generador-Tickets.command` en el Escritorio. De ahí en
adelante, **doble clic** y la app arranca sola. (La primera vez, si macOS lo
bloquea: clic derecho → **Abrir** → **Abrir**.) También puedes arrastrarlo al
Dock.

> La carpeta del proyecto incluye `Iniciar-Generador-Tickets.command`, que hace
> lo mismo si lo dejas dentro de `ticket-generator/`. El comando de arriba crea
> una copia en el Escritorio con la ruta ya fijada.

Luego en la página:

1. **Cargar Excel** → verás la vista previa con el texto de cada ticket.
2. **Crear tickets** (dos modos, ver abajo).
3. **Descargar** el Excel con los N° de ticket en la columna E.
4. **🔄 Reiniciar / Subir otro archivo** cuando quieras empezar con otro Excel
   (recuerda descargar antes; no se reinicia solo para no perder datos).

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
uno. Solo necesita saber, la primera vez, **dónde** están el campo de
descripción, el botón de enviar y el número de ticket en el portal.

El formulario del portal tiene muchos campos que son **iguales en todos los
tickets** (Tipo Seller, tipificación N1/N3/N4, tienda, comercio, datos de
contacto, Posee OC, etc.) y solo cambia la **descripción**. El detector graba
todo ese formulario fijo una vez y lo reproduce en cada ticket.

#### Configuración con el detector integrado (sin Terminal)

En la pestaña **Modo automático**, el detector tiene 3 pasos:

**Paso 1 — Abrir e iniciar sesión**
1. **Abrir portal** → se abre un navegador controlado.
2. Inicia sesión + 2FA, entra a la pestaña **Formulario tienda** y presiona
   **Ya inicié sesión**.

**Paso 2 — Grabar el formulario fijo**
3. **● Empezar a grabar**.
4. **Lo primero**: haz clic en la pestaña **«Formulario tienda»** (aunque ya
   estés en ella). Así la app sabe cómo volver al formulario en cada ticket
   sin recargar la página.
5. Luego llena **todos los campos fijos** como siempre, incluidas las **listas
   desplegables**. **No** llenes aún la descripción.
6. **■ Terminar grabación** (verás "N pasos grabados").

**Paso 3 — Marcar descripción, enviar y resultado**
6. **1) Marcar descripción** → clic en el recuadro de la descripción.
7. **2) Marcar botón enviar** → clic en el botón que crea el caso (no se envía).
8. Crea **un** ticket de prueba a mano; cuando aparezca el número, **3) Marcar
   N° ticket** → clic sobre ese número.
9. **Guardar configuración**. Queda todo en `config.json` (selectores +
   `form_steps`) y el modo automático se habilita.

> Si el portal cambia su diseño y algo deja de funcionar, vuelve a correr el
> detector: sobrescribe la configuración. Los campos fijos y desplegables se
> reproducen por texto/selector, con reintento por el texto visible de cada
> opción (más robusto para menús Angular).

#### (Alternativa avanzada) Editar `config.json` a mano

También puedes copiar `config.example.json` a `config.json` y escribir los
selectores tú mismo (`description_input`, `submit_button`, `ticket_result`,
y el opcional `logged_in_marker`).

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
