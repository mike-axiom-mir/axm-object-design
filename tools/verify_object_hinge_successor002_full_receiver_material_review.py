from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from build_modular_case import build as build_case

CONTRACT_SCHEMA = "axm.object-hinge-successor002-full-receiver-material-review/v0.1"
PAYLOAD_SCHEMA = "axm.object-hinge-successor002-full-receiver-material-review-payload/v0.1"
BUILD_SCHEMA = "axm.object-hinge-successor002-full-receiver-material-review-build/v0.1"
RUNTIME_SCHEMA = "axm.object-hinge-successor002-full-receiver-material-review-runtime/v0.1"
RESULT = "PASS_OBJECT_HINGE_SUCCESSOR002_FULL_RECEIVER_MATERIAL_REVIEW_EVIDENCE_READY"

EXPECTED_SOURCE_SHA = "49b1f9ed9865893d6de6f1ec8f069576732df694853fde4e3fcff366de32644a"
EXPECTED_PROFILE_SHA = "dc200229d6c25fa84063aa51f66103abc022efa54b2167e4432a5b47fc40360c"
EXPECTED_TA_HEAD = "f430d00d98e694dcf8302fd4df3c64a074f6f30e"
EXPECTED_TA_ARTIFACT_ID = 10531541834
EXPECTED_TA_ARTIFACT_SHA = "5e1134d0ebdf786d04ae789a841493ce9cf684f16aedd7dbad597f2e02b3ad5e"
EXPECTED_TA_RESULT = "PASS_OBJECT_HINGE_SUCCESSOR002_CURRENT_UC_GODOT_TRIANGLE_TRANSPORT"
EXPECTED_TA_REBIND_RESULT = "PASS_OBJECT_HINGE_SUCCESSOR002_TA_SCENE_REBIND_TO_CURRENT_UC__HOLD_DEFAULT_RUNTIME_VISUAL"
EXPECTED_TARGET_GLB_SHA = "f81a9bccd9de1033476da4e5bbea3871b01e2ebf9fb65fcf909447fd14c43e40"
EXPECTED_HARD_SURFACE_HEAD = "a6d18b9fe729304dc4d95d962ed27527adce211f"
EXPECTED_GEOMETRY_HEAD = "96abb2830ddabca9ed270b42a9447534d007ce64"
EXPECTED_RIGGING_HEAD = "cf377074f70ce7f7e386f1378c51705b3db4d305"
EXPECTED_UC_HEAD = "9609998db6677391766e9ee7ff53a5b9b08a3cb9"
EXPECTED_INDEX_TRANSFORM = "GODOT_4_7_2_GLTFDOCUMENT_RECEIVER_LOCAL_[a,b,c]_TO_[a,c,b]"
EXPECTED_ART_STATUS_BLOB = "e35d498292ae8dbc1f71d740b90c01329cd6c95d"
EXPECTED_ART_DIRECTION = "PASS_ART_DIRECTION_OBJECT_HINGE_SUCCESSOR002_ISOLATED_MATERIAL_CULL_REFERENCE_044"
EXPECTED_ART_HOLD = "HOLD_ART_DIRECTION_OBJECT_HINGE_SUCCESSOR002_FULL_OBJECT_ADOPTION__INTEGRATED_CASE_HIERARCHY_PENDING"
HINGE_COMPONENTS = (
    "hinge_body_b0",
    "hinge_lid_l0",
    "hinge_body_b1",
    "hinge_lid_l1",
    "hinge_body_b2",
)
CONTEXTS = (
    "full_rear_three_quarter",
    "full_rear_grazing",
    "full_side_three_quarter",
)


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"expected JSON object: {path}")
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rgba(hex_value: str) -> list[float]:
    if len(hex_value) != 9 or not hex_value.startswith("#"):
        raise AssertionError(f"invalid RGBA hex {hex_value!r}")
    return [int(hex_value[i : i + 2], 16) / 255.0 for i in (1, 3, 5, 7)]


def normalize_material_spec(spec: dict[str, Any]) -> dict[str, Any]:
    metallic = float(spec["metallic"])
    roughness = float(spec["roughness"])
    if not 0.0 <= metallic <= 1.0 or not 0.0 <= roughness <= 1.0:
        raise AssertionError("material scalar outside [0,1]")
    return {
        "albedo": rgba(str(spec["albedo"])),
        "albedo_hex": str(spec["albedo"]),
        "metallic": metallic,
        "roughness": roughness,
    }


