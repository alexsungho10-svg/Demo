import os
from pathlib import Path
from typing import Optional

DATA_ROOT = Path("/app/data/objects")

# 지원 확장자 (STL은 보류)
ALLOWED_EXTS = {".step", ".stp", ".igs", ".iges"}


def job_dir(job_id: str) -> Path:
    p = DATA_ROOT / job_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def source_path(job_id: str, ext: str) -> Path:
    """
    업로드 원본 파일 저장 경로
    예) input.step / input.igs
    """
    ext = ext.lower()
    if not ext.startswith("."):
        ext = "." + ext
    return job_dir(job_id) / f"input{ext}"


def cad_path(job_id: str) -> Optional[Path]:
    """
    현재 업로드된 CAD 파일 경로를 찾아서 반환.
    우선순위: step/stp/igs/iges 순으로 탐색
    """
    d = job_dir(job_id)
    for ext in (".step", ".stp", ".igs", ".iges"):
        p = d / f"input{ext}"
        if p.exists():
            return p
    return None


# ✅ 기존 코드 호환용 (이제는 "업로드된 실제 CAD 파일"을 의미)
def step_path(job_id: str) -> Path:
    """
    기존 코드 호환을 위해 남겨둠.
    업로드된 CAD 파일이 있으면 그 경로를 반환.
    없으면 기본값 input.step 경로(아직 파일은 없을 수 있음) 반환.
    """
    p = cad_path(job_id)
    return p if p is not None else (job_dir(job_id) / "input.step")


def preview_svg_path(job_id: str) -> Path:
    return job_dir(job_id) / "preview.svg"


def dxf_path(job_id: str) -> Path:
    return job_dir(job_id) / "output.dxf"


def ensure_data_root():
    os.makedirs(DATA_ROOT, exist_ok=True)
