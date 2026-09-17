from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA = "axm.object-target-front-latch-rig-binding/v0.2"
RESULT = "PASS_SOURCE_OWNED_FRONT_LATCH_CAPTURE_ENVELOPE_TO_UC_TARGET_BINDING_READY"
SOURCE_RIG_HEAD = "3a17a02528918ec63a46e954e883179f752c8151"
SOURCE_RIG_BINDING_BLOB = "0331d30528f58d353fa9396d7ca129a020e8c6ce"
SOURCE_MECHANICAL_AUTHORITY_HEAD = "56aaaecb45b520fdff9e08fe2d4ea42562f5690f"
SOURCE_INTERFACE_SHA256 = "bcbbe098371eb702bc9289a97370744093105925202eda6036bdced6e25e34d3"
SOURCE_CAPTURE_BLOB = "b96df9c5469dffb20e674edd4b176941eda81b8e"
PRIOR_RIGGING_HEAD = "a1acd2bcb2074f41e536562f2673508e2cb0a4d5"
TECH_ART_HEAD = "965fb2f24dbd0b0cbb748d9f8b8712d62966315f"
UC_HEAD = "6dc465987e01362264f88b7cef4213609ae50763"
SOURCE_SHA256 = "49b1f9ed9865893d6de6f1ec8f069576732df694853fde4e3fcff366de32644a"
EXPECTED_SOURCE_ANGLES = [0.0, 9.25, 9.30, 25.0, 48.65, 48.70, 50.0]
EXPECTED_CAPTURE_BRACKET = [9.25, 9.30]
EXPECTED_Z_AABB_BRACKET = [48.65, 48.70]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_to_target(point: list[float] | tuple[float, float, float]) -> list[float]:
    x, y, z = [float(value) for value in point]
    return [x, z, y]


def _float_list(values: Any) -> list[float]:
    return [float(value) for value in values]


def _mapped_bracket(values: list[float]) -> list[float]:
    return [-float(values[1]), -float(values[0])]