def load_contract(contract_path: Path, source_path: Path, profile_path: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    contract = read_json(contract_path)
    source = read_json(source_path)
    profile = read_json(profile_path)
    if contract.get("schema") != CONTRACT_SCHEMA:
        raise AssertionError("full-receiver Materials contract schema drift")
    if sha256(source_path) != EXPECTED_SOURCE_SHA or contract.get("source_sha256") != EXPECTED_SOURCE_SHA:
        raise AssertionError("Object source identity drift")
    if sha256(profile_path) != EXPECTED_PROFILE_SHA or contract.get("material_profile_sha256") != EXPECTED_PROFILE_SHA:
        raise AssertionError("Object material profile identity drift")

    owner = contract.get("technical_art_owner", {})
    expected_owner = {
        "exact_head": EXPECTED_TA_HEAD,
        "artifact_id": EXPECTED_TA_ARTIFACT_ID,
        "artifact_sha256": EXPECTED_TA_ARTIFACT_SHA,
        "expected_result": EXPECTED_TA_RESULT,
        "target_glb_sha256": EXPECTED_TARGET_GLB_SHA,
        "hard_surface_exact_head": EXPECTED_HARD_SURFACE_HEAD,
        "geometry_exact_head": EXPECTED_GEOMETRY_HEAD,
        "rigging_exact_head": EXPECTED_RIGGING_HEAD,
        "uc_exact_head": EXPECTED_UC_HEAD,
        "expected_target_triangle_index_transform": EXPECTED_INDEX_TRANSFORM,
    }
    for key, value in expected_owner.items():
        if owner.get(key) != value:
            raise AssertionError(f"Technical Art owner binding drift for {key}: {owner.get(key)!r}")
    if float(owner.get("maximum_position_delta_m", -1.0)) != 1e-6:
        raise AssertionError("Technical Art POSITION tolerance drift")

    art = contract.get("art_direction_request", {})
    if art.get("status_blob") != EXPECTED_ART_STATUS_BLOB:
        raise AssertionError("Art Direction status binding drift")
    if art.get("direction") != EXPECTED_ART_DIRECTION or art.get("hold") != EXPECTED_ART_HOLD:
        raise AssertionError("Art Direction request identity drift")

    scope = contract.get("review_scope", {})
    if int(scope.get("expected_total_mesh_nodes", -1)) != 31:
        raise AssertionError("full receiver mesh-node expectation drift")
    if int(scope.get("expected_total_triangles", -1)) != 1052:
        raise AssertionError("full receiver triangle expectation drift")
    if tuple(scope.get("hinge_components", [])) != HINGE_COMPONENTS:
        raise AssertionError("hinge component set/order drift")
    if int(scope.get("expected_hinge_triangles", -1)) != 480:
        raise AssertionError("hinge triangle expectation drift")
    if tuple(scope.get("camera_contexts", [])) != CONTEXTS:
        raise AssertionError("full receiver camera set drift")

    renderer = contract.get("renderer", {})
    if renderer != {"engine": "Godot", "version": "4.7.2-stable", "rendering_method": "gl_compatibility"}:
        raise AssertionError("renderer contract drift")

    provenance = contract.get("provenance", {})
    if provenance.get("external_textures") not in ([], None) or provenance.get("external_material_assets") not in ([], None):
        raise AssertionError("external material provenance is outside this bounded review")
    if provenance.get("technical_art_glb_bytes_edited_by_materials") is not False:
        raise AssertionError("Materials may not edit the Technical Art GLB")
    if provenance.get("technical_art_triangle_transform_reimplemented_by_materials") is not False:
        raise AssertionError("Materials may not reimplement Technical Art triangle transport")
    if provenance.get("positive_material_values_changed") is not False:
        raise AssertionError("positive material values must remain frozen")
    if provenance.get("control_material_is_existing_profile_baseline") is not True:
        raise AssertionError("hinge control must use the existing neutral-proof profile baseline")

    truth = contract.get("truth_boundary", {})
    for key in (
        "source_successor_default_adopted",
        "technical_art_transport_adopted_as_object_default",
        "materials_edits_transport_geometry",
        "materials_claims_universal_godot_winding_rule",
        "uvs_changed",
        "textures_changed",
        "positive_material_scalars_changed",
        "art_direction_acceptance",
        "visual_qa_acceptance",
        "runtime_or_physics_accepted",
        "canon",
        "production_ready",
    ):
        if truth.get(key) is not False:
            raise AssertionError(f"Materials authority expansion forbidden: {key}")
    return contract, source, profile


def normalized_full_receiver_materials(source: dict[str, Any], profile: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str], dict[str, str], dict[str, Any]]:
    if profile.get("schema") != "axm.object-material-profile/v0.1":
        raise AssertionError("material profile schema drift")
    candidate = profile.get("candidate", {})
    role_materials = profile.get("role_materials", {})
    baseline = profile.get("baseline", {}).get("neutral_proof", {})
    if not isinstance(candidate, dict) or not isinstance(role_materials, dict) or not isinstance(baseline, dict):
        raise AssertionError("material profile mappings missing")

    materials = {str(material_id): normalize_material_spec(spec) for material_id, spec in candidate.items()}
    neutral = normalize_material_spec(baseline)

    result = build_case(source)
    components = {str(item["name"]): item for item in result["components"]}
    if len(components) != 31:
        raise AssertionError(f"Object source component count drift: {len(components)}")
    group_roles: dict[str, str] = {}
    group_materials: dict[str, str] = {}
    for name, item in components.items():
        role = str(item["role"])
        material_id = str(role_materials.get(role, ""))
        if not material_id or material_id not in materials:
            raise AssertionError(f"missing material mapping for {name} role {role!r}")
        group_roles[name] = role
        group_materials[name] = material_id

    if set(HINGE_COMPONENTS) - set(group_materials):
        raise AssertionError("full receiver material mapping misses successor002 hinge nodes")
    if any(group_materials[name] != "hardware_steel" for name in HINGE_COMPONENTS):
        raise AssertionError("successor002 hinge material mapping drift")
    return materials, group_roles, group_materials, neutral


