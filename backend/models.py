from __future__ import annotations

from enum import Enum
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    DateTime,
    Text,
    ForeignKey,
    Enum as SAEnum,
)
from sqlalchemy.orm import relationship

from db import Base


class JobStatus(str, Enum):
    CREATED = "created"
    UPLOADED = "uploaded"
    QUOTED = "quoted"
    CONVERTING = "converting"
    DONE = "done"
    ERROR = "error"


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, index=True)

    status = Column(
        SAEnum(JobStatus, name="job_status", native_enum=False),
        nullable=False,
        default=JobStatus.CREATED,
    )

    # 업로드 원본 포맷(step/iges)
    input_format = Column(String, nullable=True)

    # ✅ 공정 선택 목록 JSON: '["laser","waterjet"]'
    processes_json = Column(Text, nullable=True)

    material = Column(String, nullable=False)
    thickness_mm = Column(Float, nullable=True)
    qty = Column(Integer, nullable=False, default=1)

    thickness_auto_mm = Column(Float, nullable=True)
    unit_won = Column(Integer, nullable=True)
    total_won = Column(Integer, nullable=True)

    # FreeCAD 계산 메트릭/검증 결과 JSON
    metrics_json = Column(Text, nullable=True)
    validation_json = Column(Text, nullable=True)

    # ✅ 공정별 견적 JSON: '[{...},{...}]'
    quotes_json = Column(Text, nullable=True)

    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # relationships (선택)
    dispatches = relationship("Dispatch", back_populates="job", cascade="all, delete-orphan")


class Vendor(Base):
    __tablename__ = "vendors"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    dispatches = relationship("Dispatch", back_populates="vendor", cascade="all, delete-orphan")


class Dispatch(Base):
    __tablename__ = "dispatches"

    id = Column(String, primary_key=True, index=True)

    job_id = Column(String, ForeignKey("jobs.id"), nullable=False, index=True)
    vendor_id = Column(String, ForeignKey("vendors.id"), nullable=False, index=True)

    payload_json = Column(Text, nullable=False)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    job = relationship("Job", back_populates="dispatches")
    vendor = relationship("Vendor", back_populates="dispatches")
