from __future__ import annotations

import argparse
import copy
import hashlib
import importlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

CONTRACT_SCHEMA = "axm.object-hinge-successor003-relative-facet-phase-material-review/v0.1"
PAYLOAD_SCHEMA = "axm.object-hinge-successor003-relative-facet-phase-material-review-payload/v0.1"
BUILD_SCHEMA = "axm.object-hinge-successor003-relative-facet-phase-material-review-build/v0.1"
RUNTIME_SCHEMA = "axm.object-hinge-successor003-relative-facet-phase-material-review-runtime/v0.1"
DECISION = "EVIDENCE_READY_OBJECT_HINGE_SUCCESSOR003_RELATIVE_FACET_PHASE_MATERIAL_REVIEW_001"

EXPECTED_SOURCE_SHA = "49b1f9ed9865893d6de6f1ec8f069576732df694853fde4e3fcff366de32644a"
EXPECTED_PROFILE_SHA = "dc200229d6c25fa84063aa51f66103abc022efa54b2167e4432a5b47fc40360c"
EXPECTED_PREDECESSOR_MATERIALS_HEAD = "134e9a7622868acbd184519eade15996ab20fbbe"
EXPECTED_PREDECESSOR_ARTIFACT_ID = 10536492694
EXPECTED_PREDECESSOR_ARTIFACT_SHA = "7f20f3285dff37dcb6d769870d687699bde0f9d579c8c453913a7308daa5756a"
EXPECTED_ART_COMMIT = "8a751070c0d02ff772ef78a514ac4e1d0c3568ea"
EXPECTED_ART_REVIEW_ID = 5245661337
EXPECTED_QA_REVIEW_ID = 5245562753
EXPECTED_HS_HEAD = "ef1dfc2f2c1adbe3c90ba089c66ac09d223df25c"
EXPECTED_HS_ARTIFACT_ID = 10538130737
EXPECTED_HS_ARTIFACT_SHA = "b3d684146ca109f968f330a2b32e2923e2425c6a187db92987c3773fdbd9d016"
EXPECTED_HS_RESULT = "PASS_SOURCE_OWNED_HINGE_RELATIVE_FACET_PHASE_SUCCESSOR"
EXPECTED_SUCCESSOR_ID = "modular-equipment-case-001/hinge-bored-knuckle-relative-facet-phase-source-successor-003"
EXPECTED_TA_HEAD = "f430d00d98e694dcf8302fd4df3c64a074f6f30e"
EXPECTED_TA_ARTIFACT_ID = 10531541834
EXPECTED_TA_ARTIFACT_SHA = "5e1134d0ebdf786d04ae789a841493ce9cf684f16aedd7dbad597f2e02b3ad5e"
EXPECTED_CONTROL_GLB_SHA = "f81a9bccd9de1033476da4e5bbea3871b01e2ebf9fb65fcf909447fd14c43e40"
EXPECTED_UC_HEAD = "9609998db6677391766e9ee7ff53a5b9b08a3cb9"
HARDWARE_ALBEDO = "#7E868AFF"
HARDWARE_METALLIC = 0.88
HARDWARE_ROUGHNESS = 0.32
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


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"expected JSON object: {path}")
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_head(path: Path) -> str:
    return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()


def rgba(hex_value: str) -> list[float]:
    if len(hex_value) != 9 or not hex_value.startswith("#"):
        raise AssertionError(f"invalid RGBA hex {hex_value!r}")
    return [int(hex_value[i:i + 2], 16) / 255.0 for i in (1, 3, 5, 7)]


