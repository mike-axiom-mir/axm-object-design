from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from build_object_service_dark_uc_texture_transport import (
    decode_rgba8_png,
    png_record,
    primitive_from_source,
    relative,
    sha256_bytes,
    sha256_file,
    surface_map,
    verify_materials_identity,
)

MATERIALS_HEAD = "4c12a0a57f6aa8778cff41efad321e13567c6c91"
RUNTIME_HEAD = "ce23d5edeb0766201cfbaff646dda31544cd8f9c"
RUNTIME_CONTRACT_BLOB = "839d82d46e551b9f7331aea32a86e39d960c8621"
UC_BASE_HEAD = "7f62cda0dd65139366c26bb4e643ed99481f7181"
UC_HEAD = "c8f38b4c3dd0d6183d035147e4816cff6fa6ef82"
RESULT = "PASS_OBJECT_SERVICE_DARK_RUNTIME_512X384_TO_UC_RECTANGULAR_BUNDLE_TEXTURED_GLB"
RECEIPT_SCHEMA = "axm.object-service-dark-runtime-atlas-uc-transport/v0.1"
EXPECTED_UC_CHANGED_PATHS = {
    "src/axm_uc/game_material_bridge.py",
    "src/axm_uc/material_pipeline.py",
    "tests/test_game_material_bridge.py",
}


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def require_ancestor(repo: Path, ancestor: str, descendant: str) -> None:
    proc = subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", ancestor, descendant],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.returncode != 0:
        raise AssertionError(f"required ancestor {ancestor} is not retained by {descendant}: {proc.stderr.strip()}")


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def prove_runtime_donor(
    repo_root: Path,
    runtime_contract_path: Path,
    runtime_receipt_path: Path,
    expected_runtime_head: str,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    git(repo_root, "cat-file", "-e", f"{expected_runtime_head}^{{commit}}")
    observed_blob = git(repo_root, "rev-parse", f"{expected_runtime_head}:runtime/service_dark_atlas_height_budget_001.json")
    if observed_blob != RUNTIME_CONTRACT_BLOB:
        raise AssertionError(f"Runtime contract blob drift: {observed_blob}")
    materialized_blob = git(repo_root, "hash-object", str(runtime_contract_path))
    if materialized_blob != observed_blob:
        raise AssertionError("materialized Runtime contract is not the exact donor blob")

    contract = load(runtime_contract_path)
    receipt = load(runtime_receipt_path)
    if contract.get("schema") != "axm.object-service-dark-atlas-height-budget/v0.1":
        raise AssertionError("Runtime donor contract schema drift")
    if contract.get("upstream", {}).get("materials_head") != MATERIALS_HEAD:
        raise AssertionError("Runtime donor is not bound to exact Materials authority")
    if contract.get("control") != {"width_px": 512, "height_px": 512}:
        raise AssertionError("Runtime control dimensions drift")
    if contract.get("candidate") != {"width_px": 512, "height_px": 384}:
        raise AssertionError("Runtime candidate dimensions drift")
    preserve = contract.get("preserve", {})
    if preserve.get("pixels_per_meter") != 500 or preserve.get("padding_px") != 16 or preserve.get("repeat") is not False:
        raise AssertionError("Runtime preserve policy drift")
    for key in (
        "surface_rectangles_unchanged",
        "surface_pixel_extents_unchanged",
        "diagnostic_texels_inside_surface_rectangles_unchanged",
        "material_scalars_unchanged",
    ):
        if preserve.get(key) is not True:
            raise AssertionError(f"Runtime preserve gate disabled: {key}")
    if receipt.get("result") != "PASS_OBJECT_SERVICE_DARK_ATLAS_HEIGHT_BUDGET_PACKET":
        raise AssertionError("Runtime donor build receipt is not green")
    if receipt.get("exact_runtime_head") != expected_runtime_head:
        raise AssertionError("Runtime donor receipt exact-head drift")
    if receipt.get("materials_head") != MATERIALS_HEAD:
        raise AssertionError("Runtime donor receipt Materials binding drift")
    if receipt.get("candidate_dimensions_px") != [512, 384]:
        raise AssertionError("Runtime donor receipt candidate dimensions drift")
    if receipt.get("maximum_required_padded_extent_px") != [422, 382]:
        raise AssertionError("Runtime donor padded extent drift")
    if receipt.get("candidate_spare_extent_px") != [90, 2]:
        raise AssertionError("Runtime donor spare extent drift")
    return contract, receipt, observed_blob


def crop_opaque_rgba_to_rgb(
    source: Path,
    target: Path,
    *,
    target_width: int,
    target_height: int,
    png_bytes,
    decode_png,
) -> dict[str, Any]:
    source_width, source_height, rgba, ancillary = decode_rgba8_png(source.read_bytes())
    if (source_width, source_height) != (512, 512):
        raise AssertionError("exact Materials source atlas must remain 512x512")
    if target_width != source_width or not 1 <= target_height <= source_height:
        raise AssertionError("candidate crop must preserve width and crop only bottom unused rows")
    row_bytes = source_width * 4
    cropped_rgba = rgba[: target_height * row_bytes]
    alphas = cropped_rgba[3::4]
    if not alphas or min(alphas) != 255 or max(alphas) != 255:
        raise AssertionError("candidate source crop is not fully opaque; RGB derivative would be lossy")
    rgb = bytearray(target_width * target_height * 3)
    cursor = 0
    for offset in range(0, len(cropped_rgba), 4):
        rgb[cursor : cursor + 3] = cropped_rgba[offset : offset + 3]
        cursor += 3
    encoded = png_bytes(target_width, target_height, 3, bytes(rgb))
    target.write_bytes(encoded)
    observed_width, observed_height, observed_rgb = decode_png(encoded)
    if (observed_width, observed_height) != (target_width, target_height) or observed_rgb != bytes(rgb):
        raise AssertionError("UC PNG encode/decode changed exact Runtime candidate RGB")
    return {
        "schema": "axm.object-service-dark-runtime-atlas-uc-rgb-crop/v0.1",
        "state": "PASS_EXACT_TOP_ROWS_RGBA_TO_RGB_TRANSPORT_DERIVATIVE",
        "source_rgba_sha256": sha256_file(source),
        "target_rgb_sha256": sha256_file(target),
        "decoded_rgb_sha256": sha256_bytes(bytes(rgb)),
        "source_dimensions_px": [source_width, source_height],
        "target_dimensions_px": [target_width, target_height],
        "crop_policy": "TOP_ROWS_ONLY_PRESERVE_PIXEL_COORDINATES",
        "source_ancillary_chunks": ancillary,
        "source_alpha_min": min(alphas),
        "source_alpha_max": max(alphas),
        "max_rgb_channel_delta_inside_retained_rows": 0,
    }


def write_rectangular_bundle(
    bundle: Path,
    base_color: Path,
    payload: dict[str, Any],
    *,
    width: int,
    height: int,
    png_bytes,
) -> dict[str, Any]:
    bundle.mkdir(parents=True, exist_ok=False)
    base = bundle / "base_color.png"
    base.write_bytes(base_color.read_bytes())
    service = payload.get("materials", {}).get("candidate", {}).get("service_dark")
    if not isinstance(service, dict):
        raise AssertionError("service_dark material scalar donor missing")
    roughness = float(service["roughness"])
    metallic = float(service["metallic"])
    if not (0.0 <= roughness <= 1.0 and 0.0 <= metallic <= 1.0):
        raise AssertionError("service_dark PBR scalars out of range")
    r8 = round(roughness * 255)
    m8 = round(metallic * 255)

    normal = bundle / "normal.png"
    orm = bundle / "orm.png"
    ao = bundle / "ao.png"
    rough = bundle / "roughness.png"
    height_map = bundle / "height.png"
    pixel_count = width * height
    normal.write_bytes(png_bytes(width, height, 3, bytes([128, 128, 255]) * pixel_count))
    orm.write_bytes(png_bytes(width, height, 3, bytes([255, r8, m8]) * pixel_count))
    ao.write_bytes(png_bytes(width, height, 1, bytes([255]) * pixel_count))
    rough.write_bytes(png_bytes(width, height, 1, bytes([r8]) * pixel_count))
    height_map.write_bytes(png_bytes(width, height, 1, bytes([128]) * pixel_count))

    maps = {
        "base_color": png_record(base, 3, "sRGB"),
        "normal": png_record(normal, 3, "linear-data"),
        "orm": png_record(orm, 3, "linear-data"),
        "ao": png_record(ao, 1, "linear-data"),
        "roughness": png_record(rough, 1, "linear-data"),
        "height": png_record(height_map, 1, "linear-data"),
    }
    manifest = {
        "schema": "axm.game-material/v0.1",
        "family": "painted-metal",
        "finish": "realistic",
        "dimensions": [width, height],
        "seed": 0,
        "color": [255, 255, 255],
        "profile": {
            "name": "technical-art-runtime-candidate-transport-shim",
            "note": "Base color is the exact Runtime-bounded top-row crop; neutral companions exist only for UC bundle validation.",
        },
        "maps": maps,
        "orm_channels": ["occlusion", "roughness", "metallic"],
        "normal_convention": "tangent +Y",
        "truth": (
            "Object-local Technical Art transport bundle for exact Runtime candidate. "
            "No Object atlas policy is promoted into UC. Neutral companion maps are transport shims."
        ),
        "height_usage": "Neutral transport placeholder; no displacement or normal rebake claim.",
    }
    manifest_path = bundle / "game-material.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "manifest_sha256": sha256_file(manifest_path),
        "dimensions_px": [width, height],
        "base_color_sha256": sha256_file(base),
        "roughness_scalar": roughness,
        "metallic_scalar": metallic,
        "neutral_companion_maps": ["normal", "orm", "ao", "roughness", "height"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uc-root", required=True)
    parser.add_argument("--payload", default="lookdev-proof/generated/object_service_dark_atlas_pack_payload.json")
    parser.add_argument("--source-atlas-rgba", default="lookdev-proof/service-dark-atlas-padded.png")
    parser.add_argument("--runtime-contract", required=True)
    parser.add_argument("--runtime-build-receipt", required=True)
    parser.add_argument("--out", default="creations/technical-art-proof/runtime-candidate")
    parser.add_argument("--expected-materials-head", default=MATERIALS_HEAD)
    parser.add_argument("--expected-runtime-head", default=RUNTIME_HEAD)
    parser.add_argument("--expected-uc-base-head", default=UC_BASE_HEAD)
    parser.add_argument("--expected-uc-head", default=UC_HEAD)
    args = parser.parse_args()

    repo_root = Path.cwd().resolve()
    uc_root = Path(args.uc_root).resolve()
    out_dir = Path(args.out).resolve()
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    technical_art_head = git(repo_root, "rev-parse", "HEAD")
    materials_blobs = verify_materials_identity(repo_root, args.expected_materials_head)
    contract, runtime_receipt, runtime_blob = prove_runtime_donor(
        repo_root,
        Path(args.runtime_contract).resolve(),
        Path(args.runtime_build_receipt).resolve(),
        args.expected_runtime_head,
    )

    uc_head = git(uc_root, "rev-parse", "HEAD")
    if uc_head != args.expected_uc_head:
        raise AssertionError(f"UC exact-head drift expected={args.expected_uc_head} observed={uc_head}")
    require_ancestor(uc_root, args.expected_uc_base_head, uc_head)
    changed_paths = set(git(uc_root, "diff", "--name-only", args.expected_uc_base_head, uc_head).splitlines())
    if changed_paths != EXPECTED_UC_CHANGED_PATHS:
        raise AssertionError(f"UC rectangular-bundle PR path scope drift: {sorted(changed_paths)}")

    payload = load(Path(args.payload).resolve())
    if payload.get("schema") != "axm.object-service-dark-atlas-pack-payload/v0.1":
        raise AssertionError("Materials atlas payload schema drift")
    atlas = payload.get("atlas_pack_review", {}).get("atlas", {})
    if [atlas.get("width_px"), atlas.get("height_px")] != [512, 512]:
        raise AssertionError("Materials source atlas dimensions drift")
    candidate = contract["candidate"]
    width, height = int(candidate["width_px"]), int(candidate["height_px"])
    if runtime_receipt["maximum_required_padded_extent_px"][1] > height:
        raise AssertionError("Runtime candidate clips required padded surface extent")

    sys.path.insert(0, str(uc_root / "src"))
    from axm_uc.fabric_noise import png_bytes  # type: ignore
    from axm_uc.game_material_bridge import load_material_bundle  # type: ignore
    from axm_uc.material_pipeline import observe_station, run_station  # type: ignore
    from axm_uc.native_textures import decode_png  # type: ignore

    base_rgb_path = out_dir / "service-dark-runtime-512x384-uc-rgb.png"
    crop_receipt = crop_opaque_rgba_to_rgb(
        Path(args.source_atlas_rgba).resolve(),
        base_rgb_path,
        target_width=width,
        target_height=height,
        png_bytes=png_bytes,
        decode_png=decode_png,
    )
    (out_dir / "runtime-candidate-rgb-crop-receipt.json").write_text(
        json.dumps(crop_receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    bundle_dir = out_dir / "service-dark-runtime-uc-bundle"
    bundle_receipt = write_rectangular_bundle(
        bundle_dir,
        base_rgb_path,
        payload,
        width=width,
        height=height,
        png_bytes=png_bytes,
    )
    loaded = load_material_bundle(bundle_dir)
    if loaded.get("dimensions") != [width, height]:
        raise AssertionError("UC rectangular material bundle receiver did not retain exact dimensions")
    if "size" in loaded.get("manifest", {}):
        raise AssertionError("rectangular bundle silently retained legacy square size")
    bw, bh, bp = decode_png(loaded["pngs"]["base_color"])
    if [bw, bh] != [width, height] or sha256_bytes(bp) != crop_receipt["decoded_rgb_sha256"]:
        raise AssertionError("UC rectangular bundle validation changed candidate base-color pixels")

    candidate_payload = copy.deepcopy(payload)
    candidate_atlas = candidate_payload["atlas_pack_review"]["atlas"]
    candidate_atlas["width_px"] = width
    candidate_atlas["height_px"] = height
    primitives: list[dict[str, Any]] = []
    expected_density: dict[str, float] = {}
    surfaces = surface_map(candidate_payload)
    for sid in ("lid_inner_service_surface", "front_service_panel_outer_service_surface"):
        primitive, density = primitive_from_source(candidate_payload, surfaces[sid])
        primitives.append(primitive)
        expected_density[sid] = density

    specification = {
        "schema": "axm.surface-3d/v0.1",
        "name": "modular-equipment-case-001-service-dark-runtime-512x384-transport-proof",
        "primitives": primitives,
    }
    surface_path = out_dir / "service-dark-runtime-two-surface.surface.json"
    surface_path.write_text(json.dumps(specification, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    glb_path = out_dir / "service-dark-runtime-two-surface.glb"
    bindings = {sid: {"path": relative(repo_root, bundle_dir), "wrap": "clamp"} for sid in surfaces}
    bind_inputs = {"path": relative(repo_root, glb_path), "specification": specification, "materials": bindings}
    run_station(repo_root, "bind-textured-asset", bind_inputs)
    bind_observation = observe_station(repo_root, "bind-textured-asset", bind_inputs)
    if bind_observation.get("status") != "PASS":
        raise AssertionError(f"UC exact rectangular textured-asset observation failed: {bind_observation}")

    quality_path = out_dir / "service-dark-runtime-two-surface-quality.json"
    quality_inputs = {
        "path": relative(repo_root, quality_path),
        "asset": relative(repo_root, glb_path),
        "minimum_texels_per_m": 480,
    }
    quality = run_station(repo_root, "inspect-textured-asset", quality_inputs)
    quality_observation = observe_station(repo_root, "inspect-textured-asset", quality_inputs)
    if quality.get("status") != "PASS" or quality_observation.get("status") != "PASS":
        raise AssertionError(f"UC rectangular textured-asset inspection failed: {quality}")
    uv = quality["uv"]
    if uv.get("status") != "MEASURED" or uv.get("findings"):
        raise AssertionError(f"UC UV observer did not retain clean rectangular candidate evidence: {uv}")
    measured: dict[str, float] = {}
    for index, row in enumerate(uv.get("primitives", [])):
        sid = primitives[index]["id"]
        values = [float(binding["texels_per_m"]["p50"]) for binding in row.get("bindings", [])]
        if len(values) < 4:
            raise AssertionError(f"UC did not measure every core candidate texture binding for {sid}")
        if max(abs(value - expected_density[sid]) for value in values) > 0.02:
            raise AssertionError(f"UC rectangular candidate texel-density drift for {sid}: {values}")
        measured[sid] = values[0]

    receipt = {
        "schema": RECEIPT_SCHEMA,
        "result": RESULT,
        "technical_art_head": technical_art_head,
        "materials_authority_head": args.expected_materials_head,
        "materials_authority_blobs": materials_blobs,
        "runtime_authority_head": args.expected_runtime_head,
        "runtime_contract_blob": runtime_blob,
        "runtime_build_receipt_sha256": sha256_file(Path(args.runtime_build_receipt).resolve()),
        "uc_base_head": args.expected_uc_base_head,
        "uc_head": uc_head,
        "uc_changed_paths": sorted(changed_paths),
        "uc_product_modified": True,
        "receiving_dimensions_px": [width, height],
        "maximum_required_padded_extent_px": runtime_receipt["maximum_required_padded_extent_px"],
        "candidate_spare_extent_px": runtime_receipt["candidate_spare_extent_px"],
        "rgb_crop": crop_receipt,
        "bundle": bundle_receipt,
        "glb_sha256": sha256_file(glb_path),
        "glb_bytes": glb_path.stat().st_size,
        "uc_bind_observation_status": bind_observation.get("status"),
        "uc_quality_status": quality.get("status"),
        "uc_quality_observation_status": quality_observation.get("status"),
        "uc_uv_status": uv.get("status"),
        "expected_texels_per_m": expected_density,
        "measured_texels_per_m": measured,
        "truth_boundary": {
            "runtime_candidate_policy_reauthored_by_technical_art": False,
            "runtime_candidate_production_adopted": False,
            "materials_source_atlas_rewritten": False,
            "materials_surface_rectangles_rewritten": False,
            "source_surface_authority_changed": False,
            "base_color_retained_rows_changed": False,
            "neutral_companion_maps_are_transport_shims": True,
            "uc_product_modified": True,
            "uc_change_is_generic_rectangular_bundle_receiver_only": True,
            "technical_art_transport_accepted_for_exact_candidate": True,
            "target_device_performance_proven": False,
            "final_art_direction_accepted": False,
            "final_visual_qa_accepted": False,
            "production_uv_adopted": False,
            "production_texture_authored": False,
            "tangent_space_production_quality_accepted": False,
            "canon": False,
            "production_ready": False,
        },
    }
    receipt_path = out_dir / "technical-art-runtime-atlas-uc-transport-receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
