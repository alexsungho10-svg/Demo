import io
import json
import os
import uuid
from datetime import datetime
from typing import Any

from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse

from db import SessionLocal, init_db
from models import Job, Vendor, Dispatch, JobStatus
from schemas import (
    CreateJobIn,
    JobOut,
    QuoteOut,
    DispatchCreateIn,
    ProcessQuoteOut,
)
from storage import (
    ensure_data_root,
    source_path,
    cad_path,
    step_path,  # 호환용(남겨둠)
    preview_svg_path,
    dxf_path,
)
from pricing import estimate_won, build_validation
from worker import run_quote, run_convert
from dispatcher import build_dispatch_payload, payload_to_json

# 업로드 허용 확장자
ALLOWED_EXTS = {".step", ".stp", ".igs", ".iges"}


def get_ext(filename: str) -> str:
    return os.path.splitext((filename or "").lower())[1]


app = FastAPI(title="STEP / IGES → Laser DXF Converter API", version="4.3.0")

# CORS (운영 시 도메인 제한 권장)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: 운영 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def now():
    return datetime.utcnow()


def _safe_json_load(s: str | None, default):
    if not s:
        return default
    try:
        return json.loads(s)
    except Exception:
        return default


def job_to_out(job: Job, request: Request) -> JobOut:
    base_url = str(request.base_url).rstrip("/")

    metrics = _safe_json_load(getattr(job, "metrics_json", None), None)
    validation = _safe_json_load(getattr(job, "validation_json", None), None)

    # ✅ 공정/견적 로드
    processes = _safe_json_load(getattr(job, "processes_json", None), [])
    quotes = _safe_json_load(getattr(job, "quotes_json", None), None)

    svg_url = None
    dxf_url = None

    if preview_svg_path(job.id).exists():
        svg_url = f"{base_url}/v1/jobs/{job.id}/preview.svg"

    if dxf_path(job.id).exists() and job.status == JobStatus.DONE:
        dxf_url = f"{base_url}/v1/jobs/{job.id}/download/dxf"

    # quotes -> ProcessQuoteOut 리스트로 변환(있으면)
    quotes_out = None
    if isinstance(quotes, list):
        try:
            quotes_out = [ProcessQuoteOut(**q) for q in quotes]
        except Exception:
            # 저장된 quotes_json 포맷이 살짝 달라도 서버가 죽지 않도록
            quotes_out = None

    return JobOut(
        id=job.id,
        status=job.status.value,
        input_format=getattr(job, "input_format", None),
        processes=processes if isinstance(processes, list) else [],
        material=job.material,
        thickness_mm=job.thickness_mm,
        qty=job.qty,
        thickness_auto_mm=job.thickness_auto_mm,
        # 레거시(호환용) 대표 견적
        unit_won=job.unit_won,
        total_won=job.total_won,
        # ✅ 공정별 견적
        quotes=quotes_out,
        metrics=metrics,
        validation=validation,
        error_message=getattr(job, "error_message", None),
        dxf_url=dxf_url,
        svg_url=svg_url,
    )


@app.on_event("startup")
def _startup():
    ensure_data_root()
    init_db()


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/v1/jobs", response_model=JobOut)
def create_job(payload: CreateJobIn, request: Request):
    # ✅ 공정 미선택 시 400
    if not payload.processes:
        raise HTTPException(status_code=400, detail="가공 방식을 선택해 주세요")

    job_id = str(uuid.uuid4())

    db = SessionLocal()
    try:
        job = Job(
            id=job_id,
            status=JobStatus.CREATED,
            material=payload.material,
            thickness_mm=payload.thickness_mm,
            qty=payload.qty,
            updated_at=now(),
        )

        # ✅ 공정 저장(모델에 컬럼이 있을 때만)
        if hasattr(job, "processes_json"):
            job.processes_json = json.dumps(payload.processes, ensure_ascii=False)

        db.add(job)
        db.commit()
        db.refresh(job)
        return job_to_out(job, request)
    finally:
        db.close()


@app.get("/v1/jobs/{job_id}", response_model=dict)
def get_job(job_id: str, request: Request):
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if not job:
            raise HTTPException(404, "job not found")

        out = job_to_out(job, request)
        return {"job": out.model_dump(), "log": {}}
    finally:
        db.close()


