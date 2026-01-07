from typing import Any

MATERIALS = {
    "steel": {"label": "철(SS400)", "base": 2500, "cut_per_mm": 1.3, "pierce_per_loop": 300, "area_per_mm2": 0.0002},
    "stainless": {"label": "스테인리스(SUS)", "base": 3000, "cut_per_mm": 1.6, "pierce_per_loop": 350, "area_per_mm2": 0.00025},
    "aluminum": {"label": "알루미늄(AL)", "base": 2800, "cut_per_mm": 1.4, "pierce_per_loop": 320, "area_per_mm2": 0.00022},
    "acrylic": {"label": "아크릴", "base": 2000, "cut_per_mm": 1.0, "pierce_per_loop": 250, "area_per_mm2": 0.00018},
}


def _rel_err(a: float, b: float) -> float:
    if b == 0:
        return float("inf")
    return abs(a - b) / abs(b)


def build_validation(thickness_user_mm: float, thickness_auto_mm: float | None, metrics: dict[str, Any]):
    warnings: list[str] = []
    laser_ok = True
    route = "laser"

    rel = None
    if thickness_auto_mm is not None and thickness_auto_mm > 0:
        rel = _rel_err(thickness_user_mm, thickness_auto_mm)
        if rel > 0.25:
            warnings.append(
                f"두께 불일치 큼: 입력 {thickness_user_mm:.2f}mm vs 자동 {thickness_auto_mm:.2f}mm (오차 {rel*100:.1f}%)"
            )
        elif rel > 0.10:
            warnings.append(
                f"두께 불일치: 입력 {thickness_user_mm:.2f}mm vs 자동 {thickness_auto_mm:.2f}mm (오차 {rel*100:.1f}%)"
            )

    var_ratio = metrics.get("section_area_variation_ratio")
    if isinstance(var_ratio, (int, float)):
        if var_ratio > 0.03:
            warnings.append(f"단면 면적 변동 큼 ({var_ratio*100:.2f}%) — 레이저 전제(2D+두께) 위반 가능")
            laser_ok = False
            route = "cnc"
        elif var_ratio > 0.01:
            warnings.append(f"단면 면적 변동 있음 ({var_ratio*100:.2f}%) — 레이저 가능하나 확인 권장")

    if rel is not None and rel > 0.35:
        warnings.append("두께 오차가 매우 커 CNC 가공 권장")
        laser_ok = False
        route = "cnc"

    return {
        "thickness_user_mm": thickness_user_mm,
        "thickness_auto_mm": thickness_auto_mm,
        "thickness_rel_error": rel,
        "warnings": warnings,
        "laser_ok": laser_ok,
        "route": route,
    }


def _thickness_factor(thickness_mm: float) -> float:
    if thickness_mm <= 0:
        return 1.0
    return 1.0 + max(0.0, thickness_mm - 2.0) * 0.15


def _qty_factor(qty: int) -> float:
    if qty <= 1:
        return 1.0
    if qty <= 5:
        return 0.92
    if qty <= 20:
        return 0.85
    return 0.80


def estimate_won(material_key: str, thickness_mm: float, qty: int, metrics: dict[str, Any]) -> dict[str, Any]:
    mat = MATERIALS.get(material_key) or MATERIALS["steel"]

    base = float(mat["base"])
    cut_per_mm = float(mat["cut_per_mm"])
    pierce_per_loop = float(mat["pierce_per_loop"])
    area_per_mm2 = float(mat["area_per_mm2"])

    perim = float(metrics.get("perimeter_mm", 0.0) or 0.0)
    loops = int(metrics.get("loops", 0) or 0)
    area = float(metrics.get("area_mm2", 0.0) or 0.0)

    thickness_f = _thickness_factor(thickness_mm)
    qty_f = _qty_factor(qty)

    unit = base + perim * cut_per_mm + loops * pierce_per_loop + area * area_per_mm2
    unit *= thickness_f

    total = unit * max(1, qty) * qty_f

    return {
        "material": material_key,
        "unit_won": int(round(unit)),
        "total_won": int(round(total)),
        "factors": {"thickness_factor": thickness_f, "qty_factor": qty_f},
    }
