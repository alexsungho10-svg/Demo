import io
import json
import uuid
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse

from .db import SessionLocal, init_db
from .models import Job, Vendor, Dispatch, JobStatus
from .schemas import CreateJobIn, JobOut, QuoteOut, CheckoutOut, DispatchCreateIn
from .storage import ensure_data_root, step_path, preview_svg_path, dxf_path
from .pricing import estimate_won, build_validation
from .worker import run_quote, run_convert
from .dispatcher import build_dispatch_payload, payload_to_json

app = FastAPI(title="STEP → Laser DXF Converter API", version="3.0.0")

# ✅ Cloudflare/동업자 웹에서 호출 쉬운 CORS (운영 시 도메인 제한 권장)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: 운영 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def now():
    return datetime.utcnow()


def job_to_out(job: Job, base_url: str) -> JobOut:
    metrics = json.loads(job.metrics_json) if job.metrics_json else None
    validation = json.loads(job.validation_json) if job.validation_json else None

    svg_url = None
    dxf_url = None

    if preview_svg_path(job.id).exists():
        svg_url = f"{base_url}/v1/jobs/{job.id}/preview.svg"

    if dxf_path(job.id).exists() and job.status == JobStatus.DONE and job.paid:
        dxf_url = f"{base_url}/v1/jobs/{job.id}/download/dxf"

    return JobOut(
        id=job.id,
        status=job.status.value,
        material=job.material,
        thickness_mm=job.thickness_mm,
        qty=job.qty,
        paid=job.paid,
        thickness_auto_mm=job.thickness_auto_mm,
        unit_won=job.unit_won,
        total_won=job.total_won,
        metrics=metrics,
        validation=validation,
        error_message=job.error_message,
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
def create_job(payload: CreateJobIn):
    job_id = str(uuid.uuid4())

    db = SessionLocal()
    try:
        job = Job(
            id=job_id,
            status=JobStatus.CREATED,
            material=payload.material,
            thickness_mm=payload.thickness_mm,
            qty=payload.qty,
            paid=False,
            updated_at=now(),
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job_to_out(job, base_url="http://localhost:8000")
    finally:
        db.close()


@app.get("/v1/jobs/{job_id}", response_model=dict)
def get_job(job_id: str):
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if not job:
            raise HTTPException(404, "job not found")

        base_url = "http://localhost:8000"
        out = job_to_out(job, base_url=base_url)
        return {"job": out.model_dump(), "log": {}}
    finally:
        db.close()


@app.post("/v1/jobs/{job_id}/upload", response_model=dict)
async def upload_step(job_id: str, step: UploadFile = File(...)):
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if not job:
            raise HTTPException(404, "job not found")

        p = step_path(job_id)
        data = await step.read()
        p.write_bytes(data)

        job.status = JobStatus.UPLOADED
        job.error_message = None
        job.updated_at = now()
        db.commit()

        out = job_to_out(job, base_url="http://localhost:8000")
        return {"job": out.model_dump(), "log": {"uploadStep": {"saved_to": str(p)}}}
    finally:
        db.close()


@app.post("/v1/jobs/{job_id}/quote", response_model=QuoteOut)
def quote(job_id: str):
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if not job:
            raise HTTPException(404, "job not found")

        sp = step_path(job_id)
        if not sp.exists():
            raise HTTPException(400, "STEP not uploaded")

        # quote는 DXF를 최종 저장하지 않음(임시 경로로 한 번 돌려서 metrics/svg만 확보)
        tmp_dxf = str(dxf_path(job_id)) + ".tmp"
        result = run_quote(str(sp), tmp_dxf)

        if result.get("status") != "ok":
            job.status = JobStatus.ERROR
            job.error_message = result.get("message") or "quote failed"
            job.updated_at = now()
            db.commit()
            out = job_to_out(job, base_url="http://localhost:8000")
            return QuoteOut(status="error", job=out)

        auto_th = float(result.get("thickness_mm", 0.0) or 0.0)
        used_th = job.thickness_mm if job.thickness_mm and job.thickness_mm > 0 else auto_th

        metrics = result.get("metrics") or {}
        est = estimate_won(job.material, used_th, job.qty, metrics)
        validation = build_validation(used_th, auto_th if auto_th > 0 else None, metrics)

        # SVG 저장
        svg = result.get("svg") or ""
        if svg:
            preview_svg_path(job_id).write_text(svg, encoding="utf-8")

        job.status = JobStatus.QUOTED
        job.thickness_auto_mm = auto_th
        job.unit_won = est["unit_won"]
        job.total_won = est["total_won"]
        job.metrics_json = json.dumps(metrics, ensure_ascii=False)
        job.validation_json = json.dumps(validation, ensure_ascii=False)
        job.error_message = None
        job.updated_at = now()
        db.commit()
        db.refresh(job)

        out = job_to_out(job, base_url="http://localhost:8000")
        return QuoteOut(status="ok", job=out)
    finally:
        db.close()


@app.post("/v1/jobs/{job_id}/checkout", response_model=CheckoutOut)
def checkout(job_id: str):
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if not job:
            raise HTTPException(404, "job not found")

        if job.total_won is None:
            raise HTTPException(400, "quote first")

        job.status = JobStatus.CHECKOUT_READY
        job.updated_at = now()
        db.commit()

        # ✅ 지금은 Mock: 실제 PG 붙이면 여기서 payment session url 발급
        payment_url = f"http://localhost:3000/mock-pay.html?job_id={job.id}&amount={job.total_won}"

        return CheckoutOut(job_id=job.id, amount_won=job.total_won, payment_url=payment_url)
    finally:
        db.close()


@app.post("/v1/jobs/{job_id}/pay/mock", response_model=JobOut)
def pay_mock(job_id: str):
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if not job:
            raise HTTPException(404, "job not found")

        if job.total_won is None:
            raise HTTPException(400, "quote first")

        job.paid = True
        job.status = JobStatus.PAID
        job.updated_at = now()
        db.commit()
        db.refresh(job)

        return job_to_out(job, base_url="http://localhost:8000")
    finally:
        db.close()


@app.post("/v1/jobs/{job_id}/start", response_model=JobOut)
def start_convert(job_id: str):
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if not job:
            raise HTTPException(404, "job not found")

        if not job.paid:
            raise HTTPException(402, "payment required")

        sp = step_path(job_id)
        if not sp.exists():
            raise HTTPException(400, "STEP not uploaded")

        job.status = JobStatus.CONVERTING
        job.updated_at = now()
        db.commit()

        outp = dxf_path(job_id)
        result = run_convert(str(sp), str(outp))

        if result.get("status") != "ok":
            job.status = JobStatus.ERROR
            job.error_message = result.get("message") or "convert failed"
            job.updated_at = now()
            db.commit()
            db.refresh(job)
            return job_to_out(job, base_url="http://localhost:8000")

        # thickness/metrics 업데이트 (quote 안 했어도 start로 최종 생성 가능)
        auto_th = float(result.get("thickness_mm", 0.0) or 0.0)
        used_th = job.thickness_mm if job.thickness_mm and job.thickness_mm > 0 else auto_th
        metrics = result.get("metrics") or {}

        est = estimate_won(job.material, used_th, job.qty, metrics)
        validation = build_validation(used_th, auto_th if auto_th > 0 else None, metrics)

        job.status = JobStatus.DONE
        job.thickness_auto_mm = auto_th
        job.unit_won = est["unit_won"]
        job.total_won = est["total_won"]
        job.metrics_json = json.dumps(metrics, ensure_ascii=False)
        job.validation_json = json.dumps(validation, ensure_ascii=False)
        job.error_message = None
        job.updated_at = now()
        db.commit()
        db.refresh(job)

        return job_to_out(job, base_url="http://localhost:8000")
    finally:
        db.close()


@app.get("/v1/jobs/{job_id}/download/dxf")
def download_dxf(job_id: str):
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if not job:
            raise HTTPException(404, "job not found")

        if not job.paid:
            raise HTTPException(402, "payment required")

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
    return Response(content=p.read_text(encoding="utf-8"), media_type="image/svg+xml", headers={"Cache-Control": "no-store"})


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

        if job.status != JobStatus.DONE or not job.paid:
            raise HTTPException(409, "job not ready for dispatch")

        p = dxf_path(job_id)
        if not p.exists():
            raise HTTPException(500, "dxf missing")

        meta = {
            "material": job.material,
            "qty": job.qty,
            "thickness_mm": job.thickness_mm,
            "thickness_auto_mm": job.thickness_auto_mm,
            "unit_won": job.unit_won,
            "total_won": job.total_won,
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
