import enum
from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, Boolean, Text, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class JobStatus(str, enum.Enum):
    CREATED = "CREATED"
    UPLOADED = "UPLOADED"
    QUOTED = "QUOTED"
    CHECKOUT_READY = "CHECKOUT_READY"
    PAID = "PAID"
    CONVERTING = "CONVERTING"
    DONE = "DONE"
    ERROR = "ERROR"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.CREATED)

    material: Mapped[str] = mapped_column(String, default="steel")
    thickness_mm: Mapped[float] = mapped_column(Float, default=0.0)  # 0=auto
    qty: Mapped[int] = mapped_column(Integer, default=1)

    paid: Mapped[bool] = mapped_column(Boolean, default=False)

    thickness_auto_mm: Mapped[float | None] = mapped_column(Float, nullable=True)

    unit_won: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_won: Mapped[int | None] = mapped_column(Integer, nullable=True)

    metrics_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # optional relations
    dispatches = relationship("Dispatch", back_populates="job")


class Vendor(Base):
    __tablename__ = "vendors"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, default="Seed Vendor")
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Dispatch(Base):
    __tablename__ = "dispatches"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    job_id: Mapped[str] = mapped_column(String, ForeignKey("jobs.id"))
    vendor_id: Mapped[str] = mapped_column(String)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    job = relationship("Job", back_populates="dispatches")