@app.post("/v1/jobs/{job_id}/upload", response_model=dict)
async def upload_step(job_id: str, request: Request, step: UploadFile = File(...)):
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if not job:
            raise HTTPException(404, "job not found")

        ext = get_ext(step.filename)
        if ext not in ALLOWED_EXTS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {ext}. Allowed: {sorted(ALLOWED_EXTS)}",
            )

        # ✅ 포맷 기록
        job.input_format = "iges" if ext in {".igs", ".iges"} else "step"

        # ✅ 확장자에 맞는 파일명으로 저장
        p = source_path(job_id, ext)
        data = await step.read()
        p.write_bytes(data)

        job.status = JobStatus.UPLOADED
        job.error_message = None
        job.updated_at = now()
        db.commit()

        out = job_to_out(job, request)
        return {
            "job": out.model_dump(),
            "log": {
                "upload": {
                    "filename": step.filename,
                    "format": job.input_format,
                    "saved_to": str(p),
                }
            },
        }
    finally:
        db.close()


def _ensure_processes_selected(job: Job) -> list[str]:
    processes = _safe_json_load(getattr(job, "processes_json", None), [])
    if not processes:
        raise HTTPException(status_code=400, detail="가공 방식을 선택해 주세요")
    if not isinstance(processes, list):
        raise HTTPException(status_code=400, detail="processes 형식이 올바르지 않습니다")
    return processes


def _build_quotes_and_validation(
    processes: list[str],
    material: str,
    used_th: float,
    qty: int,
    metrics: dict[str, Any],
    auto_th: float,
):
    quotes_list: list[dict[str, Any]] = []
    validation_map: dict[str, Any] = {}

    for proc in processes:
        # proc는 schemas에서 laser/waterjet로 제한되지만,
        # DB가 꼬였을 때도 서버가 죽지 않도록 방어
        if proc not in ("laser", "waterjet"):
            continue

        est = estimate_won(proc, material, used_th, qty, metrics)
        quotes_list.append(est)

        validation_map[proc] = build_validation(
            used_th,
            auto_th if auto_th > 0 else None,
            metrics,
            proc,
        )

    if not quotes_list:
        raise HTTPException(status_code=400, detail="가공 방식을 선택해 주세요")

    return quotes_list, validation_map


@app.post("/v1/jobs/{job_id}/quote", response_model=QuoteOut)
def quote(job_id: str, request: Request):
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if not job:
            raise HTTPException(404, "job not found")

        processes = _ensure_processes_selected(job)

        sp = cad_path(job_id)
        if not sp or not sp.exists():
            raise HTTPException(400, "CAD file not uploaded")

        tmp_dxf = str(dxf_path(job_id)) + ".tmp"
        result = run_quote(str(sp), tmp_dxf)

        if not isinstance(result, dict):
            job.status = JobStatus.ERROR
            job.error_message = f"quote failed: worker returned {type(result).__name__}"
            job.updated_at = now()
            db.commit()
            out = job_to_out(job, request)
            return QuoteOut(status="error", job=out, quotes=[])

        if result.get("status") != "ok":
            job.status = JobStatus.ERROR
            job.error_message = result.get("message") or "quote failed"
            job.updated_at = now()
            db.commit()
            out = job_to_out(job, request)
            return QuoteOut(status="error", job=out, quotes=[])

        auto_th = float(result.get("thickness_mm", 0.0) or 0.0)
        used_th = job.thickness_mm if job.thickness_mm and job.thickness_mm > 0 else auto_th

        metrics = result.get("metrics") or {}

        # SVG 저장
        svg = result.get("svg") or ""
        if svg:
            preview_svg_path(job_id).write_text(svg, encoding="utf-8")

        quotes_list, validation_map = _build_quotes_and_validation(
            processes=processes,
            material=job.material,
            used_th=used_th,
            qty=job.qty,
            metrics=metrics,
            auto_th=auto_th,
        )

        # 레거시 필드(unit/total)는 "첫번째 공정" 값을 대표로 채움(호환)
        primary = quotes_list[0]
        job.unit_won = int(primary["unit_won"])
        job.total_won = int(primary["total_won"])

        job.status = JobStatus.QUOTED
        job.thickness_auto_mm = auto_th
        job.metrics_json = json.dumps(metrics, ensure_ascii=False)
        job.validation_json = json.dumps(validation_map, ensure_ascii=False)

        # ✅ 공정별 견적 저장
        if hasattr(job, "quotes_json"):
            job.quotes_json = json.dumps(quotes_list, ensure_ascii=False)

        job.error_message = None
        job.updated_at = now()
        db.commit()
        db.refresh(job)

        out = job_to_out(job, request)
        quotes_out = [ProcessQuoteOut(**q) for q in quotes_list]
        return QuoteOut(status="ok", job=out, quotes=quotes_out)
    finally:
        db.close()


