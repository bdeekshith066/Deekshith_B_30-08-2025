# app/models.py

# SQLAlchemy ORM models defining database schema for the project.
# Includes store_status, business_hours, store_timezone, and report_jobs tables.
# Uses enums and indexes for efficient queries on store_id and timestamp.
# Serves as the core data layer for ingestion, computation, and API endpoints.


from __future__ import annotations
import enum
from datetime import datetime

from sqlalchemy import String, Integer, DateTime, Enum, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class StatusEnum(str, enum.Enum):
    active = "active"
    inactive = "inactive"


class StoreStatus(Base):
    __tablename__ = "store_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    timestamp_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    status: Mapped[StatusEnum] = mapped_column(Enum(StatusEnum), nullable=False)

    __table_args__ = (
        Index("idx_store_time", "store_id", "timestamp_utc"),
    )


class BusinessHours(Base):
    __tablename__ = "business_hours"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=Mon..6=Sun
    start_time_local: Mapped[str] = mapped_column(String, nullable=False)  # "HH:MM[:SS]"
    end_time_local: Mapped[str] = mapped_column(String, nullable=False)

    __table_args__ = (
        Index("idx_hours_store_day", "store_id", "day_of_week"),
    )


class StoreTimezone(Base):
    __tablename__ = "store_timezone"

    store_id: Mapped[str] = mapped_column(String, primary_key=True)
    timezone_str: Mapped[str] = mapped_column(String, nullable=False)


class ReportJob(Base):
    __tablename__ = "report_jobs"

    report_id: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String, default="Running")
    csv_path: Mapped[str | None] = mapped_column(Text, nullable=True)
