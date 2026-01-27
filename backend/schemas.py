from typing import Any, Dict, Optional, List, Literal

from pydantic import BaseModel, Field, ConfigDict

ProcessKey = Literal["laser", "waterjet"]


# ---------- Inputs ----------

class CreateJobIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # 공정 선택(복수 가능)
    # 프론트에서 미선택/누락 가능 → 서버(main.py)에서 기본 laser 처리
    processes: List[ProcessKey] = Field(default_factory=list)

    material: str
    thickness_mm: float = Field(default=0.0, ge=0.0)
    qty: int = Field(default=1, ge=1)


class DispatchCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vendor_id: str
    note: Optional[str] = None


# ---------- Outputs ----------

class ProcessQuoteOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    process: ProcessKey
    material: str
    thickness_mm: float
    qty: int

    unit_won: int
    total_won: int
    factors: Dict[str, Any] = Field(default_factory=dict)


class JobOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    status: str

    input_format: Optional[str] = None
    processes: List[ProcessKey] = Field(default_factory=list)

    material: str
    thickness_mm: Optional[float] = None
    qty: int

    thickness_auto_mm: Optional[float] = None

    unit_won: Optional[int] = None
    total_won: Optional[int] = None

    quotes: Optional[List[ProcessQuoteOut]] = None

    metrics: Optional[Dict[str, Any]] = None
    validation: Optional[Dict[str, Any]] = None

    error_message: Optional[str] = None

    dxf_url: Optional[str] = None
    svg_url: Optional[str] = None


class QuoteOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str  # "ok" | "error"
    job: JobOut
    quotes: List[ProcessQuoteOut] = Field(default_factory=list)
