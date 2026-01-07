import math
import os
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any

# FreeCAD는 런타임에만 존재하므로 import 에러 방지용 try
try:
    import FreeCAD  # type: ignore
    import Part  # type: ignore
except Exception:
    FreeCAD = None
    Part = None


@dataclass
class ConvertOptions:
    k_face_candidates: int = 2              # K=2
    n_slices: int = 40                      # 30~50 권장
    rel_tol: float = 0.008                  # 0.5~1% 권장 → 기본 0.8%
    abs_tol_area: float = 1e-6              # 면적 절대오차(보조)
    silhouette: bool = True                 # True면 실루엣(투영), False면 특정 z 단면
    section_z_ratio: float = 0.5            # silhouette=False일 때, 두께방향 중간(0~1)
    debug: bool = False
    make_svg: bool = True                   # SVG 프리뷰 생성 여부
    svg_stroke_mm: float = 0.15             # SVG 선 두께(뷰용)


class ConvertError(RuntimeError):
    pass


def _require_freecad():
    if FreeCAD is None or Part is None:
        raise ConvertError("FreeCAD Python 모듈을 불러오지 못했습니다. 컨테이너/FreeCADCmd 환경을 확인하세요.")


def _unit(v) -> "FreeCAD.Vector":
    n = v.Length
    if n <= 1e-12:
        return FreeCAD.Vector(0, 0, 0)
    return v.multiply(1.0 / n)


def _angle_between(a, b) -> float:
    a = _unit(a)
    b = _unit(b)
    dot = max(-1.0, min(1.0, a.dot(b)))
    return math.acos(dot)


def _rotation_from_to(src: "FreeCAD.Vector", dst: "FreeCAD.Vector") -> "FreeCAD.Rotation":
    src_u = _unit(src)
    dst_u = _unit(dst)
    if src_u.Length <= 1e-12 or dst_u.Length <= 1e-12:
        return FreeCAD.Rotation()

    angle = _angle_between(src_u, dst_u)
    if angle <= 1e-9:
        return FreeCAD.Rotation()

    # 반대 방향이면 임의의 수직축 선택
    if abs(angle - math.pi) <= 1e-6:
        tmp = FreeCAD.Vector(1, 0, 0)
        if abs(src_u.dot(tmp)) > 0.9:
            tmp = FreeCAD.Vector(0, 1, 0)
        axis = _unit(src_u.cross(tmp))
        return FreeCAD.Rotation(axis, 180)

    axis = _unit(src_u.cross(dst_u))
    return FreeCAD.Rotation(axis, math.degrees(angle))


def _cluster_normals(faces: List["Part.Face"], ang_tol_deg: float = 3.0) -> List[Dict]:
    ang_tol = math.radians(ang_tol_deg)
    clusters = []
    for f in faces:
        try:
            n = f.normalAt(0.5, 0.5)
        except Exception:
            continue
        n = _unit(n)
        if n.Length <= 1e-12:
            continue

        area = float(getattr(f, "Area", 0.0))
        placed = False

        for c in clusters:
            if _angle_between(n, c["normal"]) <= ang_tol or _angle_between(n, c["normal"].negative()) <= ang_tol:
                c["faces"].append(f)
                c["area_sum"] += area
                placed = True
                break

        if not placed:
            clusters.append({"normal": n, "faces": [f], "area_sum": area})

    clusters.sort(key=lambda x: x["area_sum"], reverse=True)
    return clusters


def _bbox_zminmax(shape: "Part.Shape") -> Tuple[float, float]:
    bb = shape.BoundBox
    return float(bb.ZMin), float(bb.ZMax)


def _section_area_at_z(shape: "Part.Shape", z: float) -> float:
    plane = Part.Plane(FreeCAD.Vector(0, 0, z), FreeCAD.Vector(0, 0, 1))
    sec = shape.section(plane.toShape())
    if sec is None:
        return 0.0

    edges = getattr(sec, "Edges", None)
    if not edges:
        return 0.0

    wires: List["Part.Wire"] = []
    try:
        w = Part.Wire(Part.__sortEdges__(edges))
        wires = [w]
    except Exception:
        try:
            sorted_groups = Part.sortEdges(edges)
            for g in sorted_groups:
                try:
                    wires.append(Part.Wire(g))
                except Exception:
                    pass
        except Exception:
            return 0.0

    area_sum = 0.0
    for w in wires:
        if not w.isClosed():
            continue
        try:
            face = Part.Face(w)
            area_sum += float(face.Area)
        except Exception:
            continue
    return float(area_sum)


