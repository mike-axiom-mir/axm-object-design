from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any

SCHEMA = "axm.object-technical-art-hinge-analytic-radial-normal-review-build/v0.1"
RESULT = "PASS_OBJECT_HINGE_SUCCESSOR002_ANALYTIC_RADIAL_OUTER_NORMAL_REVIEW_CARRIER_READY"
CONTRACT_SCHEMA = "axm.object-technical-art-hinge-analytic-radial-normal-review/v0.1"
EXPECTED_BASELINE_RESULT = "PASS_OBJECT_HINGE_SUCCESSOR002_TA_SCENE_REBIND_TO_CURRENT_UC__HOLD_DEFAULT_RUNTIME_VISUAL"
EXPECTED_SUCCESSOR = "modular-equipment-case-001/hinge-bored-knuckle-phase-invariant-source-successor-002"
EXPECTED_CONTROL_SHA256 = "f81a9bccd9de1033476da4e5bbea3871b01e2ebf9fb65fcf909447fd14c43e40"
HINGE_COMPONENTS = (
    "hinge_body_b0",
    "hinge_lid_l0",
    "hinge_body_b1",
    "hinge_lid_l1",
    "hinge_body_b2",
)
BODY_COMPONENTS = ("hinge_body_b0", "hinge_body_b1", "hinge_body_b2")
LID_COMPONENTS = ("hinge_lid_l0", "hinge_lid_l1")
CONTEXTS = ("full_rear_three_quarter", "full_rear_grazing", "full_side_three_quarter")
OUTER_RADIUS_TOLERANCE_M = 1e-7
AXIAL_SPAN_TOLERANCE_M = 1e-9
NORMAL_CHANGE_TOLERANCE = 1e-10


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"expected JSON object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def sha256_bytes(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_digest(value: Any) -> str:
    return sha256_bytes(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8"))


def git_head(root: Path) -> str:
    return subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()


def git_blob(root: Path, relpath: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), "rev-parse", f"HEAD:{relpath}"], text=True).strip()


def primitive_triangles(primitive: dict[str, Any]) -> int:
    positions = primitive.get("positions")
    normals = primitive.get("normals")
    indices = primitive.get("indices")
    if not isinstance(positions, list) or not isinstance(normals, list) or not isinstance(indices, list):
        raise AssertionError(f"primitive arrays missing: {primitive.get('id')}")
    if len(normals) != len(positions):
        raise AssertionError(f"normal/position count drift: {primitive.get('id')}")
    if len(indices) % 3:
        raise AssertionError(f"indices not triangulated: {primitive.get('id')}")
    if any(not isinstance(index, int) or index < 0 or index >= len(positions) for index in indices):
        raise AssertionError(f"index range drift: {primitive.get('id')}")
    return len(indices) // 3


def max_vector_delta(a: list[float], b: list[float]) -> float:
    return max(abs(float(a[i]) - float(b[i])) for i in range(3))


