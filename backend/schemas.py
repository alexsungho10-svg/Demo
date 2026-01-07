from pydantic import BaseModel, Field
from typing import Any, Optional


class CreateJobIn(BaseModel):
    material: str = "steel"
    thickness_mm: float = 0.0  # 0=auto
    qty: int = Field(1, ge=1, le=1000)


class JobOut(BaseModel):
    id: str
    status: str
    material: str
    thickness_mm: float
    qty: int
    paid: bool

    thickness_auto_mm: Optional[float] = None
    unit_won: Optional[int] = None
    total_won: Optional[int] = None

    metrics: Optional[dict[str, Any]] = None
    validation: Optional[dict[str, Any]] = None
    error_message: Optional[str] = None

    dxf_url: Optional[str] = None
    svg_url: Optional[str] = None


class QuoteOut(BaseModel):
    status: str = "ok"
    job: JobOut


class CheckoutOut(BaseModel):
    status: str = "ok"
    job_id: str
    amount_won: int
    currency: str = "KRW"
    payment_url: str  # 실제 PG 붙이면 checkout url


class DispatchCreateIn(BaseModel):
    vendor_id: str
    note: str = ""
