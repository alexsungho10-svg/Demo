import os
from pathlib import Path

DEFAULT_DATA_ROOT = "/app/data"


def data_root() -> Path:
    return Path(os.getenv("DATA_ROOT") or DEFAULT_DATA_ROOT)


def ensure_data_root() -> None:
    (data_root() / "objects").mkdir(parents=True, exist_ok=True)


def objects_dir(job_id: str) -> Path:
    d = data_root() / "objects" / job_id
    d.mkdir(parents=True, exist_ok=True)
    return d


# 업로드 파일 경로 (확장자 포함)
def source_path(job_id: str, ext: str) -> Path:
    if not ext.startswith("."):
        ext = "." + ext
    return objects_dir(job_id) / f"input{ext.lower()}"


# 실제 CAD 입력 파일 찾기 (step/iges 지원)
def cad_path(job_id: str) -> Path | None:
    d = objects_dir(job_id)
    candidates = [
        d / "input.step",
        d / "input.stp",
        d / "input.iges",
        d / "input.igs",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


# (레거시 호환용)
def step_path(job_id: str) -> Path:
    return objects_dir(job_id) / "input.stp"


def preview_svg_path(job_id: str) -> Path:
    return objects_dir(job_id) / "preview.svg"


def dxf_path(job_id: str) -> Path:
    return objects_dir(job_id) / "output.dxf"
