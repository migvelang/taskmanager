"""Configuración central de la app SERTEC.

Lee variables de entorno (con valores por defecto aptos para desarrollo local
con SQLite). En producción se define DATABASE_URL apuntando a Postgres.
"""
import os
from dotenv import load_dotenv

load_dotenv()


def _normalizar_db_url(url: str) -> str:
    """Normaliza el DSN para SQLAlchemy + psycopg2.

    Railway/Heroku entregan la URL como 'postgres://...' o 'postgresql://...';
    SQLAlchemy con psycopg2 requiere el driver explícito 'postgresql+psycopg2://'.
    """
    if url.startswith("postgres://"):
        url = "postgresql+psycopg2://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://"):]
    return url


class Settings:
    # Base de datos: por defecto SQLite local; en prod se usa Postgres vía env.
    DATABASE_URL: str = _normalizar_db_url(os.getenv("DATABASE_URL", "sqlite:///./sertec.db"))

    # Clave para firmar las cookies de sesión. CAMBIAR en producción.
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-cambiar-en-produccion")

    # Usuario administrador que se crea al inicializar si no existe.
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "admin@sertec.local")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "admin1234")

    # Clave para entrar a la pestaña de Configuración (editar reglas de alerta).
    CONFIG_PASSWORD: str = os.getenv("CONFIG_PASSWORD", "config1234")

    # Umbral (días) para la alerta de "envejecimiento / sin avance".
    DIAS_SIN_AVANCE: int = int(os.getenv("DIAS_SIN_AVANCE", "5"))

    APP_NAME: str = "SERTEC · Dashboard & Alertas"


settings = Settings()
