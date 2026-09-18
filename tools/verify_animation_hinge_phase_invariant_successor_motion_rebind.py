from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import build_modular_case

SCHEMA = "axm.object-animation-phase-invariant-hinge-successor-rebind/v0.1"
STRUCTURAL_RESULT = "PASS_OBJECT_ANIMATION_PHASE_INVARIANT_HINGE_SUCCESSOR_REBIND_INPUT"
SEQUENCE_RESULT = "PASS_ORDERED_LATCH_RELEASE_LID_CLIP_REENGAGE_SEQUENCE"
SUCCESSOR_HEAD = "a6d18b9fe729304dc4d95d962ed27527adce211f"
SUCCESSOR_BLOB = "7e078189d5c80508b28932563326cd5629c4efa6"
RIGGING_HEAD = "cf377074f70ce7f7e386f1378c51705b3db4d305"
RIGGING_BLOB = "813a4e97973a023b6a1027582a03e2fb437103ea"
SOURCE_SHA256 = "49b1f9ed9865893d6de6f1ec8f069576732df694853fde4e3fcff366de32644a"
LID_RIG_HEAD = "4b72c9918c5fc1e89bd18a0be24fb4afac6e7775"
LID_PLAN_DIGEST = "0ad6dc2ca22676cf301579932e599a441eb7c4bccce31991d1b727aeb22ac422"
SEQUENCE_DIGEST = "0a3523cf792264f610881552fd2ebd438aabdfd05e30e92af9dbb33ded1fa2d3"
EPS = 1e-9


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def distance(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((float(a[i]) - float(b[i])) ** 2 for i in range(3)))


def rotate_x(point: list[float], origin: list[float], angle_deg: float) -> list[float]:
    x, y, z = map(float, point)
    ox, oy, oz = map(float, origin)
    y -= oy
    z -= oz
    a = math.radians(float(angle_deg))
    c, s = math.cos(a), math.sin(a)
    return [x, oy + y * c - z * s, oz + y * s + z * c]