def validate_contract(contract_path: Path, source_path: Path, profile_path: Path) -> dict[str, Any]:
    contract = read_json(contract_path)
    if contract.get("schema") != CONTRACT_SCHEMA:
        raise AssertionError("relative-facet-phase Materials contract schema drift")
    if sha256(source_path) != EXPECTED_SOURCE_SHA or contract.get("source_sha256") != EXPECTED_SOURCE_SHA:
        raise AssertionError("Object source identity drift")
    if sha256(profile_path) != EXPECTED_PROFILE_SHA or contract.get("material_profile_sha256") != EXPECTED_PROFILE_SHA:
        raise AssertionError("Object material profile identity drift")

    previous = contract.get("predecessor_materials_reference", {})
    expected_previous = {
        "exact_head": EXPECTED_PREDECESSOR_MATERIALS_HEAD,
        "artifact_id": EXPECTED_PREDECESSOR_ARTIFACT_ID,
        "artifact_sha256": EXPECTED_PREDECESSOR_ARTIFACT_SHA,
        "decision": "EVIDENCE_READY_OBJECT_HINGE_SUCCESSOR002_HARDWARE_STEEL_BASE_VALUE_SUCCESSOR_001",
    }
    for key, expected in expected_previous.items():
        if previous.get(key) != expected:
            raise AssertionError(f"predecessor Materials binding drift for {key}")
    if previous.get("hardware_steel") != {
        "albedo": HARDWARE_ALBEDO,
        "metallic": HARDWARE_METALLIC,
        "roughness": HARDWARE_ROUGHNESS,
    }:
        raise AssertionError("Direction-047 frozen hardware_steel reference drift")

    art = contract.get("art_direction_request", {})
    if int(art.get("direction", -1)) != 47 or art.get("coordination_commit") != EXPECTED_ART_COMMIT:
        raise AssertionError("Art Direction 047 identity drift")
    if int(art.get("art_review_id", -1)) != EXPECTED_ART_REVIEW_ID or int(art.get("qa_review_id", -1)) != EXPECTED_QA_REVIEW_ID:
        raise AssertionError("Art / QA review binding drift")
    if art.get("request") != "ONE_LID_VS_BODY_RELATIVE_12_GON_FACET_PHASE_ONLY_SUCCESSOR":
        raise AssertionError("Art Direction bounded request drift")
    if art.get("no_more_scalar_search") is not True:
        raise AssertionError("scalar material search unexpectedly reopened")

    hs = contract.get("hard_surface_owner", {})
    expected_hs = {
        "exact_head": EXPECTED_HS_HEAD,
        "artifact_id": EXPECTED_HS_ARTIFACT_ID,
        "artifact_sha256": EXPECTED_HS_ARTIFACT_SHA,
        "expected_result": EXPECTED_HS_RESULT,
        "successor_id": EXPECTED_SUCCESSOR_ID,
        "segments": 12,
        "body_phase_deg": 0.0,
        "lid_phase_deg": 15.0,
        "relative_lid_minus_body_phase_deg": 15.0,
        "single_candidate_only": True,
        "no_phase_sweep": True,
    }
    for key, expected in expected_hs.items():
        if hs.get(key) != expected:
            raise AssertionError(f"Hard-Surface successor003 binding drift for {key}")

    ta = contract.get("technical_art_baseline", {})
    expected_ta = {
        "exact_head": EXPECTED_TA_HEAD,
        "artifact_id": EXPECTED_TA_ARTIFACT_ID,
        "artifact_sha256": EXPECTED_TA_ARTIFACT_SHA,
        "successor002_control_glb_sha256": EXPECTED_CONTROL_GLB_SHA,
        "current_uc_head": EXPECTED_UC_HEAD,
        "helper_module": "tools/build_object_hinge_successor002_ta_transport_rebind.py",
        "scene_helper_module": "tools/build_object_uc_rigid_scene_handoff.py",
        "review_carrier_rule": "MATERIALS_REEXECUTES_PINNED_TA_HELPERS_AND_GENERIC_UC_FOR_LOCAL_REVIEW_ONLY__NO_TA_ADOPTION_TRANSFER",
    }
    for key, expected in expected_ta.items():
        if ta.get(key) != expected:
            raise AssertionError(f"Technical-Art baseline binding drift for {key}")

    scope = contract.get("review_scope", {})
    if int(scope.get("expected_total_mesh_nodes", -1)) != 31 or int(scope.get("expected_total_triangles", -1)) != 1052:
        raise AssertionError("full-receiver identity drift")
    if tuple(scope.get("hinge_components", [])) != HINGE_COMPONENTS:
        raise AssertionError("hinge component set/order drift")
    if tuple(scope.get("body_hinge_components", [])) != BODY_COMPONENTS or tuple(scope.get("lid_hinge_components", [])) != LID_COMPONENTS:
        raise AssertionError("hinge owner partition drift")
    if int(scope.get("expected_hinge_triangles", -1)) != 480:
        raise AssertionError("hinge triangle count drift")
    if tuple(scope.get("camera_contexts", [])) != CONTEXTS:
        raise AssertionError("camera context drift")
    if scope.get("hardware_steel") != {
        "albedo": HARDWARE_ALBEDO,
        "metallic": HARDWARE_METALLIC,
        "roughness": HARDWARE_ROUGHNESS,
    }:
        raise AssertionError("frozen review material drift")
    for key in ("all_non_hinge_materials_frozen", "uv_texture_camera_light_exposure_frozen", "candidate_changes_source_facet_phase_only"):
        if scope.get(key) is not True:
            raise AssertionError(f"required frozen review dimension missing: {key}")

    if contract.get("renderer") != {"engine": "Godot", "version": "4.7.2-stable", "rendering_method": "gl_compatibility"}:
        raise AssertionError("renderer contract drift")

    provenance = contract.get("provenance", {})
    for key in (
        "hard_surface_source_bytes_edited_by_materials",
        "technical_art_control_glb_bytes_edited_by_materials",
        "technical_art_helper_code_copied_or_reimplemented_by_materials",
        "generic_uc_domain_policy_added",
        "material_scalar_search_performed",
        "material_values_changed_from_direction047_reference",
    ):
        if provenance.get(key) is not False:
            raise AssertionError(f"provenance boundary expanded: {key}")
    if provenance.get("external_textures") not in ([], None) or provenance.get("external_material_assets") not in ([], None):
        raise AssertionError("external material provenance outside bounded review")

    for key, value in contract.get("truth_boundary", {}).items():
        if value is not False:
            raise AssertionError(f"Materials authority expansion forbidden: {key}")
    return contract


