import os
from pathlib import Path

DATA_ROOT = Path("/app/data/objects")


def job_dir(job_id: str) -> Path:
    p = DATA_ROOT / job_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def step_path(job_id: str) -> Path:
    return job_dir(job_id) / "input.step"


def preview_svg_path(job_id: str) -> Path:
    return job_dir(job_id) / "preview.svg"


def dxf_path(job_id: str) -> Path:
    return job_dir(job_id) / "output.dxf"


def ensure_data_root():
    os.makedirs(DATA_ROOT, exist_ok=True)
