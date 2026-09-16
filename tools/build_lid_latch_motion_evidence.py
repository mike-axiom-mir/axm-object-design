from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import build_modular_case
import build_lid_motion_evidence as lid_motion

SEQUENCE_SCHEMA = "axm.object-lid-latch-motion-sequence/v0.1"
EVIDENCE_SCHEMA = "axm.object-lid-latch-motion-evidence/v0.1"
RESULT = "PASS_ORDERED_LATCH_RELEASE_LID_CLIP_REENGAGE_SEQUENCE"
EPS = 1e-12
RIGIDITY_TOLERANCE_M = 1e-9


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _component_map(source: dict[str, Any]) -> dict[str, dict[str, Any]]:
    built = build_modular_case.build(source)
    return {row["name"]: row for row in built["components"]}


def _box_corners(component: dict[str, Any]) -> list[tuple[float, float, float]]:
    if component.get("kind") != "box":
        raise AssertionError(f"component is not a box: {component.get('name')}")
    return lid_motion.box_corners(tuple(component["center_m"]), tuple(component["size_m"]))


def _smoothstep(value: float) -> float:
    value = min(1.0, max(0.0, value))
    return value * value * (3.0 - 2.0 * value)


def _pairwise_distances(points: list[tuple[float, float, float]]) -> list[float]:
    return [math.dist(a, b) for i, a in enumerate(points) for b in points[i + 1 :]]


def _max_pairwise_drift(before: list[tuple[float, float, float]], after: list[tuple[float, float, float]]) -> float:
    a = _pairwise_distances(before)
    b = _pairwise_distances(after)
    return max((abs(x - y) for x, y in zip(a, b)), default=0.0)


def _max_vertex_distance(a: list[tuple[float, float, float]], b: list[tuple[float, float, float]]) -> float:
    return max((math.dist(x, y) for x, y in zip(a, b)), default=0.0)


def _canonical_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _validate_dependencies(
    source: dict[str, Any],
    source_sha: str,
    sequence: dict[str, Any],
    motion: dict[str, Any],
    ownership: dict[str, Any],
    ownership_sha: str,
    rig_receipt: dict[str, Any],
    rig_head: str,
    rig_plan_sha: str,
) -> None:
    if sequence.get("schema") != SEQUENCE_SCHEMA:
        raise AssertionError("unsupported sequence schema")
    if sequence.get("asset_id") != source.get("asset_id"):
        raise AssertionError("sequence asset identity drift")
    if sequence.get("host_source_sha256") != source_sha:
        raise AssertionError("sequence host source identity drift")
    if motion.get("result") != "PASS_BOUNDED_LID_MOTION_CLIP":
        raise AssertionError("base lid motion prerequisite did not pass")
    if motion.get("asset_id") != source.get("asset_id") or motion.get("source_sha256") != source_sha:
        raise AssertionError("base lid motion source identity drift")

    base = sequence.get("base_lid_clip", {})
    if motion.get("clip_id") != base.get("clip_id") or motion.get("clip_digest") != base.get("clip_digest"):
        raise AssertionError("base lid clip identity drift")
    if float(motion.get("duration_s")) != float(base.get("duration_s")):
        raise AssertionError("base lid clip duration drift")
    if int(motion.get("sample_rate_hz")) != int(sequence.get("sample_rate_hz")):
        raise AssertionError("base lid clip sample-rate drift")
    if int(motion.get("endpoint_inclusive_sample_count")) != 81 or len(motion.get("samples", [])) != 81:
        raise AssertionError("base lid clip sample-count drift")

    ownership_dep = sequence.get("ownership_dependency", {})
    if ownership_dep.get("contract_sha256") != ownership_sha:
        raise AssertionError("Hard-Surface ownership contract digest drift")
    if ownership.get("contract_id") != "front-latch-ownership-001":
        raise AssertionError("unexpected Hard-Surface ownership contract")
    if ownership.get("host_source_sha256") != source_sha:
        raise AssertionError("Hard-Surface ownership host identity drift")

    rig_dep = sequence.get("latch_rig_dependency", {})
    if rig_dep.get("exact_head") != rig_head:
        raise AssertionError("Rigging donor head drift")
    if rig_dep.get("plan_sha256") != rig_plan_sha:
        raise AssertionError("Rigging plan digest drift")
    if rig_receipt.get("result") != rig_dep.get("required_result"):
        raise AssertionError("Rigging articulation prerequisite did not pass")
    if rig_receipt.get("host_source_sha256") != source_sha:
        raise AssertionError("Rigging receipt host identity drift")
    if rig_receipt.get("ownership_contract_sha256") != ownership_sha:
        raise AssertionError("Rigging receipt ownership identity drift")
    if rig_receipt.get("articulation_plan_sha256") != rig_plan_sha:
        raise AssertionError("Rigging receipt plan identity drift")
    if rig_receipt.get("ownership_donor_head") != ownership_dep.get("exact_head"):
        raise AssertionError("Rigging receipt ownership donor drift")

    if int(sequence.get("sample_rate_hz")) != 40 or float(sequence.get("duration_s")) != 2.5:
        raise AssertionError("v0.1 sequence timing drift")
    if float(base.get("start_offset_s")) != 0.25 or base.get("policy") != "COPY_EXACT_AUTHORED_SAMPLES_UNRETIMED":
        raise AssertionError("base clip placement policy drift")
    if float(rig_dep.get("required_terminal_angle_deg")) != 50.0:
        raise AssertionError("v0.1 terminal latch angle drift")
    phases = sequence.get("phases", [])
    if [row.get("id") for row in phases] != ["release_latches", "play_exact_lid_clip", "reengage_latches"]:
        raise AssertionError("sequence phase identity drift")
    if sequence.get("repeat_policy") != "OMIT_DUPLICATE_ENDPOINT_ON_REPEAT":
        raise AssertionError("sequence repeat policy drift")


