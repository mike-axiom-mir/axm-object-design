#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image

RESULT = "PASS_OBJECT_SERVICE_DARK_ROUGHNESS_L8_EXACT_SELECTED_FIELD_IDENTITY_REBOUND__HOLD_ART_QA_TARGET_DEVICE_AND_ADOPTION"
SCHEMA = "axm.object-service-dark-roughness-selected-field-runtime-rebind/v0.1"
MATERIALS_SCHEMA = "axm.object-service-dark-roughness-selected-field/v0.1"
PRIOR_COMPARISON_SCHEMA = "axm.object-service-dark-roughness-scalar-texture-runtime-comparison/v0.1"


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def scalar_digest(path: Path) -> tuple[str, int, int, int, tuple[int, int]]:
    with Image.open(path) as image:
        scalar = image.convert("L")
        raw = scalar.tobytes()
        return (
            hashlib.sha256(raw).hexdigest(),
            min(raw),
            max(raw),
            len(set(raw)),
            scalar.size,
        )


def verify(contract: dict, materials: dict, artifact_root: Path, archive_path: Path) -> dict:
    if contract.get("schema") != SCHEMA:
        raise AssertionError("Runtime selected-field rebind schema drift")
    if contract.get("asset_id") != "modular-equipment-case-001" or contract.get("material_id") != "service_dark":
        raise AssertionError("Runtime selected-field asset/material identity drift")

    selected = contract.get("materials_selected_field", {})
    prior = contract.get("prior_runtime_evidence", {})
    acceptance = contract.get("acceptance", {})
    truth = contract.get("truth_boundary", {})

    if materials.get("schema") != MATERIALS_SCHEMA:
        raise AssertionError("Materials selected-field schema drift")
    if materials.get("asset_id") != contract.get("asset_id") or materials.get("material_id") != contract.get("material_id"):
        raise AssertionError("Materials selected-field asset/material drift")
    material_selected = materials.get("selected_field", {})
    if material_selected.get("semantic_encoding") != "BASE_LEVEL_R8_SCALAR_VALUES_ROW_MAJOR":
        raise AssertionError("Materials selected-field semantic encoding drift")
    if [material_selected.get("width_px"), material_selected.get("height_px")] != [selected.get("width_px"), selected.get("height_px")]:
        raise AssertionError("Materials selected-field dimensions drift")
    if material_selected.get("scalar_r8_sha256") != selected.get("scalar_r8_sha256"):
        raise AssertionError("Materials selected scalar digest drift")
    if material_selected.get("historical_godot_png_sha256") != selected.get("historical_godot_png_sha256"):
        raise AssertionError("Materials selected PNG identity drift")
    if [material_selected.get("observed_r8_min"), material_selected.get("observed_r8_max"), material_selected.get("observed_unique_r8_values")] != [selected.get("observed_r8_min"), selected.get("observed_r8_max"), selected.get("observed_unique_r8_values")]:
        raise AssertionError("Materials selected R8 statistics drift")
    art = materials.get("art_direction_reference", {})
    if art.get("decision") != selected.get("art_direction_decision"):
        raise AssertionError("Art Direction selected-field decision drift")

    if sha256_file(archive_path) != prior.get("artifact_archive_sha256"):
        raise AssertionError("prior Runtime evidence archive identity drift")

    exact_runtime_head = (artifact_root / "runtime-proof/generated/exact-runtime-head.txt").read_text(encoding="utf-8").strip()
    if exact_runtime_head != prior.get("head"):
        raise AssertionError("prior Runtime exact head drift")

    comparison = read(artifact_root / "runtime-proof/generated/service_dark_roughness_l8_runtime_comparison.json")
    if comparison.get("schema") != PRIOR_COMPARISON_SCHEMA:
        raise AssertionError("prior Runtime comparison schema drift")
    if comparison.get("result") != prior.get("comparison_result"):
        raise AssertionError("prior Runtime comparison result drift")
    if comparison.get("exact_runtime_head") != prior.get("head"):
        raise AssertionError("prior Runtime comparison head drift")
    if comparison.get("control_format") != prior.get("control_format") or comparison.get("candidate_format") != prior.get("candidate_format"):
        raise AssertionError("prior Runtime format identity drift")

    exact_numeric = (
        "control_modeled_mip_bytes",
        "candidate_modeled_mip_bytes",
        "modeled_mip_bytes_saved",
        "modeled_mip_reduction_fraction",
        "observed_texture_allocation_bytes_saved",
        "changed_pixels_total",
        "changed_pixels_over_one_lsb_total",
        "max_channel_delta_lsb",
    )
    for key in exact_numeric:
        if comparison.get(key) != prior.get(key):
            raise AssertionError(f"prior Runtime exact result drift: {key}")

    control_png = artifact_root / "lookdev-proof/service-dark-runtime-roughness-rgba8_control-source.png"
    candidate_png = artifact_root / "lookdev-proof/service-dark-runtime-roughness-l8_candidate-source.png"
    if sha256_file(control_png) != selected.get("historical_godot_png_sha256"):
        raise AssertionError("prior Runtime RGBA8 control PNG is not the exact Materials-selected PNG identity")

    control_scalar = scalar_digest(control_png)
    candidate_scalar = scalar_digest(candidate_png)
    expected_scalar = selected.get("scalar_r8_sha256")
    expected_stats = (
        selected.get("observed_r8_min"),
        selected.get("observed_r8_max"),
        selected.get("observed_unique_r8_values"),
    )
    if control_scalar[0] != expected_scalar or candidate_scalar[0] != expected_scalar:
        raise AssertionError("Runtime control/candidate scalar bytes do not equal exact Materials-selected field")
    if control_scalar[1:4] != expected_stats or candidate_scalar[1:4] != expected_stats:
        raise AssertionError("Runtime control/candidate selected-field scalar statistics drift")
    if control_scalar[4] != (512, 512) or candidate_scalar[4] != (512, 512):
        raise AssertionError("Runtime selected-field dimensions drift")

    required_true = (
        "materials_contract_identity_must_match",
        "runtime_artifact_archive_identity_must_match",
        "runtime_control_png_container_must_equal_materials_selected_png_identity",
        "runtime_control_scalar_must_equal_materials_selected_scalar",
        "runtime_l8_candidate_scalar_must_equal_materials_selected_scalar",
        "runtime_comparison_result_must_remain_exact",
        "runtime_memory_saving_must_remain_exact",
        "runtime_visual_result_must_remain_exact",
        "no_new_renderer_measurement_claimed",
    )
    if any(acceptance.get(key) is not True for key in required_true):
        raise AssertionError("selected-field rebind acceptance contract drift")
    if any(value is not False for value in truth.values()):
        raise AssertionError("selected-field rebind truth boundary drift")

    return {
        "schema": "axm.object-service-dark-roughness-selected-field-runtime-rebind-receipt/v0.1",
        "result": RESULT,
        "materials_selected_field_head": selected["head"],
        "materials_selected_field_contract_blob": selected["contract_blob"],
        "materials_selected_scalar_r8_sha256": expected_scalar,
        "materials_selected_png_sha256": selected["historical_godot_png_sha256"],
        "prior_runtime_head": prior["head"],
        "prior_runtime_artifact_id": prior["artifact_id"],
        "prior_runtime_artifact_archive_sha256": prior["artifact_archive_sha256"],
        "runtime_control_png_sha256": sha256_file(control_png),
        "runtime_control_scalar_r8_sha256": control_scalar[0],
        "runtime_l8_candidate_scalar_r8_sha256": candidate_scalar[0],
        "selected_scalar_dimensions_px": list(control_scalar[4]),
        "selected_scalar_r8_min": control_scalar[1],
        "selected_scalar_r8_max": control_scalar[2],
        "selected_scalar_unique_r8_values": control_scalar[3],
        "control_format": comparison["control_format"],
        "candidate_format": comparison["candidate_format"],
        "control_modeled_mip_bytes": comparison["control_modeled_mip_bytes"],
        "candidate_modeled_mip_bytes": comparison["candidate_modeled_mip_bytes"],
        "modeled_mip_bytes_saved": comparison["modeled_mip_bytes_saved"],
        "modeled_mip_reduction_fraction": comparison["modeled_mip_reduction_fraction"],
        "observed_texture_allocation_bytes_saved": comparison["observed_texture_allocation_bytes_saved"],
        "changed_pixels_total": comparison["changed_pixels_total"],
        "changed_pixels_over_one_lsb_total": comparison["changed_pixels_over_one_lsb_total"],
        "max_channel_delta_lsb": comparison["max_channel_delta_lsb"],
        "visual_tradeoff": comparison["visual_tradeoff"],
        "evidence_semantics": "EXACT_IDENTITY_REBIND_OF_PRIOR_MEASURED_RUNTIME_RESULT__NO_NEW_RENDERER_MEASUREMENT",
        "acceptance": acceptance,
        "truth_boundary": truth,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", default="runtime/service_dark_roughness_selected_field_rebind_001.json")
    parser.add_argument("--materials-contract", required=True)
    parser.add_argument("--runtime-artifact-root", required=True)
    parser.add_argument("--runtime-archive", required=True)
    parser.add_argument("--out", default="runtime-proof/generated/service_dark_roughness_selected_field_rebind_receipt.json")
    args = parser.parse_args()

    receipt = verify(
        read(Path(args.contract)),
        read(Path(args.materials_contract)),
        Path(args.runtime_artifact_root),
        Path(args.runtime_archive),
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(receipt["result"])


if __name__ == "__main__":
    main()
