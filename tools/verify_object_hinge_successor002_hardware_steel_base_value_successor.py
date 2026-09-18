from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import verify_object_hinge_successor002_full_receiver_material_review as baseline

CONTRACT_SCHEMA = "axm.object-hinge-successor002-hardware-steel-base-value-successor/v0.1"
PAYLOAD_SCHEMA = "axm.object-hinge-successor002-hardware-steel-base-value-successor-payload/v0.1"
RUNTIME_SCHEMA = "axm.object-hinge-successor002-hardware-steel-base-value-successor-runtime/v0.1"
DECISION = "EVIDENCE_READY_OBJECT_HINGE_SUCCESSOR002_HARDWARE_STEEL_BASE_VALUE_SUCCESSOR_001"
EXPECTED_BASELINE_HEAD = "90789442be09aac60125f9423d1d5f7d65c1c1a3"
EXPECTED_BASELINE_ARTIFACT_ID = 10533132418
EXPECTED_BASELINE_ARTIFACT_SHA = "af712862f420a4a070c2a731136ba123f87cc40d1aca4613100a7a60d9b5dc84"
EXPECTED_BASELINE_RESULT = "PASS_OBJECT_HINGE_SUCCESSOR002_FULL_RECEIVER_MATERIAL_REVIEW_EVIDENCE_READY"
EXPECTED_FAILED_ROUGHNESS_HEAD = "db68a6b76e04ae2f19bb09cb7207f2874e19797b"
EXPECTED_FAILED_ROUGHNESS_ARTIFACT_ID = 10534614828
EXPECTED_FAILED_ROUGHNESS_ARTIFACT_SHA = "ece743ffc1735a9aa4eb5ce1b569b9a3e269d1ce3b667a329394df04c527220a"
EXPECTED_ART_STATUS_BLOB = "9ca48b36888767c2fa28882dd6974f5b53ec0c9e"
EXPECTED_ART_PACKET_COMMIT = "f2803615caf5688837410ceb3102fcdec50cdb1f"
EXPECTED_ART_REVIEW_ID = 5245176382
EXPECTED_QA_STATUS_BLOB = "34062ce08d3ad86fbe8930583af2c2ec8f92f9d4"
EXPECTED_QA_REVIEW_ID = 5245090483
CONTROL_ALBEDO_HEX = "#9AA3A8FF"
SUCCESSOR_ALBEDO_HEX = "#7E868AFF"
VALUE_SCALE_SRGB8 = 0.82
CONTROL_ROUGHNESS = 0.32
FAILED_ROUGHNESS = 0.48
METALLIC = 0.88
HINGE_COMPONENTS = baseline.HINGE_COMPONENTS
CONTEXTS = baseline.CONTEXTS


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"expected JSON object: {path}")
    return value


def scaled_rgb8(control_hex: str, scale: float) -> str:
    if len(control_hex) != 9 or not control_hex.startswith("#"):
        raise AssertionError("invalid control RGBA hex")
    channels = [int(control_hex[i : i + 2], 16) for i in (1, 3, 5)]
    alpha = int(control_hex[7:9], 16)
    scaled = [max(0, min(255, int(round(channel * scale)))) for channel in channels]
    return "#" + "".join(f"{channel:02X}" for channel in (*scaled, alpha))