def build_evidence(
    source: dict[str, Any],
    source_sha: str,
    sequence: dict[str, Any],
    motion: dict[str, Any],
    ownership: dict[str, Any],
    ownership_sha: str,
    rig_receipt: dict[str, Any],
    rig_head: str,
    rig_plan_sha: str,
    exact_head: str,
) -> dict[str, Any]:
    _validate_dependencies(source, source_sha, sequence, motion, ownership, ownership_sha, rig_receipt, rig_head, rig_plan_sha)

    components = _component_map(source)
    rig_rows = {row["station_id"]: row for row in rig_receipt["station_results"]}
    stations = ownership.get("stations", [])
    if len(stations) != 2 or set(rig_rows) != {row["id"] for row in stations}:
        raise AssertionError("bilateral latch station identity drift")

    for station in stations:
        if station.get("keeper_owner_component") != "lid_shell":
            raise AssertionError("keeper must remain lid-owned")
        if station.get("lever_owner_component") != "front_service_panel":
            raise AssertionError("lever must remain service-panel-owned")
        if station["keeper_component"] not in components or station["lever_component"] not in components:
            raise AssertionError("latch component missing from current source build")

    rate = int(sequence["sample_rate_hz"])
    total_count = int(round(float(sequence["duration_s"]) * rate)) + 1
    offset_index = int(round(float(sequence["base_lid_clip"]["start_offset_s"]) * rate))
    if total_count != 101 or offset_index != 10:
        raise AssertionError("v0.1 sample-grid drift")

    threshold = float(rig_receipt["continuous_keeper_z_separation_threshold_deg"])
    terminal_angle = float(sequence["latch_rig_dependency"]["required_terminal_angle_deg"])
    if not (0.0 < threshold < terminal_angle):
        raise AssertionError("Rigging separation threshold no longer lies inside terminal latch angle")

    neutral_lid = [tuple(p) for p in motion["samples"][0]["lid_corners_m"]]
    hinge = tuple(float(v) for v in motion["hinge_origin_m"])
    station_state = {}
    for station in stations:
        keeper = components[station["keeper_component"]]
        lever = components[station["lever_component"]]
        rig_row = rig_rows[station["id"]]
        pivot = tuple(float(v) for v in rig_row["pivot_m"])
        if abs(float(station["source_x_m"]) - pivot[0]) > EPS:
            raise AssertionError("Rigging pivot left exact latch station")
        station_state[station["id"]] = {
            "keeper_neutral": _box_corners(keeper),
            "lever_neutral": _box_corners(lever),
            "pivot": pivot,
            "keeper_component": station["keeper_component"],
            "lever_component": station["lever_component"],
        }

    samples = []
    max_lever_rigidity = 0.0
    max_lid_keeper_rigidity = 0.0
    nonzero_lid_samples_without_terminal_latch = 0
    below_threshold_samples_with_nonzero_lid = 0
    exact_base_sample_matches = 0
    station_start_geometry = {}
    station_last_visible_geometry = {}
    station_endpoint_geometry = {}

    for index in range(total_count):
        time_s = index / rate
        if index < offset_index:
            u = index / offset_index
            latch_angle = terminal_angle * _smoothstep(u)
            base_index = 0
        elif index <= offset_index + 80:
            latch_angle = terminal_angle
            base_index = index - offset_index
            exact_base_sample_matches += 1
        else:
            u = (index - (offset_index + 80)) / (total_count - 1 - (offset_index + 80))
            latch_angle = terminal_angle * (1.0 - _smoothstep(u))
            base_index = 80

        base_row = motion["samples"][base_index]
        lid_angle = float(base_row["open_angle_deg"])
        lid_math_angle = float(base_row["mathematical_rotation_deg"])
        lid_corners = [tuple(p) for p in base_row["lid_corners_m"]]

        if lid_angle > EPS and abs(latch_angle - terminal_angle) > EPS:
            nonzero_lid_samples_without_terminal_latch += 1
        if latch_angle + EPS < threshold and lid_angle > EPS:
            below_threshold_samples_with_nonzero_lid += 1

        station_rows = []
        for station in stations:
            state = station_state[station["id"]]
            keeper = [lid_motion.rotate_x(p, hinge, lid_math_angle) for p in state["keeper_neutral"]]
            lever = [lid_motion.rotate_x(p, state["pivot"], latch_angle) for p in state["lever_neutral"]]
            lever_rigidity = _max_pairwise_drift(state["lever_neutral"], lever)
            lid_keeper_rigidity = _max_pairwise_drift(
                neutral_lid + state["keeper_neutral"],
                lid_corners + keeper,
            )
            max_lever_rigidity = max(max_lever_rigidity, lever_rigidity)
            max_lid_keeper_rigidity = max(max_lid_keeper_rigidity, lid_keeper_rigidity)
            row = {
                "station_id": station["id"],
                "keeper_component": state["keeper_component"],
                "lever_component": state["lever_component"],
                "keeper_digest": _canonical_digest([[round(v, 12) for v in p] for p in keeper]),
                "lever_digest": _canonical_digest([[round(v, 12) for v in p] for p in lever]),
                "lever_rigidity_drift_m": round(lever_rigidity, 15),
                "lid_keeper_rigidity_drift_m": round(lid_keeper_rigidity, 15),
            }
            station_rows.append(row)
            geometry = {"keeper": keeper, "lever": lever}
            if index == 0:
                station_start_geometry[station["id"]] = geometry
            if index == total_count - 2:
                station_last_visible_geometry[station["id"]] = geometry
            if index == total_count - 1:
                station_endpoint_geometry[station["id"]] = geometry

        samples.append(
            {
                "index": index,
                "time_s": round(time_s, 6),
                "base_lid_sample_index": base_index,
                "lid_open_angle_deg": round(lid_angle, 12),
                "lid_mathematical_rotation_deg": round(lid_math_angle, 12),
                "latch_lever_angle_deg": round(latch_angle, 12),
                "lid_corner_digest": base_row["lid_corner_digest"],
                "stations": station_rows,
            }
        )

    if exact_base_sample_matches != 81:
        raise AssertionError("exact base lid clip was not copied as all 81 authored samples")
    if nonzero_lid_samples_without_terminal_latch or below_threshold_samples_with_nonzero_lid:
        raise AssertionError("latch/lid motion ordering violated exact Rigging review threshold")
    if max_lever_rigidity > RIGIDITY_TOLERANCE_M or max_lid_keeper_rigidity > RIGIDITY_TOLERANCE_M:
        raise AssertionError("rigid component relation drift exceeded tolerance")

    endpoint_closure = 0.0
    wrap_step = 0.0
    authored_final_step = 0.0
    for station in stations:
        sid = station["id"]
        for key in ("keeper", "lever"):
            start = station_start_geometry[sid][key]
            last = station_last_visible_geometry[sid][key]
            end = station_endpoint_geometry[sid][key]
            endpoint_closure = max(endpoint_closure, _max_vertex_distance(start, end))
            wrap_step = max(wrap_step, _max_vertex_distance(last, start))
            authored_final_step = max(authored_final_step, _max_vertex_distance(last, end))
    if endpoint_closure > RIGIDITY_TOLERANCE_M or abs(wrap_step - authored_final_step) > RIGIDITY_TOLERANCE_M:
        raise AssertionError("composed repeat seam drift")

    sample_signature = [
        [row["index"], row["base_lid_sample_index"], row["lid_open_angle_deg"], row["latch_lever_angle_deg"], row["lid_corner_digest"],
         [[s["station_id"], s["keeper_digest"], s["lever_digest"]] for s in row["stations"]]]
        for row in samples
    ]

    return {
        "schema": EVIDENCE_SCHEMA,
        "result": RESULT,
        "exact_receiving_head": exact_head,
        "asset_id": source["asset_id"],
        "host_source_sha256": source_sha,
        "sequence_id": sequence["sequence_id"],
        "sequence_digest": _canonical_digest(sequence),
        "base_lid_clip_id": motion["clip_id"],
        "base_lid_clip_digest": motion["clip_digest"],
        "base_lid_clip_exact_sample_count": 81,
        "base_lid_clip_retimed_sample_count": 0,
        "base_lid_clip_retargeted_sample_count": 0,
        "latch_rig_dependency_head": rig_head,
        "latch_rig_plan_sha256": rig_plan_sha,
        "ownership_dependency_head": sequence["ownership_dependency"]["exact_head"],
        "ownership_contract_sha256": ownership_sha,
        "rig_continuous_keeper_z_separation_threshold_deg": threshold,
        "rig_terminal_keeper_z_separation_m": float(rig_receipt["terminal_keeper_z_separation_m"]),
        "sample_rate_hz": rate,
        "duration_s": float(sequence["duration_s"]),
        "endpoint_inclusive_sample_count": total_count,
        "repeated_visible_sample_count": total_count - 1,
        "phase_landmarks": {
            "closed_start": {"index": 0, "time_s": 0.0, "lid_deg": 0.0, "latch_deg": 0.0},
            "release_complete": {"index": 10, "time_s": 0.25, "lid_deg": 0.0, "latch_deg": 50.0},
            "lid_peak_start": {"index": 40, "time_s": 1.0, "lid_deg": 100.0, "latch_deg": 50.0},
            "lid_peak_mid": {"index": 50, "time_s": 1.25, "lid_deg": 100.0, "latch_deg": 50.0},
            "lid_peak_end": {"index": 60, "time_s": 1.5, "lid_deg": 100.0, "latch_deg": 50.0},
            "lid_closed_before_reengage": {"index": 90, "time_s": 2.25, "lid_deg": 0.0, "latch_deg": 50.0},
            "closed_end": {"index": 100, "time_s": 2.5, "lid_deg": 0.0, "latch_deg": 0.0}
        },
        "observations": {
            "exact_base_lid_samples_copied_unretimed": exact_base_sample_matches,
            "nonzero_lid_samples_without_terminal_latch": nonzero_lid_samples_without_terminal_latch,
            "below_rig_separation_threshold_samples_with_nonzero_lid": below_threshold_samples_with_nonzero_lid,
            "maximum_lever_rigidity_drift_m": round(max_lever_rigidity, 15),
            "maximum_lid_keeper_rigidity_drift_m": round(max_lid_keeper_rigidity, 15),
            "endpoint_closure_max_vertex_m": round(endpoint_closure, 15),
            "last_visible_to_repeat_wrap_max_vertex_m": round(wrap_step, 12),
            "last_visible_to_authored_endpoint_max_vertex_m": round(authored_final_step, 12),
            "repeat_wrap_matches_authored_final_step": abs(wrap_step - authored_final_step) <= RIGIDITY_TOLERANCE_M,
        },
        "sequence_geometry_digest": _canonical_digest(sample_signature),
        "samples": samples,
        "truth_boundary": sequence["truth_boundary"],
        "non_claims": [
            "no physical latch hook, retention or release-mechanism acceptance",
            "no full-component collision or physics acceptance",
            "no target-engine playback, wall-clock pacing or interpolation acceptance",
            "no AnimationPlayer, controller, state-machine or gameplay acceptance",
            "no final timing, weight, personality or Art Direction acceptance",
            "no runtime-performance, CANON, production-readiness or mastery claim"
        ]
    }


