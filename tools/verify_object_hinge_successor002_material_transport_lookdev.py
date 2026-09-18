from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from build_modular_case import build as build_case

CONTRACT_SCHEMA = "axm.object-hinge-successor002-material-transport-lookdev/v0.1"
PAYLOAD_SCHEMA = "axm.object-hinge-successor002-material-transport-lookdev-payload/v0.1"
BUILD_SCHEMA = "axm.object-hinge-successor002-material-transport-lookdev-build/v0.1"
RUNTIME_SCHEMA = "axm.object-hinge-successor002-material-transport-lookdev-runtime/v0.1"
RESULT = "PASS_OBJECT_HINGE_SUCCESSOR002_TARGET_MATERIAL_BACKFACE_CULL_COHERENCE"

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
HINGE_COMPONENTS = (
    "hinge_body_b0",
    "hinge_lid_l0",
    "hinge_body_b1",
    "hinge_lid_l1",
    "hinge_body_b2",
)
CONTEXTS = ("hinge_rear", "hinge_three_quarter", "hinge_grazing")


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


def load_contract(contract_path: Path, source_path: Path, profile_path: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    contract = read_json(contract_path)
    source = read_json(source_path)
    profile = read_json(profile_path)
    if contract.get("schema") != CONTRACT_SCHEMA:
        raise AssertionError("successor002 Materials contract schema drift")
    if sha256(source_path) != EXPECTED_SOURCE_SHA or contract.get("source_sha256") != EXPECTED_SOURCE_SHA:
        raise AssertionError("Object source identity drift")
    if sha256(profile_path) != EXPECTED_PROFILE_SHA or contract.get("material_profile_sha256") != EXPECTED_PROFILE_SHA:
        raise AssertionError("Object material profile identity drift")

    owner = contract.get("technical_art_owner", {})
    expected = {
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
    for key, value in expected.items():
        if owner.get(key) != value:
            raise AssertionError(f"Technical Art owner binding drift for {key}: {owner.get(key)!r}")
    if float(owner.get("maximum_position_delta_m", -1.0)) != 1e-6:
        raise AssertionError("Technical Art POSITION tolerance drift")

    scope = contract.get("review_scope", {})
    if tuple(scope.get("hinge_components", [])) != HINGE_COMPONENTS:
        raise AssertionError("hinge review component set/order drift")
    if int(scope.get("expected_hinge_triangles", -1)) != 480:
        raise AssertionError("hinge triangle expectation drift")
    if tuple(scope.get("camera_contexts", [])) != CONTEXTS:
        raise AssertionError("hinge review camera set drift")

    renderer = contract.get("renderer", {})
    if renderer.get("engine") != "Godot" or renderer.get("version") != "4.7.2-stable" or renderer.get("rendering_method") != "gl_compatibility":
        raise AssertionError("renderer contract drift")

    provenance = contract.get("provenance", {})
    if provenance.get("external_textures") not in ([], None) or provenance.get("external_material_assets") not in ([], None):
        raise AssertionError("external material provenance is outside this bounded review")
    if provenance.get("technical_art_glb_bytes_edited_by_materials") is not False:
        raise AssertionError("Materials may not edit the Technical Art GLB")
    if provenance.get("technical_art_triangle_transform_reimplemented_by_materials") is not False:
        raise AssertionError("Materials may not reimplement the Technical Art triangle transform")
    if provenance.get("material_values_changed") is not False:
        raise AssertionError("material scalar changes are outside this receiving rebind")

    truth = contract.get("truth_boundary", {})
    forbidden_true = (
        "source_successor_default_adopted",
        "technical_art_transport_adopted_as_object_default",
        "materials_edits_transport_geometry",
        "materials_claims_universal_godot_winding_rule",
        "uvs_changed",
        "textures_changed",
        "material_scalars_changed",
        "runtime_or_physics_accepted",
        "art_direction_acceptance",
        "visual_qa_acceptance",
        "canon",
        "production_ready",
    )
    for key in forbidden_true:
        if truth.get(key) is not False:
            raise AssertionError(f"Materials authority expansion forbidden: {key}")
    return contract, source, profile


def normalized_hinge_materials(source: dict[str, Any], profile: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str], dict[str, str]]:
    if profile.get("schema") != "axm.object-material-profile/v0.1":
        raise AssertionError("material profile schema drift")
    candidate = profile.get("candidate", {})
    role_materials = profile.get("role_materials", {})
    if not isinstance(candidate, dict) or not isinstance(role_materials, dict):
        raise AssertionError("material profile mappings missing")

    materials: dict[str, Any] = {}
    for material_id, spec in candidate.items():
        metallic = float(spec["metallic"])
        roughness = float(spec["roughness"])
        if not (0.0 <= metallic <= 1.0 and 0.0 <= roughness <= 1.0):
            raise AssertionError(f"material scalar out of range: {material_id}")
        materials[str(material_id)] = {
            "albedo": rgba(str(spec["albedo"])),
            "albedo_hex": str(spec["albedo"]),
            "metallic": metallic,
            "roughness": roughness,
        }

    result = build_case(source)
    components = {str(item["name"]): item for item in result["components"]}
    if len(components) != 31:
        raise AssertionError("Object source component count drift")
    group_roles: dict[str, str] = {}
    group_materials: dict[str, str] = {}
    for name in HINGE_COMPONENTS:
        if name not in components:
            raise AssertionError(f"source missing hinge component {name}")
        role = str(components[name]["role"])
        if role not in ("hinge_knuckle_body", "hinge_knuckle_lid"):
            raise AssertionError(f"hinge role drift for {name}: {role}")
        material_id = str(role_materials.get(role, ""))
        if material_id != "hardware_steel" or material_id not in materials:
            raise AssertionError(f"hinge material mapping drift for {name}: {material_id}")
        group_roles[name] = role
        group_materials[name] = material_id
    return materials, group_roles, group_materials


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
    if int(ta.get("successor_hinge_triangles", -1)) != 480:
        raise AssertionError("Technical Art successor hinge triangle count drift")
    if target.get("result") != EXPECTED_TA_RESULT:
        raise AssertionError("Technical Art Godot transport receipt is not the pinned PASS")
    if target.get("technical_art_head") != EXPECTED_TA_HEAD:
        raise AssertionError("Technical Art target receipt head drift")
    if target.get("hard_surface_head") != EXPECTED_HARD_SURFACE_HEAD or target.get("geometry_head") != EXPECTED_GEOMETRY_HEAD or target.get("rigging_head") != EXPECTED_RIGGING_HEAD or target.get("uc_head") != EXPECTED_UC_HEAD:
        raise AssertionError("Technical Art target owner chain drift")
    if target.get("glb_sha256") != EXPECTED_TARGET_GLB_SHA or ta.get("successor_rebound_glb_sha256") != EXPECTED_TARGET_GLB_SHA:
        raise AssertionError("Technical Art target GLB receipt digest drift")
    if sha256(glb_path) != EXPECTED_TARGET_GLB_SHA:
        raise AssertionError("Technical Art target GLB byte identity drift")
    if int(target.get("aggregate_triangles", -1)) != 480:
        raise AssertionError("Technical Art target hinge triangle count drift")
    if target.get("index_and_winding_exact_for_all_five_components") is not True:
        raise AssertionError("Technical Art target index/winding evidence is not exact")
    if target.get("target_host_triangle_index_transform") != EXPECTED_INDEX_TRANSFORM:
        raise AssertionError("Technical Art target index transform drift")
    if target.get("source_indices_equal_after_import_for_any_component") is not False:
        raise AssertionError("Technical Art target source-index distinction drift")
    if float(target.get("maximum_position_delta_m", 1.0)) > 1e-6:
        raise AssertionError("Technical Art target POSITION error exceeds pinned bound")
    truth = target.get("truth_boundary", {})
    if truth.get("source_successor_default_adopted") is not False or truth.get("automatic_downstream_adoption") is not False:
        raise AssertionError("Technical Art target receipt expands adoption authority")
    return ta, target, glb_path


def build_payload(contract_path: Path, source_path: Path, profile_path: Path, ta_root: Path, exact_head: str, out_dir: Path) -> dict[str, Any]:
    contract, source, profile = load_contract(contract_path, source_path, profile_path)
    ta, target, glb_path = validate_ta_packet(ta_root)
    materials, group_roles, group_materials = normalized_hinge_materials(source, profile)
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
        "target_glb": "res://generated/object-hinge-successor002-material/object-rigid-components-hinge-successor002-rebound.glb",
        "camera_contexts": list(CONTEXTS),
        "hinge_components": list(HINGE_COMPONENTS),
        "expected_hinge_mesh_nodes": 5,
        "expected_hinge_triangles": 480,
        "expected_total_mesh_nodes": int(ta.get("mesh_nodes", -1)),
        "expected_total_triangles": int(ta.get("successor_total_triangles", -1)),
        "materials": materials,
        "group_roles": group_roles,
        "group_materials": group_materials,
        "review_scope": contract["review_scope"],
        "truth_boundary": contract["truth_boundary"],
    }
    if payload["expected_total_mesh_nodes"] != 31 or payload["expected_total_triangles"] <= 480:
        raise AssertionError("Technical Art full receiver shape drift")
    payload_path = out_dir / "object_hinge_successor002_material_transport_payload.json"
    payload_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    receipt = {
        "schema": BUILD_SCHEMA,
        "result": "PASS_SOURCE_BOUND_OBJECT_HINGE_SUCCESSOR002_MATERIAL_TRANSPORT_PAYLOAD",
        "exact_materials_head": exact_head,
        "exact_technical_art_head": EXPECTED_TA_HEAD,
        "technical_art_target_result": target["result"],
        "technical_art_target_glb_sha256": sha256(local_glb),
        "technical_art_target_triangle_index_transform": target["target_host_triangle_index_transform"],
        "technical_art_maximum_position_delta_m": target["maximum_position_delta_m"],
        "hinge_material": "hardware_steel",
        "hinge_component_count": len(group_materials),
        "hinge_triangles": 480,
        "material_scalars_changed": False,
        "source_successor_default_adopted": False,
        "technical_art_transport_adopted_as_object_default": False,
        "truth_boundary": contract["truth_boundary"],
    }
    (out_dir / "object_hinge_successor002_material_transport_build_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return receipt


def verify_runtime(path: Path) -> dict[str, Any]:
    receipt = read_json(path)
    if receipt.get("schema") != RUNTIME_SCHEMA:
        raise AssertionError("runtime receipt schema drift")
    if receipt.get("state") != "PASS_EVIDENCE":
        raise AssertionError(f"runtime evidence did not complete: {receipt.get('state')}")
    if receipt.get("exact_technical_art_head") != EXPECTED_TA_HEAD or receipt.get("target_glb_sha256") != EXPECTED_TARGET_GLB_SHA:
        raise AssertionError("runtime Technical Art identity drift")
    if receipt.get("material_profile_sha256") != EXPECTED_PROFILE_SHA:
        raise AssertionError("runtime material profile drift")
    comparisons = receipt.get("comparisons", {})
    if tuple(comparisons.keys()) != CONTEXTS:
        raise AssertionError(f"runtime camera set/order drift: {tuple(comparisons.keys())}")
    back_total = 0
    front_total = 0
    active_total = 0
    for context in CONTEXTS:
        row = comparisons[context]
        back = int(row["back_vs_two_sided"]["changed_pixels_gt_1lsb"])
        front = int(row["front_negative_vs_two_sided"]["changed_pixels_gt_1lsb"])
        active = int(row["lit_back_vs_unshaded_back"]["changed_pixels_gt_1lsb"])
        if front <= back:
            raise AssertionError(f"front-cull negative is not more disruptive than backface culling in {context}: back={back}, front={front}")
        if active <= 0:
            raise AssertionError(f"material response is visually inert in {context}")
        back_total += back
        front_total += front
        active_total += active
    if int(receipt.get("aggregate_back_vs_two_sided_gt1", -1)) != back_total:
        raise AssertionError("runtime backface aggregate drift")
    if int(receipt.get("aggregate_front_negative_vs_two_sided_gt1", -1)) != front_total:
        raise AssertionError("runtime front-negative aggregate drift")
    if int(receipt.get("aggregate_material_activity_gt1", -1)) != active_total:
        raise AssertionError("runtime material-activity aggregate drift")
    if not (front_total > back_total and front_total > 0 and active_total > 0):
        raise AssertionError("bounded cull-coherence decision is not supported")
    if receipt.get("decision") != RESULT:
        raise AssertionError(f"unexpected runtime decision: {receipt.get('decision')}")
    truth = receipt.get("truth_boundary", {})
    if truth.get("source_successor_default_adopted") is not False or truth.get("technical_art_transport_adopted_as_object_default") is not False:
        raise AssertionError("runtime receipt expands source/transport adoption authority")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", default="lookdev/object_hinge_successor002_material_transport_lookdev_001.json")
    parser.add_argument("--source", default="assets/modular-equipment-case-001/source.json")
    parser.add_argument("--profile", default="lookdev/object_material_profile_001.json")
    parser.add_argument("--exact-head", required=True)
    parser.add_argument("--ta-root")
    parser.add_argument("--out", default="lookdev-proof/generated/object-hinge-successor002-material")
    parser.add_argument("--runtime-receipt")
    args = parser.parse_args()
    contract_path = Path(args.contract)
    source_path = Path(args.source)
    profile_path = Path(args.profile)
    load_contract(contract_path, source_path, profile_path)
    if args.ta_root:
        receipt = build_payload(contract_path, source_path, profile_path, Path(args.ta_root), args.exact_head, Path(args.out))
        print(receipt["result"])
        print(json.dumps(receipt, indent=2, sort_keys=True))
    else:
        print("PASS_OBJECT_HINGE_SUCCESSOR002_MATERIAL_TRANSPORT_STATIC_BINDING")
    if args.runtime_receipt:
        runtime = verify_runtime(Path(args.runtime_receipt))
        print(runtime["decision"])
        print(json.dumps(runtime, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
