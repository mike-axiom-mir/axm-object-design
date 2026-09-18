from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import build_modular_case

CONTRACT_SCHEMA = "axm.object-animation-hinge-knuckle-parent-motion-rebind/v0.1"
RIG_RESULT = "PASS_SOURCE_OWNED_HINGE_KNUCKLE_PARENT_BINDING_CONTINUOUS_0_TO_110"
SEQUENCE_RESULT = "PASS_ORDERED_LATCH_RELEASE_LID_CLIP_REENGAGE_SEQUENCE"
STRUCTURAL_RESULT = "PASS_OBJECT_ANIMATION_HINGE_KNUCKLE_PARENT_MOTION_REBIND_INPUT"
EPS = 1e-9


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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


def validate_parent_partition(source: dict[str, Any], rig_receipt: dict[str, Any]) -> tuple[list[str], list[str]]:
    source_rows = list(source.get("hinge", {}).get("knuckles", []))
    if len(source_rows) != 5:
        raise AssertionError("expected exactly five source hinge knuckles")
    expected_moving = [row["id"] for row in source_rows if row.get("owner") == "lid"]
    expected_fixed = [row["id"] for row in source_rows if row.get("owner") == "body"]
    partition = rig_receipt.get("rig_parent_partition", {})
    moving = list(partition.get("moving_lid_knuckles", []))
    fixed = list(partition.get("fixed_body_knuckles", []))
    if moving != expected_moving:
        raise AssertionError(f"Rigging moving parent partition drift: {moving} != {expected_moving}")
    if fixed != expected_fixed:
        raise AssertionError(f"Rigging fixed parent partition drift: {fixed} != {expected_fixed}")
    if set(moving) & set(fixed) or set(moving) | set(fixed) != {row["id"] for row in source_rows}:
        raise AssertionError("Rigging parent partition does not cover exact source owner stack")
    return moving, fixed


def _validate_preservation(contract: dict[str, Any]) -> None:
    preserve = contract.get("preservation_contract", {})
    for key in (
        "retimed",
        "keys_changed",
        "easing_changed",
        "amplitude_changed",
        "source_geometry_changed",
        "rig_parent_partition_changed",
        "historical_source_replaced",
    ):
        if preserve.get(key) is not False:
            raise AssertionError(f"motion/source preservation boundary drift: {key}")

    truth = contract.get("truth_boundary", {})
    if truth.get("animation_parent_motion_rebind_owned") is not True:
        raise AssertionError("Animation rebind ownership missing")
    for key in (
        "bored_knuckle_successor_adopted",
        "technical_art_target_host_parenting_accepted",
        "runtime_controller_or_state_machine_accepted",
        "physics_or_collision_accepted",
        "gameplay_accepted",
        "final_visual_motion_accepted",
        "canon_or_production_ready",
    ):
        if truth.get(key) is not False:
            raise AssertionError(f"authority inflation: {key}")


