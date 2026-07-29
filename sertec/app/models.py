"""Modelo de datos de la app SERTEC.

Cada subida del Excel = una fila en `cargas`. Por cada carga se guarda un
snapshot completo de OSTs (`ost_snapshot`) y de casos Salesforce (`sf_snapshot`).
El motor de diffs compara la carga actual contra la anterior y genera `alertas`.
"""
import datetime as dt

from sqlalchemy import (
    JSON, Boolean, Column, Date, DateTime, Float, ForeignKey, Integer,
    String, Text, UniqueConstraint, Index,
)
from sqlalchemy.orm import relationship

from .db import Base


class User(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    nombre = Column(String(255))
    hashed_password = Column(String(255), nullable=False)
    rol = Column(String(20), default="visor")  # admin | visor
    activo = Column(Boolean, default=True)
    creado = Column(DateTime, default=dt.datetime.utcnow)


class Carga(Base):
    """Una subida del Excel histórico."""
    __tablename__ = "cargas"

    id = Column(Integer, primary_key=True)
    fecha_extraccion = Column(DateTime, nullable=False, index=True)  # desde hoja Resumen
    archivo_nombre = Column(String(500))
    subido_por = Column(String(255))
    subido_en = Column(DateTime, default=dt.datetime.utcnow)
    estado = Column(String(20), default="procesando")  # procesando | listo | error
    totales = Column(JSON)  # KPIs de la hoja Resumen
    n_ost = Column(Integer, default=0)
    n_sf = Column(Integer, default=0)
    n_alertas = Column(Integer, default=0)

    ost = relationship("OstSnapshot", back_populates="carga", cascade="all, delete-orphan")
    sf = relationship("SfSnapshot", back_populates="carga", cascade="all, delete-orphan")
    alertas = relationship("Alerta", back_populates="carga", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("fecha_extraccion", name="uq_carga_fecha"),)


class OstSnapshot(Base):
    """Estado de una OST en una carga puntual."""
    __tablename__ = "ost_snapshot"

    id = Column(Integer, primary_key=True)
    carga_id = Column(Integer, ForeignKey("cargas.id", ondelete="CASCADE"), nullable=False)

    ost_num = Column(String(30), nullable=False, index=True)
    f11_num = Column(String(30), index=True)
    f11_estado = Column(String(80))
    ost_estado = Column(String(60))
    ost_subestado = Column(String(80))
    ost_estado_gestion_producto = Column(String(80))
    sub_estado_externo = Column(String(120))

    flag_plazo = Column(String(40))          # Dentro de plazo | Fuera de plazo | None
    dias_sertec = Column(Integer)
    rango_sertec = Column(String(40))
    flag_responsable = Column(String(80))
    responsable_sac = Column(String(120))
    responsable_mini_big_ticket = Column(String(120))

    fecha_creacion = Column(DateTime)
    fecha_compromiso = Column(DateTime)
    fecha_cierre = Column(DateTime)

    prod_nombre = Column(String(300))
    prod_sku = Column(String(60))
    prod_marca = Column(String(120))
    prod_modelo = Column(String(300))
    prod_garantia_modalidad = Column(String(60))
    prod_tipo_garantia = Column(String(80))
    desc_falla = Column(Text)

    cruce_tienda = Column(String(160), index=True)
    codigo_tienda = Column(String(40))
    region = Column(String(120))
    comuna = Column(String(120))
    desc_linea = Column(String(120))
    desc_sublinea = Column(String(120))
    precio_vta = Column(Float)

    raw = Column(JSON)  # fila completa por si se necesita algún campo extra

    carga = relationship("Carga", back_populates="ost")

    __table_args__ = (
        Index("ix_ost_carga_num", "carga_id", "ost_num"),
    )


class SfSnapshot(Base):
    """Estado de un caso Salesforce en una carga puntual."""
    __tablename__ = "sf_snapshot"

    id = Column(Integer, primary_key=True)
    carga_id = Column(Integer, ForeignKey("cargas.id", ondelete="CASCADE"), nullable=False)

    ss_nro = Column(String(40), nullable=False, index=True)
    id_regulatorio = Column(String(80))
    estado = Column(String(60))
    nivel_1 = Column(String(120))
    nivel_2 = Column(String(120))
    nivel_3 = Column(String(160))
    nivel_4 = Column(String(200))
    descripcion = Column(Text)
    fecha_creacion = Column(DateTime)
    fecha_cierre = Column(DateTime)
    tipo_cierre = Column(String(80))
    nombre_propietario = Column(String(160))
    tienda_origen = Column(String(160))
    validacion_matriz = Column(String(60))
    motivo_no_cumple = Column(String(300))

    # Derivados del parseo de la descripción
    f11_parseado = Column(String(30), index=True)
    ost_parseada = Column(String(30), index=True)
    link_status = Column(String(30))  # vinculado | error_creacion

    raw = Column(JSON)

    carga = relationship("Carga", back_populates="sf")


class Alerta(Base):
    """Alerta generada al comparar la carga actual contra la anterior."""
    __tablename__ = "alertas"

    id = Column(Integer, primary_key=True)
    carga_id = Column(Integer, ForeignKey("cargas.id", ondelete="CASCADE"), nullable=False)

    tipo = Column(String(40), nullable=False, index=True)
    # incumplimiento | cambio_estado | envejecimiento | sin_responsable |
    # sf_no_cumple_matriz | sf_error_creacion
    severidad = Column(String(10), default="media")  # alta | media | baja

    ost_num = Column(String(30), index=True)
    ss_nro = Column(String(40))
    cruce_tienda = Column(String(160), index=True)

    titulo = Column(String(300))
    detalle = Column(Text)
    valor_anterior = Column(String(200))
    valor_actual = Column(String(200))

    gestion = Column(String(20), default="nueva")  # nueva | vista | gestionada
    asignado_a = Column(String(160))
    creado = Column(DateTime, default=dt.datetime.utcnow)

    carga = relationship("Carga", back_populates="alertas")