def load_ta_helpers(ta_donor_root: Path):
    if git_head(ta_donor_root) != EXPECTED_TA_HEAD:
        raise AssertionError("pinned Technical-Art helper checkout drift")
    tools = ta_donor_root / "tools"
    sys.path.insert(0, str(tools))
    for module_name in ("build_object_hinge_successor002_ta_transport_rebind", "build_object_uc_rigid_scene_handoff"):
        if module_name in sys.modules:
            del sys.modules[module_name]
    ta = importlib.import_module("build_object_hinge_successor002_ta_transport_rebind")
    scene = importlib.import_module("build_object_uc_rigid_scene_handoff")
    return ta, scene


def primitive_triangles(primitive: dict[str, Any]) -> int:
    indices = primitive.get("indices")
    if not isinstance(indices, list) or len(indices) % 3:
        raise AssertionError(f"primitive indices not triangulated: {primitive.get('id')}")
    return len(indices) // 3


def max_position_delta(a: dict[str, Any], b: dict[str, Any]) -> float:
    ap = a.get("positions")
    bp = b.get("positions")
    if not isinstance(ap, list) or not isinstance(bp, list) or len(ap) != len(bp):
        raise AssertionError("primitive position array size drift")
    ai = a.get("indices")
    bi = b.get("indices")
    if ai != bi:
        raise AssertionError("primitive index topology drift")
    maximum = 0.0
    for av, bv in zip(ap, bp):
        if len(av) != 3 or len(bv) != 3:
            raise AssertionError("primitive position tuple drift")
        maximum = max(maximum, max(abs(float(av[i]) - float(bv[i])) for i in range(3)))
    return maximum


