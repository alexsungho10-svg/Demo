import json
from typing import Any


def build_dispatch_payload(job_id: str, vendor_id: str, dxf_path: str, meta: dict[str, Any]) -> dict[str, Any]:
    return {
        "job_id": job_id,
        "vendor_id": vendor_id,
        "files": {
            "dxf_path": dxf_path,
        },
        "meta": meta,
    }


def payload_to_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)