def validate_contract(contract: dict[str, Any]) -> None:
    if contract.get("schema") != CONTRACT_SCHEMA:
        raise AssertionError("Technical Art normal-review contract schema drift")
    lane = contract.get("technical_art_lane", {})
    if lane.get("baseline_head") != "f430d00d98e694dcf8302fd4df3c64a074f6f30e":
        raise AssertionError("frozen Technical Art baseline head drift")
    if int(lane.get("baseline_artifact_id", -1)) != 10531541834:
        raise AssertionError("frozen Technical Art artifact drift")
    if lane.get("baseline_control_glb_sha256") != EXPECTED_CONTROL_SHA256:
        raise AssertionError("frozen Technical Art control GLB identity drift")
    art = contract.get("art_direction", {})
    if int(art.get("direction", -1)) != 48:
        raise AssertionError("Art Direction identity drift")
    if art.get("packet_git_blob_sha1") != "910871c06902d9c5bb42a2246aa07bdfaa029045":
        raise AssertionError("Art Direction packet blob drift")
    if art.get("request") != "ONE_REVIEW_ONLY_HINGE_OUTER_CYLINDER_ANALYTIC_RADIAL_NORMAL_CANDIDATE":
        raise AssertionError("Art Direction bounded request drift")
    if art.get("visual_acceptance_owned_by_technical_art") is not False:
        raise AssertionError("Technical Art may not take Art acceptance authority")

    scope = contract.get("receiver_scope", {})
    if tuple(scope.get("hinge_components", [])) != HINGE_COMPONENTS:
        raise AssertionError("hinge component order drift")
    if tuple(scope.get("body_hinge_components", [])) != BODY_COMPONENTS:
        raise AssertionError("body hinge owner partition drift")
    if tuple(scope.get("lid_hinge_components", [])) != LID_COMPONENTS:
        raise AssertionError("lid hinge owner partition drift")
    expected = {
        "expected_mesh_nodes": 31,
        "expected_total_triangles": 1052,
        "expected_hinge_triangles": 480,
        "expected_outer_side_triangles_per_knuckle": 24,
        "expected_outer_side_triangles_total": 120,
        "expected_changed_normal_entries_per_knuckle": 72,
        "expected_changed_normal_entries_total": 360,
    }
    for key, wanted in expected.items():
        if int(scope.get(key, -1)) != wanted:
            raise AssertionError(f"receiver scope drift for {key}")
    if scope.get("hinge_axis_target") != "+X":
        raise AssertionError("hinge target axis drift")

    rule = contract.get("candidate_rule", {})
    required_true = (
        "change_only_hinge_outer_cylindrical_side_surface_normals",
        "end_cap_normals_frozen",
        "through_bore_inner_wall_normals_frozen",
        "non_hinge_normals_frozen",
        "positions_frozen",
        "indices_frozen",
        "triangle_count_frozen",
        "mesh_node_ownership_frozen",
        "culling_front_face_transport_frozen",
        "uvs_frozen",
        "materials_frozen",
        "transforms_frozen",
        "facet_count_frozen",
        "phase_frozen",
        "roughness_value_metallic_frozen",
        "camera_light_fov_exposure_frozen",
        "single_candidate_only",
    )
    for key in required_true:
        if rule.get(key) is not True:
            raise AssertionError(f"required frozen dimension missing: {key}")
    if rule.get("smoothing_angle_sweep_authorized") is not False or rule.get("custom_normal_sculpt_authorized") is not False:
        raise AssertionError("unrequested normal search dimension reopened")

    authority = contract.get("authority", {})
    if authority.get("technical_art_review_representation_only") is not True:
        raise AssertionError("Technical Art review-only boundary missing")
    for key in (
        "source_geometry_mutation_authorized",
        "source_default_adoption_authorized",
        "automatic_downstream_adoption",
        "materials_retune_authorized",
        "geometry_rigging_animation_runtime_authority_transferred",
        "visual_or_art_acceptance_claimed",
        "visual_qa_acceptance_claimed",
        "uc_domain_policy_added",
        "canon_or_production_accepted",
    ):
        if authority.get(key) is not False:
            raise AssertionError(f"authority expansion forbidden: {key}")


def validate_disposition(disposition: dict[str, Any], contract: dict[str, Any]) -> None:
    if disposition.get("schema") != "axm.object-source-successor-review-disposition/v0.1":
        raise AssertionError("Hard Surface review disposition schema drift")
    decision = disposition.get("disposition", {})
    reference = decision.get("current_review_reference", {})
    if reference.get("source_successor") != EXPECTED_SUCCESSOR:
        raise AssertionError("Direction 048 successor002 frozen reference drift")
    if reference.get("relative_owner_phase") != "SYNCHRONIZED_PREDECESSOR_PHASE":
        raise AssertionError("Direction 048 frozen phase drift")
    if reference.get("hardware_steel_base_color") != "#7E868AFF" or float(reference.get("hardware_steel_metallic", -1.0)) != 0.88 or float(reference.get("hardware_steel_roughness", -1.0)) != 0.32:
        raise AssertionError("Direction 048 frozen material drift")
    next_owner = decision.get("next_owner", {})
    if next_owner.get("specialist") != "Technical Art / UC Integration" or int(next_owner.get("object_pr", -1)) != 16:
        raise AssertionError("Direction 048 next-owner drift")
    if next_owner.get("requested_candidate") != contract["art_direction"]["request"]:
        raise AssertionError("Direction 048 requested candidate drift")
    if next_owner.get("hard_surface_geometry_mutation_requested") is not False:
        raise AssertionError("Hard Surface geometry mutation unexpectedly requested")
    for key in ("phase_sweep_authorized", "second_phase_candidate_authorized", "source_geometry_rewrite_authorized"):
        if decision.get(key) is not False:
            raise AssertionError(f"Hard Surface forbidden search dimension reopened: {key}")
    authority = disposition.get("authority", {})
    if authority.get("technical_art_review_candidate_authorized") is not True:
        raise AssertionError("Technical Art review candidate is not authorized by disposition")
    if authority.get("uc_or_profession_fabric_promotion_authorized") is not False:
        raise AssertionError("disposition unexpectedly authorizes UC/PF promotion")


