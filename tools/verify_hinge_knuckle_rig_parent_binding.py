from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_modular_case

SCHEMA = "axm.object-hinge-knuckle-rig-parent-binding/v0.1"
RESULT = "PASS_SOURCE_OWNED_HINGE_KNUCKLE_PARENT_BINDING_CONTINUOUS_0_TO_110"
SOURCE_SHA256 = "49b1f9ed9865893d6de6f1ec8f069576732df694853fde4e3fcff366de32644a"
OWNER_STACK_HEAD = "172dd9ff5ed1fee3a21cd460c607f07ee0da7520"
OWNER_STACK_BLOB = "e4e7c95769c0827a6a019afd672ff4b20cd13541"
LID_RIG_HEAD = "4b72c9918c5fc1e89bd18a0be24fb4afac6e7775"
PREVIOUS_RIGGING_HEAD = "9d5fb18d8eb2222694e86025641256a30f57c485"
LID_PLAN_DIGEST = "0ad6dc2ca22676cf301579932e599a441eb7c4bccce31991d1b727aeb22ac422"
TOL = 1e-12


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _dist(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((float(a[i]) - float(b[i])) ** 2 for i in range(3)))


def _rotate_about_x(point: list[float], origin: list[float], angle_deg: float) -> list[float]:
    x, y, z = map(float, point)
    ox, oy, oz = map(float, origin)
    y -= oy
    z -= oz
    a = math.radians(angle_deg)
    c, s = math.cos(a), math.sin(a)
    return [x, oy + y * c - z * s, oz + y * s + z * c]


def _assert_close(actual: float, expected: float, label: str) -> None:
    if abs(float(actual) - float(expected)) > TOL:
        raise AssertionError(f"{label} drift: {actual} != {expected}")


def _assert_false_authority(contract: dict[str, Any]) -> None:
    authority = contract.get("authority", {})
    for key in (
        "source_geometry_changed",
        "rig_parenting_authorized",
        "animation_authorized",
        "physical_retention_claimed",
        "load_capacity_claimed",
        "manufacturing_fit_claimed",
    ):
        if authority.get(key) is not False:
            raise AssertionError(f"source-owner authority drift: {key}")


