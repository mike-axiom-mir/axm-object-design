#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

SCHEMA = "axm.object-service-dark-roughness-selected-field/v0.1"
PAYLOAD_SCHEMA = "axm.object-service-dark-roughness-selected-field-payload/v0.1"
RUNTIME_SCHEMA = "axm.object-service-dark-roughness-selected-field-runtime/v0.1"
EXPECTED_ROUGHNESS_HEAD = "83f8d8fc99f7c832711f7f30fbcac72938550fc2"
EXPECTED_ROUGHNESS_CONTRACT_BLOB = "a4b7ff0e454a62e20ac5c3ed14f9af01092b2c56"
EXPECTED_ROUGHNESS_OBSERVER_BLOB = "4549a086f2f61f42f852daf6337c9d444980432c"
EXPECTED_ART_DIRECTION_COMMIT = "a15d394449a77204b365726affdff14cb2ec5dac"
EXPECTED_ART_DIRECTION_BLOB = "8aa8c54b7dd007b83255ce179f2cb672ae84b7e6"
EXPECTED_ART_DIRECTION_DECISION = "PASS_ART_DIRECTION_OBJECT_SERVICE_DARK_BOUNDED_ROUGHNESS_MICROVARIATION_PREFERENCE_024"
EXPECTED_SCALAR_SHA256 = "b8d13c07f9b71278042b0d42d44b84579a3f327c6adf6723cae4c8c8f06dd38e"
EXPECTED_PNG_SHA256 = "57cf746a9a7e0615884fe3c45c6c4df677c2bd0631def61b3ccb1684daa26949"


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def canonical_sha(obj: object) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def assert_close(actual: float, expected: float, label: str, tol: float = 1e-12) -> None:
    if abs(float(actual) - float(expected)) > tol:
        raise AssertionError(f"{label} drift: {actual} != {expected}")


def verify_contract(contract: dict, roughness_payload: dict) -> dict:
    if contract.get("schema") != SCHEMA:
        raise AssertionError("selected-field contract schema drift")
    if contract.get("asset_id") != "modular-equipment-case-001" or contract.get("material_id") != "service_dark":
        raise AssertionError("selected-field asset/material identity drift")
    if contract.get("roughness_evidence_head") != EXPECTED_ROUGHNESS_HEAD:
        raise AssertionError("selected-field roughness evidence head drift")
    if contract.get("roughness_contract_blob") != EXPECTED_ROUGHNESS_CONTRACT_BLOB:
        raise AssertionError("selected-field roughness contract blob drift")
    if contract.get("roughness_observer_blob") != EXPECTED_ROUGHNESS_OBSERVER_BLOB:
        raise AssertionError("selected-field roughness observer blob drift")

    art = contract.get("art_direction_reference", {})
    if art.get("commit") != EXPECTED_ART_DIRECTION_COMMIT or art.get("blob") != EXPECTED_ART_DIRECTION_BLOB:
        raise AssertionError("Art Direction reference identity drift")
    if art.get("decision") != EXPECTED_ART_DIRECTION_DECISION:
        raise AssertionError("Art Direction bounded preference drift")

    if roughness_payload.get("schema") != "axm.object-service-dark-roughness-microvariation-payload/v0.1":
        raise AssertionError("roughness payload schema drift")
    if roughness_payload.get("result") != "PASS_OBJECT_SERVICE_DARK_ROUGHNESS_MICROVARIATION_PAYLOAD":
        raise AssertionError("roughness payload result drift")
    if roughness_payload.get("asset_id") != contract["asset_id"] or roughness_payload.get("review", {}).get("material_id") != "service_dark":
        raise AssertionError("roughness payload asset/material drift")

    review = roughness_payload["review"]
    rough = review["roughness"]
    frozen = contract["frozen_response_envelope"]
    assert_close(rough["base"], frozen["roughness_center"], "roughness center")
    assert_close(rough["candidate_amplitude"], frozen["candidate_amplitude"], "roughness amplitude")
    if [float(v) for v in rough["candidate_range"]] != [float(v) for v in frozen["declared_range"]]:
        raise AssertionError("selected roughness declared range drift")
    if rough.get("pattern") != frozen.get("pattern"):
        raise AssertionError("selected roughness pattern drift")

    atlas = roughness_payload["atlas_pack_review"]["atlas"]
    required_atlas = frozen["atlas"]
    for key in ("width_px", "height_px", "pixels_per_meter", "padding_px", "filtering", "repeat"):
        if atlas.get(key) != required_atlas.get(key):
            raise AssertionError(f"selected roughness atlas drift: {key}")

    selected = contract["selected_field"]
    if selected.get("authority") != "MATERIALS_SELECTED_REVIEW_FIELD_IDENTITY_NOT_PRODUCTION_TEXTURE":
        raise AssertionError("selected-field authority boundary drift")
    if selected.get("semantic_encoding") != "BASE_LEVEL_R8_SCALAR_VALUES_ROW_MAJOR":
        raise AssertionError("selected-field semantic encoding drift")
    if [selected.get("width_px"), selected.get("height_px")] != [512, 512]:
        raise AssertionError("selected-field dimensions drift")
    if selected.get("scalar_r8_sha256") != EXPECTED_SCALAR_SHA256:
        raise AssertionError("selected scalar field digest drift")
    if selected.get("historical_godot_png_sha256") != EXPECTED_PNG_SHA256:
        raise AssertionError("selected historical PNG digest drift")
    if selected.get("historical_godot_png_bytes") != 32595:
        raise AssertionError("selected historical PNG byte count drift")
    if [selected.get("observed_r8_min"), selected.get("observed_r8_max"), selected.get("observed_unique_r8_values")] != [153, 183, 31]:
        raise AssertionError("selected R8 observation drift")

    serialization = contract["serialization_review"]
    if serialization.get("poses") != ["mid_open", "peak_open"] or serialization.get("contexts") != ["three_quarter", "front_interior"]:
        raise AssertionError("selected serialization review contexts drift")
    if serialization.get("require_base_level_scalar_digest_identity") is not True or serialization.get("require_real_render_pixel_identity") is not True:
        raise AssertionError("selected serialization acceptance gate drift")

    truth = contract["truth_boundary"]
    if truth.get("art_direction_bounded_preference_received") is not True:
        raise AssertionError("bounded Art Direction return missing")
    required_false = (
        "source_geometry_changed", "source_surface_identities_changed", "uv_scale_changed", "atlas_layout_changed",
        "base_color_changed", "metallic_changed", "roughness_center_changed", "roughness_amplitude_changed",
        "production_texture_authored", "physically_measured_coating", "technical_art_transport_accepted",
        "runtime_storage_adopted", "target_device_accepted", "visual_qa_final_accepted",
        "art_direction_final_accepted", "canon", "production_ready",
    )
    if any(truth.get(key) is not False for key in required_false):
        raise AssertionError("selected-field truth boundary drift")

    return {
        "schema": PAYLOAD_SCHEMA,
        "result": "PASS_OBJECT_SERVICE_DARK_SELECTED_ROUGHNESS_FIELD_IDENTITY_PAYLOAD",
        "asset_id": contract["asset_id"],
        "material_id": contract["material_id"],
        "roughness_evidence_head": contract["roughness_evidence_head"],
        "contract_sha256": canonical_sha(contract),
        "roughness_payload_sha256": canonical_sha(roughness_payload),
        "selected_field": selected,
        "serialization_review": serialization,
        "truth_boundary": truth,
        "roughness_payload": roughness_payload,
    }