def validate_hs_packet(contract: dict[str, Any], hs_contract_path: Path, hs_receipt_path: Path, hs_obj_path: Path, hs_exact_head_path: Path) -> dict[str, Any]:
    if hs_exact_head_path.read_text(encoding="utf-8").strip() != EXPECTED_HS_HEAD:
        raise AssertionError("Hard-Surface retained exact-head drift")
    hs_contract = read_json(hs_contract_path)
    hs_receipt = read_json(hs_receipt_path)
    if hs_contract.get("successor_id") != EXPECTED_SUCCESSOR_ID:
        raise AssertionError("Hard-Surface successor003 contract identity drift")
    if hs_receipt.get("result") != EXPECTED_HS_RESULT or hs_receipt.get("successor_id") != EXPECTED_SUCCESSOR_ID:
        raise AssertionError("Hard-Surface retained successor003 receipt is not the pinned PASS")
    if int(hs_receipt.get("segments", -1)) != 12 or float(hs_receipt.get("body_phase_deg", -1.0)) != 0.0 or float(hs_receipt.get("lid_phase_deg", -1.0)) != 15.0:
        raise AssertionError("Hard-Surface retained phase identity drift")
    if int(hs_receipt.get("candidate_vertices", -1)) != 240 or int(hs_receipt.get("candidate_triangles", -1)) != 480:
        raise AssertionError("Hard-Surface retained candidate topology size drift")
    if hs_receipt.get("automatic_default_replacement") is not False or hs_receipt.get("automatic_downstream_adoption") is not False:
        raise AssertionError("Hard-Surface retained authority boundary drift")
    return {
        "contract_sha256": sha256(hs_contract_path),
        "receipt_sha256": sha256(hs_receipt_path),
        "candidate_obj_sha256": sha256(hs_obj_path),
    }


def validate_ta_baseline(ta_surface_path: Path, ta_manifest_path: Path, ta_scene_receipt_path: Path, control_glb_path: Path) -> dict[str, Any]:
    if sha256(control_glb_path) != EXPECTED_CONTROL_GLB_SHA:
        raise AssertionError("Technical-Art successor002 control GLB byte identity drift")
    surface = read_json(ta_surface_path)
    manifest = read_json(ta_manifest_path)
    scene_receipt = read_json(ta_scene_receipt_path)
    if surface.get("schema") != "axm.surface-3d/v0.1":
        raise AssertionError("Technical-Art successor002 surface schema drift")
    primitives = surface.get("primitives")
    if not isinstance(primitives, list) or len(primitives) != 31:
        raise AssertionError("Technical-Art successor002 surface node-count drift")
    if sum(primitive_triangles(p) for p in primitives) != 1052:
        raise AssertionError("Technical-Art successor002 surface triangle-count drift")
    if scene_receipt.get("result") != "PASS_OBJECT_SOURCE_OWNED_RIGID_PARTS_THROUGH_UC_SCENE_GRAPH":
        raise AssertionError("Technical-Art baseline scene receipt is not the pinned PASS")
    if scene_receipt.get("observed_uc_commit") != EXPECTED_UC_HEAD:
        raise AssertionError("Technical-Art baseline scene receipt UC identity drift")
    if not isinstance(scene_receipt.get("hinge_pivot_source_m"), list) or len(scene_receipt["hinge_pivot_source_m"]) != 3:
        raise AssertionError("Technical-Art baseline hinge pivot missing")
    return {"surface": surface, "manifest": manifest, "scene_receipt": scene_receipt}


def normalized_materials(source_path: Path, profile_path: Path) -> tuple[dict[str, Any], dict[str, str]]:
    tools_path = Path(__file__).resolve().parent
    sys.path.insert(0, str(tools_path))
    baseline = importlib.import_module("verify_object_hinge_successor002_full_receiver_material_review")
    source = read_json(source_path)
    profile = read_json(profile_path)
    materials, _roles, group_materials, _neutral = baseline.normalized_full_receiver_materials(source, profile)
    materials = copy.deepcopy(materials)
    materials["hardware_steel"] = {
        "albedo": rgba(HARDWARE_ALBEDO),
        "albedo_hex": HARDWARE_ALBEDO,
        "metallic": HARDWARE_METALLIC,
        "roughness": HARDWARE_ROUGHNESS,
    }
    if len(group_materials) != 31 or any(group_materials.get(name) != "hardware_steel" for name in HINGE_COMPONENTS):
        raise AssertionError("full-receiver material mapping drift")
    return materials, group_materials


