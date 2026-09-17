from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

FAMILY_PAYLOAD_SCHEMA = "axm.object-service-dark-uv-density-family-payload/v0.1"
FAMILY_CONTRACT_SCHEMA = "axm.object-service-dark-uv-density-family-review/v0.1"
CONTRACT_SCHEMA = "axm.object-service-dark-atlas-pack-review/v0.1"
PAYLOAD_SCHEMA = "axm.object-service-dark-atlas-pack-payload/v0.1"
RECEIPT_SCHEMA = "axm.object-service-dark-atlas-pack-receipt/v0.1"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def close(a: float, b: float, tol: float = 1e-12) -> bool:
    return abs(float(a) - float(b)) <= tol


def exact_int(value: float, label: str) -> int:
    rounded = round(value)
    if abs(value - rounded) > 1e-9:
        raise AssertionError(f"{label} does not map to an exact integer texel extent: {value}")
    return int(rounded)


def build(family_payload_path: Path, family_contract_path: Path, contract_path: Path, exact_head: str) -> tuple[dict[str, Any], dict[str, Any]]:
    family_payload = load(family_payload_path)
    family_contract = load(family_contract_path)
    contract = load(contract_path)

    if family_payload.get("schema") != FAMILY_PAYLOAD_SCHEMA:
        raise AssertionError("service-dark family payload schema drift")
    if family_contract.get("schema") != FAMILY_CONTRACT_SCHEMA:
        raise AssertionError("service-dark family contract schema drift")
    if contract.get("schema") != CONTRACT_SCHEMA:
        raise AssertionError("atlas contract schema drift")
    if contract.get("asset_id") != family_payload.get("asset_id") or contract.get("asset_id") != family_contract.get("asset_id"):
        raise AssertionError("asset identity drift")

    upstream = contract.get("upstream", {})
    if upstream.get("materials_family_path") != "lookdev/service_dark_uv_density_family_001.json":
        raise AssertionError("atlas review must bind the exact service-dark family contract path")
    if upstream.get("materials_family_schema") != FAMILY_CONTRACT_SCHEMA:
        raise AssertionError("atlas family schema binding drift")
    if upstream.get("art_direction_decision") != "PASS_ART_DIRECTION_OBJECT_SERVICE_DARK_0P05_M_PER_UV_REVIEW_SCALE_PREFERENCE_022":
        raise AssertionError("Art Direction review-scale decision drift")

    family = family_contract.get("family", {})
    if family.get("material_id") != "service_dark":
        raise AssertionError("atlas target material must remain service_dark")
    if not close(float(family.get("meters_per_uv_unit_u")), 0.05) or not close(float(family.get("meters_per_uv_unit_v")), 0.05):
        raise AssertionError("upstream physical review scale drift")

    atlas = contract.get("atlas", {})
    width = int(atlas.get("width_px", 0))
    height = int(atlas.get("height_px", 0))
    ppm = int(atlas.get("pixels_per_meter", 0))
    padding = int(atlas.get("padding_px", -1))
    if (width, height) != (512, 512):
        raise AssertionError("bounded atlas must remain 512x512")
    if ppm != 500:
        raise AssertionError("bounded atlas candidate must remain 500 px/m")
    if not close(float(atlas.get("meters_per_pixel")), 1.0 / ppm):
        raise AssertionError("meters-per-pixel mismatch")
    if not close(float(atlas.get("review_uv_unit_m")), 0.05):
        raise AssertionError("review UV unit drift")
    if int(atlas.get("texels_per_review_uv_unit", 0)) != 25:
        raise AssertionError("500 px/m must preserve exactly 25 texels per 0.05 m review UV unit")
    if padding != 16:
        raise AssertionError("bounded atlas edge dilation must remain 16 px")
    if atlas.get("filtering") != "LINEAR_MIPMAP_ANISOTROPIC" or atlas.get("repeat") is not False:
        raise AssertionError("atlas sampling policy drift")

    components = {str(c.get("name")): c for c in family_payload.get("components", [])}
    expected = {
        "lid_inner_service_surface": {
            "component": "lid_shell",
            "semantic": "interior_service_surface",
            "basis": "SOURCE_LOCAL_X_TO_U__SOURCE_LOCAL_Y_TO_V",
            "axes": (0, 1),
        },
        "front_service_panel_outer_service_surface": {
            "component": "front_service_panel",
            "semantic": "exterior_service_surface",
            "basis": "SOURCE_LOCAL_X_TO_U__SOURCE_LOCAL_Z_TO_V",
            "axes": (0, 2),
        },
    }

    surfaces: list[dict[str, Any]] = []
    occupied: list[tuple[int, int, int, int, str]] = []
    for raw in contract.get("surfaces", []):
        sid = str(raw.get("surface_id"))
        if sid not in expected:
            raise AssertionError(f"unexpected atlas surface {sid}")
        exp = expected[sid]
        if raw.get("component_name") != exp["component"] or raw.get("semantic") != exp["semantic"] or raw.get("basis") != exp["basis"]:
            raise AssertionError(f"surface provenance drift for {sid}")
        component = components.get(exp["component"])
        if not isinstance(component, dict) or component.get("kind") != "box":
            raise AssertionError(f"missing exact source box component for {sid}")
        size = [float(v) for v in component.get("size_m", [])]
        if len(size) != 3:
            raise AssertionError(f"invalid source size for {sid}")
        physical = [size[exp["axes"][0]], size[exp["axes"][1]]]
        declared_physical = [float(v) for v in raw.get("physical_size_m", [])]
        if len(declared_physical) != 2 or not all(close(a, b) for a, b in zip(physical, declared_physical)):
            raise AssertionError(f"source physical extent drift for {sid}: {physical} vs {declared_physical}")
        px = [exact_int(v * ppm, f"{sid} axis {i}") for i, v in enumerate(physical)]
        declared_px = [int(v) for v in raw.get("pixel_size", [])]
        if px != declared_px:
            raise AssertionError(f"declared pixel extent drift for {sid}: {px} vs {declared_px}")
        rect = [int(v) for v in raw.get("rect_px", [])]
        if len(rect) != 4 or rect[2:] != px:
            raise AssertionError(f"atlas rect extent drift for {sid}")
        x, y, w, h = rect
        if x - padding < 0 or y - padding < 0 or x + w + padding > width or y + h + padding > height:
            raise AssertionError(f"{sid} lacks declared {padding}px atlas dilation margin")
        occupied.append((x - padding, y - padding, x + w + padding, y + h + padding, sid))
        surfaces.append({
            "surface_id": sid,
            "component_name": exp["component"],
            "semantic": exp["semantic"],
            "basis": exp["basis"],
            "physical_size_m": physical,
            "pixel_size": px,
            "rect_px": rect,
            "uv_rect": [x / width, y / height, (x + w) / width, (y + h) / height],
            "half_texel_inset_uv": [0.5 / width, 0.5 / height],
            "pixels_per_meter": ppm,
            "meters_per_pixel": 1.0 / ppm,
        })

    if {s["surface_id"] for s in surfaces} != set(expected):
        raise AssertionError("atlas must contain exactly the two reviewed source-owned service surfaces")
    for i, a in enumerate(occupied):
        for b in occupied[i + 1 :]:
            overlap = not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])
            if overlap:
                raise AssertionError(f"padded atlas islands overlap: {a[4]} / {b[4]}")

    diagnostic = contract.get("diagnostic_texture", {})
    if diagnostic.get("external_assets") not in ([], None) or diagnostic.get("production_art") is not False:
        raise AssertionError("bounded atlas diagnostic must remain self-generated and non-production")
    negative = contract.get("negative_control", {})
    if negative.get("id") != "NO_EDGE_DILATION_WITH_HIGH_CONTRAST_OUTSIDE_ISLANDS":
        raise AssertionError("atlas negative-control identity drift")

    truth = contract.get("truth_boundary", {})
    required_false = [
        "source_geometry_changed", "source_surface_identities_changed", "source_material_slots_authored",
        "source_uv_authored", "production_uv_adopted", "material_scalars_changed",
        "production_texture_authored", "final_pixels_per_meter_accepted", "final_atlas_pack_accepted",
        "target_import_transport_accepted", "runtime_cost_accepted", "art_direction_final_accepted",
        "visual_qa_final_accepted", "canon", "production_ready",
    ]
    for key in required_false:
        if truth.get(key) is not False:
            raise AssertionError(f"truth-boundary drift: {key}")
    if truth.get("diagnostic_texture_generated") is not True:
        raise AssertionError("diagnostic texture generation must remain explicit")

    payload = dict(family_payload)
    payload["schema"] = PAYLOAD_SCHEMA
    payload["exact_materials_head"] = exact_head
    payload["atlas_pack_review"] = {
        "contract_sha256": digest(contract_path),
        "upstream_family_contract_sha256": digest(family_contract_path),
        "art_direction_coordination_commit": upstream["art_direction_coordination_commit"],
        "art_direction_decision": upstream["art_direction_decision"],
        "material_id": "service_dark",
        "atlas": atlas,
        "surfaces": surfaces,
        "diagnostic_texture": diagnostic,
        "negative_control": negative,
    }
    payload["truth_boundary"] = truth

    used_pixels = sum(s["pixel_size"][0] * s["pixel_size"][1] for s in surfaces)
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "result": "PASS_OBJECT_SERVICE_DARK_TWO_SURFACE_500_PPM_ATLAS_PACKET",
        "exact_materials_head": exact_head,
        "atlas_size_px": [width, height],
        "pixels_per_meter": ppm,
        "meters_per_pixel": 1.0 / ppm,
        "texels_per_review_uv_unit": 25,
        "padding_px": padding,
        "surface_count": len(surfaces),
        "surfaces": surfaces,
        "occupied_surface_texels": used_pixels,
        "atlas_texels": width * height,
        "surface_fill_fraction": used_pixels / float(width * height),
        "external_assets": [],
        "production_uv_adopted": False,
        "production_texture_authored": False,
        "truth_boundary": truth,
    }
    return payload, receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--family-payload", default="lookdev-proof/generated/object_service_dark_uv_density_family_payload.json")
    parser.add_argument("--family-contract", default="lookdev/service_dark_uv_density_family_001.json")
    parser.add_argument("--contract", default="lookdev/service_dark_atlas_pack_review_001.json")
    parser.add_argument("--out", default="lookdev-proof/generated")
    parser.add_argument("--exact-head", default="UNSPECIFIED")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    payload, receipt = build(Path(args.family_payload), Path(args.family_contract), Path(args.contract), args.exact_head)
    (out / "object_service_dark_atlas_pack_payload.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "service_dark_atlas_pack_build_receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
