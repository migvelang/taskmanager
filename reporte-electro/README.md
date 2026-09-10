# Reporte Electro

App web/móvil (PWA) para registrar y seguir la venta de **garantía extendida**, **Seguro Connect**,
No Mix, Attach, canjes de puntos y puntos + pesos, y armar el **reporte por área → departamento → asesor**
con el **resumen por jefe** listo para tomar captura y enviar.

Todo vive en un solo archivo (`index.html`): jerarquías, inventario (2.502 productos), lógica y reporte.
Funciona **sin instalar nada**; para que sea **multiusuario en línea** se conecta a **Firebase** y para
**leer boletas con IA** usa **Google Gemini**. Ambos se activan pegando sus credenciales en ⚙️ Config.

---

## Probar ya (modo local)

1. Abre `index.html` (o publícalo, ver abajo).
2. Regístrate con nombre, apellido y una clave.
3. Registra ventas y mira el Reporte.

> En modo local los datos quedan **solo en ese dispositivo**. Para compartir entre usuarios, activa Firebase.

## Estructura

| Archivo | Qué es |
|---|---|
| `index.html` | La app completa (datos embebidos incluidos). |
| `manifest.json`, `sw.js`, `icon-*.png` | Para instalarla como app (PWA). |
| `firestore.rules` | Reglas de seguridad de Firestore (pégalas en la consola de Firebase). |
| `storage.rules` | Reglas de Storage para las fotos de boletas. |

---

## 1) Activar multiusuario en línea (Firebase)

1. Entra a <https://console.firebase.google.com> → **Agregar proyecto** (ej: `reporte-electro`).
2. **Authentication** → Comenzar → habilita **Correo/contraseña**.
3. **Firestore Database** → Crear base de datos (modo producción) → pega el contenido de `firestore.rules` en la pestaña **Reglas** → Publicar.
4. **Storage** → Comenzar → pega `storage.rules` → Publicar. *(opcional, solo si quieres guardar la foto de la boleta.)*
5. **Configuración del proyecto** (⚙️) → *Tus apps* → **Web** (`</>`) → registra la app y copia el objeto `firebaseConfig`.
6. Abre la app → ⚙️ **Config** (clave `connect2025`) → pega esa config (campo por campo o el JSON completo) → **Guardar** → **Recargar**.

Cuando el indicador arriba diga **“en línea”**, todos los usuarios verán el mismo reporte.

> Los usuarios inician sesión con **nombre + apellido + clave**. Internamente se crea un correo
> tipo `nombre.apellido@reporteelectro.app` (no necesitan un email real).

## 2) Activar lectura de boletas con IA (Gemini)

1. Consigue una API key gratis en <https://aistudio.google.com/apikey>.
2. ⚙️ **Config** → pega la key en *Extracción de boletas (IA · Gemini)* → Guardar.
3. Al registrar una venta, usa **📷 Foto / archivo boleta**: la IA extrae vendedor, código, producto,
   monto y valor de garantía. **Siempre** aparece un formulario para **verificar y editar** antes de sumar;
   lo que la IA no tuvo claro queda resaltado y lo puedes ingresar manual.

> Seguridad: la key viaja desde el navegador. Es una key de uso interno; restríngela en
> Google Cloud (APIs y servicios → Credenciales → *Application restrictions* por dominio y
> *API restrictions* a “Generative Language API”).

## 3) Publicar en línea

Cualquier hosting estático sirve. Dos opciones fáciles:

- **GitHub Pages:** Settings → Pages → Deploy from branch → `main` / carpeta raíz. Queda en
  `https://<usuario>.github.io/<repo>/`.
- **Firebase Hosting:** `firebase init hosting` (carpeta pública = esta) y `firebase deploy`.

---

## Cómo se calcula el reporte

- Cada venta tiene un **tipo**; el tipo define una **categoría**: `GEXT` (Garantía Extendida),
  `SEGURO` (Seguro Connect) u `OTROS` (No Mix / Attach / Canje de Puntos / Puntos + Pesos).
- El **producto/subclase** define **departamento** y **área** (mapeo de jerarquías embebido; editable por overrides).
- El **resumen por jefe** suma las ventas de los departamentos que cada jefe cubre (configurable en ⚙️),
  compara contra el **Plan GExt / Plan Seguro** y muestra el **cumplimiento** con semáforo
  (🟢 ≥100% · 🟡 ≥80% · 🔴 <80%).
- El **detalle** desglosa por área → departamento → asesor.

Jerarquías y elegibilidad salen de los archivos oficiales (subclases elegibles + inventario).
Para actualizar el inventario o el mapeo, se regenera el bloque de datos de `index.html`.

---

## Traspasar este repo a `costaneraelectro/reporte`

Este proyecto se creó como repo de prueba. Para llevarlo al repo definitivo:

```bash
# 1) Clona este repo de prueba
git clone <URL-de-este-repo> reporte-electro && cd reporte-electro

# 2) Apunta al repo definitivo y súbelo
git remote set-url origin https://github.com/costaneraelectro/reporte.git
git push -u origin main
```

O, si prefieres copiar solo los archivos: copia todo el contenido de esta carpeta a un clon de
`costaneraelectro/reporte`, haz commit y push. Luego activa GitHub Pages en ese repo.