def validate_contract(contract_path: Path, source_path: Path, profile_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    contract = read_json(contract_path)
    profile = read_json(profile_path)
    if contract.get("schema") != CONTRACT_SCHEMA:
        raise AssertionError("base-value-successor contract schema drift")
    if baseline.sha256(source_path) != baseline.EXPECTED_SOURCE_SHA or contract.get("source_sha256") != baseline.EXPECTED_SOURCE_SHA:
        raise AssertionError("Object source identity drift")
    if baseline.sha256(profile_path) != baseline.EXPECTED_PROFILE_SHA or contract.get("material_profile_sha256") != baseline.EXPECTED_PROFILE_SHA:
        raise AssertionError("Object material profile identity drift")

    previous = contract.get("baseline_materials_owner", {})
    for key, expected in {
        "exact_head": EXPECTED_BASELINE_HEAD,
        "artifact_id": EXPECTED_BASELINE_ARTIFACT_ID,
        "artifact_sha256": EXPECTED_BASELINE_ARTIFACT_SHA,
        "expected_result": EXPECTED_BASELINE_RESULT,
    }.items():
        if previous.get(key) != expected:
            raise AssertionError(f"baseline Materials binding drift for {key}")

    failed = contract.get("failed_roughness_reference", {})
    for key, expected in {
        "exact_head": EXPECTED_FAILED_ROUGHNESS_HEAD,
        "artifact_id": EXPECTED_FAILED_ROUGHNESS_ARTIFACT_ID,
        "artifact_sha256": EXPECTED_FAILED_ROUGHNESS_ARTIFACT_SHA,
        "evidence_decision": "EVIDENCE_READY_OBJECT_HINGE_SUCCESSOR002_HARDWARE_STEEL_ROUGHNESS_SUCCESSOR_001",
        "art_result": "FAIL_ART_DIRECTION_OBJECT_HINGE_ROUGHNESS048_046__BROADENED_SPECULAR_BAND_WORSENS_HIERARCHY",
    }.items():
        if failed.get(key) != expected:
            raise AssertionError(f"failed roughness reference drift for {key}")

    ta = contract.get("technical_art_owner", {})
    for key, expected in {
        "exact_head": baseline.EXPECTED_TA_HEAD,
        "artifact_id": baseline.EXPECTED_TA_ARTIFACT_ID,
        "artifact_sha256": baseline.EXPECTED_TA_ARTIFACT_SHA,
        "target_glb_sha256": baseline.EXPECTED_TARGET_GLB_SHA,
        "target_triangle_index_transform": baseline.EXPECTED_INDEX_TRANSFORM,
    }.items():
        if ta.get(key) != expected:
            raise AssertionError(f"Technical Art binding drift for {key}")

    art = contract.get("art_direction_request", {})
    if art.get("status_blob") != EXPECTED_ART_STATUS_BLOB or art.get("direction_packet_commit") != EXPECTED_ART_PACKET_COMMIT or int(art.get("review_id", -1)) != EXPECTED_ART_REVIEW_ID:
        raise AssertionError("Art Direction 046 binding drift")
    if art.get("restore") != "RESTORE_OBJECT_HINGE_HARDWARE_STEEL_ROUGHNESS_032_CONTROL":
        raise AssertionError("Art Direction restored-control identity drift")
    if art.get("request") != "REQUEST_ONE_BASE_VALUE_ONLY_HARDWARE_STEEL_SUCCESSOR__R032_M088_GEOMETRY_TRANSPORT_CAMERA_LIGHT_FROZEN":
        raise AssertionError("Art Direction base-value successor request drift")

    qa = contract.get("visual_qa_return", {})
    if qa.get("status_blob") != EXPECTED_QA_STATUS_BLOB or int(qa.get("review_id", -1)) != EXPECTED_QA_REVIEW_ID:
        raise AssertionError("Visual QA roughness-failure binding drift")

    scope = contract.get("review_scope", {})
    if int(scope.get("expected_total_mesh_nodes", -1)) != 31 or int(scope.get("expected_total_triangles", -1)) != 1052:
        raise AssertionError("complete receiver identity drift")
    if tuple(scope.get("hinge_components", [])) != HINGE_COMPONENTS or int(scope.get("expected_hinge_triangles", -1)) != 480:
        raise AssertionError("successor002 hinge subset drift")
    if tuple(scope.get("camera_contexts", [])) != CONTEXTS:
        raise AssertionError("camera context drift")

    control = scope.get("control_hardware_steel", {})
    negative = scope.get("failed_roughness_negative", {})
    successor = scope.get("successor_hardware_steel", {})
    if control != {"albedo": CONTROL_ALBEDO_HEX, "metallic": METALLIC, "roughness": CONTROL_ROUGHNESS}:
        raise AssertionError("restored control hardware_steel drift")
    if negative != {"albedo": CONTROL_ALBEDO_HEX, "metallic": METALLIC, "roughness": FAILED_ROUGHNESS}:
        raise AssertionError("failed roughness negative identity drift")
    if successor.get("albedo") != SUCCESSOR_ALBEDO_HEX:
        raise AssertionError("single successor albedo/value drift")
    if float(successor.get("metallic", -1.0)) != METALLIC or float(successor.get("roughness", -1.0)) != CONTROL_ROUGHNESS:
        raise AssertionError("base-value successor changed metallic or restored roughness")
    if float(successor.get("base_value_scale_srgb8", -1.0)) != VALUE_SCALE_SRGB8:
        raise AssertionError("base-value scale drift")
    if successor.get("base_value_transform") != "ROUND_EACH_CONTROL_RGB8_CHANNEL_TIMES_0P82":
        raise AssertionError("base-value transform identity drift")
    if scaled_rgb8(CONTROL_ALBEDO_HEX, VALUE_SCALE_SRGB8) != SUCCESSOR_ALBEDO_HEX:
        raise AssertionError("successor albedo is not the declared one-scalar RGB8 value transform")
    if scope.get("successor_applies_only_to_hinge_components") is not True or scope.get("all_non_hinge_materials_frozen") is not True or scope.get("geometry_uv_texture_camera_light_exposure_transport_frozen") is not True:
        raise AssertionError("Art-requested frozen dimensions drift")
    if scope.get("selection_method") != "ONE_ATTRIBUTABLE_BASE_VALUE_SUCCESSOR_NOT_A_SCALAR_SWEEP":
        raise AssertionError("successor-selection method drift")

    renderer = contract.get("renderer", {})
    if renderer != {"engine": "Godot", "version": "4.7.2-stable", "rendering_method": "gl_compatibility"}:
        raise AssertionError("renderer contract drift")
    provenance = contract.get("provenance", {})
    for key in (
        "technical_art_glb_bytes_edited_by_materials",
        "technical_art_triangle_transform_reimplemented_by_materials",
        "shared_material_profile_edited_for_successor",
        "base_value_sweep_performed",
        "roughness_changed_from_restored_control",
        "metallic_changed",
    ):
        if provenance.get(key) is not False:
            raise AssertionError(f"forbidden provenance drift: {key}")
    if provenance.get("external_textures") not in ([], None) or provenance.get("external_material_assets") not in ([], None):
        raise AssertionError("external material provenance outside bounded successor")
    for key, value in contract.get("truth_boundary", {}).items():
        if value is not False:
            raise AssertionError(f"Materials authority expansion forbidden: {key}")

    hardware = profile.get("candidate", {}).get("hardware_steel", {})
    if hardware.get("albedo") != CONTROL_ALBEDO_HEX or float(hardware.get("metallic", -1.0)) != METALLIC or float(hardware.get("roughness", -1.0)) != CONTROL_ROUGHNESS:
        raise AssertionError("shared profile hardware_steel control drift")
    return contract, profile


def build_payload(contract: dict[str, Any], baseline_payload_path: Path, exact_head: str, out_dir: Path) -> dict[str, Any]:
    base = read_json(baseline_payload_path)
    if base.get("schema") != baseline.PAYLOAD_SCHEMA or base.get("exact_materials_head") != exact_head:
        raise AssertionError("baseline full-receiver payload identity drift")
    if base.get("source_sha256") != baseline.EXPECTED_SOURCE_SHA or base.get("material_profile_sha256") != baseline.EXPECTED_PROFILE_SHA or base.get("target_glb_sha256") != baseline.EXPECTED_TARGET_GLB_SHA:
        raise AssertionError("baseline source/material/GLB identity drift")
    if int(base.get("expected_total_mesh_nodes", -1)) != 31 or int(base.get("expected_total_triangles", -1)) != 1052:
        raise AssertionError("baseline complete receiver drift")
    if tuple(base.get("hinge_components", [])) != HINGE_COMPONENTS:
        raise AssertionError("baseline hinge subset drift")
    group_materials = base.get("group_materials", {})
    if len(group_materials) != 31 or any(group_materials.get(name) != "hardware_steel" for name in HINGE_COMPONENTS):
        raise AssertionError("baseline hinge material mapping drift")
    control = base.get("materials", {}).get("hardware_steel", {})
    if control.get("albedo_hex") != CONTROL_ALBEDO_HEX or float(control.get("metallic", -1.0)) != METALLIC or float(control.get("roughness", -1.0)) != CONTROL_ROUGHNESS:
        raise AssertionError("baseline payload hardware_steel drift")

    roughness_negative = dict(control)
    roughness_negative["roughness"] = FAILED_ROUGHNESS
    successor = dict(control)
    successor["albedo_hex"] = SUCCESSOR_ALBEDO_HEX
    successor["albedo"] = baseline.rgba(SUCCESSOR_ALBEDO_HEX)
    payload = dict(base)
    payload.update({
        "schema": PAYLOAD_SCHEMA,
        "review_id": contract["review_id"],
        "art_direction_request": contract["art_direction_request"],
        "visual_qa_return": contract["visual_qa_return"],
        "failed_roughness_reference": contract["failed_roughness_reference"],
        "control_hardware_steel": dict(control),
        "failed_roughness_hardware_steel": roughness_negative,
        "successor_hardware_steel": successor,
        "successor_base_value_scale_srgb8": VALUE_SCALE_SRGB8,
        "successor_applies_only_to_hinge_components": True,
        "selection_method": contract["review_scope"]["selection_method"],
        "truth_boundary": contract["truth_boundary"],
    })
    out_dir.mkdir(parents=True, exist_ok=True)
    payload_path = out_dir / "object_hinge_successor002_hardware_steel_base_value_successor_payload.json"
    payload_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    receipt = {
        "schema": "axm.object-hinge-successor002-hardware-steel-base-value-successor-build/v0.1",
        "result": "PASS_SOURCE_BOUND_OBJECT_HINGE_SUCCESSOR002_SINGLE_BASE_VALUE_SUCCESSOR_PAYLOAD",
        "exact_materials_head": exact_head,
        "baseline_materials_head": EXPECTED_BASELINE_HEAD,
        "failed_roughness_head": EXPECTED_FAILED_ROUGHNESS_HEAD,
        "target_glb_sha256": baseline.EXPECTED_TARGET_GLB_SHA,
        "control_albedo": CONTROL_ALBEDO_HEX,
        "successor_albedo": SUCCESSOR_ALBEDO_HEX,
        "base_value_scale_srgb8": VALUE_SCALE_SRGB8,
        "control_roughness": CONTROL_ROUGHNESS,
        "failed_roughness": FAILED_ROUGHNESS,
        "successor_roughness": CONTROL_ROUGHNESS,
        "metallic": METALLIC,
        "hinge_components": list(HINGE_COMPONENTS),
        "camera_contexts": list(CONTEXTS),
        "shared_material_profile_edited": False,
        "base_value_sweep_performed": False,
        "promotion_effect": "NONE",
    }
    (out_dir / "object_hinge_successor002_hardware_steel_base_value_successor_build_receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def validate_runtime(receipt_path: Path, exact_head: str) -> dict[str, Any]:
    receipt = read_json(receipt_path)
    if receipt.get("schema") != RUNTIME_SCHEMA or receipt.get("state") != "PASS_EVIDENCE" or receipt.get("decision") != DECISION:
        raise AssertionError("base-value-successor runtime identity/state drift")
    if receipt.get("exact_materials_head") != exact_head or receipt.get("target_glb_sha256") != baseline.EXPECTED_TARGET_GLB_SHA:
        raise AssertionError("runtime exact-head/GLB identity drift")
    if receipt.get("control_albedo") != CONTROL_ALBEDO_HEX or receipt.get("successor_albedo") != SUCCESSOR_ALBEDO_HEX:
        raise AssertionError("runtime base-value identity drift")
    if float(receipt.get("control_roughness", -1.0)) != CONTROL_ROUGHNESS or float(receipt.get("failed_roughness", -1.0)) != FAILED_ROUGHNESS or float(receipt.get("successor_roughness", -1.0)) != CONTROL_ROUGHNESS:
        raise AssertionError("runtime roughness identity drift")
    if float(receipt.get("metallic", -1.0)) != METALLIC:
        raise AssertionError("runtime metallic drift")
    observations = receipt.get("observations", {})
    if set(observations) != set(CONTEXTS):
        raise AssertionError("runtime camera observation set drift")
    aggregate_successor = 0
    aggregate_negative = 0
    for context in CONTEXTS:
        obs = observations.get(context, {})
        for prefix in ("control", "failed_roughness", "successor"):
            if int(obs.get(f"{prefix}_total_mesh_nodes", -1)) != 31:
                raise AssertionError(f"complete receiver node count drift in {context}/{prefix}")
            if int(obs.get(f"{prefix}_total_triangles", -1)) != 1052:
                raise AssertionError(f"complete receiver triangle count drift in {context}/{prefix}")
        if int(obs.get("hinge_mask_pixels", 0)) <= 0:
            raise AssertionError(f"hinge mask is empty in {context}")
        successor_delta = obs.get("control_vs_successor", {})
        negative_delta = obs.get("control_vs_failed_roughness", {})
        if successor_delta.get("state") != "PASS" or negative_delta.get("state") != "PASS":
            raise AssertionError(f"comparison delta missing in {context}")
        aggregate_successor += int(successor_delta.get("changed_pixels_gt_1lsb", 0))
        aggregate_negative += int(negative_delta.get("changed_pixels_gt_1lsb", 0))
        for prefix in ("control", "failed_roughness", "successor"):
            for suffix in ("hinge_share_above_visible_p99", "hinge_mean_luminance", "hinge_p95_luminance"):
                value = float(obs.get(f"{prefix}_{suffix}", -1.0))
                if not 0.0 <= value <= 1.0:
                    raise AssertionError(f"invalid {prefix}_{suffix} in {context}: {value}")
    if aggregate_successor <= 0 or int(receipt.get("aggregate_control_vs_successor_gt1", -1)) != aggregate_successor:
        raise AssertionError("base-value successor renderer-visible delta accounting drift")
    if aggregate_negative <= 0 or int(receipt.get("aggregate_control_vs_failed_roughness_gt1", -1)) != aggregate_negative:
        raise AssertionError("failed roughness reference renderer-visible delta accounting drift")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=Path("lookdev/object_hinge_successor002_hardware_steel_base_value_successor_001.json"))
    parser.add_argument("--source", type=Path, default=Path("assets/modular-equipment-case-001/source.json"))
    parser.add_argument("--profile", type=Path, default=Path("lookdev/object_material_profile_001.json"))
    parser.add_argument("--baseline-payload", type=Path)
    parser.add_argument("--out", type=Path, default=Path("lookdev-proof/generated/object-hinge-successor002-hardware-steel-base-value-successor"))
    parser.add_argument("--runtime-receipt", type=Path)
    parser.add_argument("--exact-head", required=True)
    args = parser.parse_args()
    contract, _profile = validate_contract(args.contract, args.source, args.profile)
    result: dict[str, Any] = {
        "state": "PASS_CONTRACT",
        "exact_materials_head": args.exact_head,
        "control_albedo": CONTROL_ALBEDO_HEX,
        "successor_albedo": SUCCESSOR_ALBEDO_HEX,
        "base_value_scale_srgb8": VALUE_SCALE_SRGB8,
        "control_roughness": CONTROL_ROUGHNESS,
        "failed_roughness": FAILED_ROUGHNESS,
        "metallic": METALLIC,
    }
    if args.baseline_payload is not None:
        result["build"] = build_payload(contract, args.baseline_payload, args.exact_head, args.out)
    if args.runtime_receipt is not None:
        result["runtime"] = validate_runtime(args.runtime_receipt, args.exact_head)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