def verify(
    source: dict[str, Any],
    owner_stack: dict[str, Any],
    lid_plan: dict[str, Any],
    *,
    source_sha256: str,
    observed_owner_stack_head: str,
    observed_owner_stack_blob: str,
    observed_lid_rig_head: str,
    observed_previous_rigging_head: str,
) -> dict[str, Any]:
    if source_sha256 != SOURCE_SHA256:
        raise AssertionError("exact Object source byte identity drift")
    if observed_owner_stack_head != OWNER_STACK_HEAD:
        raise AssertionError("hinge owner-stack source-owner head drift")
    if observed_owner_stack_blob != OWNER_STACK_BLOB:
        raise AssertionError("hinge owner-stack source-owner blob drift")
    if observed_lid_rig_head != LID_RIG_HEAD:
        raise AssertionError("historical lid articulation donor head drift")
    if observed_previous_rigging_head != PREVIOUS_RIGGING_HEAD:
        raise AssertionError("previous Rigging head drift")

    if owner_stack.get("schema") != "axm.object-hinge-knuckle-owner-stack/v0.1":
        raise AssertionError("unexpected hinge owner-stack schema")
    if owner_stack.get("contract_id") != "modular-equipment-case-001-hinge-knuckle-owner-stack-001":
        raise AssertionError("hinge owner-stack contract identity drift")
    if owner_stack.get("asset_id") != source.get("asset_id"):
        raise AssertionError("owner-stack asset identity drift")
    if owner_stack.get("host_source_sha256") != SOURCE_SHA256:
        raise AssertionError("owner-stack source identity drift")
    if owner_stack.get("hinge_axis") != [1, 0, 0]:
        raise AssertionError("owner-stack hinge axis drift")
    _assert_false_authority(owner_stack)

    if lid_plan.get("schema") != "axm.object-articulation-plan/v0.1":
        raise AssertionError("unexpected lid articulation plan schema")
    if lid_plan.get("asset_id") != source.get("asset_id") or lid_plan.get("source_sha256") != SOURCE_SHA256:
        raise AssertionError("lid articulation source identity drift")
    if digest(lid_plan) != LID_PLAN_DIGEST:
        raise AssertionError("lid articulation plan digest drift")

    joint = lid_plan.get("joint", {})
    if joint.get("id") != "rear-lid-hinge-001":
        raise AssertionError("lid joint identity drift")
    if joint.get("axis_source") != "hinge.axis":
        raise AssertionError("lid joint axis-source drift")
    if joint.get("moving_component") != "lid_shell" or joint.get("fixed_component") != "body_shell":
        raise AssertionError("lid joint owner components drift")
    if joint.get("opening_rotation_sign") != -1:
        raise AssertionError("lid articulation sign drift")
    if joint.get("angle_limit_deg") != [0, 110]:
        raise AssertionError("lid articulation envelope drift")
    if joint.get("sweep_step_deg") != 1:
        raise AssertionError("lid articulation sampled cross-check step drift")

    hinge = source.get("hinge", {})
    if hinge.get("axis") != [1, 0, 0]:
        raise AssertionError("source hinge axis drift")
    source_rows = sorted(hinge.get("knuckles", []), key=lambda row: float(row["center_x"]))
    contract_rows = owner_stack.get("ordered_knuckles", [])
    if len(source_rows) != 5 or len(contract_rows) != 5:
        raise AssertionError("bounded proof requires exactly five hinge knuckles")

    expected_order = [{"id": row["id"], "owner": row["owner"]} for row in source_rows]
    if contract_rows != expected_order:
        raise AssertionError("source/owner-stack knuckle identity drift")

    moving_from_owner = [row["id"] for row in contract_rows if row["owner"] == "lid"]
    fixed_from_owner = [row["id"] for row in contract_rows if row["owner"] == "body"]
    moving_from_rig = list(joint.get("coaxial_moving_knuckles", []))
    if moving_from_rig != moving_from_owner:
        raise AssertionError(
            f"source-owned lid knuckles do not match rig moving-knuckle set: {moving_from_owner} != {moving_from_rig}"
        )
    if set(moving_from_rig) & set(fixed_from_owner):
        raise AssertionError("body-owned knuckle entered moving rig set")
    if set(moving_from_rig) | set(fixed_from_owner) != {row["id"] for row in contract_rows}:
        raise AssertionError("rig parent partition does not cover exact source owner stack")

    expected_length = float(owner_stack["expected_knuckle_length_m"])
    expected_pitch = float(owner_stack["expected_center_pitch_m"])
    expected_gap = float(owner_stack["expected_inter_knuckle_gap_m"])
    minimum_clearance = float(owner_stack["minimum_source_axial_clearance_m"])

    intervals: list[dict[str, Any]] = []
    for row in source_rows:
        center = float(row["center_x"])
        length = float(row["length"])
        _assert_close(length, expected_length, f"knuckle length {row['id']}")
        intervals.append(
            {
                "id": row["id"],
                "owner": row["owner"],
                "center_x_m": center,
                "x_min_m": center - length / 2.0,
                "x_max_m": center + length / 2.0,
                "length_m": length,
                "rig_parent": "lid_shell" if row["owner"] == "lid" else "body_shell",
                "moves_with_lid": row["id"] in moving_from_rig,
            }
        )

    gaps: list[float] = []
    pitches: list[float] = []
    for left, right in zip(intervals, intervals[1:]):
        pitch = right["center_x_m"] - left["center_x_m"]
        gap = right["x_min_m"] - left["x_max_m"]
        _assert_close(pitch, expected_pitch, f"center pitch {left['id']}->{right['id']}")
        _assert_close(gap, expected_gap, f"axial gap {left['id']}->{right['id']}")
        if gap < minimum_clearance - TOL:
            raise AssertionError(f"source minimum axial clearance violated: {left['id']}->{right['id']}")
        pitches.append(pitch)
        gaps.append(gap)

    built = build_modular_case.build(source)
    hinge_origin = [float(v) for v in built["hinge_axis"]["origin_m"]]
    if [float(v) for v in built["hinge_axis"]["axis"]] != [1.0, 0.0, 0.0]:
        raise AssertionError("built hinge axis drift")
    radius = float(hinge["knuckle_radius"])
    if radius <= 0.0:
        raise AssertionError("knuckle radius must remain positive")

    representative_angles = [0, 30, 60, 90, 110]
    witnesses: list[dict[str, Any]] = []
    max_axial_center_residual = 0.0
    max_axial_interval_residual = 0.0
    max_moving_radius_residual = 0.0
    max_inverse_recovery_residual = 0.0
    max_fixed_point_drift = 0.0

    for angle in representative_angles:
        applied = float(joint["opening_rotation_sign"]) * float(angle)
        pose_rows: list[dict[str, Any]] = []
        for row in intervals:
            neutral_point = [row["center_x_m"], hinge_origin[1] + radius, hinge_origin[2]]
            if row["moves_with_lid"]:
                posed_point = _rotate_about_x(neutral_point, hinge_origin, applied)
                recovered = _rotate_about_x(posed_point, hinge_origin, -applied)
                radial_neutral = math.hypot(neutral_point[1] - hinge_origin[1], neutral_point[2] - hinge_origin[2])
                radial_posed = math.hypot(posed_point[1] - hinge_origin[1], posed_point[2] - hinge_origin[2])
                max_moving_radius_residual = max(max_moving_radius_residual, abs(radial_posed - radial_neutral))
                max_inverse_recovery_residual = max(max_inverse_recovery_residual, _dist(recovered, neutral_point))
            else:
                posed_point = list(neutral_point)
                max_fixed_point_drift = max(max_fixed_point_drift, _dist(posed_point, neutral_point))

            center_residual = abs(float(posed_point[0]) - row["center_x_m"])
            interval_min = float(posed_point[0]) - row["length_m"] / 2.0
            interval_max = float(posed_point[0]) + row["length_m"] / 2.0
            interval_residual = max(abs(interval_min - row["x_min_m"]), abs(interval_max - row["x_max_m"]))
            max_axial_center_residual = max(max_axial_center_residual, center_residual)
            max_axial_interval_residual = max(max_axial_interval_residual, interval_residual)
            pose_rows.append(
                {
                    "id": row["id"],
                    "owner": row["owner"],
                    "rig_parent": row["rig_parent"],
                    "moves_with_lid": row["moves_with_lid"],
                    "source_angle_deg": angle,
                    "applied_rig_angle_deg": applied if row["moves_with_lid"] else 0.0,
                    "witness_point_m": posed_point,
                    "x_interval_m": [interval_min, interval_max],
                }
            )
        witnesses.append({"source_angle_deg": angle, "applied_lid_angle_deg": applied, "knuckles": pose_rows})

    for label, value in (
        ("axial center residual", max_axial_center_residual),
        ("axial interval residual", max_axial_interval_residual),
        ("moving radial residual", max_moving_radius_residual),
        ("moving inverse recovery residual", max_inverse_recovery_residual),
        ("fixed point drift", max_fixed_point_drift),
    ):
        if value > TOL:
            raise AssertionError(f"{label} exceeds tolerance: {value}")

    # Continuous certificate: every permitted moving knuckle is transformed only by a
    # rotation about exact +X. Such a rotation leaves x unchanged for every real angle,
    # while body-owned knuckles remain identity-transformed. Therefore each axial
    # interval, pitch, gap, owner order and body/lid/body/lid/body interleave is invariant
    # on the complete closed real interval [0, 110], not merely at the sampled witnesses.
    continuous_certificate = {
        "kind": "ANALYTIC_AXIS_INVARIANCE",
        "domain_deg": [0.0, 110.0],
        "axis": [1.0, 0.0, 0.0],
        "moving_transform": "lid-owned l0/l1 rotate about exact source +X hinge axis with articulation opening_rotation_sign",
        "fixed_transform": "body-owned b0/b1/b2 remain body_shell-local identity",
        "invariant_coordinate": "x",
        "invariant_owner_sequence": [row["owner"] for row in intervals],
        "invariant_adjacent_gaps_m": gaps,
        "minimum_invariant_gap_m": min(gaps),
        "source_minimum_axial_clearance_m": minimum_clearance,
        "minimum_clearance_surplus_m": min(gaps) - minimum_clearance,
        "proof_scope": "axial owner-stack/parent partition only; not radial bore, contact, force, retention or collision proof",
    }

    return {
        "schema": SCHEMA,
        "result": RESULT,
        "asset_id": source["asset_id"],
        "source_sha256": SOURCE_SHA256,
        "source_owner_stack": {
            "head": OWNER_STACK_HEAD,
            "blob": OWNER_STACK_BLOB,
            "contract_id": owner_stack["contract_id"],
        },
        "lid_rig": {
            "head": LID_RIG_HEAD,
            "plan_digest": LID_PLAN_DIGEST,
            "joint_id": joint["id"],
            "opening_rotation_sign": joint["opening_rotation_sign"],
            "angle_limit_deg": joint["angle_limit_deg"],
        },
        "predecessor_rigging_head": PREVIOUS_RIGGING_HEAD,
        "rig_parent_partition": {
            "moving_lid_knuckles": moving_from_rig,
            "fixed_body_knuckles": fixed_from_owner,
            "ordered_knuckles": intervals,
        },
        "representative_pose_witnesses": witnesses,
        "continuous_certificate": continuous_certificate,
        "metrics": {
            "max_axial_center_residual_m": max_axial_center_residual,
            "max_axial_interval_residual_m": max_axial_interval_residual,
            "max_moving_radius_residual_m": max_moving_radius_residual,
            "max_moving_inverse_recovery_residual_m": max_inverse_recovery_residual,
            "max_fixed_body_knuckle_point_drift_m": max_fixed_point_drift,
            "minimum_adjacent_gap_m": min(gaps),
            "minimum_center_pitch_m": min(pitches),
        },
        "truth_boundary": {
            "source_geometry_changed": False,
            "source_owner_semantics_changed": False,
            "rig_joint_or_range_changed": False,
            "animation_accepted": False,
            "technical_art_target_host_parenting_accepted": False,
            "runtime_accepted": False,
            "physical_pin_retention_or_load_accepted": False,
            "full_component_collision_accepted": False,
            "manufacturing_fit_accepted": False,
            "visual_acceptance": False,
            "canon": False,
            "production_ready": False,
        },
    }


