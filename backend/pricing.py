from __future__ import annotations

from typing import Dict, Any, List, Optional, Literal
import math
import os

ProcessKey = Literal["laser", "waterjet"]

# =============================
# 1) 두께별 단가표 (가공비)
# =============================
# 단위:
# - base_fee: 원
# - cut_per_mm: 원/mm
# - pierce_per_loop: 원/loop(윤곽/홀 1개)
# - area_per_mm2: 원/mm^2 (필요 없으면 0)
#
# ✅ 여기 숫자만 "현장 단가"로 채우면 됨.
RATE_TABLE: Dict[ProcessKey, Dict[str, Dict[float, Dict[str, float]]]] = {
    "laser": {
        "steel": {
            1.0: {"base_fee": 7000, "cut_per_mm": 100, "pierce_per_loop": 250, "area_per_mm2": 0.0, "min_unit": 12000},
            2.0: {"base_fee": 7000, "cut_per_mm": 120, "pierce_per_loop": 280, "area_per_mm2": 0.0, "min_unit": 12000},
            3.0: {"base_fee": 7000, "cut_per_mm": 140, "pierce_per_loop": 310, "area_per_mm2": 0.0, "min_unit": 13000},
            4.0: {"base_fee": 8000, "cut_per_mm": 170, "pierce_per_loop": 360, "area_per_mm2": 0.0, "min_unit": 15000},
            5.0: {"base_fee": 9000, "cut_per_mm": 210, "pierce_per_loop": 420, "area_per_mm2": 0.0, "min_unit": 17000},
            6.0: {"base_fee": 10000, "cut_per_mm": 260, "pierce_per_loop": 480, "area_per_mm2": 0.0, "min_unit": 19000},
            8.0: {"base_fee": 12000, "cut_per_mm": 340, "pierce_per_loop": 600, "area_per_mm2": 0.0, "min_unit": 23000},
            10.0: {"base_fee": 14000, "cut_per_mm": 430, "pierce_per_loop": 760, "area_per_mm2": 0.0, "min_unit": 28000},
            12.0: {"base_fee": 16000, "cut_per_mm": 520, "pierce_per_loop": 920, "area_per_mm2": 0.0, "min_unit": 33000},
        },
        "stainless": {
            1.0: {"base_fee": 9000, "cut_per_mm": 130, "pierce_per_loop": 320, "area_per_mm2": 0.0, "min_unit": 15000},
            2.0: {"base_fee": 9000, "cut_per_mm": 155, "pierce_per_loop": 360, "area_per_mm2": 0.0, "min_unit": 15000},
            3.0: {"base_fee": 9000, "cut_per_mm": 185, "pierce_per_loop": 410, "area_per_mm2": 0.0, "min_unit": 16000},
            4.0: {"base_fee": 10500, "cut_per_mm": 225, "pierce_per_loop": 480, "area_per_mm2": 0.0, "min_unit": 19000},
            6.0: {"base_fee": 12500, "cut_per_mm": 340, "pierce_per_loop": 650, "area_per_mm2": 0.0, "min_unit": 24000},
            8.0: {"base_fee": 14500, "cut_per_mm": 450, "pierce_per_loop": 820, "area_per_mm2": 0.0, "min_unit": 30000},
        },
        "aluminum": {
            1.0: {"base_fee": 7000, "cut_per_mm": 110, "pierce_per_loop": 260, "area_per_mm2": 0.0, "min_unit": 12000},
            2.0: {"base_fee": 7000, "cut_per_mm": 130, "pierce_per_loop": 290, "area_per_mm2": 0.0, "min_unit": 12000},
            3.0: {"base_fee": 7000, "cut_per_mm": 150, "pierce_per_loop": 330, "area_per_mm2": 0.0, "min_unit": 13000},
        },
        "acrylic": {
            3.0: {"base_fee": 6000, "cut_per_mm": 60, "pierce_per_loop": 200, "area_per_mm2": 0.0, "min_unit": 10000},
        },
    },

    "waterjet": {
        "steel": {
            1.0: {"base_fee": 11000, "cut_per_mm": 140, "pierce_per_loop": 180, "area_per_mm2": 0.0, "min_unit": 16000},
            2.0: {"base_fee": 11000, "cut_per_mm": 160, "pierce_per_loop": 190, "area_per_mm2": 0.0, "min_unit": 17000},
            3.0: {"base_fee": 11000, "cut_per_mm": 180, "pierce_per_loop": 200, "area_per_mm2": 0.0, "min_unit": 18000},
            4.0: {"base_fee": 12000, "cut_per_mm": 210, "pierce_per_loop": 220, "area_per_mm2": 0.0, "min_unit": 20000},
            6.0: {"base_fee": 13000, "cut_per_mm": 270, "pierce_per_loop": 260, "area_per_mm2": 0.0, "min_unit": 24000},
            8.0: {"base_fee": 14000, "cut_per_mm": 330, "pierce_per_loop": 300, "area_per_mm2": 0.0, "min_unit": 28000},
            10.0: {"base_fee": 15500, "cut_per_mm": 400, "pierce_per_loop": 340, "area_per_mm2": 0.0, "min_unit": 32000},
            12.0: {"base_fee": 17000, "cut_per_mm": 470, "pierce_per_loop": 390, "area_per_mm2": 0.0, "min_unit": 36000},
        },
        "stainless": {
            6.0: {"base_fee": 15000, "cut_per_mm": 320, "pierce_per_loop": 300, "area_per_mm2": 0.0, "min_unit": 28000},
        },
    },
}

