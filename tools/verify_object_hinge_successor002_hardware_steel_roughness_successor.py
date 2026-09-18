from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import verify_object_hinge_successor002_full_receiver_material_review as baseline

CONTRACT_SCHEMA = "axm.object-hinge-successor002-hardware-steel-roughness-successor/v0.1"
PAYLOAD_SCHEMA = "axm.object-hinge-successor002-hardware-steel-roughness-successor-payload/v0.1"
RUNTIME_SCHEMA = "axm.object-hinge-successor002-hardware-steel-roughness-successor-runtime/v0.1"
DECISION = "EVIDENCE_READY_OBJECT_HINGE_SUCCESSOR002_HARDWARE_STEEL_ROUGHNESS_SUCCESSOR_001"

EXPECTED_BASELINE_HEAD = "90789442be09aac60125f9423d1d5f7d65c1c1a3"
EXPECTED_BASELINE_ARTIFACT_ID = 10533132418
EXPECTED_BASELINE_ARTIFACT_SHA = "af712862f420a4a070c2a731136ba123f87cc40d1aca4613100a7a60d9b5dc84"
EXPECTED_BASELINE_RESULT = "PASS_OBJECT_HINGE_SUCCESSOR002_FULL_RECEIVER_MATERIAL_REVIEW_EVIDENCE_READY"
EXPECTED_ART_STATUS_BLOB = "35aa92c525fc08bc624e334b2a2427f95bd308a8"
EXPECTED_ART_PACKET_COMMIT = "030a170d265a115449d323c40a0f742037bf7774"
EXPECTED_ART_REVIEW_ID = 5244755848
EXPECTED_QA_STATUS_BLOB = "27453fcebcbcd4e8899324a703d5a733db5e95c9"
EXPECTED_QA_REVIEW_ID = 5244682857
EXPECTED_CONTROL_ROUGHNESS = 0.32
EXPECTED_SUCCESSOR_ROUGHNESS = 0.48
EXPECTED_ALBEDO_HEX = "#9AA3A8FF"
EXPECTED_METALLIC = 0.88
HINGE_COMPONENTS = baseline.HINGE_COMPONENTS
CONTEXTS = baseline.CONTEXTS


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"expected JSON object: {path}")
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_contract(contract_path: Path, source_path: Path, profile_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    contract = read_json(contract_path)
    profile = read_json(profile_path)
    if contract.get("schema") != CONTRACT_SCHEMA:
        raise AssertionError("roughness-successor contract schema drift")
    if baseline.sha256(source_path) != baseline.EXPECTED_SOURCE_SHA or contract.get("source_sha256") != baseline.EXPECTED_SOURCE_SHA:
        raise AssertionError("Object source identity drift")
    if baseline.sha256(profile_path) != baseline.EXPECTED_PROFILE_SHA or contract.get("material_profile_sha256") != baseline.EXPECTED_PROFILE_SHA:
        raise AssertionError("Object material profile identity drift")

    previous = contract.get("baseline_materials_owner", {})
    expected_previous = {
        "exact_head": EXPECTED_BASELINE_HEAD,
        "artifact_id": EXPECTED_BASELINE_ARTIFACT_ID,
        "artifact_sha256": EXPECTED_BASELINE_ARTIFACT_SHA,
        "expected_result": EXPECTED_BASELINE_RESULT,
    }
    for key, expected in expected_previous.items():
        if previous.get(key) != expected:
            raise AssertionError(f"baseline Materials binding drift for {key}")

    ta = contract.get("technical_art_owner", {})
    expected_ta = {
        "exact_head": baseline.EXPECTED_TA_HEAD,
        "artifact_id": baseline.EXPECTED_TA_ARTIFACT_ID,
        "artifact_sha256": baseline.EXPECTED_TA_ARTIFACT_SHA,
        "target_glb_sha256": baseline.EXPECTED_TARGET_GLB_SHA,
        "target_triangle_index_transform": baseline.EXPECTED_INDEX_TRANSFORM,
    }
    for key, expected in expected_ta.items():
        if ta.get(key) != expected:
            raise AssertionError(f"Technical Art binding drift for {key}")

    art = contract.get("art_direction_request", {})
    if art.get("status_blob") != EXPECTED_ART_STATUS_BLOB:
        raise AssertionError("Art Direction 045 status binding drift")
    if art.get("direction_packet_commit") != EXPECTED_ART_PACKET_COMMIT:
        raise AssertionError("Art Direction 045 packet binding drift")
    if int(art.get("review_id", -1)) != EXPECTED_ART_REVIEW_ID:
        raise AssertionError("Art Direction PR review binding drift")
    if art.get("failure") != "FAIL_ART_DIRECTION_OBJECT_HINGE_SUCCESSOR002_REAR_HIERARCHY_045__REPEATED_SPECULAR_STRIPE_TOO_DOMINANT":
        raise AssertionError("Art Direction failure identity drift")
    if art.get("side_reference") != "PASS_ART_DIRECTION_OBJECT_HINGE_SUCCESSOR002_SIDE_THREE_QUARTER_HIERARCHY_REFERENCE_045":
        raise AssertionError("Art Direction side reference identity drift")
    if art.get("request") != "REQUEST_ONE_BOUNDED_ROUGHNESS_ONLY_HARDWARE_STEEL_SUCCESSOR__ALBEDO_METALLIC_GEOMETRY_CAMERA_LIGHT_FROZEN":
        raise AssertionError("Art Direction successor request drift")

    qa = contract.get("visual_qa_return", {})
    if qa.get("status_blob") != EXPECTED_QA_STATUS_BLOB or int(qa.get("review_id", -1)) != EXPECTED_QA_REVIEW_ID:
        raise AssertionError("Visual QA return binding drift")

    scope = contract.get("review_scope", {})
    if int(scope.get("expected_total_mesh_nodes", -1)) != 31 or int(scope.get("expected_total_triangles", -1)) != 1052:
        raise AssertionError("complete receiver identity drift")
    if tuple(scope.get("hinge_components", [])) != HINGE_COMPONENTS or int(scope.get("expected_hinge_triangles", -1)) != 480:
        raise AssertionError("successor002 hinge subset drift")
    if tuple(scope.get("camera_contexts", [])) != CONTEXTS:
        raise AssertionError("camera context drift")

    control = scope.get("control_hardware_steel", {})
    successor = scope.get("successor_hardware_steel", {})
    for label, spec in (("control", control), ("successor", successor)):
        if spec.get("albedo") != EXPECTED_ALBEDO_HEX:
            raise AssertionError(f"{label} hardware_steel albedo drift")
        if float(spec.get("metallic", -1.0)) != EXPECTED_METALLIC:
            raise AssertionError(f"{label} hardware_steel metallic drift")
    if float(control.get("roughness", -1.0)) != EXPECTED_CONTROL_ROUGHNESS:
        raise AssertionError("control hardware_steel roughness drift")
    if float(successor.get("roughness", -1.0)) != EXPECTED_SUCCESSOR_ROUGHNESS:
        raise AssertionError("single successor roughness drift")
    if float(successor.get("roughness", -1.0)) == float(control.get("roughness", -1.0)):
        raise AssertionError("roughness successor must differ from the control")
    if scope.get("successor_applies_only_to_hinge_components") is not True:
        raise AssertionError("successor must remain hinge-only")
    if scope.get("all_non_hinge_materials_frozen") is not True or scope.get("geometry_uv_texture_camera_light_exposure_transport_frozen") is not True:
        raise AssertionError("Art-requested frozen dimensions drift")
    if scope.get("selection_method") != "ONE_ATTRIBUTABLE_SUCCESSOR_NOT_A_SCALAR_SWEEP":
        raise AssertionError("successor-selection method drift")

    renderer = contract.get("renderer", {})
    if renderer != {"engine": "Godot", "version": "4.7.2-stable", "rendering_method": "gl_compatibility"}:
        raise AssertionError("renderer contract drift")

    provenance = contract.get("provenance", {})
    if provenance.get("external_textures") not in ([], None) or provenance.get("external_material_assets") not in ([], None):
        raise AssertionError("external material provenance outside bounded successor")
    for key in (
        "technical_art_glb_bytes_edited_by_materials",
        "technical_art_triangle_transform_reimplemented_by_materials",
        "shared_material_profile_edited_for_successor",
        "roughness_sweep_performed",
    ):
        if provenance.get(key) is not False:
            raise AssertionError(f"forbidden provenance drift: {key}")

    truth = contract.get("truth_boundary", {})
    for key, value in truth.items():
        if value is not False:
            raise AssertionError(f"Materials authority expansion forbidden: {key}")

    candidate = profile.get("candidate", {})
    hardware = candidate.get("hardware_steel", {}) if isinstance(candidate, dict) else {}
    if hardware.get("albedo") != EXPECTED_ALBEDO_HEX or float(hardware.get("metallic", -1.0)) != EXPECTED_METALLIC or float(hardware.get("roughness", -1.0)) != EXPECTED_CONTROL_ROUGHNESS:
        raise AssertionError("shared profile hardware_steel control drift")
    return contract, profile


def build_payload(contract: dict[str, Any], baseline_payload_path: Path, exact_head: str, out_dir: Path) -> dict[str, Any]:
    base = read_json(baseline_payload_path)
    if base.get("schema") != baseline.PAYLOAD_SCHEMA:
        raise AssertionError("baseline full-receiver payload schema drift")
    if base.get("exact_materials_head") != exact_head:
        raise AssertionError("baseline payload is not bound to the exact successor head")
    if base.get("source_sha256") != baseline.EXPECTED_SOURCE_SHA or base.get("material_profile_sha256") != baseline.EXPECTED_PROFILE_SHA:
        raise AssertionError("baseline payload source/material identity drift")
    if base.get("target_glb_sha256") != baseline.EXPECTED_TARGET_GLB_SHA:
        raise AssertionError("baseline payload target GLB identity drift")
    if int(base.get("expected_total_mesh_nodes", -1)) != 31 or int(base.get("expected_total_triangles", -1)) != 1052:
        raise AssertionError("baseline payload full receiver drift")
    if tuple(base.get("hinge_components", [])) != HINGE_COMPONENTS:
        raise AssertionError("baseline payload hinge subset drift")
    group_materials = base.get("group_materials", {})
    if set(group_materials) != set(base.get("group_roles", {})) or len(group_materials) != 31:
        raise AssertionError("baseline payload material mapping drift")
    if any(group_materials.get(name) != "hardware_steel" for name in HINGE_COMPONENTS):
        raise AssertionError("hinge nodes no longer map to hardware_steel")
    control = base.get("materials", {}).get("hardware_steel", {})
    if control.get("albedo_hex") != EXPECTED_ALBEDO_HEX or float(control.get("metallic", -1.0)) != EXPECTED_METALLIC or float(control.get("roughness", -1.0)) != EXPECTED_CONTROL_ROUGHNESS:
        raise AssertionError("baseline payload hardware_steel drift")

    successor = dict(control)
    successor["roughness"] = EXPECTED_SUCCESSOR_ROUGHNESS
    payload = dict(base)
    payload["schema"] = PAYLOAD_SCHEMA
    payload["review_id"] = contract["review_id"]
    payload["art_direction_request"] = contract["art_direction_request"]
    payload["visual_qa_return"] = contract["visual_qa_return"]
    payload["control_hardware_steel"] = dict(control)
    payload["successor_hardware_steel"] = successor
    payload["successor_applies_only_to_hinge_components"] = True
    payload["selection_method"] = contract["review_scope"]["selection_method"]
    payload["truth_boundary"] = contract["truth_boundary"]

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "object_hinge_successor002_hardware_steel_roughness_successor_payload.json"
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    receipt = {
        "schema": "axm.object-hinge-successor002-hardware-steel-roughness-successor-build/v0.1",
        "result": "PASS_SOURCE_BOUND_OBJECT_HINGE_SUCCESSOR002_SINGLE_ROUGHNESS_SUCCESSOR_PAYLOAD",
        "exact_materials_head": exact_head,
        "baseline_materials_head": EXPECTED_BASELINE_HEAD,
        "target_glb_sha256": baseline.EXPECTED_TARGET_GLB_SHA,
        "control_roughness": EXPECTED_CONTROL_ROUGHNESS,
        "successor_roughness": EXPECTED_SUCCESSOR_ROUGHNESS,
        "albedo_unchanged": True,
        "metallic_unchanged": True,
        "hinge_components": list(HINGE_COMPONENTS),
        "camera_contexts": list(CONTEXTS),
        "shared_material_profile_edited": False,
        "roughness_sweep_performed": False,
        "promotion_effect": "NONE",
    }
    (out_dir / "object_hinge_successor002_hardware_steel_roughness_successor_build_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return receipt


def validate_runtime(receipt_path: Path, exact_head: str) -> dict[str, Any]:
    receipt = read_json(receipt_path)
    if receipt.get("schema") != RUNTIME_SCHEMA:
        raise AssertionError("roughness-successor runtime schema drift")
    if receipt.get("state") != "PASS_EVIDENCE":
        raise AssertionError(f"runtime evidence did not complete: {receipt.get('state')!r}")
    if receipt.get("decision") != DECISION:
        raise AssertionError("runtime evidence decision drift")
    if receipt.get("exact_materials_head") != exact_head:
        raise AssertionError("runtime exact Materials head drift")
    if receipt.get("target_glb_sha256") != baseline.EXPECTED_TARGET_GLB_SHA:
        raise AssertionError("runtime GLB identity drift")
    if float(receipt.get("control_roughness", -1.0)) != EXPECTED_CONTROL_ROUGHNESS or float(receipt.get("successor_roughness", -1.0)) != EXPECTED_SUCCESSOR_ROUGHNESS:
        raise AssertionError("runtime roughness identity drift")
    observations = receipt.get("observations", {})
    if set(observations) != set(CONTEXTS):
        raise AssertionError("runtime camera observation set drift")
    total_changed = 0
    for context in CONTEXTS:
        obs = observations.get(context, {})
        if int(obs.get("control_total_mesh_nodes", -1)) != 31 or int(obs.get("successor_total_mesh_nodes", -1)) != 31:
            raise AssertionError(f"complete receiver node count drift in {context}")
        if int(obs.get("control_total_triangles", -1)) != 1052 or int(obs.get("successor_total_triangles", -1)) != 1052:
            raise AssertionError(f"complete receiver triangle count drift in {context}")
        if int(obs.get("hinge_mask_pixels", 0)) <= 0:
            raise AssertionError(f"hinge mask is empty in {context}")
        total_changed += int(obs.get("control_vs_successor_changed_pixels_gt_1lsb", 0))
        for key in (
            "control_hinge_share_above_visible_p99",
            "successor_hinge_share_above_visible_p99",
            "control_hinge_mean_luminance",
            "successor_hinge_mean_luminance",
            "control_hinge_p95_luminance",
            "successor_hinge_p95_luminance",
        ):
            value = float(obs.get(key, -1.0))
            if not 0.0 <= value <= 1.0:
                raise AssertionError(f"invalid {key} in {context}: {value}")
    if total_changed <= 0:
        raise AssertionError("roughness-only successor produced no renderer-visible change in any retained context")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=Path("lookdev/object_hinge_successor002_hardware_steel_roughness_successor_001.json"))
    parser.add_argument("--source", type=Path, default=Path("assets/modular-equipment-case-001/source.json"))
    parser.add_argument("--profile", type=Path, default=Path("lookdev/object_material_profile_001.json"))
    parser.add_argument("--baseline-payload", type=Path)
    parser.add_argument("--out", type=Path, default=Path("lookdev-proof/generated/object-hinge-successor002-hardware-steel-roughness-successor"))
    parser.add_argument("--runtime-receipt", type=Path)
    parser.add_argument("--exact-head", required=True)
    args = parser.parse_args()

    contract, _profile = validate_contract(args.contract, args.source, args.profile)
    result: dict[str, Any] = {
        "state": "PASS_CONTRACT",
        "exact_materials_head": args.exact_head,
        "control_roughness": EXPECTED_CONTROL_ROUGHNESS,
        "successor_roughness": EXPECTED_SUCCESSOR_ROUGHNESS,
    }
    if args.baseline_payload is not None:
        result["build"] = build_payload(contract, args.baseline_payload, args.exact_head, args.out)
    if args.runtime_receipt is not None:
        result["runtime"] = validate_runtime(args.runtime_receipt, args.exact_head)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
