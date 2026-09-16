from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA = "axm.object-target-lid-rig-binding/v0.1"
TECH_ART_HEAD = "965fb2f24dbd0b0cbb748d9f8b8712d62966315f"
LID_RIG_HEAD = "4b72c9918c5fc1e89bd18a0be24fb4afac6e7775"
UC_HEAD = "6dc465987e01362264f88b7cef4213609ae50763"
SOURCE_SHA256 = "49b1f9ed9865893d6de6f1ec8f069576732df694853fde4e3fcff366de32644a"
LID_RIG_PLAN_FILE_SHA256 = "05b4daad475c30f4c1ea72826fbafd452bf037e58523e18a0c338dd0d7999c0a"
LID_RIG_PLAN_CANONICAL_SHA256 = "0ad6dc2ca22676cf301579932e599a441eb7c4bccce31991d1b727aeb22ac422"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_json_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _as_floats(values: Any) -> list[float]:
    return [float(value) for value in values]


def build_binding(
    source_path: Path,
    lid_rig_plan_path: Path,
    tech_receipt_path: Path,
    rebound_glb_path: Path,
    out_path: Path,
) -> dict[str, Any]:
    observed_source_sha = sha256_file(source_path)
    if observed_source_sha != SOURCE_SHA256:
        raise AssertionError(f"Object source identity drift: {observed_source_sha}")

    observed_plan_file_sha = sha256_file(lid_rig_plan_path)
    if observed_plan_file_sha != LID_RIG_PLAN_FILE_SHA256:
        raise AssertionError(f"lid rig plan byte identity drift: {observed_plan_file_sha}")

    plan = json.loads(lid_rig_plan_path.read_text(encoding="utf-8"))
    observed_plan_canonical_sha = canonical_json_sha256(plan)
    if observed_plan_canonical_sha != LID_RIG_PLAN_CANONICAL_SHA256:
        raise AssertionError(f"lid rig plan canonical identity drift: {observed_plan_canonical_sha}")

    tech = json.loads(tech_receipt_path.read_text(encoding="utf-8"))

    if plan.get("schema") != "axm.object-articulation-plan/v0.1":
        raise AssertionError("unexpected lid rig schema")
    if plan.get("asset_id") != "modular-equipment-case-001":
        raise AssertionError("lid rig asset identity mismatch")
    if plan.get("source_sha256") != observed_source_sha:
        raise AssertionError("lid rig is not bound to the exact current Object source")

    joint = plan.get("joint", {})
    if joint.get("id") != "rear-lid-hinge-001":
        raise AssertionError("unexpected lid joint identity")
    if joint.get("axis_source") != "hinge.axis":
        raise AssertionError("lid rig no longer binds the source hinge axis")
    if joint.get("moving_component") != "lid_shell" or joint.get("fixed_component") != "body_shell":
        raise AssertionError("lid rig moving/fixed component identity drift")
    if int(joint.get("opening_rotation_sign", 0)) != -1:
        raise AssertionError("bounded target binding expects the exact source opening sign -1")
    if _as_floats(joint.get("angle_limit_deg", [])) != [0.0, 110.0]:
        raise AssertionError("lid rig angle limit drift")
    representative_source_angles = _as_floats(joint.get("representative_angles_deg", []))
    if representative_source_angles != [0.0, 30.0, 60.0, 90.0, 110.0]:
        raise AssertionError("lid rig representative pose identity drift")

    if tech.get("schema") != "axm.object-uc-rigid-scene-handoff/v0.1":
        raise AssertionError("unexpected Technical Art receipt schema")
    if tech.get("result") != "PASS_OBJECT_SOURCE_OWNED_RIGID_PARTS_THROUGH_UC_SCENE_GRAPH":
        raise AssertionError("Technical Art rigid-scene prerequisite is not green")
    if tech.get("source_repository_head") != TECH_ART_HEAD:
        raise AssertionError("Technical Art donor head drift")
    if tech.get("source_sha256") != observed_source_sha:
        raise AssertionError("Technical Art donor source identity drift")
    if tech.get("observed_uc_commit") != UC_HEAD:
        raise AssertionError("Technical Art UC donor identity drift")
    observed_glb_sha = sha256_file(rebound_glb_path)
    if tech.get("rebound_glb_sha256") != observed_glb_sha:
        raise AssertionError("rebound GLB does not match exact Technical Art receipt")
    if tech.get("binary_geometry_payload_identical") is not True:
        raise AssertionError("Technical Art donor did not preserve binary geometry payload")

    pivot_source = _as_floats(tech.get("hinge_pivot_source_m", []))
    pivot_target = _as_floats(tech.get("hinge_pivot_uc_m", []))
    if len(pivot_source) != 3 or len(pivot_target) != 3:
        raise AssertionError("Technical Art donor lacks exact hinge pivot")
    expected_target_pivot = [pivot_source[0], pivot_source[2], pivot_source[1]]
    if max(abs(pivot_target[i] - expected_target_pivot[i]) for i in range(3)) > 1e-12:
        raise AssertionError("source -> UC hinge pivot mapping drift")

    # Object source space is Z-up and the UC/glTF handoff maps [x,y,z] -> [x,z,y].
    # That map has negative determinant, so the exact source -X opening sign becomes
    # a +X target rotation. This is a coordinate conversion, not a retimed/reauthored rig.
    source_opening_sign = int(joint["opening_rotation_sign"])
    target_x_rotation_sign = -source_opening_sign
    representative_target_angles = [target_x_rotation_sign * angle for angle in representative_source_angles]
    target_angle_limit = [
        target_x_rotation_sign * float(joint["angle_limit_deg"][0]),
        target_x_rotation_sign * float(joint["angle_limit_deg"][1]),
    ]

    lid_owned_children = list(tech.get("lid_owned_children", []))
    keepers = list(tech.get("source_owned_keeper_children", []))
    fixed_levers = list(tech.get("source_owned_fixed_levers", []))
    if sorted(keepers) != ["latch_0_keeper", "latch_1_keeper"]:
        raise AssertionError("keeper identity drift")
    if sorted(fixed_levers) != ["latch_0_lever", "latch_1_lever"]:
        raise AssertionError("lever identity drift")
    if not all(name in lid_owned_children for name in keepers):
        raise AssertionError("source-owned keepers are not retained lid children")

    binding = {
        "schema": SCHEMA,
        "result": "PASS_EXACT_LID_RIG_TO_UC_TARGET_BINDING_READY",
        "asset_id": "modular-equipment-case-001",
        "source_sha256": observed_source_sha,
        "source_repository": "mike-axiom-mir/axm-object-design",
        "technical_art_donor_head": TECH_ART_HEAD,
        "technical_art_receipt_sha256": sha256_file(tech_receipt_path),
        "technical_art_rebound_glb_sha256": observed_glb_sha,
        "uc_donor_head": UC_HEAD,
        "lid_rig_donor_head": LID_RIG_HEAD,
        "lid_rig_plan_file_sha256": observed_plan_file_sha,
        "lid_rig_plan_canonical_sha256": observed_plan_canonical_sha,
        "joint_id": joint["id"],
        "source_axis": [1.0, 0.0, 0.0],
        "source_opening_rotation_sign": source_opening_sign,
        "source_to_target_coordinate_map": "[x,y,z] -> [x,z,y] / determinant -1",
        "target_axis": [1.0, 0.0, 0.0],
        "target_x_rotation_sign": target_x_rotation_sign,
        "hinge_pivot_source_m": pivot_source,
        "hinge_pivot_target_m": pivot_target,
        "source_angle_limit_deg": _as_floats(joint["angle_limit_deg"]),
        "target_angle_limit_deg": target_angle_limit,
        "representative_source_angles_deg": representative_source_angles,
        "representative_target_angles_deg": representative_target_angles,
        "moving_component": "lid_shell",
        "fixed_component": "body_shell",
        "lid_owned_children": lid_owned_children,
        "source_owned_keeper_children": keepers,
        "source_owned_fixed_levers": fixed_levers,
        "failure_policy": "FAIL_CLOSED_ON_SOURCE_RIG_TECH_ART_UC_GLB_COORDINATE_OR_IDENTITY_SEMANTICS_DRIFT",
        "truth_boundary": {
            "exact_source_identity_pinned": True,
            "exact_lid_rig_file_byte_identity_pinned": True,
            "exact_lid_rig_canonical_semantic_identity_pinned": True,
            "exact_technical_art_target_identity_pinned": True,
            "coordinate_handedness_conversion_explicit": True,
            "animation_timing_or_clip_acceptance": False,
            "runtime_controller_or_state_machine_acceptance": False,
            "collision_physics_or_gameplay_acceptance": False,
            "final_visual_acceptance": False,
        },
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return binding


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="assets/modular-equipment-case-001/source.json")
    parser.add_argument("--lid-rig-plan", required=True)
    parser.add_argument("--tech-receipt", required=True)
    parser.add_argument("--rebound-glb", required=True)
    parser.add_argument("--out", default="rig-envelope-proof/generated/target-lid-rig-binding.json")
    args = parser.parse_args()
    result = build_binding(
        Path(args.source).resolve(),
        Path(args.lid_rig_plan).resolve(),
        Path(args.tech_receipt).resolve(),
        Path(args.rebound_glb).resolve(),
        Path(args.out).resolve(),
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