def build_review(
    *,
    contract_path: Path,
    source_path: Path,
    profile_path: Path,
    exact_head: str,
    hs_contract_path: Path,
    hs_receipt_path: Path,
    hs_obj_path: Path,
    hs_exact_head_path: Path,
    ta_surface_path: Path,
    ta_manifest_path: Path,
    ta_scene_receipt_path: Path,
    control_glb_path: Path,
    ta_donor_root: Path,
    uc_root: Path,
    out_dir: Path,
) -> dict[str, Any]:
    contract = validate_contract(contract_path, source_path, profile_path)
    if git_head(uc_root) != EXPECTED_UC_HEAD:
        raise AssertionError("pinned generic UC checkout drift")
    hs_identity = validate_hs_packet(contract, hs_contract_path, hs_receipt_path, hs_obj_path, hs_exact_head_path)
    ta_packet = validate_ta_baseline(ta_surface_path, ta_manifest_path, ta_scene_receipt_path, control_glb_path)
    ta, scene = load_ta_helpers(ta_donor_root)

    baseline_surface = ta_packet["surface"]
    baseline_manifest = ta_packet["manifest"]
    scene_receipt = ta_packet["scene_receipt"]
    by_id = {str(p["id"]): p for p in baseline_surface["primitives"]}
    if set(HINGE_COMPONENTS) - set(by_id):
        raise AssertionError("Technical-Art baseline misses hinge receiver nodes")

    successor_mesh = ta.parse_grouped_obj(hs_obj_path)
    groups = {str(g["name"]): g for g in successor_mesh["groups"]}
    expected_source_groups = {f"{name}_relative_phase_candidate" for name in HINGE_COMPONENTS}
    if set(groups) != expected_source_groups:
        raise AssertionError(f"Hard-Surface candidate group set drift: {sorted(groups)}")

    pivot = scene_receipt["hinge_pivot_source_m"]
    replacements: dict[str, dict[str, Any]] = {}
    per_component: dict[str, Any] = {}
    body_max_delta = 0.0
    lid_min_delta = None
    for target in HINGE_COMPONENTS:
        source_name = f"{target}_relative_phase_candidate"
        group = dict(groups[source_name])
        group["name"] = target
        primitive, localization_error = ta.make_component_surface_group(
            successor_mesh,
            group,
            local_origin_source=pivot if target in LID_COMPONENTS else None,
        )
        if primitive_triangles(primitive) != 96:
            raise AssertionError(f"candidate triangle count drift for {target}")
        delta = max_position_delta(by_id[target], primitive)
        if target in BODY_COMPONENTS:
            body_max_delta = max(body_max_delta, delta)
            if delta > 1e-9:
                raise AssertionError(f"body-owned zero-phase candidate drifted from successor002: {target} max {delta}")
        else:
            lid_min_delta = delta if lid_min_delta is None else min(lid_min_delta, delta)
            if delta <= 1e-6:
                raise AssertionError(f"lid-owned +15 degree candidate did not change geometry: {target} max {delta}")
        replacements[target] = primitive
        per_component[target] = {
            "source_group": source_name,
            "owner": "lid" if target in LID_COMPONENTS else "body",
            "triangles": primitive_triangles(primitive),
            "positions": len(primitive["positions"]),
            "closed_static_localization_max_error_m": float(localization_error),
            "max_position_delta_vs_successor002_m": delta,
        }

    candidate_surface = copy.deepcopy(baseline_surface)
    candidate_surface["name"] = "modular-equipment-case-001-rigid-component-proof-hinge-successor003-material-review"
    candidate_surface["primitives"] = [replacements.get(str(p["id"]), p) for p in baseline_surface["primitives"]]

    candidate_by_id = {str(p["id"]): p for p in candidate_surface["primitives"]}
    for component_id, primitive in by_id.items():
        if component_id in HINGE_COMPONENTS:
            continue
        if scene.canonical_digest(primitive) != scene.canonical_digest(candidate_by_id[component_id]):
            raise AssertionError(f"unrelated receiver primitive drift: {component_id}")
    changed_semantic_ids = list(LID_COMPONENTS)

    sys.path.insert(0, str(uc_root / "src"))
    from axm_uc.procedural_3d import build_glb, verify_glb  # type: ignore
    from axm_uc.rigid_scene_graph import rebind_rigid_scene_graph, verify_rigid_scene_graph  # type: ignore

    flat = build_glb(candidate_surface)
    rebound = rebind_rigid_scene_graph(
        flat["body"],
        baseline_manifest,
        expected_spec_digest=flat["specification_sha256"],
    )
    flat_verify = verify_glb(flat["body"], expected_spec_digest=flat["specification_sha256"])
    rebound_verify = verify_glb(rebound["body"], expected_spec_digest=flat["specification_sha256"])
    graph_verify = verify_rigid_scene_graph(
        rebound["body"], expected_manifest_digest=rebound["manifest_sha256"]
    )
    if int(flat_verify["nodes"]) != 31 or int(rebound_verify["nodes"]) != 31:
        raise AssertionError("candidate review carrier node-count drift")
    if int(flat_verify["triangles"]) != 1052 or int(rebound_verify["triangles"]) != 1052:
        raise AssertionError("candidate review carrier triangle-count drift")
    if rebound["receipt"].get("binary_geometry_payload_identical") is not True:
        raise AssertionError("generic UC scene rebind changed candidate binary geometry payload")
    for name in LID_COMPONENTS:
        if graph_verify["parent_by_child"].get(name) != "lid_shell":
            raise AssertionError(f"candidate lid hinge parentage drift: {name}")
    for name in BODY_COMPONENTS:
        if name in graph_verify["parent_by_child"]:
            raise AssertionError(f"candidate body hinge unexpectedly parented: {name}")

    materials, group_materials = normalized_materials(source_path, profile_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    control_out = out_dir / "control-successor002.glb"
    candidate_surface_out = out_dir / "candidate-successor003.surface.json"
    candidate_manifest_out = out_dir / "candidate-successor003.scene-graph.json"
    candidate_flat_out = out_dir / "candidate-successor003-flat.glb"
    candidate_out = out_dir / "candidate-successor003.glb"
    shutil.copyfile(control_glb_path, control_out)
    candidate_surface_out.write_text(json.dumps(candidate_surface, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    candidate_manifest_out.write_text(json.dumps(rebound["manifest"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    candidate_flat_out.write_bytes(flat["body"])
    candidate_out.write_bytes(rebound["body"])

    candidate_sha = sha256(candidate_out)
    control_sha = sha256(control_out)
    if control_sha != EXPECTED_CONTROL_GLB_SHA:
        raise AssertionError("copied control GLB byte identity drift")
    if candidate_sha == control_sha:
        raise AssertionError("successor003 review carrier unexpectedly byte-identical to successor002 control")

    payload = {
        "schema": PAYLOAD_SCHEMA,
        "review_id": contract["review_id"],
        "exact_materials_head": exact_head,
        "source_sha256": EXPECTED_SOURCE_SHA,
        "material_profile_sha256": EXPECTED_PROFILE_SHA,
        "hard_surface_owner": contract["hard_surface_owner"],
        "technical_art_baseline": contract["technical_art_baseline"],
        "art_direction_request": contract["art_direction_request"],
        "control_glb": "res://generated/object-hinge-successor003-relative-facet-phase-material-review/control-successor002.glb",
        "control_glb_sha256": control_sha,
        "candidate_glb": "res://generated/object-hinge-successor003-relative-facet-phase-material-review/candidate-successor003.glb",
        "candidate_glb_sha256": candidate_sha,
        "expected_total_mesh_nodes": 31,
        "expected_total_triangles": 1052,
        "expected_hinge_triangles": 480,
        "hinge_components": list(HINGE_COMPONENTS),
        "body_hinge_components": list(BODY_COMPONENTS),
        "lid_hinge_components": list(LID_COMPONENTS),
        "camera_contexts": list(CONTEXTS),
        "materials": materials,
        "group_materials": group_materials,
        "hardware_steel_review": materials["hardware_steel"],
        "review_carrier_changed_primitive_ids": sorted(changed_semantic_ids),
        "truth_boundary": contract["truth_boundary"],
    }
    payload_path = out_dir / "object_hinge_successor003_relative_facet_phase_material_review_payload.json"
    payload_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    receipt = {
        "schema": BUILD_SCHEMA,
        "result": "PASS_SOURCE_BOUND_OBJECT_HINGE_SUCCESSOR003_MATERIALS_LOCAL_REVIEW_CARRIER",
        "exact_materials_head": exact_head,
        "hard_surface_head": EXPECTED_HS_HEAD,
        "hard_surface_artifact_id": EXPECTED_HS_ARTIFACT_ID,
        "hard_surface_artifact_sha256": EXPECTED_HS_ARTIFACT_SHA,
        "hard_surface_packet": hs_identity,
        "technical_art_baseline_head": EXPECTED_TA_HEAD,
        "technical_art_artifact_id": EXPECTED_TA_ARTIFACT_ID,
        "technical_art_artifact_sha256": EXPECTED_TA_ARTIFACT_SHA,
        "generic_uc_head": EXPECTED_UC_HEAD,
        "control_glb_sha256": control_sha,
        "candidate_glb_sha256": candidate_sha,
        "candidate_surface_sha256": sha256(candidate_surface_out),
        "candidate_manifest_sha256": sha256(candidate_manifest_out),
        "candidate_flat_glb_sha256": sha256(candidate_flat_out),
        "mesh_nodes": int(rebound_verify["nodes"]),
        "triangles": int(rebound_verify["triangles"]),
        "hinge_triangles": sum(primitive_triangles(candidate_by_id[name]) for name in HINGE_COMPONENTS),
        "body_zero_phase_max_position_delta_vs_control_m": body_max_delta,
        "lid_phase_min_position_delta_vs_control_m": lid_min_delta,
        "changed_primitive_ids": sorted(changed_semantic_ids),
        "per_component": per_component,
        "flat_uc_verification": flat_verify,
        "rebound_uc_verification": rebound_verify,
        "graph_verification": graph_verify,
        "material_reference": {"albedo": HARDWARE_ALBEDO, "metallic": HARDWARE_METALLIC, "roughness": HARDWARE_ROUGHNESS},
        "materials_local_review_carrier_only": True,
        "technical_art_successor003_adoption_claimed": False,
        "source_default_adoption_claimed": False,
        "art_or_qa_acceptance_claimed": False,
        "promotion_effect": "NONE",
    }
    receipt_path = out_dir / "object_hinge_successor003_relative_facet_phase_material_review_build_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def validate_runtime(runtime_path: Path, exact_head: str, build_receipt_path: Path) -> dict[str, Any]:
    runtime = read_json(runtime_path)
    build = read_json(build_receipt_path)
    if runtime.get("schema") != RUNTIME_SCHEMA or runtime.get("state") != "PASS_EVIDENCE" or runtime.get("decision") != DECISION:
        raise AssertionError("successor003 runtime evidence identity/state drift")
    if runtime.get("exact_materials_head") != exact_head or build.get("exact_materials_head") != exact_head:
        raise AssertionError("successor003 runtime/build exact-head drift")
    if runtime.get("control_glb_sha256") != build.get("control_glb_sha256") or runtime.get("candidate_glb_sha256") != build.get("candidate_glb_sha256"):
        raise AssertionError("successor003 runtime GLB identity drift")
    material = runtime.get("hardware_steel_review", {})
    if material.get("albedo_hex") != HARDWARE_ALBEDO or float(material.get("metallic", -1.0)) != HARDWARE_METALLIC or float(material.get("roughness", -1.0)) != HARDWARE_ROUGHNESS:
        raise AssertionError("runtime frozen hardware_steel reference drift")
    observations = runtime.get("observations", {})
    if set(observations) != set(CONTEXTS):
        raise AssertionError("runtime context set drift")
    for context in CONTEXTS:
        obs = observations[context]
        for key in ("control", "candidate", "control_hinge_mask", "candidate_hinge_mask"):
            frame = obs.get(key, {})
            if frame.get("state") != "PASS":
                raise AssertionError(f"runtime frame did not pass: {context}/{key}")
            if int(frame.get("total_mesh_nodes", -1)) != 31 or int(frame.get("total_triangles", -1)) != 1052:
                raise AssertionError(f"runtime receiver identity drift: {context}/{key}")
        if obs.get("control_vs_candidate", {}).get("state") != "PASS":
            raise AssertionError(f"runtime image comparison failed: {context}")
        for key in ("control_near_white", "candidate_near_white"):
            if obs.get(key, {}).get("state") != "PASS":
                raise AssertionError(f"runtime near-white extraction failed: {context}/{key}")
        if obs.get("near_white_overlap", {}).get("state") != "PASS":
            raise AssertionError(f"runtime near-white overlap failed: {context}")
    if runtime.get("promotion_effect") != "NONE":
        raise AssertionError("runtime evidence unexpectedly promotes candidate")
    return runtime


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--contract", type=Path, default=Path("lookdev/object_hinge_successor003_relative_facet_phase_material_review_001.json"))
    p.add_argument("--source", type=Path, default=Path("assets/modular-equipment-case-001/source.json"))
    p.add_argument("--profile", type=Path, default=Path("lookdev/object_material_profile_001.json"))
    p.add_argument("--exact-head", required=True)
    p.add_argument("--validate-only", action="store_true")
    p.add_argument("--hs-contract", type=Path)
    p.add_argument("--hs-receipt", type=Path)
    p.add_argument("--hs-obj", type=Path)
    p.add_argument("--hs-exact-head", type=Path)
    p.add_argument("--ta-surface", type=Path)
    p.add_argument("--ta-manifest", type=Path)
    p.add_argument("--ta-scene-receipt", type=Path)
    p.add_argument("--control-glb", type=Path)
    p.add_argument("--ta-donor-root", type=Path)
    p.add_argument("--uc-root", type=Path)
    p.add_argument("--out", type=Path)
    p.add_argument("--runtime-receipt", type=Path)
    p.add_argument("--build-receipt", type=Path)
    args = p.parse_args()

    validate_contract(args.contract, args.source, args.profile)
    if args.validate_only:
        print("PASS_OBJECT_HINGE_SUCCESSOR003_RELATIVE_FACET_PHASE_MATERIAL_REVIEW_CONTRACT")
        return
    if args.runtime_receipt is not None:
        if args.build_receipt is None:
            raise SystemExit("--build-receipt is required with --runtime-receipt")
        runtime = validate_runtime(args.runtime_receipt, args.exact_head, args.build_receipt)
        print(json.dumps(runtime, indent=2, sort_keys=True))
        return

    required = {
        "--hs-contract": args.hs_contract,
        "--hs-receipt": args.hs_receipt,
        "--hs-obj": args.hs_obj,
        "--hs-exact-head": args.hs_exact_head,
        "--ta-surface": args.ta_surface,
        "--ta-manifest": args.ta_manifest,
        "--ta-scene-receipt": args.ta_scene_receipt,
        "--control-glb": args.control_glb,
        "--ta-donor-root": args.ta_donor_root,
        "--uc-root": args.uc_root,
        "--out": args.out,
    }
    missing = [name for name, value in required.items() if value is None]
    if missing:
        raise SystemExit("missing build arguments: " + ", ".join(missing))
    receipt = build_review(
        contract_path=args.contract,
        source_path=args.source,
        profile_path=args.profile,
        exact_head=args.exact_head,
        hs_contract_path=args.hs_contract,
        hs_receipt_path=args.hs_receipt,
        hs_obj_path=args.hs_obj,
        hs_exact_head_path=args.hs_exact_head,
        ta_surface_path=args.ta_surface,
        ta_manifest_path=args.ta_manifest,
        ta_scene_receipt_path=args.ta_scene_receipt,
        control_glb_path=args.control_glb,
        ta_donor_root=args.ta_donor_root,
        uc_root=args.uc_root,
        out_dir=args.out,
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