def _areas_are_constant(areas: List[float], rel_tol: float, abs_tol: float) -> bool:
    if not areas:
        return False
    mn = min(areas)
    mx = max(areas)
    mean = sum(areas) / len(areas)

    if mean <= abs_tol:
        return False

    rel_err = (mx - mn) / max(mean, abs_tol)
    if rel_err <= rel_tol:
        return True

    if (mx - mn) <= abs_tol:
        return True

    return False


# ----------------------------
# 2D extraction helpers
# ----------------------------
def _dedupe_points_xy(pts: List[Tuple[float, float]], tol: float = 1e-6) -> List[Tuple[float, float]]:
    if not pts:
        return pts
    out = [pts[0]]
    for x, y in pts[1:]:
        px, py = out[-1]
        if abs(x - px) > tol or abs(y - py) > tol:
            out.append((x, y))
    return out


def _wire_to_points_xy(wire: "Part.Wire") -> List[Tuple[float, float]]:
    pts: List[Tuple[float, float]] = []
    edges = list(getattr(wire, "Edges", []))
    if not edges:
        return pts

    for e in edges:
        try:
            # 길이에 따라 샘플 수 가변(0.5mm 정도)
            n = max(16, min(400, int(float(e.Length) / 0.5)))
            pr = e.ParameterRange
            u0, u1 = float(pr[0]), float(pr[1])
            for i in range(n + 1):
                u = u0 + (u1 - u0) * (i / n)
                p = e.valueAt(u)
                pts.append((float(p.x), float(p.y)))
        except Exception:
            continue

    pts = _dedupe_points_xy(pts, tol=1e-6)

    # 닫힌 와이어면 시작/끝 맞추기
    try:
        if wire.isClosed() and pts:
            sx, sy = pts[0]
            ex, ey = pts[-1]
            if abs(sx - ex) > 1e-6 or abs(sy - ey) > 1e-6:
                pts.append((sx, sy))
    except Exception:
        pass

    return pts


def _shape_edges_to_wires(shape2d: "Part.Shape") -> List["Part.Wire"]:
    edges = list(getattr(shape2d, "Edges", []))
    if not edges:
        return []

    wires: List["Part.Wire"] = []
    try:
        groups = Part.sortEdges(edges)
    except Exception:
        try:
            w = Part.Wire(Part.__sortEdges__(edges))
            return [w]
        except Exception:
            return []

    for g in groups:
        try:
            wires.append(Part.Wire(g))
        except Exception:
            continue
    return wires


def _polyline_length(pts: List[Tuple[float, float]]) -> float:
    if len(pts) < 2:
        return 0.0
    s = 0.0
    for i in range(1, len(pts)):
        x0, y0 = pts[i - 1]
        x1, y1 = pts[i]
        s += math.hypot(x1 - x0, y1 - y0)
    return float(s)


def _poly_area_shoelace(pts: List[Tuple[float, float]]) -> float:
    if len(pts) < 3:
        return 0.0
    if pts[0] != pts[-1]:
        pts = pts + [pts[0]]
    a = 0.0
    for i in range(len(pts) - 1):
        x0, y0 = pts[i]
        x1, y1 = pts[i + 1]
        a += x0 * y1 - x1 * y0
    return float(a) / 2.0