def _negative_controls(
    source: dict[str, Any], owner_stack: dict[str, Any], lid_plan: dict[str, Any], source_sha256: str
) -> dict[str, str]:
    base_kwargs = dict(
        source_sha256=source_sha256,
        observed_owner_stack_head=OWNER_STACK_HEAD,
        observed_owner_stack_blob=OWNER_STACK_BLOB,
        observed_lid_rig_head=LID_RIG_HEAD,
        observed_previous_rigging_head=PREVIOUS_RIGGING_HEAD,
    )
    out: dict[str, str] = {}

    bad = copy.deepcopy(owner_stack)
    bad["ordered_knuckles"][1]["owner"] = "body"
    try:
        verify(source, bad, lid_plan, **base_kwargs)
    except AssertionError as exc:
        out["owner_label_drift"] = f"HOLD:{exc}"
    else:
        raise AssertionError("owner-label drift unexpectedly passed")

    bad_plan = copy.deepcopy(lid_plan)
    bad_plan["joint"]["coaxial_moving_knuckles"] = ["l0", "b1", "l1"]
    try:
        verify(source, owner_stack, bad_plan, **base_kwargs)
    except AssertionError as exc:
        out["body_knuckle_added_to_moving_set"] = f"HOLD:{exc}"
    else:
        raise AssertionError("body-owned moving-knuckle mutation unexpectedly passed")

    bad_plan = copy.deepcopy(lid_plan)
    bad_plan["joint"]["coaxial_moving_knuckles"] = ["l0"]
    try:
        verify(source, owner_stack, bad_plan, **base_kwargs)
    except AssertionError as exc:
        out["lid_knuckle_missing_from_moving_set"] = f"HOLD:{exc}"
    else:
        raise AssertionError("missing lid-owned moving knuckle unexpectedly passed")

    bad_contract = copy.deepcopy(owner_stack)
    bad_contract["authority"]["rig_parenting_authorized"] = True
    try:
        verify(source, bad_contract, lid_plan, **base_kwargs)
    except AssertionError as exc:
        out["source_authority_inflation"] = f"HOLD:{exc}"
    else:
        raise AssertionError("source authority inflation unexpectedly passed")

    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--owner-stack", required=True)
    parser.add_argument("--lid-plan", required=True)
    parser.add_argument("--observed-owner-stack-head", required=True)
    parser.add_argument("--observed-owner-stack-blob", required=True)
    parser.add_argument("--observed-lid-rig-head", required=True)
    parser.add_argument("--observed-previous-rigging-head", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    source_path = Path(args.source)
    owner_path = Path(args.owner_stack)
    plan_path = Path(args.lid_plan)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    source = json.loads(source_path.read_text(encoding="utf-8"))
    owner_stack = json.loads(owner_path.read_text(encoding="utf-8"))
    lid_plan = json.loads(plan_path.read_text(encoding="utf-8"))
    source_sha = sha256_file(source_path)

    receipt = verify(
        source,
        owner_stack,
        lid_plan,
        source_sha256=source_sha,
        observed_owner_stack_head=args.observed_owner_stack_head,
        observed_owner_stack_blob=args.observed_owner_stack_blob,
        observed_lid_rig_head=args.observed_lid_rig_head,
        observed_previous_rigging_head=args.observed_previous_rigging_head,
    )
    receipt["owner_stack_file_sha256"] = sha256_file(owner_path)
    receipt["negative_controls"] = _negative_controls(source, owner_stack, lid_plan, source_sha)

    (out / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(RESULT)
    print(
        json.dumps(
            {
                "moving_lid_knuckles": receipt["rig_parent_partition"]["moving_lid_knuckles"],
                "fixed_body_knuckles": receipt["rig_parent_partition"]["fixed_body_knuckles"],
                "continuous_domain_deg": receipt["continuous_certificate"]["domain_deg"],
                "minimum_invariant_gap_m": receipt["continuous_certificate"]["minimum_invariant_gap_m"],
                "minimum_clearance_surplus_m": receipt["continuous_certificate"]["minimum_clearance_surplus_m"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
