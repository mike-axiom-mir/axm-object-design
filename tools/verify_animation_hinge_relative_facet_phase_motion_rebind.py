from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import build_modular_case

SCHEMA = "axm.object-animation-relative-facet-phase-motion-rebind/v0.1"
RESULT = "PASS_OBJECT_ANIMATION_RELATIVE_FACET_PHASE_MOTION_REBIND_INPUT"
SEQUENCE_RESULT = "PASS_ORDERED_LATCH_RELEASE_LID_CLIP_REENGAGE_SEQUENCE"
SOURCE_SHA256 = "49b1f9ed9865893d6de6f1ec8f069576732df694853fde4e3fcff366de32644a"
SEQUENCE_DIGEST = "0a3523cf792264f610881552fd2ebd438aabdfd05e30e92af9dbb33ded1fa2d3"
SUCCESSOR_HEAD = "ef1dfc2f2c1adbe3c90ba089c66ac09d223df25c"
SUCCESSOR_BLOB = "e7a44523ea80e567a745cd61af7fd7005757cc12"
RIGGING_HEAD = "0974a97af10fedf62a5803a88921faf96f3448d5"
RIGGING_BLOB = "6d3e78476ea2b79ca48ad96d823d80d956e5bf49"
LID_RIG_HEAD = "4b72c9918c5fc1e89bd18a0be24fb4afac6e7775"
LID_PLAN_DIGEST = "0ad6dc2ca22676cf301579932e599a441eb7c4bccce31991d1b727aeb22ac422"
EPS = 1e-9


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exact(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"{label} drift: {actual!r} != {expected!r}")


def rotate_x(point: list[float], origin: list[float], angle_deg: float) -> list[float]:
    x, y, z = map(float, point)
    ox, oy, oz = map(float, origin)
    y -= oy
    z -= oz
    a = math.radians(float(angle_deg))
    c, s = math.cos(a), math.sin(a)
    return [x, oy + y * c - z * s, oz + y * s + z * c]


def distance(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((float(a[i]) - float(b[i])) ** 2 for i in range(3)))


def phase_point(center_x: float, origin: list[float], radius: float, phase_deg: float) -> list[float]:
    a = math.radians(float(phase_deg))
    return [
        float(center_x),
        float(origin[1]) + float(radius) * math.cos(a),
        float(origin[2]) + float(radius) * math.sin(a),
    ]