def _metrics_from_polylines(polylines: List[List[Tuple[float, float]]]) -> Dict[str, Any]:
    loops = 0
    total_len = 0.0
    total_area = 0.0
    xmin = ymin = float("inf")
    xmax = ymax = float("-inf")

    for pts in polylines:
        if len(pts) < 2:
            continue

        for x, y in pts:
            xmin = min(xmin, x)
            ymin = min(ymin, y)
            xmax = max(xmax, x)
            ymax = max(ymax, y)

        total_len += _polyline_length(pts)

        # 닫힘 판정
        closed = False
        if len(pts) >= 3:
            sx, sy = pts[0]
            ex, ey = pts[-1]
            closed = (abs(sx - ex) <= 1e-6 and abs(sy - ey) <= 1e-6)

        if closed:
            loops += 1
            total_area += abs(_poly_area_shoelace(pts))

    if xmin == float("inf"):
        xmin = ymin = xmax = ymax = 0.0

    return {
        "loops": int(loops),
        "perimeter_mm": float(total_len),
        "area_mm2": float(total_area),
        "bbox_mm": {"w": float(xmax - xmin), "h": float(ymax - ymin)},
        "bbox_xy": {"xmin": float(xmin), "ymin": float(ymin), "xmax": float(xmax), "ymax": float(ymax)},
    }


def _polylines_from_wires(wires: List["Part.Wire"]) -> List[List[Tuple[float, float]]]:
    polylines: List[List[Tuple[float, float]]] = []
    for w in wires:
        pts = _wire_to_points_xy(w)
        if len(pts) >= 2:
            polylines.append(pts)
    return polylines


# ----------------------------
# DXF writer (ezdxf)
# ----------------------------
def _write_dxf_from_polylines(out_dxf: str, polylines: List[List[Tuple[float, float]]]) -> None:
    os.makedirs(os.path.dirname(out_dxf) or ".", exist_ok=True)

    try:
        import ezdxf  # type: ignore
    except Exception as e:
        raise ConvertError(f"ezdxf import 실패: {e}")

    doc = ezdxf.new(dxfversion="R2010")
    try:
        doc.units = ezdxf.units.MM
    except Exception:
        pass

    msp = doc.modelspace()

    wrote_any = False
    for pts in polylines:
        if len(pts) < 2:
            continue

        # 닫힘 판정
        close_flag = False
        if len(pts) >= 3:
            sx, sy = pts[0]
            ex, ey = pts[-1]
            close_flag = (abs(sx - ex) <= 1e-6 and abs(sy - ey) <= 1e-6)

        # close_flag면 마지막 점 제거하고 close로 닫기
        if close_flag and len(pts) >= 2:
            pts2 = pts[:-1]
        else:
            pts2 = pts

        if len(pts2) < 2:
            continue

        msp.add_lwpolyline(pts2, close=close_flag)
        wrote_any = True

    if not wrote_any:
        raise ConvertError("DXF로 내보낼 2D 폴리라인을 만들지 못했습니다(결과가 비어있음).")

    doc.saveas(out_dxf)

    if (not os.path.exists(out_dxf)) or os.path.getsize(out_dxf) <= 0:
        raise ConvertError(f"ezdxf로 DXF 저장을 시도했지만 파일이 생성되지 않았습니다: {out_dxf}")


# ----------------------------
# SVG preview
# ----------------------------
def _svg_from_polylines(polylines: List[List[Tuple[float, float]]], stroke_mm: float = 0.15) -> str:
    m = _metrics_from_polylines(polylines)
    bb = m["bbox_xy"]
    xmin, ymin, xmax, ymax = bb["xmin"], bb["ymin"], bb["xmax"], bb["ymax"]
    w = max(1e-6, xmax - xmin)
    h = max(1e-6, ymax - ymin)

    # 패딩(보기 좋게)
    pad = 0.03 * max(w, h)
    xmin -= pad
    ymin -= pad
    w += 2 * pad
    h += 2 * pad

    # SVG는 y가 아래로 증가하므로, y축 뒤집기 위해 transform 사용
    # viewBox: xmin ymin w h 를 쓰고, 내부에서 scale(1,-1) + translate로 뒤집음
    paths = []
    for pts in polylines:
        if len(pts) < 2:
            continue
        d = []
        x0, y0 = pts[0]
        d.append(f"M {x0:.6f} {y0:.6f}")
        for x, y in pts[1:]:
            d.append(f"L {x:.6f} {y:.6f}")
        paths.append(" ".join(d))

    stroke = max(0.05, float(stroke_mm))

    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg"
     viewBox="{xmin:.6f} {ymin:.6f} {w:.6f} {h:.6f}"
     width="100%" height="100%" preserveAspectRatio="xMidYMid meet">
  <g transform="translate(0,{(ymin + h + ymin):.6f}) scale(1,-1)">
    <rect x="{xmin:.6f}" y="{ymin:.6f}" width="{w:.6f}" height="{h:.6f}" fill="white"/>