def validate_ta_packet(ta_root: Path) -> tuple[dict[str, Any], dict[str, Any], Path]:
    ta_receipt_path = ta_root / "object-hinge-successor002-ta-transport-rebind-receipt.json"
    target_receipt_path = ta_root / "hinge-successor002-target-transport-receipt.json"
    glb_path = ta_root / "object-rigid-components-hinge-successor002-rebound.glb"
    for path in (ta_receipt_path, target_receipt_path, glb_path):
        if not path.exists():
            raise AssertionError(f"exact Technical Art packet file missing: {path}")
    ta = read_json(ta_receipt_path)
    target = read_json(target_receipt_path)
    if ta.get("result") != EXPECTED_TA_REBIND_RESULT:
        raise AssertionError("Technical Art rebind receipt is not the pinned PASS")
    if ta.get("technical_art_head") != EXPECTED_TA_HEAD:
        raise AssertionError("Technical Art rebind head drift")
    if ta.get("hard_surface_head") != EXPECTED_HARD_SURFACE_HEAD or ta.get("geometry_head") != EXPECTED_GEOMETRY_HEAD or ta.get("rigging_head") != EXPECTED_RIGGING_HEAD or ta.get("uc_head") != EXPECTED_UC_HEAD:
        raise AssertionError("Technical Art owner chain drift")
    if int(ta.get("mesh_nodes", -1)) != 31 or int(ta.get("successor_total_triangles", -1)) != 1052:
        raise AssertionError("Technical Art full receiver shape drift")
    if int(ta.get("successor_hinge_triangles", -1)) != 480:
        raise AssertionError("Technical Art successor hinge triangle count drift")
    if target.get("result") != EXPECTED_TA_RESULT:
        raise AssertionError("Technical Art Godot target receipt is not the pinned PASS")
    if target.get("technical_art_head") != EXPECTED_TA_HEAD:
        raise AssertionError("Technical Art target head drift")
    if target.get("glb_sha256") != EXPECTED_TARGET_GLB_SHA or ta.get("successor_rebound_glb_sha256") != EXPECTED_TARGET_GLB_SHA:
        raise AssertionError("Technical Art target GLB receipt digest drift")
    if sha256(glb_path) != EXPECTED_TARGET_GLB_SHA:
        raise AssertionError("Technical Art target GLB byte identity drift")
    if target.get("target_host_triangle_index_transform") != EXPECTED_INDEX_TRANSFORM:
        raise AssertionError("Technical Art target index transform drift")
    if float(target.get("maximum_position_delta_m", 1.0)) > 1e-6:
        raise AssertionError("Technical Art target POSITION error exceeds pinned bound")
    return ta, target, glb_path