DEFAULT_MATERIAL = "steel"
DEFAULT_PROCESS: ProcessKey = "laser"

# =============================
# 1-B) 소재비: 무게(kg) 기반
# =============================
# density: kg/m^3, price_per_kg_won: 원/kg
# ✅ 여기 price_per_kg_won만 현장 단가로 바꾸면 됨.
MATERIAL_DB: Dict[str, Dict[str, float]] = {
    "steel": {"density_kg_m3": 7850.0, "price_per_kg_won": 2500.0, "min_material_won": 800.0},
    "stainless": {"density_kg_m3": 8000.0, "price_per_kg_won": 9000.0, "min_material_won": 1500.0},
    "aluminum": {"density_kg_m3": 2700.0, "price_per_kg_won": 6500.0, "min_material_won": 1000.0},
    "acrylic": {"density_kg_m3": 1180.0, "price_per_kg_won": 4500.0, "min_material_won": 800.0},
}

# 환경변수로 쉽게 조절 가능(없으면 기본값 사용)
DEFAULT_SCRAP_FACTOR = float(os.getenv("MATERIAL_SCRAP_FACTOR", "1.15"))  # 바운딩박스 + 스크랩 여유


def _normalize_material_key(material: str) -> str:
    k = (material or DEFAULT_MATERIAL).strip().lower()
    # alias 처리(필요하면 추가)
    alias = {
        "ss304": "stainless",
        "sus304": "stainless",
        "al6061": "aluminum",
        "al5052": "aluminum",
    }
    k = alias.get(k, k)
    if k not in MATERIAL_DB:
        return DEFAULT_MATERIAL
    return k


def _material_cost_from_bbox_weight(
    *,
    material_key: str,
    bbox_w_mm: float,
    bbox_h_mm: float,
    thickness_mm: float,
    scrap_factor: float,
) -> Dict[str, Any]:
    mk = _normalize_material_key(material_key)
    spec = MATERIAL_DB.get(mk) or MATERIAL_DB[DEFAULT_MATERIAL]

    density = float(spec["density_kg_m3"])
    price_per_kg = float(spec["price_per_kg_won"])
    min_material_won = float(spec.get("min_material_won", 0.0))

    w = max(0.0, float(bbox_w_mm))
    h = max(0.0, float(bbox_h_mm))
    t = max(0.0, float(thickness_mm))
    scrap = max(1.0, float(scrap_factor))

    vol_mm3 = (w * h * t) * scrap
    vol_m3 = vol_mm3 * 1e-9
    weight_kg = vol_m3 * density

    material_won = weight_kg * price_per_kg
    material_won = max(material_won, min_material_won)

    return {
        "material_key": mk,
        "density_kg_m3": density,
        "price_per_kg_won": price_per_kg,
        "scrap_factor": scrap,
        "bbox_w_mm": w,
        "bbox_h_mm": h,
        "thickness_mm": t,
        "volume_mm3": vol_mm3,
        "weight_kg": weight_kg,
        "material_won": material_won,
        "min_material_won": min_material_won,
    }


