# Stock Costanera 📦

Aplicación web (PWA) para consultar el inventario diario de la tienda, optimizada para el teléfono móvil.

## Acceso (login + aprobación)

- Antes de ver el stock, cada persona debe **ingresar** con usuario y contraseña, o **registrarse** (nombre, apellido y clave).
- Al registrarse la cuenta queda **pendiente**. El **administrador** la aprueba en **Configuración** y recién ahí la persona puede entrar. Desde ahí también se pueden **eliminar** usuarios.
- La **Configuración** está protegida con la **clave de administrador** (por defecto `connect2025`). Sin esa clave no se muestra ninguna configuración. La clave se puede cambiar en `index.html` (constante `ADMIN_KEY`).
- La **subida del archivo diario** vive dentro de Configuración (solo el administrador sube stock).

### Modo local y modo nube

La app tiene **dos modos**, según el archivo `index.html`:

- **Local** (por defecto): usuarios, aprobaciones y stock se guardan en el navegador de **cada dispositivo**. Sirve para probar o para un equipo/tablet compartido. No se sincroniza entre teléfonos distintos.
- **Nube** (recomendado): al pegar tu configuración de **Firebase** en `index.html`, todo queda **compartido entre todos los teléfonos** en tiempo real. Sigue las instrucciones en **`CONFIGURACION-FIREBASE.md`**.

En modo nube, el **administrador** es la cuenta marcada como `admin` en Firebase (solo esa puede subir stock y aprobar/eliminar usuarios). La clave `connect2025` protege abrir la pantalla de configuración.

## Qué hace

- **Sube el archivo diario** de inventario disponible (`.gz` o `.txt`) desde Configuración. El archivo viene separado por `;` y en codificación Latin‑1; la app lo descomprime y lo lee automáticamente.
- **Escáner con la cámara**: apunta al código de barras (EAN/UPC) y abre el producto. Usa `BarcodeDetector` nativo cuando está disponible y ZXing como respaldo (iPhone). También puedes escribir el EAN a mano.
- **Búsqueda** por SKU, EAN/UPC o descripción.
- **Filtros siempre visibles** por línea, sublínea, clase, subclase y marca (en cascada).
- **Muestra todos los UPC/EAN de cada SKU** (algunos tienen hasta 3), con opción de **copiar** y de **ver el código de barras** en pantalla (para leerlo desde otra pantalla o reimprimirlo).
- **Ver imagen** del producto desde `https://media.falabella.com/falabellaCL/{sku}/public`.
- **Aviso de bodega**: cuando quedan **menos de 3 unidades** (umbral configurable) recomienda consultar stock con la bodega.
- **Aviso de datos antiguos**: si pasó **más de un día** sin subir el archivo, muestra una alerta para actualizar.
- **Colores**: paleta de acentos con el verde de Falabella `#aad503` por defecto y varios más, además de un botón de **modo oscuro** en el encabezado.
- **Funciona offline** (service worker) y se puede **instalar** en la pantalla de inicio.

No se muestran precios (venta, costo ni margen). Todo se guarda **solo en el dispositivo**; no se envía a ningún servidor.

## Estructura

```
stock/
├── index.html              # Toda la app (HTML + CSS + JS)
├── manifest.webmanifest    # Instalación como PWA
├── sw.js                   # Service worker (uso offline)
├── vendor/
│   └── JsBarcode.all.min.js  # Genera el gráfico de código de barras (offline)
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
