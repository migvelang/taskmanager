FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000
# Railway/otros PaaS inyectan $PORT; en local cae a 8000. Forma shell para
# que la variable se expanda en tiempo de ejecución.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