# =============================
# 2) 표 조회 방식 옵션
# =============================
THICKNESS_LOOKUP_MODE: Literal["nearest", "lerp"] = "nearest"


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _sorted_keys(d: Dict[float, Any]) -> List[float]:
    return sorted(float(k) for k in d.keys())


def _nearest_key(x: float, keys: List[float]) -> float:
    best = keys[0]
    best_dist = abs(x - best)
    for k in keys[1:]:
        dist = abs(x - k)
        if dist < best_dist:
            best = k
            best_dist = dist
    return best


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _get_rate_row(process: ProcessKey, material: str, thickness_mm: float) -> Dict[str, float]:
    proc_table = RATE_TABLE.get(process) or RATE_TABLE[DEFAULT_PROCESS]
    mat_key = _normalize_material_key(material)
    mat_table = proc_table.get(mat_key) or proc_table.get(DEFAULT_MATERIAL)

    if not mat_table:
        raise ValueError(f"No rate table for process={process}, material={material}")

    t = float(thickness_mm or 0.0)
    t = _clamp(t, 0.1, 200.0)

    keys = _sorted_keys(mat_table)

    if t in mat_table:
        return dict(mat_table[t])

    if THICKNESS_LOOKUP_MODE == "nearest" or len(keys) == 1:
        k = _nearest_key(t, keys)
        row = dict(mat_table[k])
        row["_picked_thickness_mm"] = float(k)
        return row

    if t <= keys[0]:
        row = dict(mat_table[keys[0]])
        row["_picked_thickness_mm"] = float(keys[0])
        return row
    if t >= keys[-1]:
        row = dict(mat_table[keys[-1]])
        row["_picked_thickness_mm"] = float(keys[-1])
        return row

    for i in range(len(keys) - 1):
        t0, t1 = keys[i], keys[i + 1]
        if t0 <= t <= t1:
            r0 = mat_table[t0]
            r1 = mat_table[t1]
            tt = (t - t0) / (t1 - t0) if t1 != t0 else 0.0

            out = {}
            for k in ("base_fee", "cut_per_mm", "pierce_per_loop", "area_per_mm2", "min_unit"):
                out[k] = float(_lerp(float(r0.get(k, 0.0)), float(r1.get(k, 0.0)), tt))
            out["_picked_thickness_mm"] = float(t)
            out["_bracket"] = [float(t0), float(t1)]
            return out

    k = _nearest_key(t, keys)
    row = dict(mat_table[k])
    row["_picked_thickness_mm"] = float(k)
    return row


def qty_discount_factor(qty: int) -> float:
    if qty <= 1:
        return 1.0
    if qty < 5:
        return 0.97
    if qty < 10:
        return 0.94
    if qty < 30:
        return 0.90
    return 0.87


# =============================
# 3) Public: estimate_won / build_validation
# =============================