def verify_runtime(contract: dict, receipt: dict) -> None:
    selected = contract["selected_field"]
    if receipt.get("schema") != RUNTIME_SCHEMA:
        raise AssertionError("selected-field runtime schema drift")
    if receipt.get("state") != "PASS":
        raise AssertionError("selected-field runtime state is not PASS")
    if receipt.get("result") != "PASS_OBJECT_SERVICE_DARK_SELECTED_ROUGHNESS_FIELD_SERIALIZATION_CONTINUITY":
        raise AssertionError("selected-field runtime result drift")
    if receipt.get("selected_scalar_r8_sha256") != selected["scalar_r8_sha256"]:
        raise AssertionError("selected scalar field digest drift")
    if receipt.get("serialized_scalar_r8_sha256") != selected["scalar_r8_sha256"]:
        raise AssertionError("serialized scalar field digest drift")
    if receipt.get("selected_png_sha256") != selected["historical_godot_png_sha256"]:
        raise AssertionError("selected PNG digest drift")
    if int(receipt.get("selected_png_bytes", -1)) != int(selected["historical_godot_png_bytes"]):
        raise AssertionError("selected PNG byte count drift")
    if [receipt.get("observed_r8_min"), receipt.get("observed_r8_max"), receipt.get("observed_unique_r8_values")] != [
        selected["observed_r8_min"], selected["observed_r8_max"], selected["observed_unique_r8_values"]
    ]:
        raise AssertionError("selected R8 observation drift")
    if receipt.get("base_level_scalar_identity") is not True or receipt.get("render_pixel_identity_all_contexts") is not True:
        raise AssertionError("selected-field serialization continuity gate failed")

    comparisons = receipt.get("comparisons", {})
    expected_pairs = {(p, c) for p in contract["serialization_review"]["poses"] for c in contract["serialization_review"]["contexts"]}
    actual_pairs = {(p, c) for p, contexts in comparisons.items() for c in contexts}
    if actual_pairs != expected_pairs:
        raise AssertionError(f"selected-field comparison coverage drift: {actual_pairs} != {expected_pairs}")
    for pose, context in sorted(expected_pairs):
        diff = comparisons[pose][context]
        if int(diff.get("changed_pixels_raw", -1)) != 0:
            raise AssertionError(f"serialized selected field changed rendered pixels: {pose}/{context}")
        if int(diff.get("changed_pixels_gt_1lsb", -1)) != 0:
            raise AssertionError(f"serialized selected field changed >1-LSB pixels: {pose}/{context}")
        assert_close(diff.get("max_rgb_channel_delta", -1.0), 0.0, f"render max delta {pose}/{context}")
        assert_close(diff.get("mean_abs_rgb_channel_delta", -1.0), 0.0, f"render mean delta {pose}/{context}")

    truth = receipt.get("truth_boundary", {})
    for key, value in contract["truth_boundary"].items():
        if truth.get(key) != value:
            raise AssertionError(f"runtime truth boundary drift: {key}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--contract", default="lookdev/service_dark_roughness_selected_field_001.json")
    ap.add_argument("--roughness-payload", default="lookdev-proof/generated/object_service_dark_roughness_microvariation_payload.json")
    ap.add_argument("--out", default="lookdev-proof/generated/object_service_dark_roughness_selected_field_payload.json")
    ap.add_argument("--runtime-receipt")
    args = ap.parse_args()

    contract = read(Path(args.contract))
    payload = verify_contract(contract, read(Path(args.roughness_payload)))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    if args.runtime_receipt:
        verify_runtime(contract, read(Path(args.runtime_receipt)))
        print("PASS_OBJECT_SERVICE_DARK_SELECTED_ROUGHNESS_FIELD_SERIALIZATION_CONTINUITY")
    else:
        print(payload["result"])


if __name__ == "__main__":
    main()