"""
    for d in paths:
        svg += f'    <path d="{d}" fill="none" stroke="black" stroke-width="{stroke:.6f}" stroke-linejoin="round" stroke-linecap="round"/>\n'

    svg += """  </g>
</svg>
"""
    return svg


# ----------------------------
# 2D generation (silhouette / section)
# ----------------------------
def _project_silhouette_polylines(shape3d: "Part.Shape") -> Tuple[List[List[Tuple[float, float]]], Dict[str, Any]]:
    proj_edges = []

    for e in shape3d.Edges:
        try:
            n = max(24, min(500, int(float(e.Length) / 0.5)))
            pr = e.ParameterRange
            u0, u1 = float(pr[0]), float(pr[1])
            pts = []
            for i in range(n + 1):
                u = u0 + (u1 - u0) * (i / n)
                p = e.valueAt(u)
                pts.append(FreeCAD.Vector(float(p.x), float(p.y), 0.0))

            clean = []
            for v in pts:
                if not clean:
                    clean.append(v)
                else:
                    if (v.sub(clean[-1])).Length > 1e-6:
                        clean.append(v)

            if len(clean) >= 2:
                proj_edges.append(Part.makePolygon(clean))
        except Exception:
            continue

    if not proj_edges:
        raise ConvertError("투영 에지를 생성하지 못했습니다(형상이 비정상일 수 있음).")

    comp2d = Part.Compound(proj_edges)
    wires = _shape_edges_to_wires(comp2d)

    if not wires:
        # 최후 보장: 에지 단위로라도 폴리라인 생성
        wires = []
        for ed in comp2d.Edges:
            try:
                wires.append(Part.Wire([ed]))
            except Exception:
                pass

    polylines = _polylines_from_wires(wires)
    extra = {"wires": len(wires), "edges": len(proj_edges)}
    return polylines, extra


def _section_polylines(shape3d: "Part.Shape", ratio: float) -> Tuple[List[List[Tuple[float, float]]], Dict[str, Any]]:
    zmin, zmax = _bbox_zminmax(shape3d)
    z = zmin + (zmax - zmin) * max(0.0, min(1.0, ratio))

    plane = Part.Plane(FreeCAD.Vector(0, 0, z), FreeCAD.Vector(0, 0, 1))
    sec = shape3d.section(plane.toShape())
    edges = getattr(sec, "Edges", None) if sec is not None else None

    if sec is None or not edges:
        raise ConvertError("요청한 z 단면이 비어 있습니다.")

    wires = _shape_edges_to_wires(sec)

    if not wires:
        wires = []
        for ed in sec.Edges:
            try:
                wires.append(Part.Wire([ed]))
            except Exception:
                pass

    polylines = _polylines_from_wires(wires)
    extra = {"wires": len(wires), "edges": len(sec.Edges)}
    return polylines, extra


# ----------------------------
# Public API
# ----------------------------
def convert_step_to_dxf(step_path: str, out_dxf: str, opts: Optional[ConvertOptions] = None) -> Dict:
    """
    Returns:
      - status: ok/failed
      - out_dxf
      - thickness_mm
      - metrics (loops, perimeter_mm, area_mm2, bbox_mm)
      - svg (if opts.make_svg True)
      - debug (if opts.debug True)
    """
    _require_freecad()
    opts = opts or ConvertOptions()

    if not os.path.exists(step_path):
        raise ConvertError(f"STEP 파일이 없습니다: {step_path}")

    os.makedirs(os.path.dirname(out_dxf) or ".", exist_ok=True)
    doc = FreeCAD.newDocument("ConvertDoc")

    try:
        import Import  # type: ignore
        Import.insert(step_path, doc.Name)
        doc.recompute()

        shapes = []
        for obj in doc.Objects:
            if hasattr(obj, "Shape") and getattr(obj.Shape, "ShapeType", ""):
                if obj.Shape and not obj.Shape.isNull():
                    shapes.append(obj.Shape)

        if not shapes:
            raise ConvertError("STEP에서 유효한 Shape을 찾지 못했습니다.")

        shape = shapes[0]
        if len(shapes) > 1:
            shape = Part.makeCompound(shapes)

        faces = list(shape.Faces)
        if not faces:
            raise ConvertError("Shape에 Face가 없습니다(비정상 모델).")

        clusters = _cluster_normals(faces, ang_tol_deg=3.0)
        if not clusters:
            raise ConvertError("평면 방향 후보를 추출하지 못했습니다.")

        cand = clusters[: max(1, opts.k_face_candidates)]
        z_axis = FreeCAD.Vector(0, 0, 1)

        debug_info = []

        for idx, c in enumerate(cand):
            n = c["normal"]

            rot = _rotation_from_to(n, z_axis)
            placed = shape.copy()
            placed.Placement = FreeCAD.Placement(
                FreeCAD.Vector(0, 0, 0),
                rot,
                FreeCAD.Vector(0, 0, 0),
            )

            zmin, zmax = _bbox_zminmax(placed)
            thickness_mm = float(zmax - zmin)

            if thickness_mm <= 1e-9:
                debug_info.append({"candidate": idx, "reason": "bbox thickness ~0"})
                continue

            eps = 0.02
            areas = []
            for i in range(opts.n_slices):
                t = (i + 0.5) / opts.n_slices
                t = eps + (1 - 2 * eps) * t
                z = zmin + thickness_mm * t
                a = _section_area_at_z(placed, z)
                areas.append(a)

            ok = _areas_are_constant(areas, opts.rel_tol, opts.abs_tol_area)

            dbg = {
                "candidate": idx,
                "area_sum_cluster": c["area_sum"],
                "areas_min": min(areas),
                "areas_max": max(areas),
                "areas_mean": sum(areas) / len(areas),
                "ok": ok,
                "thickness_mm": thickness_mm,
            }

            if not ok:
                debug_info.append(dbg)
                continue

            # 2D 생성
            if opts.silhouette:
                polylines, extra = _project_silhouette_polylines(placed)
                mode = "silhouette_projection_ezdxf"
            else:
                polylines, extra = _section_polylines(placed, opts.section_z_ratio)
                mode = "section_at_ratio_ezdxf"

            if not polylines:
                raise ConvertError("2D 폴리라인 생성 결과가 비어 있습니다.")

            metrics = _metrics_from_polylines(polylines)

            # DXF 저장
            _write_dxf_from_polylines(out_dxf, polylines)

            # SVG 생성(옵션)
            svg = None
            if opts.make_svg:
                svg = _svg_from_polylines(polylines, stroke_mm=opts.svg_stroke_mm)

            dbg.update({"dxf": {"extra": extra, "metrics": metrics}})
            debug_info.append(dbg)

            # 생성 검증
            if (not os.path.exists(out_dxf)) or os.path.getsize(out_dxf) <= 0:
                raise ConvertError(f"변환은 성공으로 판정됐지만 DXF 파일이 생성되지 않았습니다: {out_dxf}")

            return {
                "status": "ok",
                "mode": mode,
                "used_candidate_index": idx,
                "k": opts.k_face_candidates,
                "n_slices": opts.n_slices,
                "rel_tol": opts.rel_tol,
                "thickness_mm": thickness_mm,
                "metrics": metrics,
                "svg": svg,
                "debug": debug_info if opts.debug else None,
                "out_dxf": out_dxf,
            }

        return {
            "status": "failed",
            "reason": "no_candidate_passed_section_constancy",
            "k": opts.k_face_candidates,
            "n_slices": opts.n_slices,
            "rel_tol": opts.rel_tol,
            "debug": debug_info if opts.debug else None,
        }

    finally:
        try:
            FreeCAD.closeDocument(doc.Name)
        except Exception:
            pass