def verify(
    contract: dict[str, Any],
    source: dict[str, Any],
    source_sha: str,
    sequence: dict[str, Any],
    successor: dict[str, Any],
    rigging: dict[str, Any],
    lid_plan: dict[str, Any],
    *,
    exact_animation_head: str,
    observed_successor_head: str,
    observed_successor_blob: str,
    observed_rigging_head: str,
    observed_rigging_blob: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    exact(contract.get("schema"), SCHEMA, "Animation rebind schema")
    exact(contract.get("asset_id"), "modular-equipment-case-001", "asset id")
    exact(source_sha, SOURCE_SHA256, "legacy source SHA-256")
    exact(contract.get("legacy_host_source_sha256"), SOURCE_SHA256, "contract source SHA-256")
    exact(source.get("asset_id"), contract.get("asset_id"), "source asset id")

    seq_ref = contract.get("animation_sequence", {})
    exact(sequence.get("result"), SEQUENCE_RESULT, "Animation sequence prerequisite")
    exact(sequence.get("sequence_id"), seq_ref.get("sequence_id"), "sequence id")
    exact(sequence.get("sequence_digest"), SEQUENCE_DIGEST, "sequence digest")
    exact(seq_ref.get("sequence_digest"), SEQUENCE_DIGEST, "contract sequence digest")
    exact(int(sequence.get("sample_rate_hz", -1)), 40, "sequence sample rate")
    exact(int(seq_ref.get("sample_rate_hz", -1)), 40, "contract sample rate")
    if abs(float(sequence.get("duration_s", -1.0)) - 2.5) > EPS:
        raise AssertionError("sequence duration drift")
    if abs(float(seq_ref.get("duration_s", -1.0)) - 2.5) > EPS:
        raise AssertionError("contract duration drift")
    samples = list(sequence.get("samples", []))
    exact(len(samples), 101, "sequence sample count")
    exact(int(seq_ref.get("endpoint_inclusive_sample_count", -1)), 101, "contract sample count")

    successor_ref = contract.get("source_successor", {})
    exact(observed_successor_head, SUCCESSOR_HEAD, "source-successor head")
    exact(observed_successor_blob, SUCCESSOR_BLOB, "source-successor blob")
    exact(successor_ref.get("exact_head"), SUCCESSOR_HEAD, "contract source-successor head")
    exact(successor_ref.get("contract_git_blob_sha1"), SUCCESSOR_BLOB, "contract source-successor blob")
    exact(successor.get("schema"), successor_ref.get("schema"), "source-successor schema")
    exact(successor.get("successor_id"), successor_ref.get("successor_id"), "source-successor id")
    exact(successor.get("replacement_scope"), "HINGE_KNUCKLE_CROSS_SECTION_ORIENTATION_ONLY", "successor scope")
    exact(successor.get("prerequisite_identity", {}).get("legacy_host_source_sha256"), SOURCE_SHA256, "successor source identity")
    state = successor.get("source_owned_successor", {})
    exact(int(state.get("segments", -1)), 12, "successor segment count")
    exact(state.get("hinge_axis"), [1, 0, 0], "successor axis")
    phases = state.get("owner_group_phase_deg", {})
    exact(float(phases.get("body", 999.0)), 0.0, "body source phase")
    exact(float(phases.get("lid", 999.0)), 15.0, "lid source phase")
    exact(float(state.get("relative_lid_minus_body_phase_deg", 999.0)), 15.0, "relative source phase")
    exact(bool(state.get("rotate_outer_and_bore_cross_sections_together", False)), True, "outer/bore phase lock")
    for key in ("automatic_default_replacement", "automatic_downstream_adoption", "legacy_host_source_rewritten", "successor002_rewritten"):
        exact(state.get(key), False, f"source boundary {key}")
    exact(successor.get("authority", {}).get("animation_authorized"), False, "source does not grant Animation authority")
    exact(float(successor_ref.get("body_phase_deg", 999.0)), 0.0, "contract body phase")
    exact(float(successor_ref.get("lid_phase_deg", 999.0)), 15.0, "contract lid phase")
    exact(float(successor_ref.get("relative_lid_minus_body_phase_deg", 999.0)), 15.0, "contract relative phase")

    rig_ref = contract.get("rigging_receiver", {})
    exact(observed_rigging_head, RIGGING_HEAD, "Rigging receiver head")
    exact(observed_rigging_blob, RIGGING_BLOB, "Rigging receiver blob")
    exact(rig_ref.get("exact_head"), RIGGING_HEAD, "contract Rigging head")
    exact(rig_ref.get("compatibility_contract_git_blob_sha1"), RIGGING_BLOB, "contract Rigging blob")
    exact(rigging.get("schema"), rig_ref.get("schema"), "Rigging schema")
    exact(rigging.get("compatibility_id"), rig_ref.get("compatibility_id"), "Rigging id")
    exact(rigging.get("source_successor", {}).get("head"), SUCCESSOR_HEAD, "Rigging source-successor head")
    exact(rigging.get("source_successor", {}).get("contract_git_blob_sha1"), SUCCESSOR_BLOB, "Rigging source-successor blob")
    historical = rigging.get("historical_rig", {})
    exact(historical.get("head"), LID_RIG_HEAD, "historical lid rig")
    exact(historical.get("plan_digest"), LID_PLAN_DIGEST, "historical lid plan")
    exact(historical.get("joint_id"), "rear-lid-hinge-001", "joint id")
    exact(historical.get("axis"), [1, 0, 0], "Rigging axis")
    exact(historical.get("angle_limit_deg"), [0, 110], "Rigging range")
    exact(historical.get("opening_rotation_sign"), -1, "opening sign")
    exact(historical.get("moving_lid_knuckles"), ["l0", "l1"], "moving knuckles")
    exact(historical.get("fixed_body_knuckles"), ["b0", "b1", "b2"], "fixed knuckles")
    phase_contract = rigging.get("source_phase_contract", {})
    exact(float(phase_contract.get("body_phase_deg", 999.0)), 0.0, "Rigging body phase")
    exact(float(phase_contract.get("lid_phase_deg", 999.0)), 15.0, "Rigging lid phase")
    exact(float(phase_contract.get("relative_lid_minus_body_phase_deg", 999.0)), 15.0, "Rigging relative phase")
    exact(bool(phase_contract.get("outer_and_bore_rotate_together", False)), True, "Rigging phase lock")
    decision = rigging.get("decision", {})
    exact(decision.get("source_successor_rig_compatibility_authorized"), True, "Rigging compatibility")
    exact(decision.get("source_owner_relative_facet_phase_preserved_through_rig"), True, "Rigging phase preservation")
    exact(decision.get("source_successor_geometry_adopted"), False, "Rigging source adoption boundary")
    exact(decision.get("automatic_downstream_adoption"), False, "Rigging downstream boundary")
    exact(rigging.get("authority", {}).get("animation_accepted"), False, "Rigging does not grant Animation acceptance")

    bounded = contract.get("bounded_receiver_decision", {})
    exact(bounded.get("adopt_source_successor_for_this_animation_proof"), True, "bounded Animation opt-in")
    for key in (
        "production_default_adoption",
        "automatic_downstream_adoption",
        "technical_art_receiver_adoption",
        "runtime_controller_or_state_machine_accepted",
        "gameplay_accepted",
    ):
        exact(bounded.get(key), False, f"bounded receiver boundary {key}")
    for key, value in contract.get("preservation_contract", {}).items():
        exact(value, False, f"preservation boundary {key}")
    truth = contract.get("truth_boundary", {})
    exact(truth.get("animation_motion_rebind_owned"), True, "Animation ownership")
    exact(truth.get("source_successor_bounded_animation_proof_consumed"), True, "successor proof consumption")
    exact(truth.get("source_owner_phase_preservation_observed"), True, "phase observation scope")
    for key in (
        "technical_art_target_host_adopted",
        "runtime_controller_or_state_machine_accepted",
        "physics_or_collision_accepted",
        "gameplay_accepted",
        "target_device_performance_accepted",
        "final_visual_motion_accepted",
        "canon_or_production_ready",
    ):
        exact(truth.get(key), False, f"truth boundary {key}")

    exact(lid_plan.get("schema"), "axm.object-articulation-plan/v0.1", "lid articulation schema")
    joint = lid_plan.get("joint", {})
    exact(joint.get("id"), "rear-lid-hinge-001", "lid joint")
    exact(joint.get("axis_source"), "hinge.axis", "lid axis source")
    exact(joint.get("moving_component"), "lid_shell", "lid moving component")
    exact(joint.get("fixed_component"), "body_shell", "lid fixed component")
    exact(joint.get("opening_rotation_sign"), -1, "lid opening sign")
    exact(joint.get("angle_limit_deg"), [0, 110], "lid range")

    frozen = successor.get("frozen_geometry", {})
    outer_radius = float(frozen.get("knuckle_outer_circumradius_m", -1.0))
    bore_radius = float(frozen.get("bore_circumradius_m", -1.0))
    pin_radius = float(frozen.get("source_pin_circumradius_m", -1.0))
    if abs(outer_radius - 0.021) > EPS:
        raise AssertionError("outer knuckle radius drift")
    if bore_radius <= pin_radius:
        raise AssertionError("bore no longer exceeds source pin")
    phase_independent_clearance = bore_radius * math.cos(math.pi / 12.0) - pin_radius
    if phase_independent_clearance < 0.001 - 1e-12:
        raise AssertionError("phase-independent radial lower bound below 1mm")

    built = build_modular_case.build(source)
    origin = [float(v) for v in built["hinge_axis"]["origin_m"]]
    exact([float(v) for v in built["hinge_axis"]["axis"]], [1.0, 0.0, 0.0], "built hinge axis")
    source_rows = list(source.get("hinge", {}).get("knuckles", []))
    exact([r.get("id") for r in source_rows], ["b0", "l0", "b1", "l1", "b2"], "source knuckle order")
    exact([r.get("owner") for r in source_rows], ["body", "lid", "body", "lid", "body"], "source knuckle owners")

    witnesses: list[dict[str, Any]] = []
    neutral_by_id: dict[str, list[float]] = {}
    for row in source_rows:
        kid = str(row["id"])
        owner = str(row["owner"])
        phase_deg = 15.0 if owner == "lid" else 0.0
        expected_parent = "lid_shell" if owner == "lid" else "body_shell"
        for radial_kind, radius in (("outer", outer_radius), ("bore", bore_radius)):
            witness_id = f"{kid}_{radial_kind}"
            neutral = phase_point(float(row["center_x"]), origin, radius, phase_deg)
            neutral_by_id[witness_id] = neutral
            witnesses.append({
                "id": witness_id,
                "knuckle_id": kid,
                "radial_kind": radial_kind,
                "owner": owner,
                "expected_parent": expected_parent,
                "source_phase_deg": phase_deg,
                "radius_m": radius,
                "neutral_witness_m": neutral,
            })

    godot_samples: list[dict[str, Any]] = []
    max_open = 0.0
    max_sign_residual = 0.0
    max_composition_residual = 0.0
    for expected_index, sample in enumerate(samples):
        exact(int(sample.get("index", -1)), expected_index, "sample index")
        expected_time = expected_index / 40.0
        if abs(float(sample.get("time_s", -1.0)) - expected_time) > 1e-6:
            raise AssertionError(f"sample time-grid drift at {expected_index}")
        open_angle = float(sample.get("lid_open_angle_deg"))
        math_angle = float(sample.get("lid_mathematical_rotation_deg"))
        max_open = max(max_open, open_angle)
        max_sign_residual = max(max_sign_residual, abs(math_angle + open_angle))
        if open_angle < -EPS or open_angle > 110.0 + EPS:
            raise AssertionError(f"Animation sample escaped Rigging owner range at {expected_index}: {open_angle}")
        if abs(math_angle + open_angle) > 1e-9:
            raise AssertionError("Animation/Rigging sign relation drift")

        expected_positions: dict[str, list[float]] = {}
        expected_effective_phase: dict[str, float] = {}
        for witness in witnesses:
            wid = str(witness["id"])
            owner = str(witness["owner"])
            neutral = neutral_by_id[wid]
            posed = rotate_x(neutral, origin, math_angle) if owner == "lid" else list(neutral)
            expected_positions[wid] = [round(float(v), 15) for v in posed]
            phase = float(witness["source_phase_deg"]) + (math_angle if owner == "lid" else 0.0)
            expected_effective_phase[wid] = phase
            direct = phase_point(float(posed[0]), origin, float(witness["radius_m"]), phase)
            max_composition_residual = max(max_composition_residual, distance(posed, direct))
        godot_samples.append({
            "index": expected_index,
            "time_s": float(sample["time_s"]),
            "lid_open_angle_deg": open_angle,
            "lid_mathematical_rotation_deg": math_angle,
            "expected_witness_world_positions_m": expected_positions,
            "expected_effective_phase_deg": expected_effective_phase,
        })

    if abs(max_open - 100.0) > EPS:
        raise AssertionError(f"frozen Animation peak drift: {max_open}")
    if max_sign_residual > EPS:
        raise AssertionError("Animation/Rigging sign residual exceeded tolerance")
    if max_composition_residual > 1e-12:
        raise AssertionError(f"same-axis phase composition residual too large: {max_composition_residual}")
    endpoint_closure = max(
        distance(godot_samples[0]["expected_witness_world_positions_m"][wid], godot_samples[-1]["expected_witness_world_positions_m"][wid])
        for wid in neutral_by_id
    )
    if endpoint_closure > EPS:
        raise AssertionError("frozen Animation endpoint no longer closes")

    payload = {
        "schema": "axm.object-animation-relative-facet-phase-godot-input/v0.1",
        "exact_animation_head": exact_animation_head,
        "asset_id": contract["asset_id"],
        "legacy_host_source_sha256": SOURCE_SHA256,
        "source_successor_head": SUCCESSOR_HEAD,
        "source_successor_blob": SUCCESSOR_BLOB,
        "source_successor_id": successor["successor_id"],
        "rigging_receiver_head": RIGGING_HEAD,
        "rigging_receiver_blob": RIGGING_BLOB,
        "rigging_compatibility_id": rigging["compatibility_id"],
        "hinge_origin_m": origin,
        "hinge_axis": [1, 0, 0],
        "rig_angle_limit_deg": [0, 110],
        "sample_rate_hz": 40,
        "duration_s": 2.5,
        "endpoint_inclusive_sample_count": 101,
        "body_phase_deg": 0.0,
        "lid_phase_deg": 15.0,
        "relative_lid_minus_body_phase_deg": 15.0,
        "phase_independent_radial_clearance_lower_bound_m": phase_independent_clearance,
        "bounded_animation_candidate_adopted": True,
        "production_default_adoption": False,
        "automatic_downstream_adoption": False,
        "technical_art_target_host_adopted": False,
        "runtime_controller_or_state_machine_accepted": False,
        "gameplay_accepted": False,
        "witnesses": witnesses,
        "samples": godot_samples,
    }
    receipt = {
        "schema": "axm.object-animation-relative-facet-phase-structural-evidence/v0.1",
        "result": RESULT,
        "exact_animation_head": exact_animation_head,
        "source_successor_head": SUCCESSOR_HEAD,
        "source_successor_blob": SUCCESSOR_BLOB,
        "rigging_receiver_head": RIGGING_HEAD,
        "rigging_receiver_blob": RIGGING_BLOB,
        "sequence_digest": SEQUENCE_DIGEST,
        "sample_rate_hz": 40,
        "duration_s": 2.5,
        "endpoint_inclusive_sample_count": 101,
        "witness_count": len(witnesses),
        "source_body_phase_deg": 0.0,
        "source_lid_phase_deg": 15.0,
        "peak_lid_open_angle_deg": max_open,
        "peak_lid_effective_phase_deg": 15.0 - max_open,
        "maximum_animation_rig_sign_residual_deg": max_sign_residual,
        "maximum_same_axis_phase_composition_residual_m": max_composition_residual,
        "endpoint_witness_closure_m": endpoint_closure,
        "phase_independent_radial_clearance_lower_bound_m": phase_independent_clearance,
        "truth_boundary": contract["truth_boundary"],
    }
    return payload, receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--sequence-evidence", type=Path, required=True)
    parser.add_argument("--source-successor", type=Path, required=True)
    parser.add_argument("--rigging-compatibility", type=Path, required=True)
    parser.add_argument("--lid-plan", type=Path, required=True)
    parser.add_argument("--exact-head", required=True)
    parser.add_argument("--observed-successor-head", required=True)
    parser.add_argument("--observed-successor-blob", required=True)
    parser.add_argument("--observed-rigging-head", required=True)
    parser.add_argument("--observed-rigging-blob", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    payload, receipt = verify(
        load_json(args.contract),
        load_json(args.source),
        sha256_file(args.source),
        load_json(args.sequence_evidence),
        load_json(args.source_successor),
        load_json(args.rigging_compatibility),
        load_json(args.lid_plan),
        exact_animation_head=args.exact_head,
        observed_successor_head=args.observed_successor_head,
        observed_successor_blob=args.observed_successor_blob,
        observed_rigging_head=args.observed_rigging_head,
        observed_rigging_blob=args.observed_rigging_blob,
    )
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "godot-input.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (args.out / "structural-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
