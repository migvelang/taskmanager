"""Configuración central de la app SERTEC.

Lee variables de entorno (con valores por defecto aptos para desarrollo local
con SQLite). En producción se define DATABASE_URL apuntando a Postgres.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Base de datos: por defecto SQLite local; en prod se usa Postgres vía env.
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./sertec.db")

    # Clave para firmar las cookies de sesión. CAMBIAR en producción.
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-cambiar-en-produccion")

    # Usuario administrador que se crea al inicializar si no existe.
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "admin@sertec.local")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "admin1234")

    # Umbral (días) para la alerta de "envejecimiento / sin avance".
    DIAS_SIN_AVANCE: int = int(os.getenv("DIAS_SIN_AVANCE", "5"))

    APP_NAME: str = "SERTEC · Dashboard & Alertas"


settings = Settings()
