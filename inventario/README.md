# 📦 Inventario · Beta

App web (móvil) para **toma de inventario físico** a partir del archivo de stock del sistema.
Es un único archivo `index-beta.html` (sin instalación, sin servidor, funciona offline). Todos los
datos se procesan **solo en el teléfono**.

> Versión **beta**. Pensada para probar el flujo completo antes de una versión definitiva.

## Cómo se usa

1. **Cargar** el archivo `.txt`/`.csv` que exporta el sistema (separado por `;`, con las columnas
   `NUMBER`, `UPC`, `STOCK DISPONIBLE`, `CLASE`, `SUBCLASE`, etc.). En `ejemplo/` hay un archivo real de muestra.
2. **Elegir el alcance**: todo el archivo, o solo una **clase** o **subclase** en particular.
3. **Escanear / ingresar** códigos UPC/EAN o el SKU (`NUMBER`). Cada lectura suma al stock físico.
4. Revisar **diferencias en línea** y los **códigos no encontrados**.

## Qué hace (requisitos cubiertos)

| Requisito | Estado |
|---|---|
| Cargar `.txt` y trabajarlo como planilla / exportar a `.csv` | ✅ Carga el `.txt`; exporta base, diferencias y no-encontrados a CSV (Excel) |
| Ingresar UPC o SKU y sumarlos como stock físico | ✅ Campo de captura + cantidad |
| Mostrar los últimos 3 productos tomados y lo que falta | ✅ Tarjetas de los últimos 3 con físico / disponible / faltante |
| Alerta si hay excedente | ✅ Aviso rojo + sonido cuando físico > disponible |
| Escanear EAN/UPC con la cámara | ✅ Cámara con `BarcodeDetector` (ver soporte abajo) |
| Conectar un lector Bluetooth | ✅ Cualquier lector en modo **HID/teclado** escribe en el campo y suma |
| SKU con 2 EAN/UPC → sumar al que tenga stock | ✅ El conteo se agrega por `NUMBER`; muestra el UPC con stock disponible |
| Código no reconocido → no sumar, alertar y revisar luego | ✅ Va a *Pendientes*; se confirma para pasar a *No encontrados* |
| Revisar diferencias en línea | ✅ Pestaña Diferencias con filtros (faltantes / excedentes / sin contar) |
| Elegir qué tomar (todo / clase / subclase) | ✅ Selectores de alcance |
| Versión beta | ✅ |

## Escaneo: cámara vs. Bluetooth

- **Lector Bluetooth (recomendado, universal):** la mayoría de los lectores funcionan como **teclado HID**:
  emparejas por Bluetooth, apuntas al campo de código y el lector "escribe" el número y da Enter.
  Funciona en **cualquier teléfono** (Android e iPhone) sin código extra. Deja el campo enfocado (botón *Enfocar*).
- **Cámara del teléfono:** usa la API nativa `BarcodeDetector`.
  - ✅ **Android / Chrome:** funciona directo.
  - ⚠️ **iPhone / Safari:** hoy no soporta `BarcodeDetector`; en iPhone conviene el lector Bluetooth.
    (En una versión futura se puede incluir una librería de escaneo para cubrir iOS.)

## Modelo de datos (multi-EAN)

Cada línea del archivo es `NUMBER` + `UPC` + su `STOCK DISPONIBLE`. Un mismo `NUMBER` (SKU) puede tener
**varios UPC/EAN** (p. ej. el EAN del fabricante y uno interno que empieza en `2000…`). El conteo se
**agrega por `NUMBER`**: escanear cualquiera de sus códigos suma al mismo producto, y la app asocia la
lectura al UPC que tiene stock disponible. El disponible que se compara es la **suma** de las variantes
del SKU.

## Persistencia

El conteo, los pendientes y los no-encontrados se guardan automáticamente en el navegador
(`localStorage`), así que puedes cerrar la página o quedarte sin señal sin perder el avance. El botón
*Borrar conteo* reinicia todo.

## Publicar (GitHub Pages)

Se puede servir como página estática: en **Settings → Pages** del repo, elegir la rama y la carpeta
`/inventario`, y quedará disponible como `https://<usuario>.github.io/<repo>/inventario/index-beta.html`.
Al ser HTTPS, la cámara funciona en el teléfono.

## Repositorio propio `inventario`

Se pidió crear un repositorio nuevo llamado `inventario`, pero el token de esta sesión solo tiene
permiso sobre `taskmanager`, así que la beta se construyó aquí en `taskmanager/inventario/`. Para
moverlo a su propio repo:

1. Crear en GitHub el repo vacío `inventario`.
2. `git subtree split --prefix=inventario -b inventario-only` y empujar esa rama al nuevo repo, **o**
   simplemente copiar la carpeta `inventario/` a un clon del repo nuevo y hacer commit.