def verify(
    contract: dict[str, Any],
    source: dict[str, Any],
    source_sha: str,
    sequence: dict[str, Any],
    rig_receipt: dict[str, Any],
    lid_plan: dict[str, Any],
    known_successor: dict[str, Any],
    *,
    exact_head: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if contract.get("schema") != CONTRACT_SCHEMA:
        raise AssertionError("unsupported Animation hinge-parent rebind contract")
    if contract.get("asset_id") != source.get("asset_id"):
        raise AssertionError("contract/source asset identity drift")
    if contract.get("host_source_sha256") != source_sha:
        raise AssertionError("historical source identity drift")
    _validate_preservation(contract)

    seq_ref = contract.get("animation_sequence", {})
    if sequence.get("result") != SEQUENCE_RESULT:
        raise AssertionError("Animation sequence prerequisite did not pass")
    if sequence.get("asset_id") != source.get("asset_id") or sequence.get("host_source_sha256") != source_sha:
        raise AssertionError("Animation sequence source identity drift")
    if sequence.get("sequence_id") != seq_ref.get("sequence_id"):
        raise AssertionError("Animation sequence ID drift")
    if sequence.get("sequence_digest") != seq_ref.get("sequence_digest"):
        raise AssertionError("Animation sequence digest drift")
    if int(sequence.get("sample_rate_hz", -1)) != int(seq_ref.get("sample_rate_hz", -2)) or int(seq_ref.get("sample_rate_hz", -1)) != 40:
        raise AssertionError("Animation sample rate drift")
    if abs(float(sequence.get("duration_s", -1.0)) - float(seq_ref.get("duration_s", -2.0))) > EPS or float(seq_ref.get("duration_s")) != 2.5:
        raise AssertionError("Animation duration drift")
    samples = list(sequence.get("samples", []))
    if len(samples) != int(seq_ref.get("endpoint_inclusive_sample_count", -1)) or len(samples) != 101:
        raise AssertionError("Animation sample count drift")

    rig_ref = contract.get("rigging_parent_authority", {})
    if rig_receipt.get("result") != rig_ref.get("required_result") or rig_receipt.get("result") != RIG_RESULT:
        raise AssertionError("current Rigging parent prerequisite did not pass")
    if rig_receipt.get("source_sha256") != source_sha:
        raise AssertionError("Rigging historical source identity drift")
    owner_ref = rig_receipt.get("source_owner_stack", {})
    if owner_ref.get("head") != rig_ref.get("source_owner_stack_head") or owner_ref.get("blob") != rig_ref.get("source_owner_stack_blob"):
        raise AssertionError("Rigging source-owner-stack identity drift")
    lid_ref = rig_receipt.get("lid_rig", {})
    if lid_ref.get("head") != rig_ref.get("lid_rig_head"):
        raise AssertionError("Rigging lid donor head drift")
    if lid_ref.get("plan_digest") != rig_ref.get("lid_rig_plan_digest"):
        raise AssertionError("Rigging lid plan digest drift")
    if lid_ref.get("joint_id") != rig_ref.get("joint_id"):
        raise AssertionError("Rigging joint identity drift")

    if lid_plan.get("schema") != "axm.object-articulation-plan/v0.1":
        raise AssertionError("unexpected lid articulation plan schema")
    joint = lid_plan.get("joint", {})
    if joint.get("id") != rig_ref.get("joint_id") or joint.get("axis_source") != "hinge.axis":
        raise AssertionError("lid articulation joint identity drift")
    if joint.get("moving_component") != "lid_shell" or joint.get("fixed_component") != "body_shell":
        raise AssertionError("lid/body component ownership drift")
    if joint.get("opening_rotation_sign") != -1:
        raise AssertionError("opening rotation sign drift")
    if joint.get("angle_limit_deg") != [0, 110]:
        raise AssertionError("lid articulation envelope drift")

    moving, fixed = validate_parent_partition(source, rig_receipt)
    if moving != list(rig_ref.get("moving_lid_knuckles", [])) or fixed != list(rig_ref.get("fixed_body_knuckles", [])):
        raise AssertionError("contract/Rigging knuckle partition drift")

    successor_ref = contract.get("known_unconsumed_source_successor", {})
    if known_successor.get("schema") != successor_ref.get("schema"):
        raise AssertionError("known Hard-Surface successor schema drift")
    if known_successor.get("successor_id") != successor_ref.get("successor_id"):
        raise AssertionError("known Hard-Surface successor identity drift")
    successor_state = known_successor.get("source_owned_successor", {})
    successor_auth = known_successor.get("authority", {})
    if successor_state.get("automatic_downstream_adoption") is not False:
        raise AssertionError("known source successor no longer requires explicit receiver adoption")
    if successor_auth.get("animation_authorized") is not False:
        raise AssertionError("known source successor unexpectedly grants Animation authority")
    if successor_ref.get("animation_authorized") is not False or successor_ref.get("automatic_downstream_adoption") is not False:
        raise AssertionError("Animation contract silently promotes known source successor")
    if successor_ref.get("adopted_by_this_animation_contract") is not False:
        raise AssertionError("Animation contract silently adopted bored-knuckle successor")

    built = build_modular_case.build(source)
    hinge_axis = [float(v) for v in built["hinge_axis"]["axis"]]
    hinge_origin = [float(v) for v in built["hinge_axis"]["origin_m"]]
    if hinge_axis != [1.0, 0.0, 0.0]:
        raise AssertionError("source hinge axis drift")
    radius = float(source["hinge"]["knuckle_radius"])
    source_rows = list(source["hinge"]["knuckles"])
    neutral = {
        row["id"]: [float(row["center_x"]), hinge_origin[1] + radius, hinge_origin[2]]
        for row in source_rows
    }

    max_body_drift = 0.0
    max_lid_radius_residual = 0.0
    max_x_residual = 0.0
    max_angle_sign_residual = 0.0
    max_open_angle = 0.0
    endpoint_drift = 0.0
    moving_nonzero_samples = 0
    godot_samples: list[dict[str, Any]] = []

    for expected_index, row in enumerate(samples):
        if int(row.get("index", -1)) != expected_index:
            raise AssertionError("Animation sample index drift")
        expected_time = expected_index / 40.0
        if abs(float(row.get("time_s")) - expected_time) > 1e-6:
            raise AssertionError("Animation sample time-grid drift")
        open_angle = float(row.get("lid_open_angle_deg"))
        math_angle = float(row.get("lid_mathematical_rotation_deg"))
        sign_expected = float(joint["opening_rotation_sign"]) * open_angle
        max_angle_sign_residual = max(max_angle_sign_residual, abs(math_angle - sign_expected))
        if abs(math_angle - sign_expected) > 1e-9:
            raise AssertionError("Animation mathematical lid rotation no longer follows exact Rigging opening sign")
        if open_angle < -EPS or open_angle > 110.0 + EPS:
            raise AssertionError("Animation lid angle escaped exact Rigging articulation envelope")
        max_open_angle = max(max_open_angle, open_angle)

        expected_positions: dict[str, list[float]] = {}
        for source_row in source_rows:
            kid = source_row["id"]
            base = neutral[kid]
            if kid in moving:
                posed = rotate_x(base, hinge_origin, math_angle)
                radial0 = math.hypot(base[1] - hinge_origin[1], base[2] - hinge_origin[2])
                radial1 = math.hypot(posed[1] - hinge_origin[1], posed[2] - hinge_origin[2])
                max_lid_radius_residual = max(max_lid_radius_residual, abs(radial1 - radial0))
                if open_angle > EPS:
                    moving_nonzero_samples += 1
            else:
                posed = list(base)
                max_body_drift = max(max_body_drift, distance(posed, base))
            max_x_residual = max(max_x_residual, abs(posed[0] - base[0]))
            expected_positions[kid] = [round(float(v), 15) for v in posed]

        godot_samples.append(
            {
                "index": expected_index,
                "time_s": float(row["time_s"]),
                "lid_open_angle_deg": open_angle,
                "lid_mathematical_rotation_deg": math_angle,
                "expected_knuckle_world_positions_m": expected_positions,
            }
        )

    if max_angle_sign_residual > 1e-9 or max_body_drift > EPS or max_lid_radius_residual > EPS or max_x_residual > EPS:
        raise AssertionError("source-rig parent motion invariants drift")
    if moving_nonzero_samples == 0:
        raise AssertionError("Animation never exercises the lid-owned hinge knuckles")
    if abs(max_open_angle - 100.0) > 1e-9:
        raise AssertionError("unexpected unchanged Object lid peak angle")

    for kid in neutral:
        endpoint_drift = max(endpoint_drift, distance(godot_samples[0]["expected_knuckle_world_positions_m"][kid], godot_samples[-1]["expected_knuckle_world_positions_m"][kid]))
    if endpoint_drift > EPS:
        raise AssertionError("hinge knuckle parent motion did not close at Animation endpoint")

    ordered_ids = [row["id"] for row in source_rows]
    ordered_owners = [row["owner"] for row in source_rows]
    payload = {
        "schema": "axm.object-animation-hinge-knuckle-parent-motion-godot-input/v0.1",
        "exact_animation_head": exact_head,
        "asset_id": source["asset_id"],
        "host_source_sha256": source_sha,
        "rigging_parent_head": rig_ref["exact_head"],
        "rigging_parent_result": rig_receipt["result"],
        "known_unconsumed_hard_surface_successor_head": successor_ref["hard_surface_head"],
        "bored_knuckle_successor_adopted": False,
        "sample_rate_hz": 40,
        "duration_s": 2.5,
        "endpoint_inclusive_sample_count": 101,
        "hinge_axis": hinge_axis,
        "hinge_origin_m": hinge_origin,
        "opening_rotation_sign": int(joint["opening_rotation_sign"]),
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
        "schema": "axm.object-animation-hinge-knuckle-parent-motion-rebind-evidence/v0.1",
        "result": STRUCTURAL_RESULT,
        "exact_animation_head": exact_head,
        "asset_id": source["asset_id"],
        "host_source_sha256": source_sha,
        "sequence_id": sequence["sequence_id"],
        "sequence_digest": sequence["sequence_digest"],
        "sample_rate_hz": 40,
        "duration_s": 2.5,
        "endpoint_inclusive_sample_count": 101,
        "rigging_parent_head": rig_ref["exact_head"],
        "rigging_parent_result": rig_receipt["result"],
        "source_owner_stack_head": owner_ref["head"],
        "source_owner_stack_blob": owner_ref["blob"],
        "lid_rig_head": lid_ref["head"],
        "lid_rig_plan_digest": lid_ref["plan_digest"],
        "ordered_knuckle_ids": ordered_ids,
        "ordered_knuckle_owners": ordered_owners,
        "moving_lid_knuckles": moving,
        "fixed_body_knuckles": fixed,
        "maximum_lid_open_angle_deg": max_open_angle,
        "maximum_body_knuckle_drift_m": max_body_drift,
        "maximum_lid_knuckle_radius_residual_m": max_lid_radius_residual,
        "maximum_axial_x_residual_m": max_x_residual,
        "maximum_animation_to_rig_sign_residual_deg": max_angle_sign_residual,
        "endpoint_parent_motion_closure_m": endpoint_drift,
        "known_unconsumed_hard_surface_successor_head": successor_ref["hard_surface_head"],
        "known_unconsumed_successor_adopted": False,
        "motion_preservation": dict(contract["preservation_contract"]),
        "truth_boundary": dict(contract["truth_boundary"]),
    }
    return receipt, payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--sequence-evidence", required=True, type=Path)
    parser.add_argument("--rigging-receipt", required=True, type=Path)
    parser.add_argument("--lid-plan", required=True, type=Path)
    parser.add_argument("--known-successor", required=True, type=Path)
    parser.add_argument("--exact-head", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    source = load_json(args.source)
    receipt, payload = verify(
        load_json(args.contract),
        source,
        sha256_file(args.source),
        load_json(args.sequence_evidence),
        load_json(args.rigging_receipt),
        load_json(args.lid_plan),
        load_json(args.known_successor),
        exact_head=args.exact_head,
    )
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "structural-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    (args.out / "godot-input.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