def _assert_exact(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"{label} drift: {actual!r} != {expected!r}")


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
    _assert_exact(contract.get("schema"), SCHEMA, "Animation successor-rebind schema")
    _assert_exact(contract.get("asset_id"), "modular-equipment-case-001", "asset id")
    _assert_exact(source.get("asset_id"), contract.get("asset_id"), "legacy source asset")
    _assert_exact(source_sha, SOURCE_SHA256, "legacy source SHA-256")
    _assert_exact(contract.get("legacy_host_source_sha256"), SOURCE_SHA256, "contract legacy source")

    seq_ref = contract.get("animation_sequence", {})
    _assert_exact(sequence.get("result"), SEQUENCE_RESULT, "Animation sequence prerequisite")
    _assert_exact(sequence.get("sequence_id"), seq_ref.get("sequence_id"), "sequence id")
    _assert_exact(sequence.get("sequence_digest"), SEQUENCE_DIGEST, "sequence digest")
    _assert_exact(seq_ref.get("sequence_digest"), SEQUENCE_DIGEST, "contract sequence digest")
    _assert_exact(int(sequence.get("sample_rate_hz", -1)), 40, "sequence sample rate")
    _assert_exact(int(seq_ref.get("sample_rate_hz", -1)), 40, "contract sample rate")
    if abs(float(sequence.get("duration_s", -1)) - 2.5) > EPS:
        raise AssertionError("sequence duration drift")
    if abs(float(seq_ref.get("duration_s", -1)) - 2.5) > EPS:
        raise AssertionError("contract duration drift")
    samples = list(sequence.get("samples", []))
    _assert_exact(len(samples), 101, "sequence sample count")
    _assert_exact(int(seq_ref.get("endpoint_inclusive_sample_count", -1)), 101, "contract sample count")

    successor_ref = contract.get("source_successor", {})
    _assert_exact(observed_successor_head, SUCCESSOR_HEAD, "source-successor head")
    _assert_exact(observed_successor_blob, SUCCESSOR_BLOB, "source-successor blob")
    _assert_exact(successor_ref.get("exact_head"), SUCCESSOR_HEAD, "contract source-successor head")
    _assert_exact(successor_ref.get("contract_git_blob_sha1"), SUCCESSOR_BLOB, "contract source-successor blob")
    _assert_exact(successor.get("schema"), successor_ref.get("schema"), "source-successor schema")
    _assert_exact(successor.get("successor_id"), successor_ref.get("successor_id"), "source-successor id")
    _assert_exact(successor.get("legacy_host_source_sha256"), SOURCE_SHA256, "successor legacy source")
    _assert_exact(successor.get("replacement_scope"), "HINGE_KNUCKLE_BORE_GEOMETRY_ONLY", "successor replacement scope")
    _assert_exact(successor.get("phase_invariant_claim_scope"), "CONCENTRIC_REGULAR_12_GON_RADIAL_CROSS_SECTION_ONLY", "successor phase-invariant scope")
    successor_state = successor.get("source_owned_successor", {})
    _assert_exact(successor_state.get("segments"), 12, "successor segment count")
    _assert_exact(successor_state.get("pin_relative_axial_phase"), "UNSPECIFIED", "successor pin phase")
    _assert_exact(successor_state.get("pin_physical_owner"), "UNSPECIFIED", "successor pin owner")
    for key in ("automatic_default_replacement", "automatic_downstream_adoption", "legacy_host_source_rewritten", "predecessor_source_successor_rewritten"):
        _assert_exact(successor_state.get(key), False, f"source-successor boundary {key}")
    _assert_exact(successor.get("authority", {}).get("animation_authorized"), False, "source does not grant Animation authority")

    rig_ref = contract.get("rigging_receiver", {})
    _assert_exact(observed_rigging_head, RIGGING_HEAD, "Rigging receiver head")
    _assert_exact(observed_rigging_blob, RIGGING_BLOB, "Rigging receiver blob")
    _assert_exact(rig_ref.get("exact_head"), RIGGING_HEAD, "contract Rigging head")
    _assert_exact(rig_ref.get("compatibility_contract_git_blob_sha1"), RIGGING_BLOB, "contract Rigging blob")
    _assert_exact(rigging.get("schema"), rig_ref.get("schema"), "Rigging compatibility schema")
    _assert_exact(rigging.get("compatibility_id"), rig_ref.get("compatibility_id"), "Rigging compatibility id")
    _assert_exact(rigging.get("source_successor", {}).get("head"), SUCCESSOR_HEAD, "Rigging source-successor head")
    _assert_exact(rigging.get("source_successor", {}).get("contract_git_blob_sha1"), SUCCESSOR_BLOB, "Rigging source-successor blob")
    historical = rigging.get("historical_rig", {})
    _assert_exact(historical.get("head"), LID_RIG_HEAD, "historical lid rig")
    _assert_exact(historical.get("plan_digest"), LID_PLAN_DIGEST, "historical lid-plan digest")
    _assert_exact(historical.get("joint_id"), "rear-lid-hinge-001", "joint id")
    _assert_exact(historical.get("axis"), [1, 0, 0], "hinge axis")
    _assert_exact(historical.get("angle_limit_deg"), [0, 110], "rig range")
    _assert_exact(historical.get("opening_rotation_sign"), -1, "opening sign")
    _assert_exact(historical.get("moving_lid_knuckles"), ["l0", "l1"], "moving knuckles")
    _assert_exact(historical.get("fixed_body_knuckles"), ["b0", "b1", "b2"], "fixed knuckles")
    decision = rigging.get("decision", {})
    _assert_exact(decision.get("source_successor_rig_compatibility_authorized"), True, "Rigging compatibility authorization")
    _assert_exact(decision.get("phase_independent_1mm_radial_lower_bound_accepted_as_source_geometric_constraint"), True, "Rigging 1mm acceptance")
    _assert_exact(decision.get("source_successor_geometry_adopted"), False, "Rigging production adoption boundary")
    _assert_exact(decision.get("automatic_downstream_adoption"), False, "Rigging downstream adoption boundary")
    _assert_exact(rigging.get("authority", {}).get("animation_accepted"), False, "Rigging does not grant Animation acceptance")

    bounded = contract.get("bounded_receiver_decision", {})
    _assert_exact(bounded.get("adopt_source_successor_for_this_animation_proof"), True, "bounded Animation candidate opt-in")
    for key in ("production_default_adoption", "automatic_downstream_adoption", "pin_relative_axial_phase_claimed", "pin_physical_owner_claimed", "technical_art_receiver_adoption"):
        _assert_exact(bounded.get(key), False, f"bounded receiver boundary {key}")

    preserve = contract.get("preservation_contract", {})
    for key in ("retimed", "keys_changed", "easing_changed", "amplitude_changed", "legacy_host_source_rewritten", "source_successor_rewritten", "rigging_constraint_rewritten", "parent_partition_changed"):
        _assert_exact(preserve.get(key), False, f"preservation boundary {key}")

    truth = contract.get("truth_boundary", {})
    _assert_exact(truth.get("animation_motion_rebind_owned"), True, "Animation rebind authority")
    _assert_exact(truth.get("source_successor_bounded_animation_proof_consumed"), True, "bounded successor consumption")
    for key in ("phase_independent_clearance_owned_by_animation", "technical_art_target_host_adopted", "runtime_controller_or_state_machine_accepted", "physics_or_collision_accepted", "gameplay_accepted", "target_device_performance_accepted", "final_visual_motion_accepted", "canon_or_production_ready"):
        _assert_exact(truth.get(key), False, f"authority inflation {key}")

    _assert_exact(lid_plan.get("schema"), "axm.object-articulation-plan/v0.1", "lid articulation schema")
    joint = lid_plan.get("joint", {})
    _assert_exact(joint.get("id"), "rear-lid-hinge-001", "lid joint")
    _assert_exact(joint.get("axis_source"), "hinge.axis", "lid axis source")
    _assert_exact(joint.get("moving_component"), "lid_shell", "moving component")
    _assert_exact(joint.get("fixed_component"), "body_shell", "fixed component")
    _assert_exact(joint.get("opening_rotation_sign"), -1, "lid opening sign")
    _assert_exact(joint.get("angle_limit_deg"), [0, 110], "lid angle range")

    segments = int(successor_state["segments"])
    pin = float(successor_state["source_pin_circumradius_m"])
    bore = float(successor_state["bore_circumradius_m"])
    phase_clearance = bore * math.cos(math.pi / segments) - pin
    if phase_clearance < 0.001 - 1e-12:
        raise AssertionError(f"Rigging-accepted phase-independent clearance no longer reaches 1mm: {phase_clearance}")

    hinge = source.get("hinge", {})
    built = build_modular_case.build(source)
    axis = [float(v) for v in built["hinge_axis"]["axis"]]
    if axis != [1.0, 0.0, 0.0]:
        raise AssertionError("legacy source hinge axis drift")
    origin = [float(v) for v in built["hinge_axis"]["origin_m"]]
    radius = float(hinge.get("knuckle_radius"))
    source_rows = list(hinge.get("knuckles", []))
    if len(source_rows) != 5:
        raise AssertionError("expected five legacy source knuckles")
    moving = [row["id"] for row in source_rows if row.get("owner") == "lid"]
    fixed = [row["id"] for row in source_rows if row.get("owner") == "body"]
    _assert_exact(moving, ["l0", "l1"], "source moving knuckles")
    _assert_exact(fixed, ["b0", "b1", "b2"], "source fixed knuckles")
    neutral = {
        row["id"]: [float(row["center_x"]), origin[1] + radius, origin[2]]
        for row in source_rows
    }

    godot_samples: list[dict[str, Any]] = []
    max_open = 0.0
    max_sign_residual = 0.0
    endpoint_closure = 0.0
    for expected_index, sample in enumerate(samples):
        _assert_exact(int(sample.get("index", -1)), expected_index, "sample index")
        expected_time = expected_index / 40.0
        if abs(float(sample.get("time_s", -1)) - expected_time) > 1e-6:
            raise AssertionError(f"sample time-grid drift at {expected_index}")
        open_angle = float(sample.get("lid_open_angle_deg"))
        math_angle = float(sample.get("lid_mathematical_rotation_deg"))
        max_open = max(max_open, open_angle)
        max_sign_residual = max(max_sign_residual, abs(math_angle + open_angle))
        if abs(math_angle + open_angle) > 1e-9:
            raise AssertionError("Animation lid mathematical angle no longer follows -1 Rigging sign")
        if open_angle < -EPS or open_angle > 110.0 + EPS:
            raise AssertionError(f"Animation sample escaped Rigging owner range at {expected_index}: {open_angle}")

        expected_positions: dict[str, list[float]] = {}
        for row in source_rows:
            kid = row["id"]
            base = neutral[kid]
            posed = rotate_x(base, origin, math_angle) if kid in moving else list(base)
            expected_positions[kid] = [round(float(v), 15) for v in posed]
        godot_samples.append({
            "index": expected_index,
            "time_s": float(sample["time_s"]),
            "lid_open_angle_deg": open_angle,
            "lid_mathematical_rotation_deg": math_angle,
            "expected_knuckle_world_positions_m": expected_positions,
        })

    if abs(max_open - 100.0) > 1e-9:
        raise AssertionError(f"frozen Animation peak drift: {max_open}")
    if max_sign_residual > 1e-9:
        raise AssertionError("Animation/Rigging sign residual exceeded tolerance")
    for kid in neutral:
        endpoint_closure = max(endpoint_closure, distance(godot_samples[0]["expected_knuckle_world_positions_m"][kid], godot_samples[-1]["expected_knuckle_world_positions_m"][kid]))
    if endpoint_closure > EPS:
        raise AssertionError("frozen Animation endpoint no longer closes")

    payload = {
        "schema": "axm.object-animation-phase-invariant-hinge-successor-godot-input/v0.1",
        "exact_animation_head": exact_animation_head,
        "asset_id": contract["asset_id"],
        "legacy_host_source_sha256": SOURCE_SHA256,
        "source_successor_head": SUCCESSOR_HEAD,
        "source_successor_blob": SUCCESSOR_BLOB,
        "source_successor_id": successor["successor_id"],
        "rigging_receiver_head": RIGGING_HEAD,
        "rigging_receiver_blob": RIGGING_BLOB,
        "bounded_animation_candidate_adopted": True,
        "production_default_adoption": False,
        "automatic_downstream_adoption": False,
        "sample_rate_hz": 40,
        "duration_s": 2.5,
        "endpoint_inclusive_sample_count": 101,
        "hinge_axis": axis,
        "hinge_origin_m": origin,
        "opening_rotation_sign": -1,
        "rig_angle_limit_deg": [0.0, 110.0],
        "phase_independent_radial_clearance_lower_bound_m": phase_clearance,
        "knuckles": [
            {
                "id": row["id"],
                "owner": row["owner"],
                "expected_parent": "lid_shell" if row["id"] in moving else "body_shell",
                "neutral_witness_m": neutral[row["id"]],
            }
            for row in source_rows
        ],
        "samples": godot_samples,
    }
    receipt = {
        "schema": "axm.object-animation-phase-invariant-hinge-successor-rebind-evidence/v0.1",
        "result": STRUCTURAL_RESULT,
        "exact_animation_head": exact_animation_head,
        "asset_id": contract["asset_id"],
        "legacy_host_source_sha256": SOURCE_SHA256,
        "sequence_id": sequence["sequence_id"],
        "sequence_digest": sequence["sequence_digest"],
        "sample_rate_hz": 40,
        "duration_s": 2.5,
        "endpoint_inclusive_sample_count": 101,
        "maximum_lid_open_angle_deg": max_open,
        "rig_angle_limit_deg": [0, 110],
        "source_successor_head": SUCCESSOR_HEAD,
        "source_successor_blob": SUCCESSOR_BLOB,
        "source_successor_id": successor["successor_id"],
        "rigging_receiver_head": RIGGING_HEAD,
        "rigging_receiver_blob": RIGGING_BLOB,
        "historical_lid_rig_head": LID_RIG_HEAD,
        "lid_rig_plan_digest": LID_PLAN_DIGEST,
        "moving_lid_knuckles": moving,
        "fixed_body_knuckles": fixed,
        "phase_independent_radial_clearance_lower_bound_m": phase_clearance,
        "maximum_animation_to_rig_sign_residual_deg": max_sign_residual,
        "endpoint_parent_motion_closure_m": endpoint_closure,
        "retimed": False,
        "keys_changed": False,
        "easing_changed": False,
        "amplitude_changed": False,
        "source_successor_bounded_animation_proof_consumed": True,
        "production_default_adoption": False,
        "technical_art_target_host_adopted": False,
        "runtime_controller_or_state_machine_accepted": False,
        "physics_or_collision_accepted": False,
        "gameplay_accepted": False,
        "final_visual_motion_accepted": False,
        "canon_or_production_ready": False,
    }
    return payload, receipt


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--contract", type=Path, required=True)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--sequence-evidence", type=Path, required=True)
    p.add_argument("--source-successor", type=Path, required=True)
    p.add_argument("--rigging-compatibility", type=Path, required=True)
    p.add_argument("--lid-plan", type=Path, required=True)
    p.add_argument("--exact-head", required=True)
    p.add_argument("--observed-successor-head", required=True)
    p.add_argument("--observed-successor-blob", required=True)
    p.add_argument("--observed-rigging-head", required=True)
    p.add_argument("--observed-rigging-blob", required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()

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
    (args.out / "godot-input.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (args.out / "structural-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