def build_payload(contract_path: Path, source_path: Path, profile_path: Path, ta_root: Path, exact_head: str, out_dir: Path) -> dict[str, Any]:
    contract, source, profile = load_contract(contract_path, source_path, profile_path)
    ta, target, glb_path = validate_ta_packet(ta_root)
    materials, group_roles, group_materials, neutral = normalized_full_receiver_materials(source, profile)
    out_dir.mkdir(parents=True, exist_ok=True)
    local_glb = out_dir / "object-rigid-components-hinge-successor002-rebound.glb"
    local_glb.write_bytes(glb_path.read_bytes())
    payload = {
        "schema": PAYLOAD_SCHEMA,
        "asset_id": contract["asset_id"],
        "exact_materials_head": exact_head,
        "exact_technical_art_head": EXPECTED_TA_HEAD,
        "exact_hard_surface_head": EXPECTED_HARD_SURFACE_HEAD,
        "exact_geometry_head": EXPECTED_GEOMETRY_HEAD,
        "exact_rigging_head": EXPECTED_RIGGING_HEAD,
        "exact_uc_head": EXPECTED_UC_HEAD,
        "source_sha256": EXPECTED_SOURCE_SHA,
        "material_profile_sha256": EXPECTED_PROFILE_SHA,
        "target_glb_sha256": EXPECTED_TARGET_GLB_SHA,
        "target_glb": "res://generated/object-hinge-successor002-full-receiver/object-rigid-components-hinge-successor002-rebound.glb",
        "camera_contexts": list(CONTEXTS),
        "hinge_components": list(HINGE_COMPONENTS),
        "expected_total_mesh_nodes": 31,
        "expected_total_triangles": 1052,
        "expected_hinge_triangles": 480,
        "materials": materials,
        "neutral_material": neutral,
        "group_roles": group_roles,
        "group_materials": group_materials,
        "review_scope": contract["review_scope"],
        "truth_boundary": contract["truth_boundary"],
    }
    if len(group_materials) != 31:
        raise AssertionError("full receiver material mapping must cover exactly 31 source components")
    payload_path = out_dir / "object_hinge_successor002_full_receiver_material_review_payload.json"
    payload_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    receipt = {
        "schema": BUILD_SCHEMA,
        "result": "PASS_SOURCE_BOUND_OBJECT_HINGE_SUCCESSOR002_FULL_RECEIVER_MATERIAL_REVIEW_PAYLOAD",
        "exact_materials_head": exact_head,
        "exact_technical_art_head": EXPECTED_TA_HEAD,
        "technical_art_target_result": target["result"],
        "technical_art_target_glb_sha256": sha256(local_glb),
        "technical_art_target_triangle_index_transform": target["target_host_triangle_index_transform"],
        "mesh_nodes": 31,
        "triangles": 1052,
        "material_role_bindings": len(group_materials),
        "hinge_control_nodes": list(HINGE_COMPONENTS),
        "positive_material_scalars_changed": False,
        "source_successor_default_adopted": False,
        "technical_art_transport_adopted_as_object_default": False,
        "truth_boundary": contract["truth_boundary"],
    }
    (out_dir / "object_hinge_successor002_full_receiver_material_review_build_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return receipt


def verify_runtime(path: Path, exact_head: str) -> dict[str, Any]:
    receipt = read_json(path)
    if receipt.get("schema") != RUNTIME_SCHEMA:
        raise AssertionError("runtime receipt schema drift")
    if receipt.get("state") != "PASS_EVIDENCE" or receipt.get("decision") != RESULT:
        raise AssertionError("full receiver runtime evidence did not reach the bounded PASS")
    if receipt.get("exact_materials_head") != exact_head:
        raise AssertionError("runtime exact Materials head drift")
    if receipt.get("exact_technical_art_head") != EXPECTED_TA_HEAD:
        raise AssertionError("runtime Technical Art head drift")
    if receipt.get("target_glb_sha256") != EXPECTED_TARGET_GLB_SHA:
        raise AssertionError("runtime GLB identity drift")
    renderer = receipt.get("renderer", {})
    if renderer.get("engine") != "Godot" or not str(renderer.get("version", "")).startswith("4.7.2"):
        raise AssertionError("unexpected target-host renderer")
    if renderer.get("rendering_method") != "gl_compatibility":
        raise AssertionError("unexpected rendering method")
    if set(receipt.get("hinge_control_nodes", [])) != set(HINGE_COMPONENTS):
        raise AssertionError("runtime hinge control-node set drift")
    contexts = receipt.get("contexts", {})
    if set(contexts) != set(CONTEXTS):
        raise AssertionError("runtime camera-context set drift")
    aggregate_hinge_control = 0
    aggregate_material_activity = 0
    for context in CONTEXTS:
        entry = contexts[context]
        for variant in ("candidate", "hinge_neutral", "unshaded"):
            frame = entry.get(variant, {})
            if frame.get("state") != "PASS":
                raise AssertionError(f"{context}/{variant} render missing")
            if int(frame.get("total_mesh_nodes", -1)) != 31 or int(frame.get("total_triangles", -1)) != 1052:
                raise AssertionError(f"{context}/{variant} full receiver shape drift")
            if int(frame.get("visible_mesh_nodes", -1)) != 31:
                raise AssertionError(f"{context}/{variant} did not keep all 31 nodes visible")
            if int(frame.get("visible_pixels", 0)) <= 1000:
                raise AssertionError(f"{context}/{variant} has insufficient complete-object coverage")
        hinge_delta = entry.get("candidate_vs_hinge_neutral", {})
        activity_delta = entry.get("candidate_vs_unshaded", {})
        if hinge_delta.get("state") != "PASS" or int(hinge_delta.get("changed_pixels_gt_1lsb", 0)) <= 0:
            raise AssertionError(f"{context} hinge material control is not visibly distinct")
        if activity_delta.get("state") != "PASS" or int(activity_delta.get("changed_pixels_gt_1lsb", 0)) <= 0:
            raise AssertionError(f"{context} full material family appears visually inert")
        aggregate_hinge_control += int(hinge_delta["changed_pixels_gt_1lsb"])
        aggregate_material_activity += int(activity_delta["changed_pixels_gt_1lsb"])
    if int(receipt.get("aggregate_candidate_vs_hinge_neutral_gt1", -1)) != aggregate_hinge_control:
        raise AssertionError("aggregate hinge-control delta drift")
    if int(receipt.get("aggregate_candidate_vs_unshaded_gt1", -1)) != aggregate_material_activity:
        raise AssertionError("aggregate material-activity delta drift")
    if aggregate_hinge_control <= 0 or aggregate_material_activity <= 0:
        raise AssertionError("full receiver review lacks useful visual differentiation")
    truth = receipt.get("truth_boundary", {})
    for key in ("art_direction_acceptance", "visual_qa_acceptance", "canon", "production_ready"):
        if truth.get(key) is not False:
            raise AssertionError(f"runtime receipt overclaims {key}")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=Path("lookdev/object_hinge_successor002_full_receiver_material_review_001.json"))
    parser.add_argument("--source", type=Path, default=Path("assets/modular-equipment-case-001/source.json"))
    parser.add_argument("--profile", type=Path, default=Path("lookdev/object_material_profile_001.json"))
    parser.add_argument("--ta-root", type=Path)
    parser.add_argument("--out", type=Path, default=Path("lookdev-proof/generated/object-hinge-successor002-full-receiver"))
    parser.add_argument("--runtime-receipt", type=Path)
    parser.add_argument("--exact-head", required=True)
    args = parser.parse_args()

    contract, source, profile = load_contract(args.contract, args.source, args.profile)
    materials, roles, group_materials, neutral = normalized_full_receiver_materials(source, profile)
    static = {
        "state": "PASS_STATIC",
        "materials": len(materials),
        "group_roles": len(roles),
        "group_materials": len(group_materials),
        "neutral_material": neutral,
        "art_direction_question": contract["art_direction_request"]["question"],
    }
    if args.ta_root is not None:
        static["build"] = build_payload(args.contract, args.source, args.profile, args.ta_root, args.exact_head, args.out)
    if args.runtime_receipt is not None:
        static["runtime"] = verify_runtime(args.runtime_receipt, args.exact_head)
    print(json.dumps(static, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