def _side_rect(center_y: float, center_z: float, size_y: float, size_z: float, x: float = 0.0) -> list[tuple[float, float, float]]:
    return [
        (x, center_y - size_y / 2.0, center_z - size_z / 2.0),
        (x, center_y + size_y / 2.0, center_z - size_z / 2.0),
        (x, center_y + size_y / 2.0, center_z + size_z / 2.0),
        (x, center_y - size_y / 2.0, center_z + size_z / 2.0),
    ]


def write_svg(path: Path, source: dict[str, Any], motion: dict[str, Any], ownership: dict[str, Any], rig_receipt: dict[str, Any], evidence: dict[str, Any]) -> None:
    components = _component_map(source)
    station = ownership["stations"][0]
    rig_row = next(row for row in rig_receipt["station_results"] if row["station_id"] == station["id"])
    keeper = components[station["keeper_component"]]
    lever = components[station["lever_component"]]
    pivot = tuple(float(v) for v in rig_row["pivot_m"])
    hinge = tuple(float(v) for v in motion["hinge_origin_m"])
    d = source["dimensions_m"]
    body_h = float(d["body_height"])
    depth = float(d["depth"])
    lid_h = float(d["lid_height"])
    split = float(d["split_gap"])
    panel = components["front_service_panel"]

    selected = [0, 5, 10, 25, 40, 50, 90, 95, 100]
    pw, ph = 230, 300
    width, height = pw * len(selected), ph + 62
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="white"/>',
        '<text x="14" y="348" font-family="monospace" font-size="12">Exact source-space Y/Z proof; representative left station. Structural choreography only — not physical latch/controller/gameplay acceptance.</text>'
    ]

    for panel_index, sample_index in enumerate(selected):
        row = evidence["samples"][sample_index]
        x0 = panel_index * pw
        scale = 520.0
        oy, oz = -0.33, 0.16

        def sy(y: float) -> float:
            return x0 + 24 + (y - oy) * scale

        def sz(z: float) -> float:
            return 276 - (z - oz) * scale

        def poly(points: list[tuple[float, float, float]], stroke: str, width_px: int = 2) -> None:
            pts = " ".join(f"{sy(p[1]):.2f},{sz(p[2]):.2f}" for p in points)
            lines.append(f'<polygon points="{pts}" fill="none" stroke="{stroke}" stroke-width="{width_px}"/>')

        body = _side_rect(0.0, body_h / 2.0, depth, body_h)
        poly(body, "#999", 1)
        pc = panel["center_m"]; ps = panel["size_m"]
        poly(_side_rect(float(pc[1]), float(pc[2]), float(ps[1]), float(ps[2])), "#777", 1)

        neutral_lid = _side_rect(0.0, body_h + split + lid_h / 2.0, depth, lid_h)
        moved_lid = [lid_motion.rotate_x(p, hinge, float(row["lid_mathematical_rotation_deg"])) for p in neutral_lid]
        poly(moved_lid, "#111", 2)

        kc = keeper["center_m"]; ks = keeper["size_m"]
        neutral_keeper = _side_rect(float(kc[1]), float(kc[2]), float(ks[1]), float(ks[2]), float(kc[0]))
        moved_keeper = [lid_motion.rotate_x(p, hinge, float(row["lid_mathematical_rotation_deg"])) for p in neutral_keeper]
        poly(moved_keeper, "#333", 2)

        lc = lever["center_m"]; ls = lever["size_m"]
        neutral_lever = _side_rect(float(lc[1]), float(lc[2]), float(ls[1]), float(ls[2]), float(lc[0]))
        moved_lever = [lid_motion.rotate_x(p, pivot, float(row["latch_lever_angle_deg"])) for p in neutral_lever]
        poly(moved_lever, "#666", 2)
        lines.append(f'<circle cx="{sy(pivot[1]):.2f}" cy="{sz(pivot[2]):.2f}" r="3" fill="#111"/>')
        lines.append(f'<text x="{x0+8}" y="18" font-family="monospace" font-size="12">t={row["time_s"]:.3f}s</text>')
        lines.append(f'<text x="{x0+8}" y="33" font-family="monospace" font-size="11">lid {row["lid_open_angle_deg"]:.1f} / latch {row["latch_lever_angle_deg"]:.1f} deg</text>')

    lines.append('</svg>')
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--sequence", type=Path, required=True)
    p.add_argument("--motion-evidence", type=Path, required=True)
    p.add_argument("--ownership", type=Path, required=True)
    p.add_argument("--rig-receipt", type=Path, required=True)
    p.add_argument("--rig-head", required=True)
    p.add_argument("--rig-plan-sha256", required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--exact-head", required=True)
    args = p.parse_args()

    source = json.loads(args.source.read_text(encoding="utf-8"))
    sequence = json.loads(args.sequence.read_text(encoding="utf-8"))
    motion = json.loads(args.motion_evidence.read_text(encoding="utf-8"))
    ownership = json.loads(args.ownership.read_text(encoding="utf-8"))
    rig_receipt = json.loads(args.rig_receipt.read_text(encoding="utf-8"))
    evidence = build_evidence(
        source,
        file_sha256(args.source),
        sequence,
        motion,
        ownership,
        file_sha256(args.ownership),
        rig_receipt,
        args.rig_head,
        args.rig_plan_sha256,
        args.exact_head,
    )
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "lid-latch-motion-evidence.json").write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (args.out / "exact-head.txt").write_text(args.exact_head + "\n", encoding="utf-8")
    (args.out / "latch-rig-donor-head.txt").write_text(args.rig_head + "\n", encoding="utf-8")
    write_svg(args.out / "lid-latch-motion-proof.svg", source, motion, ownership, rig_receipt, evidence)
    print(evidence["result"])


if __name__ == "__main__":
    main()