def validate_material_payload(material_payload: dict[str, Any]) -> None:
    if material_payload.get("exact_materials_head") != "5509084acbaca2a7d45f072203b98174c621d5ef":
        raise AssertionError("exact Materials donor head drift")
    materials = material_payload.get("materials")
    mapping = material_payload.get("group_materials")
    if not isinstance(materials, dict) or not isinstance(mapping, dict):
        raise AssertionError("Materials payload missing normalized maps")
    if len(mapping) != 31:
        raise AssertionError("full-receiver material mapping count drift")
    steel = materials.get("hardware_steel", {})
    if steel.get("albedo_hex") != "#7E868AFF" or float(steel.get("metallic", -1.0)) != 0.88 or float(steel.get("roughness", -1.0)) != 0.32:
        raise AssertionError("frozen hardware_steel values drift")
    if any(mapping.get(name) != "hardware_steel" for name in HINGE_COMPONENTS):
        raise AssertionError("one or more hinge nodes lost hardware_steel mapping")


def lid_pivot_from_manifest(manifest: dict[str, Any]) -> list[float]:
    nodes = manifest.get("nodes")
    if not isinstance(nodes, list):
        raise AssertionError("scene manifest nodes missing")
    for node in nodes:
        if isinstance(node, dict) and node.get("name") == "lid_shell":
            translation = node.get("translation")
            if not isinstance(translation, list) or len(translation) != 3:
                raise AssertionError("lid_shell translation missing")
            return [float(v) for v in translation]
    raise AssertionError("lid_shell node missing from manifest")


def radial_normal(position: list[float], center: list[float]) -> list[float]:
    dy = float(position[1]) - float(center[1])
    dz = float(position[2]) - float(center[2])
    length = math.hypot(dy, dz)
    if not math.isfinite(length) or length <= 1e-12:
        raise AssertionError("outer-cylinder corner collapsed onto +X axis")
    return [0.0, dy / length, dz / length]


