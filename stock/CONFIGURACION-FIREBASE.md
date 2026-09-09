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

## Paso 7 — Entrar como administrador (¡sin crear nada!)
Ya **no** hay que crear ni editar cuentas a mano. El administrador se activa solo con la clave:

1. Abre la app publicada.
2. Toca el **engranaje ⚙️** de la esquina superior derecha (en la pantalla de inicio).
3. Escribe la clave de administrador **`connect2025`** → **Ingresar como administrador**.
4. Listo: ya puedes **subir el archivo** del día y **aprobar/eliminar** usuarios.

> La **primera vez** que escribas `connect2025`, la app crea sola la cuenta de administrador con esa clave. Las siguientes veces, esa misma clave te deja entrar. (Puedes cambiarla en `index.html`, constante `ADMIN_KEY`, si quieres otra.)

## Uso diario
- **Tú (administrador):** ⚙️ en la esquina → `connect2025` → subes el archivo del día y gestionas usuarios.
- **El resto del equipo:** se registran una vez (nombre, apellido, clave), tú los apruebas desde ⚙️, y luego consultan el stock desde cualquier teléfono. Lo que subes se ve al instante en todos.

## Notas
- **Eliminar a alguien:** bórralo desde ⚙️ → Usuarios (pierde el acceso). Para borrar también su login, ve a **Authentication → Users** en Firebase y elimínalo ahí.
- **Costo:** el plan gratuito (Spark) alcanza de sobra para una tienda (miles de lecturas/escrituras al día).
- Si ya habías pegado una versión anterior de las reglas, **vuelve a pegar** las de `firestore.rules` (cambiaron) y **Publica**.