def build_binding(
    source_rig_binding_path: Path,
    source_interface_path: Path,
    tech_receipt_path: Path,
    rebound_glb_path: Path,
    out_path: Path,
    *,
    observed_source_rig_head: str,
    observed_tech_art_head: str,
    observed_uc_head: str,
) -> dict[str, Any]:
    if observed_source_rig_head != SOURCE_RIG_HEAD:
        raise AssertionError(f"source Rigging donor head drift: {observed_source_rig_head}")
    if observed_tech_art_head != TECH_ART_HEAD:
        raise AssertionError(f"Technical Art donor head drift: {observed_tech_art_head}")
    if observed_uc_head != UC_HEAD:
        raise AssertionError(f"UC donor head drift: {observed_uc_head}")

    source_binding = json.loads(source_rig_binding_path.read_text(encoding="utf-8"))
    interface = json.loads(source_interface_path.read_text(encoding="utf-8"))
    tech = json.loads(tech_receipt_path.read_text(encoding="utf-8"))

    if source_binding.get("schema") != "axm.object-front-latch-source-rig-binding/v0.2":
        raise AssertionError("unexpected source Rigging binding schema")
    if source_binding.get("binding_id") != "front-latch-source-rig-binding-003":
        raise AssertionError("source Rigging binding identity drift")
    if source_binding.get("asset_id") != "modular-equipment-case-001":
        raise AssertionError("source Rigging asset identity drift")
    if source_binding.get("host_source_sha256") != SOURCE_SHA256:
        raise AssertionError("source Rigging host source identity drift")

    mechanical = source_binding.get("source_mechanical_authority", {})
    if mechanical.get("head") != SOURCE_MECHANICAL_AUTHORITY_HEAD:
        raise AssertionError("source mechanical authority head drift")
    if mechanical.get("role") != "CURRENT_SOURCE_PIVOT_AND_PROOF_VOLUME_CAPTURE_AUTHORITY":
        raise AssertionError("source mechanical authority role drift")
    pivot_ref = mechanical.get("pivot_interface", {})
    if pivot_ref.get("path") != "assets/modular-equipment-case-001/front-latch-pivot-interface-001.json":
        raise AssertionError("source pivot-interface path drift")
    if pivot_ref.get("sha256") != SOURCE_INTERFACE_SHA256:
        raise AssertionError("source pivot-interface declared identity drift")
    capture_ref = mechanical.get("capture_envelope", {})
    if capture_ref.get("git_blob_sha") != SOURCE_CAPTURE_BLOB:
        raise AssertionError("source capture-envelope blob drift")
    if capture_ref.get("required_result") != "PASS_SOURCE_OWNED_FRONT_LATCH_CAPTURE_TO_CLEARANCE_ENVELOPE":
        raise AssertionError("source capture-envelope authority result drift")

    prior = source_binding.get("prior_rigging_binding", {})
    if prior.get("head") != PRIOR_RIGGING_HEAD:
        raise AssertionError("prior Rigging lineage drift")
    if prior.get("role") != "HISTORICAL_PRE_CAPTURE_ENVELOPE_CLASSIFICATION":
        raise AssertionError("historical pre-capture Rigging binding was re-promoted")
    if source_binding.get("historical_rigging_observation", {}).get("role") != "PROVENANCE_ONLY_NOT_CURRENT_INTERFACE_AUTHORITY":
        raise AssertionError("historical Rigging observation was re-promoted")

    if _float_list(source_binding.get("joint_axis", [])) != [1.0, 0.0, 0.0]:
        raise AssertionError("source Rigging joint axis drift")
    source_angles = _float_list(source_binding.get("pose_samples_deg", []))
    if source_angles != EXPECTED_SOURCE_ANGLES:
        raise AssertionError("source Rigging representative boundary-pose schedule drift")
    capture_bracket = _float_list(source_binding.get("required_capture_transition_bracket_deg", []))
    z_aabb_bracket = _float_list(source_binding.get("required_z_aabb_only_transition_bracket_deg", []))
    if capture_bracket != EXPECTED_CAPTURE_BRACKET:
        raise AssertionError("source proof-volume capture bracket drift")
    if z_aabb_bracket != EXPECTED_Z_AABB_BRACKET:
        raise AssertionError("source Z-AABB broad-phase bracket drift")
    if capture_bracket == z_aabb_bracket:
        raise AssertionError("source capture and Z-AABB broad-phase brackets were collapsed")
    if float(source_binding.get("required_minimum_threshold_separation_deg", 0.0)) < 39.0:
        raise AssertionError("source capture/broad-phase threshold separation weakened")
    semantics = source_binding.get("capture_semantics", {})
    if semantics.get("z_aabb_transition") != "BROAD_PHASE_AXIS_SEPARATION_ONLY_NOT_CAPTURE_THRESHOLD":
        raise AssertionError("source Z-AABB broad-phase semantics drift")

    observed_interface_sha = sha256_file(source_interface_path)
    if observed_interface_sha != SOURCE_INTERFACE_SHA256:
        raise AssertionError("source interface byte identity drift")
    if interface.get("schema") != "axm.object-front-latch-pivot-interface/v0.1":
        raise AssertionError("unexpected source interface schema")
    if interface.get("host_source_sha256") != SOURCE_SHA256:
        raise AssertionError("source interface host identity drift")
    if _float_list(interface.get("joint_axis", [])) != [1.0, 0.0, 0.0]:
        raise AssertionError("source interface joint axis drift")
    travel = interface.get("travel_envelope_deg", {})
    if float(travel.get("closed", -1.0)) != 0.0 or float(travel.get("review_release", -1.0)) != 50.0:
        raise AssertionError("source interface review envelope drift")

    if tech.get("schema") != "axm.object-uc-rigid-scene-handoff/v0.1":
        raise AssertionError("unexpected Technical Art receipt schema")
    if tech.get("result") != "PASS_OBJECT_SOURCE_OWNED_RIGID_PARTS_THROUGH_UC_SCENE_GRAPH":
        raise AssertionError("Technical Art rigid-scene prerequisite is not green")
    if tech.get("source_repository_head") != TECH_ART_HEAD:
        raise AssertionError("Technical Art receipt head drift")
    if tech.get("source_sha256") != SOURCE_SHA256:
        raise AssertionError("Technical Art source identity drift")
    if tech.get("observed_uc_commit") != UC_HEAD:
        raise AssertionError("Technical Art UC identity drift")
    observed_glb_sha = sha256_file(rebound_glb_path)
    if tech.get("rebound_glb_sha256") != observed_glb_sha:
        raise AssertionError("rebound GLB byte identity drift")
    if tech.get("binary_geometry_payload_identical") is not True:
        raise AssertionError("Technical Art donor did not preserve binary geometry payload")

    target_levers = sorted(str(value) for value in tech.get("source_owned_fixed_levers", []))
    target_keepers = sorted(str(value) for value in tech.get("source_owned_keeper_children", []))
    if target_levers != ["latch_0_lever", "latch_1_lever"]:
        raise AssertionError("target lever identity drift")
    if target_keepers != ["latch_0_keeper", "latch_1_keeper"]:
        raise AssertionError("target keeper identity drift")
    parent_by_child = tech.get("graph_verification", {}).get("parent_by_child", {})
    for keeper in target_keepers:
        if parent_by_child.get(keeper) != "lid_shell":
            raise AssertionError(f"target keeper hierarchy drift: {keeper}")
    for lever in target_levers:
        if lever in parent_by_child:
            raise AssertionError(f"target lever unexpectedly parented: {lever}")

    stations = interface.get("stations", [])
    if len(stations) != 2:
        raise AssertionError("bounded target proof expects exactly two latch stations")

    target_angles = [-angle for angle in source_angles]
    target_stations: list[dict[str, Any]] = []
    for station in stations:
        lever = str(station.get("lever_component", ""))
        keeper = str(station.get("keeper_component", ""))
        if lever not in target_levers or keeper not in target_keepers:
            raise AssertionError("source station component is absent from exact target hierarchy")
        if station.get("lever_owner_component") != "front_service_panel":
            raise AssertionError("source lever ownership drift")
        if station.get("keeper_owner_component") != "lid_shell":
            raise AssertionError("source keeper ownership drift")
        pivot_source = _float_list(station.get("pivot_origin_m", []))
        if len(pivot_source) != 3:
            raise AssertionError("source station pivot malformed")
        target_stations.append(
            {
                "station_id": str(station.get("id", "")),
                "lever_component": lever,
                "keeper_component": keeper,
                "pivot_source_m": pivot_source,
                "pivot_target_m": source_to_target(pivot_source),
            }
        )

    if sorted(row["station_id"] for row in target_stations) != ["left", "right"]:
        raise AssertionError("bilateral station identity drift")

    result = {
        "schema": SCHEMA,
        "result": RESULT,
        "asset_id": "modular-equipment-case-001",
        "source_sha256": SOURCE_SHA256,
        "source_rig_donor_head": SOURCE_RIG_HEAD,
        "source_rig_binding_git_blob": SOURCE_RIG_BINDING_BLOB,
        "source_rig_binding_sha256": sha256_file(source_rig_binding_path),
        "source_mechanical_authority_head": SOURCE_MECHANICAL_AUTHORITY_HEAD,
        "source_interface_sha256": observed_interface_sha,
        "source_capture_envelope_git_blob": SOURCE_CAPTURE_BLOB,
        "technical_art_donor_head": TECH_ART_HEAD,
        "technical_art_receipt_sha256": sha256_file(tech_receipt_path),
        "technical_art_rebound_glb_sha256": observed_glb_sha,
        "uc_donor_head": UC_HEAD,
        "source_axis": [1.0, 0.0, 0.0],
        "source_to_target_coordinate_map": "[x,y,z] -> [x,z,y] / determinant -1",
        "target_axis": [1.0, 0.0, 0.0],
        "source_rotation_sign": 1,
        "target_x_rotation_sign": -1,
        "representative_source_angles_deg": source_angles,
        "representative_target_angles_deg": target_angles,
        "source_capture_transition_bracket_deg": capture_bracket,
        "target_capture_transition_bracket_x_deg": _mapped_bracket(capture_bracket),
        "source_z_aabb_only_transition_bracket_deg": z_aabb_bracket,
        "target_z_aabb_only_transition_bracket_x_deg": _mapped_bracket(z_aabb_bracket),
        "stations": target_stations,
        "fixed_target_components": ["body_shell", "lid_shell", *target_keepers],
        "failure_policy": "FAIL_CLOSED_ON_SOURCE_RIG_MECHANICAL_AUTHORITY_CAPTURE_CLASSIFICATION_INTERFACE_TECH_ART_UC_GLB_HIERARCHY_COORDINATE_OR_BOUNDARY_POSE_DRIFT",
        "truth_boundary": {
            "exact_source_rig_identity_pinned": True,
            "exact_source_owned_mechanical_authority_pinned": True,
            "proof_volume_capture_and_z_aabb_broad_phase_kept_distinct": True,
            "exact_technical_art_target_identity_pinned": True,
            "coordinate_handedness_conversion_explicit": True,
            "static_target_boundary_pose_fidelity_only": True,
            "target_host_independently_proves_capture_contact": False,
            "target_host_independently_proves_z_aabb_separation": False,
            "continuous_between_pose_motion_accepted": False,
            "animation_timing_or_clip_acceptance": False,
            "animationplayer_acceptance": False,
            "runtime_controller_or_state_machine_acceptance": False,
            "collision_physics_or_gameplay_acceptance": False,
            "physical_latch_engineering_acceptance": False,
            "final_visual_acceptance": False,
        },
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-rig-binding", required=True)
    parser.add_argument("--interface", required=True)
    parser.add_argument("--tech-receipt", required=True)
    parser.add_argument("--rebound-glb", required=True)
    parser.add_argument("--observed-source-rig-head", required=True)
    parser.add_argument("--observed-tech-art-head", required=True)
    parser.add_argument("--observed-uc-head", required=True)
    parser.add_argument("--out", default="latch-rig-target-proof/generated/target-front-latch-rig-binding.json")
    args = parser.parse_args()
    result = build_binding(
        Path(args.source_rig_binding).resolve(),
        Path(args.interface).resolve(),
        Path(args.tech_receipt).resolve(),
        Path(args.rebound_glb).resolve(),
        Path(args.out).resolve(),
        observed_source_rig_head=args.observed_source_rig_head,
        observed_tech_art_head=args.observed_tech_art_head,
        observed_uc_head=args.observed_uc_head,
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
