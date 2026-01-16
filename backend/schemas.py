from typing import Any, Dict, Optional, List, Literal

from pydantic import BaseModel, Field, ConfigDict


ProcessKey = Literal["laser", "waterjet"]


# ---------- Inputs ----------

class CreateJobIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # ✅ 추가: 공정 선택(복수 가능)
    # - 프론트에서 미선택 시 [] 또는 아예 누락될 수 있으니 default_factory로 받고,
    #   main.py에서 "가공 방식을 선택해 주세요"로 400 처리.
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

    # ✅ 업로드 원본 포맷(step/iges)
    input_format: Optional[str] = None

    # ✅ 선택 공정들
    processes: List[ProcessKey] = Field(default_factory=list)

    material: str
    thickness_mm: Optional[float] = None
    qty: int

    thickness_auto_mm: Optional[float] = None

    # (레거시/호환용) 대표 견적 1개를 여기에 넣어두되,
    # 실제 비교 표시는 quotes 배열로 하게 만들기
    unit_won: Optional[int] = None
    total_won: Optional[int] = None

    # ✅ 공정별 견적 배열
    quotes: Optional[List[ProcessQuoteOut]] = None

    metrics: Optional[Dict[str, Any]] = None
    # validation은 공정별로 다룰 수 있게 dict로 유지(예: {"laser": {...}, "waterjet": {...}})
    validation: Optional[Dict[str, Any]] = None

    error_message: Optional[str] = None

    dxf_url: Optional[str] = None
    svg_url: Optional[str] = None


class QuoteOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str  # "ok" | "error"
    job: JobOut
    # ✅ 프론트가 바로 비교할 수 있게 top-level에도 quotes 제공
    quotes: List[ProcessQuoteOut] = Field(default_factory=list)
