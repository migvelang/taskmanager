# Stock Costanera 📦

Aplicación web (PWA) para consultar el inventario diario de la tienda, optimizada para el teléfono móvil.

## Qué hace

- **Sube el archivo diario** de inventario disponible (`.gz` o `.txt`) y actualiza el stock. El archivo viene separado por `;` y en codificación Latin‑1; la app lo descomprime y lo lee automáticamente.
- **Escáner con la cámara**: apunta al código de barras (EAN/UPC) y abre el producto. Usa `BarcodeDetector` nativo cuando está disponible y ZXing como respaldo (iPhone). También puedes escribir el EAN a mano.
- **Búsqueda** por SKU, EAN/UPC o descripción.
- **Filtros** por línea, sublínea, clase, subclase y marca (en cascada).
- **Muestra todos los UPC/EAN de cada SKU** (algunos tienen hasta 3) y permite copiarlos.
- **Imagen del producto** desde `https://media.falabella.com/falabellaCL/{sku}/public`.
- **Cada marca con su distintivo** (color e iniciales de la marca).
- **Aviso de bodega**: cuando quedan **menos de 3 unidades** (umbral configurable) recomienda consultar stock con la bodega.
- **Aviso de datos antiguos**: si pasó **más de un día** sin subir el archivo, muestra una alerta para actualizar.
- **Colores**: paleta de acentos con el verde de Falabella `#aad503` por defecto y varios más, además de modo claro/oscuro.
- **Funciona offline** (service worker) y se puede **instalar** en la pantalla de inicio.

Los datos se guardan **solo en el dispositivo** (localStorage); no se envían a ningún servidor.

## Estructura

```
stock/
├── index.html              # Toda la app (HTML + CSS + JS)
├── manifest.webmanifest    # Instalación como PWA
├── sw.js                   # Service worker (uso offline)
└── icons/                  # Íconos de la app
    ├── icon-32.png  icon-180.png  icon-192.png  icon-512.png
```

## Cómo publicarla (GitHub Pages)

1. Copia el contenido de esta carpeta `stock/` a la **raíz** del repositorio donde la quieras publicar (por ejemplo `costaneraelectro/stock`).
2. En GitHub: **Settings → Pages → Build and deployment → Source: Deploy from a branch**, elige la rama y carpeta `/root`.
3. Abre la URL que entrega GitHub Pages desde el teléfono y usa **“Agregar a pantalla de inicio”**.

> Si la mantienes dentro de una subcarpeta `stock/`, la URL será `https://<usuario>.github.io/<repo>/stock/`. Todas las rutas son relativas, así que funciona igual.

## Uso diario

1. Abre la app y toca **Subir archivo**.
2. Selecciona el archivo del día (`inv_disponible_*.gz` o `.txt`).
3. Consulta con el buscador, los filtros o el escáner.

Los íconos se generan con `scripts/gen-stock-icons.js` (Node, sin dependencias).
