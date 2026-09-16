#!/usr/bin/env python3
"""Diagnose phase-boundary velocity continuity in the exact Object Animation sequence.

This observer does not edit the authored clip, keys, timing, rig, or source authority.
It measures one-sided angular velocities implied by the already-proven LINEAR
AnimationPlayer key interpolation and records where C1 velocity continuity is and is
not present. The result is diagnosis for Animation review, not a smoothing proposal,
runtime/controller certification, gameplay evidence, or final motion acceptance.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

RESULT = "PASS_OBJECT_PHASE_DERIVATIVE_DIAGNOSIS_MOTION_UNCHANGED"
SCHEMA = "axm.object-animation-phase-derivative-diagnosis/v0.1"
EXPECTED_SEQUENCE_ID = "lid-latch-open-hold-close-001"
EXPECTED_SEQUENCE_DIGEST = "0a3523cf792264f610881552fd2ebd438aabdfd05e30e92af9dbb33ded1fa2d3"
EXPECTED_SOURCE_INTERFACE_HEAD = "6086f39a3da344c57a68653f90d040e03e04cec2"
EXPECTED_SOURCE_RIG_HEAD = "a1acd2bcb2074f41e536562f2673508e2cb0a4d5"
EXPECTED_AUTHORITY_RESULT = "PASS_ANIMATION_SOURCE_AUTHORITY_REBIND_MOTION_EQUIVALENCE"
EPS = 1e-12
JUMP_EPS = 1e-9


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _interval_velocities(values: list[float], dt: float) -> list[float]:
    if len(values) < 2:
        raise ValueError("at least two samples are required")
    if dt <= 0.0:
        raise ValueError("sample interval must be positive")
    return [(values[i + 1] - values[i]) / dt for i in range(len(values) - 1)]


def _track_diagnosis(values: list[float], dt: float) -> dict[str, Any]:
    velocity = _interval_velocities(values, dt)
    interior = []
    for sample_index in range(1, len(values) - 1):
        incoming = velocity[sample_index - 1]
        outgoing = velocity[sample_index]
        jump = outgoing - incoming
        interior.append(
            {
                "sample_index": sample_index,
                "incoming_velocity_deg_per_s": incoming,
                "outgoing_velocity_deg_per_s": outgoing,
                "signed_velocity_jump_deg_per_s": jump,
                "absolute_velocity_jump_deg_per_s": abs(jump),
            }
        )

    seam_incoming = velocity[-1]
    seam_outgoing = velocity[0]
    seam_jump = seam_outgoing - seam_incoming
    worst = max(interior, key=lambda row: float(row["absolute_velocity_jump_deg_per_s"]))
    nonzero = sum(float(row["absolute_velocity_jump_deg_per_s"]) > JUMP_EPS for row in interior)

    return {
        "interval_count": len(velocity),
        "interior_boundary_count": len(interior),
        "maximum_absolute_interval_velocity_deg_per_s": max(abs(v) for v in velocity),
        "interior_boundaries_with_nonzero_velocity_jump": nonzero,
        "interior_boundaries_with_zero_velocity_jump": len(interior) - nonzero,
        "maximum_interior_absolute_velocity_jump_deg_per_s": float(worst["absolute_velocity_jump_deg_per_s"]),
        "worst_interior_boundary_sample_index": int(worst["sample_index"]),
        "repeat_seam": {
            "incoming_velocity_deg_per_s": seam_incoming,
            "outgoing_velocity_deg_per_s": seam_outgoing,
            "signed_velocity_jump_deg_per_s": seam_jump,
            "absolute_velocity_jump_deg_per_s": abs(seam_jump),
            "c1_continuous_within_tolerance": abs(seam_jump) <= JUMP_EPS,
        },
        "interior_boundaries": interior,
    }


def _phase_rows(
    landmarks: dict[str, Any],
    lid_values: list[float],
    latch_values: list[float],
    dt: float,
) -> list[dict[str, Any]]:
    lid_v = _interval_velocities(lid_values, dt)
    latch_v = _interval_velocities(latch_values, dt)
    last_sample = len(lid_values) - 1
    rows: list[dict[str, Any]] = []
    for name, raw in landmarks.items():
        index = int(raw["index"])
        if index < 0 or index > last_sample:
            raise ValueError(f"phase landmark {name} index out of range")
        seam = index in (0, last_sample)
        incoming_i = len(lid_v) - 1 if seam else index - 1
        outgoing_i = 0 if seam else index
        if not seam and (incoming_i < 0 or outgoing_i >= len(lid_v)):
            raise ValueError(f"phase landmark {name} lacks one-sided intervals")
        rows.append(
            {
                "name": name,
                "sample_index": index,
                "time_s": float(raw["time_s"]),
                "lid_angle_deg": float(lid_values[index]),
                "latch_angle_deg": float(latch_values[index]),
                "repeat_seam_equivalent": seam,
                "lid_incoming_velocity_deg_per_s": lid_v[incoming_i],
                "lid_outgoing_velocity_deg_per_s": lid_v[outgoing_i],
                "lid_signed_velocity_jump_deg_per_s": lid_v[outgoing_i] - lid_v[incoming_i],
                "latch_incoming_velocity_deg_per_s": latch_v[incoming_i],
                "latch_outgoing_velocity_deg_per_s": latch_v[outgoing_i],
                "latch_signed_velocity_jump_deg_per_s": latch_v[outgoing_i] - latch_v[incoming_i],
            }
        )
    return rows


def _synthetic_controls() -> dict[str, Any]:
    constant = _track_diagnosis([0.0, 1.0, 2.0], 1.0)
    kink = _track_diagnosis([0.0, 1.0, 1.0], 1.0)
    if constant["maximum_interior_absolute_velocity_jump_deg_per_s"] > EPS:
        raise ValueError("observer false-positive on constant-speed control")
    if kink["maximum_interior_absolute_velocity_jump_deg_per_s"] <= 0.5:
        raise ValueError("observer failed deliberate velocity-change control")
    return {
        "constant_speed_interior_jump_deg_per_s": constant["maximum_interior_absolute_velocity_jump_deg_per_s"],
        "deliberate_kink_interior_jump_deg_per_s": kink["maximum_interior_absolute_velocity_jump_deg_per_s"],
        "constant_speed_control": "PASS_ZERO_INTERIOR_JUMP",
        "deliberate_kink_control": "PASS_NONZERO_INTERIOR_JUMP_DETECTED",
    }


def diagnose(
    sequence: dict[str, Any],
    authority: dict[str, Any],
    *,
    exact_head: str,
) -> dict[str, Any]:
    if sequence.get("result") != "PASS_ORDERED_LATCH_RELEASE_LID_CLIP_REENGAGE_SEQUENCE":
        raise ValueError("sequence prerequisite is not green")
    if sequence.get("sequence_id") != EXPECTED_SEQUENCE_ID:
        raise ValueError("Animation sequence identity drift")
    if sequence.get("sequence_digest") != EXPECTED_SEQUENCE_DIGEST:
        raise ValueError("Animation sequence digest drift")
    if int(sequence.get("sample_rate_hz", 0)) != 40:
        raise ValueError("Animation sample-rate drift")
    if float(sequence.get("duration_s", 0.0)) != 2.5:
        raise ValueError("Animation duration drift")

    if authority.get("result") != EXPECTED_AUTHORITY_RESULT:
        raise ValueError("current source-authority Animation prerequisite is not green")
    if authority.get("exact_receiving_head") == "":
        raise ValueError("source-authority evidence lacks receiving head")
    if authority.get("prior_sequence_id") != EXPECTED_SEQUENCE_ID:
        raise ValueError("source-authority sequence identity drift")
    if authority.get("prior_sequence_digest") != EXPECTED_SEQUENCE_DIGEST:
        raise ValueError("source-authority sequence digest drift")
    if authority.get("current_source_interface_head") != EXPECTED_SOURCE_INTERFACE_HEAD:
        raise ValueError("source interface authority drift")
    if authority.get("current_source_rig_head") != EXPECTED_SOURCE_RIG_HEAD:
        raise ValueError("source Rigging authority drift")
    if any(bool(authority.get(key)) for key in ("motion_change", "retimed", "retargeted", "key_count_changed")):
        raise ValueError("diagnosis refuses mutated motion authority")

    samples = sequence.get("samples", [])
    if len(samples) != 101 or int(sequence.get("endpoint_inclusive_sample_count", 0)) != 101:
        raise ValueError("expected exact 101 endpoint-inclusive samples")
    if [int(row.get("index", -1)) for row in samples] != list(range(101)):
        raise ValueError("sample ordering drift")

    rate = int(sequence["sample_rate_hz"])
    dt = 1.0 / rate
    for index, row in enumerate(samples):
        if abs(float(row.get("time_s", -1.0)) - index * dt) > EPS:
            raise ValueError(f"sample timing drift at index {index}")

    lid_values = [float(row["lid_open_angle_deg"]) for row in samples]
    latch_values = [float(row["latch_lever_angle_deg"]) for row in samples]
    if abs(lid_values[0] - lid_values[-1]) > EPS or abs(latch_values[0] - latch_values[-1]) > EPS:
        raise ValueError("endpoint pose no longer closes exactly")

    lid = _track_diagnosis(lid_values, dt)
    latch = _track_diagnosis(latch_values, dt)
    raw_phases = _phase_rows(sequence.get("phase_landmarks", {}), lid_values, latch_values, dt)
    expected_phase_names = [
        "closed_start",
        "release_complete",
        "lid_peak_start",
        "lid_peak_mid",
        "lid_peak_end",
        "lid_closed_before_reengage",
        "closed_end",
    ]
    phase_by_name = {row["name"]: row for row in raw_phases}
    if len(phase_by_name) != len(raw_phases) or set(phase_by_name) != set(expected_phase_names):
        raise ValueError("phase-landmark identity drift")
    phases = [phase_by_name[name] for name in expected_phase_names]

    phase_map = {row["name"]: row for row in phases}
    if abs(float(phase_map["lid_peak_mid"]["lid_incoming_velocity_deg_per_s"])) > EPS:
        raise ValueError("exact lid hold midpoint lost zero incoming velocity")
    if abs(float(phase_map["lid_peak_mid"]["lid_outgoing_velocity_deg_per_s"])) > EPS:
        raise ValueError("exact lid hold midpoint lost zero outgoing velocity")
    if abs(float(phase_map["lid_peak_mid"]["latch_incoming_velocity_deg_per_s"])) > EPS:
        raise ValueError("latch moved during lid hold midpoint")
    if abs(float(phase_map["lid_peak_mid"]["latch_outgoing_velocity_deg_per_s"])) > EPS:
        raise ValueError("latch moved during lid hold midpoint")

    controls = _synthetic_controls()
    return {
        "schema": SCHEMA,
        "result": RESULT,
        "exact_receiving_head": exact_head,
        "diagnosed_authority_head": authority["exact_receiving_head"],
        "asset_id": sequence.get("asset_id"),
        "sequence_id": EXPECTED_SEQUENCE_ID,
        "sequence_digest": EXPECTED_SEQUENCE_DIGEST,
        "current_source_interface_head": EXPECTED_SOURCE_INTERFACE_HEAD,
        "current_source_rig_head": EXPECTED_SOURCE_RIG_HEAD,
        "sample_rate_hz": rate,
        "sample_interval_s": dt,
        "duration_s": float(sequence["duration_s"]),
        "endpoint_inclusive_sample_count": len(samples),
        "interpolation_under_diagnosis": "EXISTING_LINEAR_CONTINUOUS_ANIMATIONPLAYER_KEYS",
        "motion_changed": False,
        "retimed": False,
        "retargeted": False,
        "key_count_changed": False,
        "smoothing_candidate_authored": False,
        "tracks": {
            "lid_open_angle_deg": lid,
            "latch_lever_angle_deg": latch,
        },
        "phase_boundaries": phases,
        "observations": {
            "endpoint_position_continuity_exact": True,
            "lid_repeat_seam_c1_continuous": lid["repeat_seam"]["c1_continuous_within_tolerance"],
            "latch_repeat_seam_c1_continuous": latch["repeat_seam"]["c1_continuous_within_tolerance"],
            "current_linear_interpolation_c1_continuous_all_tracks": (
                lid["interior_boundaries_with_nonzero_velocity_jump"] == 0
                and latch["interior_boundaries_with_nonzero_velocity_jump"] == 0
                and lid["repeat_seam"]["c1_continuous_within_tolerance"]
                and latch["repeat_seam"]["c1_continuous_within_tolerance"]
            ),
        },
        "synthetic_controls": controls,
        "truth_boundary": {
            "diagnoses_exact_authored_key_velocity_continuity": True,
            "changes_motion": False,
            "proves_visual_badness": False,
            "proposes_smoothing": False,
            "proves_wall_clock_pacing": False,
            "proves_runtime_controller_or_state_machine": False,
            "proves_collision_or_physics": False,
            "proves_gameplay": False,
            "proves_final_motion_quality": False,
            "proves_canon_or_production_readiness": False,
        },
        "non_claims": [
            "no claim that a non-zero one-sided velocity jump is perceptually objectionable",
            "no spline, Hermite, easing, dwell, retime or key-edit proposal is authored",
            "no wall-clock playback, scheduler, controller or state-machine acceptance",
            "no collision, physics, gameplay or target-device performance acceptance",
            "no final motion style, Art Direction, Visual QA, CANON or production-readiness claim",
        ],
    }


def _write_svg(receipt: dict[str, Any], path: Path) -> None:
    width, height = 1180, 460
    left, right, top, bottom = 65.0, 30.0, 46.0, 72.0
    plot_w, plot_h = width - left - right, height - top - bottom
    lid_rows = receipt["tracks"]["lid_open_angle_deg"]["interior_boundaries"]
    latch_rows = receipt["tracks"]["latch_lever_angle_deg"]["interior_boundaries"]
    seam_lid = float(receipt["tracks"]["lid_open_angle_deg"]["repeat_seam"]["absolute_velocity_jump_deg_per_s"])
    seam_latch = float(receipt["tracks"]["latch_lever_angle_deg"]["repeat_seam"]["absolute_velocity_jump_deg_per_s"])
    y_max = max(
        seam_lid,
        seam_latch,
        max(float(row["absolute_velocity_jump_deg_per_s"]) for row in lid_rows),
        max(float(row["absolute_velocity_jump_deg_per_s"]) for row in latch_rows),
        1.0,
    )

    def sx(index: int) -> float:
        return left + (index / 100.0) * plot_w

    def sy(value: float) -> float:
        return top + plot_h - (value / y_max) * plot_h

    lid_points = [(0, seam_lid)] + [(int(row["sample_index"]), float(row["absolute_velocity_jump_deg_per_s"])) for row in lid_rows] + [(100, seam_lid)]
    latch_points = [(0, seam_latch)] + [(int(row["sample_index"]), float(row["absolute_velocity_jump_deg_per_s"])) for row in latch_rows] + [(100, seam_latch)]
    lid_poly = " ".join(f"{sx(i):.2f},{sy(v):.2f}" for i, v in lid_points)
    latch_poly = " ".join(f"{sx(i):.2f},{sy(v):.2f}" for i, v in latch_points)
    phase_indices = [0, 10, 40, 50, 60, 90, 100]

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<style>text{font-family:monospace;fill:#111}.axis{stroke:#777;stroke-width:1}.lid{fill:none;stroke:#111;stroke-width:2}.latch{fill:none;stroke:#777;stroke-width:2;stroke-dasharray:6 4}.phase{stroke:#bbb;stroke-width:1;stroke-dasharray:3 3}</style>',
        f'<line class="axis" x1="{left}" y1="{top+plot_h}" x2="{left+plot_w}" y2="{top+plot_h}"/>',
        f'<line class="axis" x1="{left}" y1="{top}" x2="{left}" y2="{top+plot_h}"/>',
        '<text x="65" y="24" font-size="14">Object Animation source-authority sequence — one-sided velocity-jump diagnosis</text>',
        f'<text x="790" y="24" font-size="12">vertical scale max {y_max:.6f} deg/s</text>',
        '<text x="75" y="44" font-size="11">solid: lid | dashed: latch | diagnosis only; motion unchanged</text>',
        f'<polyline class="lid" points="{lid_poly}"/>',
        f'<polyline class="latch" points="{latch_poly}"/>',
    ]
    for idx in phase_indices:
        x = sx(idx)
        lines.append(f'<line class="phase" x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top+plot_h}"/>')
        lines.append(f'<text x="{x-9:.2f}" y="{top+plot_h+22}" font-size="11">{idx}</text>')
    lines.extend([
        f'<text x="{left}" y="{height-20}" font-size="11">phase samples: 0 closed | 10 released | 40 hold start | 50 hold mid | 60 hold end | 90 lid closed | 100 closed/repeat seam</text>',
        '</svg>',
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sequence-evidence", type=Path, required=True)
    parser.add_argument("--authority-rebind", type=Path, required=True)
    parser.add_argument("--exact-head", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    sequence = _load(args.sequence_evidence)
    authority = _load(args.authority_rebind)
    receipt = diagnose(sequence, authority, exact_head=args.exact_head)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "object-animation-phase-derivative-diagnosis.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (args.out / "exact-head.txt").write_text(args.exact_head + "\n", encoding="utf-8")
    _write_svg(receipt, args.out / "object-animation-phase-derivative-diagnosis.svg")
    print(receipt["result"])


if __name__ == "__main__":
    main()
