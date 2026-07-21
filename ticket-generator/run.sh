#!/usr/bin/env bash
# Lanzador para macOS / Linux.
# Crea el entorno virtual la primera vez, instala dependencias y arranca la app.
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "→ Creando entorno virtual (.venv)…"
  python3 -m venv .venv
  ./.venv/bin/pip install --upgrade pip
  ./.venv/bin/pip install -r requirements.txt
  echo "→ Instalando navegador de Playwright (solo la primera vez)…"
  ./.venv/bin/python -m playwright install chromium || \
    echo "  (Aviso: no se pudo instalar Chromium; el modo AUTOMÁTICO no estará disponible, el asistido sí.)"
fi

echo ""
echo "  Generador de Tickets  ->  http://127.0.0.1:8000"
echo "  (Ctrl+C para detener)"
echo ""

# Abrir el navegador automáticamente (macOS: open, Linux: xdg-open).
( sleep 2; command -v open >/dev/null && open http://127.0.0.1:8000 || \
  (command -v xdg-open >/dev/null && xdg-open http://127.0.0.1:8000) ) >/dev/null 2>&1 &

exec ./.venv/bin/python app.py
