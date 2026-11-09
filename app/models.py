"""Modelo de datos: yacimiento -> unidades estratigráficas (UE) -> hallazgos.

Una UE es la unidad mínima del registro estratigráfico. La tabla de relaciones guarda
qué UE cubre a cuál (base del diagrama de Harris).
"""
from datetime import date

from sqlalchemy import CheckConstraint, Date, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    municipality: Mapped[str | None] = mapped_column(String(120), index=True)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)

    units: Mapped[list["Unit"]] = relationship(back_populates="site", cascade="all, delete-orphan")
    finds: Mapped[list["Find"]] = relationship(back_populates="site", cascade="all, delete-orphan")


class Unit(Base):
    __tablename__ = "units"
    __table_args__ = (UniqueConstraint("site_id", "number", name="uq_unit_site_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), index=True)
    number: Mapped[int]
    kind: Mapped[str] = mapped_column(String(20))  # deposit | cut | structure
    description: Mapped[str | None] = mapped_column(Text)
    period: Mapped[str | None] = mapped_column(String(80))

    site: Mapped[Site] = relationship(back_populates="units")


class Relation(Base):
    """`upper` cubre (es posterior a) `lower`."""

    __tablename__ = "relations"
    __table_args__ = (
        UniqueConstraint("upper_id", "lower_id", name="uq_relation_pair"),
        CheckConstraint("upper_id <> lower_id", name="ck_relation_distinct"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    upper_id: Mapped[int] = mapped_column(ForeignKey("units.id", ondelete="CASCADE"), index=True)
    lower_id: Mapped[int] = mapped_column(ForeignKey("units.id", ondelete="CASCADE"), index=True)


class Find(Base):
    __tablename__ = "finds"

    id: Mapped[int] = mapped_column(primary_key=True)
    inventory_code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), index=True)
    unit_id: Mapped[int | None] = mapped_column(ForeignKey("units.id", ondelete="SET NULL"))
    category: Mapped[str] = mapped_column(String(60), index=True)
    material: Mapped[str] = mapped_column(String(60), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    found_on: Mapped[date | None] = mapped_column(Date)

    site: Mapped[Site] = relationship(back_populates="finds")
    unit: Mapped[Unit | None] = relationship()
