from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

MATERIALS_SCHEMA = "axm.object-service-dark-atlas-pack-review/v0.1"
RUNTIME_SCHEMA = "axm.object-service-dark-atlas-height-budget/v0.1"
RECEIPT_SCHEMA = "axm.object-service-dark-atlas-height-budget-receipt/v0.1"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def rgba8_mip_bytes(width: int, height: int) -> int:
    if width <= 0 or height <= 0:
        raise AssertionError("atlas dimensions must be positive")
    total = 0
    w, h = width, height
    while True:
        total += w * h * 4
        if w == 1 and h == 1:
            break
        w = max(1, w // 2)
        h = max(1, h // 2)
    return total


def build(materials_path: Path, runtime_path: Path, exact_head: str) -> dict[str, Any]:
    materials = load(materials_path)
    runtime = load(runtime_path)
    if materials.get("schema") != MATERIALS_SCHEMA:
        raise AssertionError("Materials atlas contract schema drift")
    if runtime.get("schema") != RUNTIME_SCHEMA:
        raise AssertionError("Runtime atlas budget contract schema drift")
    if runtime.get("asset_id") != materials.get("asset_id"):
        raise AssertionError("asset identity drift")

    upstream = runtime.get("upstream", {})
    if upstream.get("materials_contract_path") != "lookdev/service_dark_atlas_pack_review_001.json":
        raise AssertionError("Materials contract path drift")
    if upstream.get("materials_contract_schema") != MATERIALS_SCHEMA:
        raise AssertionError("Materials contract schema binding drift")

    atlas = materials.get("atlas", {})
    preserve = runtime.get("preserve", {})
    if [int(atlas.get("width_px", 0)), int(atlas.get("height_px", 0))] != [512, 512]:
        raise AssertionError("measure-before Materials atlas dimensions drift")
    for key in ("pixels_per_meter", "padding_px", "texels_per_review_uv_unit"):
        if preserve.get(key) != atlas.get(key):
            raise AssertionError(f"preserved Materials field drift: {key}")
    if float(preserve.get("meters_per_pixel", -1.0)) != float(atlas.get("meters_per_pixel", -2.0)):
        raise AssertionError("preserved meters_per_pixel drift")
    if preserve.get("filtering") != atlas.get("filtering") or preserve.get("repeat") != atlas.get("repeat"):
        raise AssertionError("preserved sampling policy drift")
    for key in (
        "surface_rectangles_unchanged",
        "surface_pixel_extents_unchanged",
        "diagnostic_texels_inside_surface_rectangles_unchanged",
        "material_scalars_unchanged",
    ):
        if preserve.get(key) is not True:
            raise AssertionError(f"Runtime preserve gate disabled: {key}")

    control = runtime.get("control", {})
    candidate = runtime.get("candidate", {})
    cw, ch = int(control.get("width_px", 0)), int(control.get("height_px", 0))
    nw, nh = int(candidate.get("width_px", 0)), int(candidate.get("height_px", 0))
    if [cw, ch] != [512, 512]:
        raise AssertionError("control must remain exact Materials 512x512")
    if [nw, nh] != [512, 384]:
        raise AssertionError("bounded candidate must remain 512x384")

    padding = int(atlas["padding_px"])
    max_padded_x = 0
    max_padded_y = 0
    surfaces: list[dict[str, Any]] = []
    for raw in materials.get("surfaces", []):
        rect = [int(v) for v in raw.get("rect_px", [])]
        pixel_size = [int(v) for v in raw.get("pixel_size", [])]
        if len(rect) != 4 or rect[2:] != pixel_size:
            raise AssertionError("Materials surface rectangle drift")
        x0, y0, w, h = rect
        padded = [x0 - padding, y0 - padding, x0 + w + padding, y0 + h + padding]
        if padded[0] < 0 or padded[1] < 0:
            raise AssertionError("Materials padded surface starts outside atlas")
        if padded[2] > nw or padded[3] > nh:
            raise AssertionError(
                f"candidate clips required padded surface {raw.get('surface_id')}: {padded} not within {nw}x{nh}"
            )
        max_padded_x = max(max_padded_x, padded[2])
        max_padded_y = max(max_padded_y, padded[3])
        surfaces.append({
            "surface_id": raw.get("surface_id"),
            "rect_px": rect,
            "pixel_size": pixel_size,
            "padded_bounds_px": padded,
        })

    control_base = cw * ch * 4
    candidate_base = nw * nh * 4
    control_mips = rgba8_mip_bytes(cw, ch)
    candidate_mips = rgba8_mip_bytes(nw, nh)
    if candidate_base >= control_base or candidate_mips >= control_mips:
        raise AssertionError("candidate does not reduce modeled RGBA8 atlas bytes")

    truth = runtime.get("truth_boundary", {})
    required_false = (
        "source_geometry_changed",
        "source_surface_identities_changed",
        "source_uv_authored",
        "production_uv_adopted",
        "production_texture_authored",
        "final_pixels_per_meter_accepted",
        "final_atlas_pack_accepted",
        "materials_atlas_rewritten",
        "technical_art_transport_accepted",
        "art_direction_final_accepted",
        "visual_qa_final_accepted",
        "target_device_performance_proven",
        "canon",
        "production_ready",
    )
    for key in required_false:
        if truth.get(key) is not False:
            raise AssertionError(f"truth-boundary drift: {key}")

    return {
        "schema": RECEIPT_SCHEMA,
        "result": "PASS_OBJECT_SERVICE_DARK_ATLAS_HEIGHT_BUDGET_PACKET",
        "exact_runtime_head": exact_head,
        "materials_head": upstream.get("materials_head"),
        "control_dimensions_px": [cw, ch],
        "candidate_dimensions_px": [nw, nh],
        "pixels_per_meter": atlas["pixels_per_meter"],
        "padding_px": padding,
        "surfaces": surfaces,
        "maximum_required_padded_extent_px": [max_padded_x, max_padded_y],
        "candidate_spare_extent_px": [nw - max_padded_x, nh - max_padded_y],
        "control_base_rgba8_bytes": control_base,
        "candidate_base_rgba8_bytes": candidate_base,
        "base_rgba8_bytes_saved": control_base - candidate_base,
        "base_rgba8_reduction_fraction": (control_base - candidate_base) / control_base,
        "control_rgba8_mip_chain_bytes": control_mips,
        "candidate_rgba8_mip_chain_bytes": candidate_mips,
        "rgba8_mip_chain_bytes_saved": control_mips - candidate_mips,
        "rgba8_mip_chain_reduction_fraction": (control_mips - candidate_mips) / control_mips,
        "truth_boundary": truth,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--materials", default="lookdev/service_dark_atlas_pack_review_001.json")
    parser.add_argument("--runtime", default="runtime/service_dark_atlas_height_budget_001.json")
    parser.add_argument("--out", default="runtime-proof/generated")
    parser.add_argument("--exact-head", default="UNSPECIFIED")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    receipt = build(Path(args.materials), Path(args.runtime), args.exact_head)
    (out / "service_dark_atlas_height_budget_build_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