@app.post("/v1/jobs/{job_id}/start", response_model=JobOut)
def start_convert(job_id: str, request: Request):
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if not job:
            raise HTTPException(404, "job not found")

        processes = _ensure_processes_selected(job)

        sp = cad_path(job_id)
        if not sp or not sp.exists():
            raise HTTPException(400, "CAD file not uploaded")

        tmp_dxf = str(dxf_path(job_id)) + ".tmp"
        result = run_quote(str(sp), tmp_dxf)

        if not isinstance(result, dict) or result.get("status") != "ok":
            job.status = JobStatus.ERROR
            job.error_message = (result.get("message") if isinstance(result, dict) else None) or "quote failed"
            job.updated_at = now()
            db.commit()
            db.refresh(job)
            return job_to_out(job, request)

        svg = result.get("svg") or ""
        if svg:
            preview_svg_path(job_id).write_text(svg, encoding="utf-8")

        auto_th = float(result.get("thickness_mm", 0.0) or 0.0)
        used_th = job.thickness_mm if job.thickness_mm and job.thickness_mm > 0 else auto_th
        metrics = result.get("metrics") or {}

        quotes_list, validation_map = _build_quotes_and_validation(
            processes=processes,
            material=job.material,
            used_th=used_th,
            qty=job.qty,
            metrics=metrics,
            auto_th=auto_th,
        )

        primary = quotes_list[0]
        job.status = JobStatus.CONVERTING
        job.thickness_auto_mm = auto_th
        job.unit_won = int(primary["unit_won"])
        job.total_won = int(primary["total_won"])
        job.metrics_json = json.dumps(metrics, ensure_ascii=False)
        job.validation_json = json.dumps(validation_map, ensure_ascii=False)

        if hasattr(job, "quotes_json"):
            job.quotes_json = json.dumps(quotes_list, ensure_ascii=False)

        job.error_message = None
        job.updated_at = now()
        db.commit()

        outp = dxf_path(job_id)
        conv = run_convert(str(sp), str(outp))

        if not isinstance(conv, dict) or conv.get("status") != "ok":
            job.status = JobStatus.ERROR
            job.error_message = (conv.get("message") if isinstance(conv, dict) else None) or "convert failed"
            job.updated_at = now()
            db.commit()
            db.refresh(job)
            return job_to_out(job, request)

        job.status = JobStatus.DONE
        job.updated_at = now()
        db.commit()
        db.refresh(job)

        return job_to_out(job, request)
    finally:
        db.close()


@app.get("/v1/jobs/{job_id}/download/dxf")
def download_dxf(job_id: str):
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if not job:
            raise HTTPException(404, "job not found")

        if job.status != JobStatus.DONE:
            raise HTTPException(409, "dxf not ready")

        p = dxf_path(job_id)
        if not p.exists():
            raise HTTPException(500, "dxf file missing")

        data = p.read_bytes()
        headers = {
            "Content-Disposition": f'attachment; filename="{job_id}.dxf"',
            "Cache-Control": "no-store",
        }
        return StreamingResponse(io.BytesIO(data), media_type="application/dxf", headers=headers)
    finally:
        db.close()


@app.get("/v1/jobs/{job_id}/preview.svg")
def preview_svg(job_id: str):
    p = preview_svg_path(job_id)
    if not p.exists():
        raise HTTPException(404, "preview not found")
    return Response(
        content=p.read_text(encoding="utf-8"),
        media_type="image/svg+xml",
        headers={"Cache-Control": "no-store"},
    )


@app.post("/v1/vendors/seed", response_model=dict)
def seed_vendor():
    db = SessionLocal()
    try:
        v = Vendor(id=str(uuid.uuid4()), name="Seed Vendor", email="vendor@example.com")
        db.add(v)
        db.commit()
        db.refresh(v)
        return {"vendor_id": v.id, "name": v.name}
    finally:
        db.close()


@app.post("/v1/jobs/{job_id}/dispatch", response_model=dict)
def create_dispatch(job_id: str, payload: DispatchCreateIn):
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if not job:
            raise HTTPException(404, "job not found")

        if job.status != JobStatus.DONE:
            raise HTTPException(409, "job not ready for dispatch")

        p = dxf_path(job_id)
        if not p.exists():
            raise HTTPException(500, "dxf missing")

        quotes = _safe_json_load(getattr(job, "quotes_json", None), None)

        meta = {
            "material": job.material,
            "qty": job.qty,
            "thickness_mm": job.thickness_mm,
            "thickness_auto_mm": job.thickness_auto_mm,
            "unit_won": job.unit_won,
            "total_won": job.total_won,
            "quotes": quotes,
            "note": payload.note,
        }

        dp = build_dispatch_payload(job_id, payload.vendor_id, str(p), meta)
        dp_json = payload_to_json(dp)

        disp = Dispatch(
            id=str(uuid.uuid4()),
            job_id=job_id,
            vendor_id=payload.vendor_id,
            payload_json=dp_json,
        )
        db.add(disp)
        db.commit()
        db.refresh(disp)

        return {"status": "ok", "dispatch_id": disp.id, "payload": dp}
    finally:
        db.close()