def estimate_won(
    process: ProcessKey,
    material_key: str,
    thickness_mm: float,
    qty: int,
    metrics: Dict[str, Any],
) -> Dict[str, Any]:
    """
    ✅ 최종 단가(원) = 가공비(단가표 기반) + 소재비(무게 기반)
    - 가공비: base + perimeter*cut + loops*pierce (+ area option)
    - 소재비: bbox(w,h) * thickness -> volume -> weight -> won/kg
    """
    proc: ProcessKey = process if process in ("laser", "waterjet") else DEFAULT_PROCESS

    loops = int(metrics.get("loops") or 0)
    perim = float(metrics.get("perimeter_mm") or 0.0)
    area = float(metrics.get("area_mm2") or 0.0)

    bbox = metrics.get("bbox_mm") or {}
    bbox_w = float(bbox.get("w") or 0.0)
    bbox_h = float(bbox.get("h") or 0.0)

    # ✅ 가공 단가 조회
    row = _get_rate_row(proc, material_key, float(thickness_mm))

    base_fee = float(row.get("base_fee", 0.0))
    cut_per_mm = float(row.get("cut_per_mm", 0.0))
    pierce_per_loop = float(row.get("pierce_per_loop", 0.0))
    area_per_mm2 = float(row.get("area_per_mm2", 0.0))
    min_unit = float(row.get("min_unit", 0.0))

    process_unit = base_fee + perim * cut_per_mm + loops * pierce_per_loop + area * area_per_mm2
    process_unit = max(process_unit, min_unit)

    # ✅ 소재비(무게 기반) 추가
    scrap_factor = DEFAULT_SCRAP_FACTOR
    mat = _material_cost_from_bbox_weight(
        material_key=material_key,
        bbox_w_mm=bbox_w,
        bbox_h_mm=bbox_h,
        thickness_mm=float(thickness_mm),
        scrap_factor=scrap_factor,
    )
    material_unit = float(mat["material_won"])

    unit = process_unit + material_unit
    unit_won = int(math.ceil(unit))

    q = max(1, int(qty or 1))
    q_factor = qty_discount_factor(q)
    total_won = int(math.ceil(unit_won * q * q_factor))

    # 홀 개수(보수적): loops = outer 1 + holes N
    hole_count_est = max(0, loops - 1) if loops > 0 else 0

    factors: Dict[str, Any] = {
        "qty_factor": round(q_factor, 4),
        "lookup_mode": THICKNESS_LOOKUP_MODE,
        "picked_thickness_mm": row.get("_picked_thickness_mm"),
        "rate": {
            "base_fee": base_fee,
            "cut_per_mm": cut_per_mm,
            "pierce_per_loop": pierce_per_loop,
            "area_per_mm2": area_per_mm2,
            "min_unit": min_unit,
        },
        "processing": {
            "process_unit_won": float(process_unit),
            "loops_total": loops,
            "hole_count_est": int(hole_count_est),
            "perimeter_mm": perim,
            "area_mm2": area,
        },
        "material_cost": {
            **mat,
        },
    }
    if "_bracket" in row:
        factors["lerp_bracket_mm"] = row["_bracket"]

    return {
        "process": proc,
        "material": _normalize_material_key(material_key),
        "thickness_mm": float(thickness_mm),
        "qty": q,
        "unit_won": unit_won,
        "total_won": total_won,
        "factors": factors,
    }


def _rel_err(a: float, b: float) -> float:
    if b == 0:
        return float("inf")
    return abs(a - b) / abs(b)


def build_validation(
    thickness_user_mm: float,
    thickness_auto_mm: Optional[float],
    metrics: Dict[str, Any],
    process: ProcessKey,
) -> Dict[str, Any]:
    warnings: List[str] = []
    ok = True

    tu = float(thickness_user_mm or 0.0)
    ta = float(thickness_auto_mm or 0.0) if thickness_auto_mm is not None else 0.0

    rel = None
    if ta > 0 and tu > 0:
        rel = _rel_err(tu, ta)
        if rel > 0.25:
            warnings.append(
                f"두께 불일치 큼: 입력 {tu:.2f}mm vs 자동 {ta:.2f}mm (오차 {rel*100:.1f}%)"
            )
            ok = False
        elif rel > 0.10:
            warnings.append(
                f"두께 불일치: 입력 {tu:.2f}mm vs 자동 {ta:.2f}mm (오차 {rel*100:.1f}%)"
            )

    loops = int(metrics.get("loops") or 0)
    perim = float(metrics.get("perimeter_mm") or 0.0)
    if loops <= 0 or perim <= 1.0:
        warnings.append("형상 메트릭(loops/perimeter)이 비정상일 수 있음 (결과 확인 권장)")

    route = process if ok else "cnc"

    return {
        "process": process,
        "thickness_user_mm": tu,
        "thickness_auto_mm": (ta if thickness_auto_mm is not None else None),
        "thickness_rel_error": rel,
        "warnings": warnings,
        "ok": ok,
        "route": route,
    }
