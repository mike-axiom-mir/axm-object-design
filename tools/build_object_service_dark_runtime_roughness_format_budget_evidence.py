#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

RUNTIME_SCHEMA = "axm.object-service-dark-roughness-scalar-texture-budget/v0.1"
ROUGHNESS_PAYLOAD_SCHEMA = "axm.object-service-dark-roughness-microvariation-payload/v0.1"
RESULT = "PASS_OBJECT_SERVICE_DARK_ROUGHNESS_SCALAR_TEXTURE_BUDGET_PACKET"


def read(path: Path):
    return json.loads(path.read_text())


def canonical_sha(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def mip_texel_count(width: int, height: int) -> int:
    total = 0
    w, h = width, height
    while True:
        total += w * h
        if w == 1 and h == 1:
            return total
        w = max(1, w // 2)
        h = max(1, h // 2)


def verify(runtime: dict, roughness_payload: dict, exact_head: str) -> dict:
    if runtime.get("schema") != RUNTIME_SCHEMA:
        raise AssertionError("runtime budget schema drift")
    if roughness_payload.get("schema") != ROUGHNESS_PAYLOAD_SCHEMA:
        raise AssertionError("roughness payload schema drift")
    if runtime.get("asset_id") != roughness_payload.get("asset_id"):
        raise AssertionError("asset identity drift")
    if runtime.get("material_id") != roughness_payload.get("review", {}).get("material_id"):
        raise AssertionError("material identity drift")

    upstream = runtime.get("upstream", {})
    if roughness_payload.get("exact_materials_head") != upstream.get("materials_head"):
        raise AssertionError("exact Materials head drift")

    atlas = roughness_payload["atlas_pack_review"]["atlas"]
    preserve = runtime.get("preserve", {})
    for key in ("width_px", "height_px", "pixels_per_meter", "padding_px", "filtering", "repeat"):
        if atlas.get(key) != preserve.get(key):
            raise AssertionError(f"preserved atlas property drift: {key}")

    review_rough = roughness_payload["review"]["roughness"]
    expected = {
        "base_roughness": float(review_rough["base"]),
        "candidate_roughness_amplitude": float(review_rough["candidate_amplitude"]),
        "candidate_roughness_range": [float(v) for v in review_rough["candidate_range"]],
    }
    for key, value in expected.items():
        if preserve.get(key) != value:
            raise AssertionError(f"preserved roughness property drift: {key}")

    required_true = (
        "surface_rectangles_unchanged",
        "roughness_generator_unchanged",
        "uvs_unchanged",
        "shader_sample_semantics_unchanged",
        "mipmaps_enabled",
    )
    if any(preserve.get(key) is not True for key in required_true):
        raise AssertionError("Runtime preserve contract must remain fail-closed true")

    control = runtime.get("control", {})
    candidate = runtime.get("candidate", {})
    if control != {"mode": "rgba8_control", "image_format": "RGBA8", "bytes_per_texel": 4, "sample_channel": "R"}:
        raise AssertionError("control format contract drift")
    if candidate != {"mode": "l8_candidate", "image_format": "L8", "bytes_per_texel": 1, "sample_channel": "R"}:
        raise AssertionError("candidate format contract drift; bounded candidate must remain L8/R")

    acceptance = runtime.get("acceptance", {})
    for key in (
        "candidate_source_scalar_samples_must_match_control",
        "candidate_texture_memory_must_be_lower_on_proof_host",
        "draw_calls_must_not_increase",
        "objects_must_not_increase",
        "primitives_must_not_increase",
        "buffer_memory_must_not_increase",
        "visual_tradeoff_requires_art_qa_review",
    ):
        if acceptance.get(key) is not True:
            raise AssertionError(f"acceptance gate drift: {key}")

    truth = runtime.get("truth_boundary", {})
    if any(value is not False for value in truth.values()):
        raise AssertionError("truth boundary drift")

    width = int(preserve["width_px"])
    height = int(preserve["height_px"])
    texels = mip_texel_count(width, height)
    control_bytes = texels * int(control["bytes_per_texel"])
    candidate_bytes = texels * int(candidate["bytes_per_texel"])
    saved = control_bytes - candidate_bytes
    if saved <= 0:
        raise AssertionError("modeled scalar texture candidate does not reduce bytes")

    return {
        "schema": "axm.object-service-dark-roughness-scalar-texture-budget-build/v0.1",
        "result": RESULT,
        "exact_runtime_head": exact_head,
        "materials_head": upstream["materials_head"],
        "runtime_contract_sha256": canonical_sha(runtime),
        "roughness_payload_sha256": canonical_sha(roughness_payload),
        "dimensions_px": [width, height],
        "mip_texel_count": texels,
        "control_format": control["image_format"],
        "candidate_format": candidate["image_format"],
        "control_modeled_mip_bytes": control_bytes,
        "candidate_modeled_mip_bytes": candidate_bytes,
        "modeled_mip_bytes_saved": saved,
        "modeled_mip_reduction_fraction": saved / control_bytes,
        "preserve": preserve,
        "acceptance": acceptance,
        "truth_boundary": truth,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", default="runtime/service_dark_roughness_l8_budget_001.json")
    parser.add_argument("--roughness-payload", default="lookdev-proof/generated/object_service_dark_roughness_microvariation_payload.json")
    parser.add_argument("--exact-head", required=True)
    parser.add_argument("--out", default="runtime-proof/generated/service_dark_roughness_l8_budget_build_receipt.json")
    parser.add_argument("--runtime-copy", default="lookdev-proof/generated/service_dark_roughness_l8_budget_001.json")
    args = parser.parse_args()

    runtime = read(Path(args.runtime))
    payload = read(Path(args.roughness_payload))
    receipt = verify(runtime, payload, args.exact_head)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")

    runtime_copy = Path(args.runtime_copy)
    runtime_copy.parent.mkdir(parents=True, exist_ok=True)
    runtime_copy.write_text(json.dumps(runtime, indent=2, sort_keys=True) + "\n")

    print(receipt["result"])


if __name__ == "__main__":
    main()