def make_radial_candidate(control_surface: dict[str, Any], manifest: dict[str, Any], contract: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    candidate = copy.deepcopy(control_surface)
    primitives = candidate.get("primitives")
    control_primitives = control_surface.get("primitives")
    if not isinstance(primitives, list) or not isinstance(control_primitives, list):
        raise AssertionError("surface primitives missing")
    if len(primitives) != 31:
        raise AssertionError("receiver mesh-node count drift")
    by_id = {str(p.get("id")): p for p in primitives}
    control_by_id = {str(p.get("id")): p for p in control_primitives}
    if len(by_id) != len(primitives) or set(by_id) != set(control_by_id):
        raise AssertionError("receiver primitive identity drift")
    if set(HINGE_COMPONENTS) - set(by_id):
        raise AssertionError("frozen receiver misses one or more hinge nodes")

    total_triangles = sum(primitive_triangles(p) for p in primitives)
    hinge_triangles = sum(primitive_triangles(by_id[name]) for name in HINGE_COMPONENTS)
    if total_triangles != 1052 or hinge_triangles != 480:
        raise AssertionError("frozen receiver triangle-count drift")

    pivot_target = lid_pivot_from_manifest(manifest)
    per_component: dict[str, Any] = {}
    all_changed_pairs: list[tuple[str, int]] = []
    maximum_normal_delta = 0.0

    for name in HINGE_COMPONENTS:
        primitive = by_id[name]
        control = control_by_id[name]
        positions = primitive["positions"]
        normals = primitive["normals"]
        indices = primitive["indices"]
        control_normals = control["normals"]
        center = [0.0, 0.0, 0.0] if name in LID_COMPONENTS else pivot_target
        radii = [math.hypot(float(p[1]) - center[1], float(p[2]) - center[2]) for p in positions]
        if not radii:
            raise AssertionError(f"empty hinge primitive: {name}")
        outer_radius = max(radii)
        if outer_radius <= 1e-6:
            raise AssertionError(f"invalid hinge outer radius: {name}")

        changed_indices: set[int] = set()
        outer_triangles = 0
        for offset in range(0, len(indices), 3):
            tri_indices = [int(v) for v in indices[offset:offset + 3]]
            tri_positions = [positions[index] for index in tri_indices]
            tri_radii = [radii[index] for index in tri_indices]
            axial_span = max(float(p[0]) for p in tri_positions) - min(float(p[0]) for p in tri_positions)
            is_outer_side = all(abs(radius - outer_radius) <= OUTER_RADIUS_TOLERANCE_M for radius in tri_radii) and axial_span > AXIAL_SPAN_TOLERANCE_M
            if not is_outer_side:
                continue
            outer_triangles += 1
            for index in tri_indices:
                new_normal = radial_normal(positions[index], center)
                delta = max_vector_delta(control_normals[index], new_normal)
                if delta <= NORMAL_CHANGE_TOLERANCE:
                    raise AssertionError(f"analytic radial normal unexpectedly equals faceted control: {name}/{index}")
                normals[index] = new_normal
                changed_indices.add(index)
                all_changed_pairs.append((name, index))
                maximum_normal_delta = max(maximum_normal_delta, delta)

        if outer_triangles != 24:
            raise AssertionError(f"outer cylindrical triangle classification drift for {name}: {outer_triangles}")
        if len(changed_indices) != 72:
            raise AssertionError(f"changed outer normal-entry count drift for {name}: {len(changed_indices)}")

        for index, (before, after) in enumerate(zip(control_normals, normals)):
            changed = max_vector_delta(before, after) > NORMAL_CHANGE_TOLERANCE
            if changed != (index in changed_indices):
                raise AssertionError(f"normal change escaped outer-side classification: {name}/{index}")
        if control["positions"] != primitive["positions"] or control["indices"] != primitive["indices"] or control.get("material") != primitive.get("material"):
            raise AssertionError(f"normal-only candidate changed frozen primitive payload: {name}")

        per_component[name] = {
            "owner": "lid" if name in LID_COMPONENTS else "body",
            "outer_radius_target_m": outer_radius,
            "outer_side_triangles": outer_triangles,
            "changed_normal_entries": len(changed_indices),
            "position_count": len(positions),
            "triangle_count": primitive_triangles(primitive),
        }

    for name, primitive in by_id.items():
        if name in HINGE_COMPONENTS:
            continue
        if canonical_digest(primitive) != canonical_digest(control_by_id[name]):
            raise AssertionError(f"non-hinge primitive drift: {name}")

    unique_pairs = set(all_changed_pairs)
    if len(unique_pairs) != 360:
        raise AssertionError(f"aggregate changed-normal entry count drift: {len(unique_pairs)}")
    if sum(row["outer_side_triangles"] for row in per_component.values()) != 120:
        raise AssertionError("aggregate outer-side triangle count drift")

    candidate["name"] = "modular-equipment-case-001-hinge-successor002-analytic-radial-normal-review-048"
    return candidate, {
        "per_component": per_component,
        "outer_side_triangles_total": 120,
        "changed_normal_entries_total": 360,
        "maximum_normal_component_delta_vs_faceted_control": maximum_normal_delta,
        "body_axis_center_target_m": pivot_target,
        "lid_axis_center_local_m": [0.0, 0.0, 0.0],
        "classification": "ALL_THREE_TRIANGLE_CORNERS_AT_MAX_RADIAL_DISTANCE_AND_NONZERO_AXIAL_SPAN",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--baseline-surface", type=Path, required=True)
    parser.add_argument("--baseline-manifest", type=Path, required=True)
    parser.add_argument("--baseline-receipt", type=Path, required=True)
    parser.add_argument("--frozen-control-glb", type=Path, required=True)
    parser.add_argument("--hard-surface-disposition", type=Path, required=True)
    parser.add_argument("--material-payload", type=Path, required=True)
    parser.add_argument("--uc-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    contract = read_json(args.contract)
    validate_contract(contract)
    disposition = read_json(args.hard_surface_disposition)
    validate_disposition(disposition, contract)
    material_payload = read_json(args.material_payload)
    validate_material_payload(material_payload)

    baseline_surface = read_json(args.baseline_surface)
    baseline_manifest = read_json(args.baseline_manifest)
    baseline_receipt = read_json(args.baseline_receipt)
    if baseline_receipt.get("result") != EXPECTED_BASELINE_RESULT:
        raise AssertionError("frozen Technical Art baseline receipt is not the pinned PASS")
    if baseline_receipt.get("successor_id") != EXPECTED_SUCCESSOR:
        raise AssertionError("frozen Technical Art successor identity drift")
    if sha256_file(args.frozen_control_glb) != EXPECTED_CONTROL_SHA256:
        raise AssertionError("frozen successor002 control GLB byte identity drift")

    uc_root = args.uc_root.resolve()
    uc_contract = contract["universal_creation"]
    observed_uc = git_head(uc_root)
    if observed_uc != uc_contract["exact_head"]:
        raise AssertionError(f"exact UC head drift: {observed_uc}")
    observed_blobs = {
        "procedural_3d": git_blob(uc_root, "src/axm_uc/procedural_3d.py"),
        "rigid_scene_graph": git_blob(uc_root, "src/axm_uc/rigid_scene_graph.py"),
    }
    if observed_blobs["procedural_3d"] != uc_contract["procedural_3d_blob_sha1"] or observed_blobs["rigid_scene_graph"] != uc_contract["rigid_scene_graph_blob_sha1"]:
        raise AssertionError("generic UC executable receiver continuity drift")

    sys.path.insert(0, str(uc_root / "src"))
    from axm_uc.procedural_3d import build_glb, verify_glb  # type: ignore
    from axm_uc.rigid_scene_graph import rebind_rigid_scene_graph, verify_rigid_scene_graph  # type: ignore

    control_flat = build_glb(baseline_surface)
    control_rebound = rebind_rigid_scene_graph(
        control_flat["body"], baseline_manifest, expected_spec_digest=control_flat["specification_sha256"]
    )
    control_verify = verify_glb(control_rebound["body"], expected_spec_digest=control_flat["specification_sha256"])
    control_graph = verify_rigid_scene_graph(
        control_rebound["body"], expected_manifest_digest=control_rebound["manifest_sha256"]
    )
    rebuilt_control_sha = sha256_bytes(control_rebound["body"])
    if rebuilt_control_sha != EXPECTED_CONTROL_SHA256:
        raise AssertionError(f"fresh UC did not reproduce frozen successor002 control GLB: {rebuilt_control_sha}")
    if control_rebound["body"] != args.frozen_control_glb.read_bytes():
        raise AssertionError("fresh UC control output hash matched but bytes were not identical")
    if int(control_verify["nodes"]) != 31 or int(control_verify["triangles"]) != 1052:
        raise AssertionError("fresh UC control receiver shape drift")

    candidate_surface, normal_receipt = make_radial_candidate(baseline_surface, baseline_manifest, contract)
    candidate_flat = build_glb(candidate_surface)
    candidate_rebound = rebind_rigid_scene_graph(
        candidate_flat["body"], baseline_manifest, expected_spec_digest=candidate_flat["specification_sha256"]
    )
    candidate_verify = verify_glb(candidate_rebound["body"], expected_spec_digest=candidate_flat["specification_sha256"])
    candidate_graph = verify_rigid_scene_graph(
        candidate_rebound["body"], expected_manifest_digest=candidate_rebound["manifest_sha256"]
    )
    if int(candidate_verify["nodes"]) != 31 or int(candidate_verify["triangles"]) != 1052:
        raise AssertionError("candidate UC receiver node/triangle count drift")
    if candidate_rebound["receipt"].get("binary_geometry_payload_identical") is not True:
        raise AssertionError("UC scene-graph rebind changed candidate binary geometry payload")
    if candidate_graph.get("parent_by_child") != control_graph.get("parent_by_child"):
        raise AssertionError("candidate scene-graph ownership changed relative to frozen control")
    candidate_sha = sha256_bytes(candidate_rebound["body"])
    if candidate_sha == rebuilt_control_sha:
        raise AssertionError("normal candidate produced no GLB byte change")

    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    control_out = out / "control-successor002.glb"
    candidate_surface_out = out / "candidate-analytic-radial-normal.surface.json"
    candidate_out = out / "candidate-analytic-radial-normal.glb"
    manifest_out = out / "frozen-successor002.scene-graph.json"
    control_out.write_bytes(control_rebound["body"])
    candidate_out.write_bytes(candidate_rebound["body"])
    write_json(candidate_surface_out, candidate_surface)
    write_json(manifest_out, baseline_manifest)

    payload = {
        "schema": "axm.object-hinge-analytic-radial-normal-review-payload/v0.1",
        "candidate_id": contract["candidate_id"],
        "technical_art_head": git_head(Path.cwd()),
        "uc_head": observed_uc,
        "control_glb": "res://generated/object-hinge-analytic-radial-normal-review/control-successor002.glb",
        "control_glb_sha256": rebuilt_control_sha,
        "candidate_glb": "res://generated/object-hinge-analytic-radial-normal-review/candidate-analytic-radial-normal.glb",
        "candidate_glb_sha256": candidate_sha,
        "expected_total_mesh_nodes": 31,
        "expected_total_triangles": 1052,
        "expected_hinge_triangles": 480,
        "hinge_components": list(HINGE_COMPONENTS),
        "camera_contexts": list(CONTEXTS),
        "materials": material_payload["materials"],
        "group_materials": material_payload["group_materials"],
        "hardware_steel_review": material_payload["materials"]["hardware_steel"],
        "normal_transport": normal_receipt,
        "truth_boundary": {
            "normal_only_review_representation": True,
            "positions_indices_hierarchy_material_camera_light_frozen": True,
            "source_or_default_adoption": False,
            "automatic_downstream_adoption": False,
            "art_direction_acceptance": False,
            "visual_qa_acceptance": False,
            "uc_inferred_object_normal_policy": False,
            "runtime_or_device_acceptance": False,
            "canon_or_production_readiness": False,
        },
    }
    payload_path = out / "object_hinge_analytic_radial_normal_review_payload.json"
    write_json(payload_path, payload)

    receipt = {
        "schema": SCHEMA,
        "result": RESULT,
        "technical_art_head": git_head(Path.cwd()),
        "frozen_technical_art_baseline_head": contract["technical_art_lane"]["baseline_head"],
        "hard_surface_disposition_head": contract["hard_surface_disposition"]["exact_head"],
        "materials_review_head": contract["materials_review_owner"]["exact_head"],
        "uc_head": observed_uc,
        "uc_executable_blobs": observed_blobs,
        "fresh_uc_reproduced_frozen_control_byte_for_byte": True,
        "control_glb_sha256": rebuilt_control_sha,
        "candidate_glb_sha256": candidate_sha,
        "candidate_surface_sha256": sha256_file(candidate_surface_out),
        "scene_graph_sha256": sha256_file(manifest_out),
        "mesh_nodes": int(candidate_verify["nodes"]),
        "triangles": int(candidate_verify["triangles"]),
        "hinge_triangles": 480,
        "normal_change": normal_receipt,
        "frozen_material": {
            "albedo": "#7E868AFF",
            "metallic": 0.88,
            "roughness": 0.32,
        },
        "camera_contexts": list(CONTEXTS),
        "control_uc_verification": control_verify,
        "candidate_uc_verification": candidate_verify,
        "control_graph_verification": control_graph,
        "candidate_graph_verification": candidate_graph,
        "truth_boundary": payload["truth_boundary"],
        "promotion_effect": "NONE",
    }
    receipt_path = out / "object-hinge-analytic-radial-normal-review-build-receipt.json"
    write_json(receipt_path, receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
