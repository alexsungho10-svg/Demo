from typing import Any
from .freecad_convert import convert_step_to_dxf, ConvertOptions, ConvertError


def run_quote(step_path: str, tmp_dxf_path: str) -> dict[str, Any]:
    opts = ConvertOptions(
        k_face_candidates=2,
        n_slices=40,
        rel_tol=0.008,
        silhouette=True,
        debug=False,
        make_svg=True,
        svg_stroke_mm=0.20,
    )
    try:
        return convert_step_to_dxf(step_path, tmp_dxf_path, opts)
    except ConvertError as e:
        return {"status": "error", "message": str(e)}


def run_convert(step_path: str, out_dxf_path: str) -> dict[str, Any]:
    opts = ConvertOptions(
        k_face_candidates=2,
        n_slices=40,
        rel_tol=0.008,
        silhouette=True,
        debug=False,
        make_svg=False,
    )
    try:
        return convert_step_to_dxf(step_path, out_dxf_path, opts)
    except ConvertError as e:
        return {"status": "error", "message": str(e)}
