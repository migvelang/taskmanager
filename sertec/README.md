# SERTEC · Dashboard & Alertas de Servicio Técnico

Aplicación web para gestionar los ingresos de servicio técnico (OST) a partir del
Excel diario que exporta el sistema actual (alimentado por Salesforce). Cada
mañana se **sube el Excel manualmente**; la app guarda el snapshot del día, lo
compara con la carga anterior y genera **alertas de cambios de estado,
incumplimientos y otros**.

## ¿Qué hace?

- **Carga diaria** del Excel `HISTORICO_SERTEC_*.xlsx` (hojas *Base SERTEC*,
  *Base SF* y *Resumen*).
- **Dashboard** con KPIs y gráficos (OST abiertas, en plazo / fuera de plazo,
  rango de antigüedad, subestado, tipo de garantía, top tiendas/marcas), con
  filtro por tienda.
- **Panel de alertas** comparando la carga de hoy contra la anterior:
  | Tipo | Regla |
  |------|-------|
  | 🔴 Nuevo incumplimiento | Una OST abierta cruzó a *Fuera de plazo*. |
  | 🔄 Cambio de estado | Cambió `OST_ESTADO`, `OST_SUBESTADO` o `ESTADO_GESTION_PRODUCTO`. |
  | ⏳ Envejecimiento | La OST subió de tramo en `RANGO_SERTEC`. |
  | ⚠️ Sin responsable | OST abierta sin responsable asignado. |
  | 🧩 SF no cumple matriz | Caso Salesforce con `VALIDACION_MATRIZ = NO_CUMPLE`. |
  | ✍️ SF error de creación | Caso SF sin F11/OST identificable en la descripción. |
- **Pantalla única de caso**: busca por OST / F11 / N° de caso SF y muestra la
  OST, su **línea de tiempo** de estados a través de las cargas y los casos
  Salesforce vinculados (parseando la descripción de SF).

## Stack

FastAPI · SQLAlchemy · PostgreSQL (SQLite en local) · Jinja2 + HTMX + Tailwind + ECharts.

## Correr en local (SQLite, sin Docker)

```bash
cd sertec
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Abre http://localhost:8000 e ingresa con el usuario admin por defecto
(`admin@sertec.local` / `admin1234` — configurable por variables de entorno).

## Correr con Docker (Postgres)

```bash
cd sertec
cp .env.example .env   # ajusta SECRET_KEY y credenciales admin
docker compose up --build
```

## Despliegue en la nube

1. Provisiona un Postgres administrado (Railway, Render, Supabase, etc.).
2. Define las variables `DATABASE_URL`, `SECRET_KEY`, `ADMIN_EMAIL`,
   `ADMIN_PASSWORD`.
3. Despliega el contenedor (`Dockerfile` incluido) o el proceso
   `uvicorn app.main:app`.

## Notas técnicas

- Las tablas se crean automáticamente al iniciar (`Base.metadata.create_all`).
  Para producción con evolución de esquema se recomienda migrar a Alembic.
- Una carga = una fila en `cargas`; cada OST/caso SF se guarda **por carga**,
  lo que permite reconstruir la línea de tiempo y comparar días.
- La detección del F11/OST dentro de la descripción de Salesforce vive en
  `app/services/sf_link.py` (expresiones regulares ajustables).
