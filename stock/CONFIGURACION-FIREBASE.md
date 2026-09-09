# Configurar el servidor (Firebase) — paso a paso

La app funciona en **modo local** hasta que pegues tu configuración de Firebase.
Al pegarla, pasa a **la nube**: usuarios, aprobaciones y stock quedan **compartidos entre todos los teléfonos**. Firebase es gratis para este uso.

Toma unos 10–15 minutos. Todo se hace con clicks en la consola de Firebase.

---

## Paso 1 — Crear el proyecto
1. Entra a **https://console.firebase.google.com** e inicia sesión con tu cuenta Google.
2. Click en **“Agregar proyecto”** (Add project).
3. Nombre: `stock-costanera` → **Continuar**.
4. Google Analytics: puedes **desactivarlo** → **Crear proyecto** → espera y **Continuar**.

## Paso 2 — Activar el inicio de sesión por usuario y clave
1. En el menú izquierdo: **Compilación (Build) → Authentication → Comenzar**.
2. Pestaña **“Sign-in method”** → en la lista, elige **“Correo electrónico/contraseña”**.
3. Activa el **primer interruptor** (Email/Password) → **Guardar**.

## Paso 3 — Crear la base de datos
1. Menú izquierdo: **Compilación (Build) → Firestore Database → Crear base de datos**.
2. Elige una ubicación (por ejemplo `southamerica-east1`) → **Siguiente**.
3. Selecciona **“Comenzar en modo de producción”** → **Habilitar**.

## Paso 4 — Pegar las reglas de seguridad
1. Dentro de Firestore, abre la pestaña **“Reglas” (Rules)**.
2. **Borra todo** lo que haya y **pega** el contenido del archivo **`firestore.rules`** (está en esta misma carpeta).
3. Click en **“Publicar” (Publish)**.

## Paso 5 — Copiar tu configuración
1. Arriba a la izquierda, click en la **rueda ⚙️ → Configuración del proyecto** (Project settings).
2. Baja hasta **“Tus apps” (Your apps)** y click en el ícono **`</>`** (Web).
3. Apodo de la app: `stock` → **Registrar app** (no marques Hosting).
4. Firebase te mostrará un bloque `const firebaseConfig = { ... }`. Copia **los valores** entre llaves.

## Paso 6 — Pegar la configuración en la app
1. Abre el archivo **`index.html`** y busca, cerca del inicio, el bloque:
   ```js
   var FIREBASE_CONFIG={
     apiKey:"PEGA_AQUI",
     authDomain:"PEGA_AQUI",
     projectId:"PEGA_AQUI",
     storageBucket:"PEGA_AQUI",
     messagingSenderId:"PEGA_AQUI",
     appId:"PEGA_AQUI"
   };
   ```
2. Reemplaza cada `"PEGA_AQUI"` por el valor que te dio Firebase (respeta las comillas).
   > Estos valores **no son secretos**: son identificadores públicos. La seguridad real está en las reglas del Paso 4.
3. Guarda el archivo y súbelo a tu repositorio (o vuelve a subir el sitio).

## Paso 7 — Crear tu cuenta de administrador (una sola vez)
1. Abre la app publicada → pestaña **“Registrarse”** → ingresa tu **nombre, apellido y clave** (mínimo 6 caracteres) → **Enviar registro**. Anota el **usuario** que te muestra (ej: `miguel.aranguiz`).
2. Vuelve a la consola de Firebase → **Firestore Database → pestaña Datos**.
3. Abre la colección **`usuarios`** y haz click en tu documento (tu ficha).
4. Edita dos campos:
   - `estado` → cámbialo de `pendiente` a **`aprobado`**.
   - `rol` → cámbialo de `user` a **`admin`**.
   (Se edita con el lápiz ✏️ junto a cada campo; **Actualizar/Update**.)
5. Listo. Vuelve a la app e **inicia sesión** con tu usuario y clave: ya eres administrador.

## Uso diario
- **Tú (administrador):** entras con tu usuario → ⚙️ → clave `connect2025` → **subes el archivo** del día y **apruebas/eliminas** usuarios.
- **El resto del equipo:** se registran una vez, tú los apruebas desde ⚙️, y luego consultan el stock desde cualquier teléfono. El stock que subes se ve al instante en todos.

> La clave de configuración `connect2025` protege la pantalla de ⚙️. El poder de administrador (subir stock, aprobar usuarios) lo tiene solo la cuenta marcada como `admin`. Puedes cambiar `connect2025` en `index.html` (constante `ADMIN_KEY`).

## Notas
- **Cambiar de admin o agregar otro:** repite el Paso 7 (poner `rol: admin`) en la ficha de esa persona.
- **Eliminar a alguien del todo:** bórralo desde ⚙️ en la app (pierde el acceso). Para borrar también su login, ve a **Authentication → Users** en Firebase y elimínalo ahí.
- **Costo:** el plan gratuito (Spark) alcanza de sobra para una tienda (miles de lecturas/escrituras al día).
