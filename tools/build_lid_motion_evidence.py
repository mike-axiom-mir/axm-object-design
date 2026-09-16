from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any

SOURCE_SCHEMA = "axm.object-hard-surface/v0.1"
RIG_SCHEMA = "axm.object-articulation-plan/v0.1"
CLIP_SCHEMA = "axm.object-motion-clip/v0.1"
EVIDENCE_SCHEMA = "axm.object-motion-evidence/v0.1"
EPS = 1e-12
RIGIDITY_TOLERANCE_M = 1e-9


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def smoothstep(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return t * t * (3.0 - 2.0 * t)


def rotate_x(point: tuple[float, float, float], origin: tuple[float, float, float], angle_deg: float) -> tuple[float, float, float]:
    x, y, z = point
    ox, oy, oz = origin
    dy, dz = y - oy, z - oz
    a = math.radians(angle_deg)
    c, s = math.cos(a), math.sin(a)
    return (x, oy + dy * c - dz * s, oz + dy * s + dz * c)


def box_corners(center: tuple[float, float, float], size: tuple[float, float, float]) -> list[tuple[float, float, float]]:
    cx, cy, cz = center
    sx, sy, sz = size
    return [
        (cx + dx * sx / 2.0, cy + dy * sy / 2.0, cz + dz * sz / 2.0)
        for dx in (-1.0, 1.0)
        for dy in (-1.0, 1.0)
        for dz in (-1.0, 1.0)
    ]


def pairwise_rigidity_drift(before: list[tuple[float, float, float]], after: list[tuple[float, float, float]]) -> float:
    drift = 0.0
    for i in range(len(before)):
        for j in range(i + 1, len(before)):
            drift = max(drift, abs(math.dist(before[i], before[j]) - math.dist(after[i], after[j])))
    return drift


def max_vertex_distance(a: list[tuple[float, float, float]], b: list[tuple[float, float, float]]) -> float:
    return max(math.dist(x, y) for x, y in zip(a, b))


def angle_at(clip: dict[str, Any], time_s: float) -> float:
    phases = clip["phases"]
    for idx, phase in enumerate(phases):
        start = float(phase["start_s"])
        end = float(phase["end_s"])
        if time_s + EPS < start:
            continue
        if time_s <= end + EPS or idx == len(phases) - 1:
            a0 = float(phase["start_angle_deg"])
            a1 = float(phase["end_angle_deg"])
            if phase["easing"] == "constant":
                return a0
            if phase["easing"] != "smoothstep":
                raise ValueError(f"unsupported easing: {phase['easing']}")
            u = 0.0 if end == start else (time_s - start) / (end - start)
            return a0 + (a1 - a0) * smoothstep(u)
    raise ValueError(f"time {time_s} is outside clip phases")


def validate(source: dict[str, Any], source_sha: str, rig: dict[str, Any], clip: dict[str, Any]) -> None:
    if source.get("schema") != SOURCE_SCHEMA:
        raise ValueError("unexpected source schema")
    if rig.get("schema") != RIG_SCHEMA:
        raise ValueError("unexpected rig schema")
    if clip.get("schema") != CLIP_SCHEMA:
        raise ValueError("unexpected clip schema")
    asset_id = source.get("asset_id")
    if rig.get("asset_id") != asset_id or clip.get("asset_id") != asset_id:
        raise ValueError("asset identity drift")
    if rig.get("source_sha256") != source_sha or clip.get("source_sha256") != source_sha:
        raise ValueError("source digest drift")
    dependency = clip.get("rig_dependency", {})
    if dependency.get("plan_digest") != digest(rig):
        raise ValueError("rig plan digest drift")
    joint = rig.get("joint", {})
    if joint.get("id") != clip.get("joint_id") or joint.get("id") != "rear-lid-hinge-001":
        raise ValueError("joint identity drift")
    if joint.get("moving_component") != "lid_shell" or joint.get("fixed_component") != "body_shell":
        raise ValueError("unexpected articulation component identity")
    if joint.get("opening_rotation_sign") != -1:
        raise ValueError("unexpected opening rotation sign")
    if source.get("hinge", {}).get("axis") != [1, 0, 0]:
        raise ValueError("motion proof requires exact +X source hinge")
    limit = joint.get("angle_limit_deg")
    if limit != [0, 110]:
        raise ValueError("rig envelope drift")
    if float(clip.get("hard_limit_max_deg")) != float(limit[1]):
        raise ValueError("clip hard limit must equal rig hard limit")
    peak = float(clip.get("peak_open_angle_deg"))
    guard = float(clip.get("hard_limit_guard_deg"))
    if peak <= float(limit[0]) or peak >= float(limit[1]):
        raise ValueError("clip peak must remain strictly inside articulation envelope")
    if abs((float(limit[1]) - peak) - guard) > EPS or guard <= 0.0:
        raise ValueError("clip limit guard must remain explicit and positive")
    rate = clip.get("sample_rate_hz")
    duration = float(clip.get("duration_s"))
    if not isinstance(rate, int) or rate <= 0 or duration <= 0.0:
        raise ValueError("invalid sample timing")
    if abs(duration * rate - round(duration * rate)) > EPS:
        raise ValueError("duration must land exactly on the authored sample grid")
    phases = clip.get("phases")
    if not isinstance(phases, list) or len(phases) != 3:
        raise ValueError("v0.1 clip requires open/hold/close phases")
    expected_ids = ["open", "hold", "close"]
    previous_end = 0.0
    previous_angle = 0.0
    for idx, (phase, expected_id) in enumerate(zip(phases, expected_ids)):
        if phase.get("id") != expected_id:
            raise ValueError("phase identity drift")
        start = float(phase["start_s"])
        end = float(phase["end_s"])
        start_angle = float(phase["start_angle_deg"])
        end_angle = float(phase["end_angle_deg"])
        if abs(start - previous_end) > EPS or abs(start_angle - previous_angle) > EPS:
            raise ValueError("phase continuity drift")
        if end <= start:
            raise ValueError("phase duration must be positive")
        previous_end, previous_angle = end, end_angle
        if idx in (0, 2) and phase.get("easing") != "smoothstep":
            raise ValueError("open/close phases require smoothstep")
        if idx == 1 and phase.get("easing") != "constant":
            raise ValueError("hold phase requires constant easing")
    if abs(previous_end - duration) > EPS or abs(previous_angle) > EPS:
        raise ValueError("clip must end exactly neutral at duration")
    if float(phases[0]["end_angle_deg"]) != peak or float(phases[1]["start_angle_deg"]) != peak or float(phases[1]["end_angle_deg"]) != peak:
        raise ValueError("peak/hold phase drift")
    if clip.get("repeat_policy") != "OMIT_DUPLICATE_ENDPOINT_ON_REPEAT":
        raise ValueError("unexpected repeat policy")


def neutral_geometry(source: dict[str, Any]) -> tuple[list[tuple[float, float, float]], list[tuple[float, float, float]], tuple[float, float, float]]:
    d = source["dimensions_m"]
    width = float(d["width"])
    depth = float(d["depth"])
    body_h = float(d["body_height"])
    lid_h = float(d["lid_height"])
    split = float(d["split_gap"])
    body = box_corners((0.0, 0.0, body_h / 2.0), (width, depth, body_h))
    lid_center_z = body_h + split + lid_h / 2.0
    lid = box_corners((0.0, 0.0, lid_center_z), (width, depth, lid_h))
    hinge = source["hinge"]
    origin = (0.0, depth / 2.0 + float(hinge["offset_y"]), body_h + float(hinge["offset_z"]))
    return body, lid, origin


def build_evidence(source: dict[str, Any], source_sha: str, rig: dict[str, Any], clip: dict[str, Any], exact_head: str) -> dict[str, Any]:
    validate(source, source_sha, rig, clip)
    body, neutral_lid, hinge_origin = neutral_geometry(source)
    rate = int(clip["sample_rate_hz"])
    duration = float(clip["duration_s"])
    sample_count = int(round(duration * rate)) + 1
    sign = int(rig["joint"]["opening_rotation_sign"])
    body_digest = digest([[round(v, 12) for v in p] for p in body])
    samples = []
    max_rigidity = 0.0
    max_angle_step = 0.0
    max_vertex_step = 0.0
    previous = None
    for index in range(sample_count):
        time_s = index / rate
        angle = angle_at(clip, time_s)
        math_angle = sign * angle
        lid = [rotate_x(p, hinge_origin, math_angle) for p in neutral_lid]
        rigidity = pairwise_rigidity_drift(neutral_lid, lid)
        max_rigidity = max(max_rigidity, rigidity)
        row = {
            "index": index,
            "time_s": round(time_s, 6),
            "open_angle_deg": round(angle, 12),
            "mathematical_rotation_deg": round(math_angle, 12),
            "lid_corner_digest": digest([[round(v, 12) for v in p] for p in lid]),
            "lid_corners_m": [[round(v, 12) for v in p] for p in lid],
            "lid_pairwise_rigidity_max_drift_m": round(rigidity, 15),
            "body_corner_digest": body_digest,
        }
        if previous is not None:
            max_angle_step = max(max_angle_step, abs(angle - previous["angle"]))
            max_vertex_step = max(max_vertex_step, max_vertex_distance(lid, previous["lid"]))
        previous = {"angle": angle, "lid": lid}
        samples.append(row)

    last_visible = samples[-2]
    endpoint = samples[-1]
    first = samples[0]
    last_vertices = [tuple(p) for p in last_visible["lid_corners_m"]]
    endpoint_vertices = [tuple(p) for p in endpoint["lid_corners_m"]]
    first_vertices = [tuple(p) for p in first["lid_corners_m"]]
    wrap_step = max_vertex_distance(last_vertices, first_vertices)
    authored_final_step = max_vertex_distance(last_vertices, endpoint_vertices)
    endpoint_closure = max_vertex_distance(endpoint_vertices, first_vertices)

    phase_rows = {}
    for name, time_s in (("start", 0.0), ("open_end", 0.75), ("hold_mid", 1.0), ("hold_end", 1.25), ("end", 2.0)):
        idx = int(round(time_s * rate))
        phase_rows[name] = {"index": idx, "time_s": time_s, "open_angle_deg": samples[idx]["open_angle_deg"]}

    all_angles = [float(row["open_angle_deg"]) for row in samples]
    result = "PASS_BOUNDED_LID_MOTION_CLIP"
    if max(all_angles) > float(clip["peak_open_angle_deg"]) + EPS or min(all_angles) < -EPS:
        result = "FAIL"
    if max_rigidity > RIGIDITY_TOLERANCE_M or endpoint_closure > RIGIDITY_TOLERANCE_M:
        result = "FAIL"
    if abs(wrap_step - authored_final_step) > RIGIDITY_TOLERANCE_M:
        result = "FAIL"
    if phase_rows["open_end"]["open_angle_deg"] != float(clip["peak_open_angle_deg"]):
        result = "FAIL"
    if phase_rows["hold_mid"]["open_angle_deg"] != float(clip["peak_open_angle_deg"]):
        result = "FAIL"
    if phase_rows["hold_end"]["open_angle_deg"] != float(clip["peak_open_angle_deg"]):
        result = "FAIL"

    return {
        "schema": EVIDENCE_SCHEMA,
        "result": result,
        "exact_receiving_head": exact_head,
        "asset_id": source["asset_id"],
        "source_sha256": source_sha,
        "clip_id": clip["clip_id"],
        "clip_digest": digest(clip),
        "rig_dependency": clip["rig_dependency"],
        "observed_rig_plan_digest": digest(rig),
        "joint_id": clip["joint_id"],
        "hinge_origin_m": [round(v, 12) for v in hinge_origin],
        "sample_rate_hz": rate,
        "duration_s": duration,
        "endpoint_inclusive_sample_count": sample_count,
        "repeated_visible_sample_count": sample_count - 1,
        "peak_open_angle_deg": float(clip["peak_open_angle_deg"]),
        "hard_limit_max_deg": float(clip["hard_limit_max_deg"]),
        "hard_limit_guard_deg": float(clip["hard_limit_guard_deg"]),
        "phase_landmarks": phase_rows,
        "max_adjacent_angle_step_deg": round(max_angle_step, 12),
        "max_adjacent_lid_vertex_step_m": round(max_vertex_step, 12),
        "max_lid_pairwise_rigidity_drift_m": round(max_rigidity, 15),
        "fixed_body_digest": body_digest,
        "loop_endpoint_closure_max_vertex_m": round(endpoint_closure, 15),
        "last_visible_to_repeat_wrap_max_vertex_m": round(wrap_step, 12),
        "last_visible_to_authored_endpoint_max_vertex_m": round(authored_final_step, 12),
        "repeat_wrap_matches_authored_final_step": abs(wrap_step - authored_final_step) <= RIGIDITY_TOLERANCE_M,
        "motion_truth_label": clip["motion_truth_label"],
        "samples": samples,
        "non_claims": [
            "no target-engine playback or controller acceptance",
            "no interaction, input, gameplay or state-machine acceptance",
            "no collision-engine or attachment dynamics acceptance",
            "no final timing, weight, style or Art Direction acceptance",
            "no target-device runtime or performance acceptance"
        ]
    }


def write_svg(path: Path, source: dict[str, Any], rig: dict[str, Any], clip: dict[str, Any]) -> None:
    _, neutral_lid, hinge = neutral_geometry(source)
    d = source["dimensions_m"]
    depth = float(d["depth"])
    body_h = float(d["body_height"])
    sign = int(rig["joint"]["opening_rotation_sign"])
    times = [0.0, 0.375, 0.75, 1.0, 1.25, 1.625, 2.0]
    panel_w, panel_h = 220, 240
    total_w = panel_w * len(times)
    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" height="{panel_h}" viewBox="0 0 {total_w} {panel_h}">',
             f'<rect width="{total_w}" height="{panel_h}" fill="#ffffff"/>',
             '<text x="12" y="18" font-family="monospace" font-size="12">lid-open-hold-close-001 — deterministic side-view motion evidence; not final visual acceptance</text>']
    def map_point(y: float, z: float, ox: float) -> tuple[float, float]:
        return ox + 110 + y * 300.0, 205 - z * 330.0
    body_yz = [(-depth/2,0.0),(depth/2,0.0),(depth/2,body_h),(-depth/2,body_h)]
    for pidx, t in enumerate(times):
        ox = pidx * panel_w
        angle = angle_at(clip, t)
        lid = [rotate_x(p, hinge, sign * angle) for p in neutral_lid]
        # unique side rectangle corners from one X side are sufficient for motion presentation.
        yz = sorted({(round(p[1], 12), round(p[2], 12)) for p in lid})
        cy = sum(p[0] for p in yz) / len(yz)
        cz = sum(p[1] for p in yz) / len(yz)
        yz.sort(key=lambda p: math.atan2(p[1]-cz, p[0]-cy))
        body_pts = ' '.join(f'{map_point(y,z,ox)[0]:.2f},{map_point(y,z,ox)[1]:.2f}' for y,z in body_yz)
        lid_pts = ' '.join(f'{map_point(y,z,ox)[0]:.2f},{map_point(y,z,ox)[1]:.2f}' for y,z in yz)
        hy,hz = hinge[1],hinge[2]
        hx,hy_px = map_point(hy,hz,ox)
        lines.append(f'<polygon points="{body_pts}" fill="none" stroke="#333" stroke-width="2"/>')
        lines.append(f'<polygon points="{lid_pts}" fill="none" stroke="#111" stroke-width="3"/>')
        lines.append(f'<circle cx="{hx:.2f}" cy="{hy_px:.2f}" r="4" fill="#111"/>')
        lines.append(f'<text x="{ox+10}" y="224" font-family="monospace" font-size="11">t={t:.3f}s  open={angle:.3f}deg</text>')
        if pidx < len(times)-1:
            lines.append(f'<line x1="{ox+panel_w-1}" y1="28" x2="{ox+panel_w-1}" y2="230" stroke="#ddd"/>')
    lines.append('</svg>')
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--rig", required=True)
    parser.add_argument("--clip", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--exact-head", default=os.environ.get("EXACT_HEAD_SHA", "UNKNOWN"))
    args = parser.parse_args()
    source_path = Path(args.source)
    source = load_json(source_path)
    rig = load_json(Path(args.rig))
    clip = load_json(Path(args.clip))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    evidence = build_evidence(source, file_sha256(source_path), rig, clip, args.exact_head)
    if evidence["result"] != "PASS_BOUNDED_LID_MOTION_CLIP":
        raise SystemExit(f"motion evidence failed: {evidence['result']}")
    (out / "lid-motion-evidence.json").write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "exact-head.txt").write_text(args.exact_head + "\n", encoding="utf-8")
    write_svg(out / "lid-motion-pose-strip.svg", source, rig, clip)
    print(json.dumps({k: evidence[k] for k in (
        "result", "clip_id", "endpoint_inclusive_sample_count", "repeated_visible_sample_count",
        "peak_open_angle_deg", "hard_limit_guard_deg", "max_adjacent_angle_step_deg",
        "max_adjacent_lid_vertex_step_m", "max_lid_pairwise_rigidity_drift_m",
        "loop_endpoint_closure_max_vertex_m", "repeat_wrap_matches_authored_final_step"
    )}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
