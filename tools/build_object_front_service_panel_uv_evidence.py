from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from build_modular_case import build as build_case

REVIEW_SCHEMA = "axm.object-front-service-panel-uv-review/v0.1"
PAYLOAD_SCHEMA = "axm.object-front-service-panel-uv-lookdev-payload/v0.1"
RECEIPT_SCHEMA = "axm.object-front-service-panel-uv-build-receipt/v0.1"
PROFILE_SCHEMA = "axm.object-material-profile/v0.1"
SOURCE_SCHEMA = "axm.object-hard-surface/v0.1"

EXPECTED_SOURCE_SHA256 = "49b1f9ed9865893d6de6f1ec8f069576732df694853fde4e3fcff366de32644a"
EXPECTED_PROFILE_SHA256 = "dc200229d6c25fa84063aa51f66103abc022efa54b2167e4432a5b47fc40360c"
EXPECTED_TARGET = {
    "name": "front_service_panel",
    "kind": "box",
    "role": "service_panel",
    "center_m": [0.0, -0.249, 0.156],
    "size_m": [0.468, 0.018, 0.156],
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rgba(value: str) -> list[float]:
    if not isinstance(value, str) or len(value) != 9 or not value.startswith("#"):
        raise AssertionError(f"invalid RGBA hex: {value!r}")
    try:
        return [int(value[i : i + 2], 16) / 255.0 for i in (1, 3, 5, 7)]
    except ValueError as exc:
        raise AssertionError(f"invalid RGBA hex: {value!r}") from exc


def _close(a: float, b: float, tol: float = 1e-12) -> bool:
    return abs(float(a) - float(b)) <= tol


def _same_float_list(a, b, tol: float = 1e-12) -> bool:
    return len(a) == len(b) and all(_close(x, y, tol) for x, y in zip(a, b))


def _normalized_materials(profile: dict) -> dict:
    if profile.get("schema") != PROFILE_SCHEMA:
        raise AssertionError("material profile schema mismatch")
    result: dict[str, dict] = {}
    for material_id, spec in profile.get("candidate", {}).items():
        metallic = float(spec["metallic"])
        roughness = float(spec["roughness"])
        if not (0.0 <= metallic <= 1.0 and 0.0 <= roughness <= 1.0):
            raise AssertionError(f"invalid PBR scalar for {material_id}")
        result[material_id] = {
            "albedo": _rgba(spec["albedo"]),
            "albedo_hex": spec["albedo"],
            "metallic": metallic,
            "roughness": roughness,
        }
    return result


def _checker_tints(base_rgba: list[float]) -> dict:
    rgb = base_rgba[:3]
    dark = [max(0.0, min(1.0, value * 0.55)) for value in rgb]
    light = [max(0.0, min(1.0, value * 1.85 + 0.08)) for value in rgb]
    return {
        "dark_rgba": dark + [base_rgba[3]],
        "light_rgba": light + [base_rgba[3]],
    }


def build_payload(source_path: Path, profile_path: Path, review_path: Path, exact_head: str) -> tuple[dict, dict]:
    source_sha = sha256(source_path)
    profile_sha = sha256(profile_path)
    if source_sha != EXPECTED_SOURCE_SHA256:
        raise AssertionError(f"source identity drift: {source_sha}")
    if profile_sha != EXPECTED_PROFILE_SHA256:
        raise AssertionError(f"material profile identity drift: {profile_sha}")

    source = json.loads(source_path.read_text(encoding="utf-8"))
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    review = json.loads(review_path.read_text(encoding="utf-8"))
    if source.get("schema") != SOURCE_SCHEMA:
        raise AssertionError("source schema mismatch")
    if review.get("schema") != REVIEW_SCHEMA:
        raise AssertionError("review schema mismatch")
    if review.get("asset_id") != source.get("asset_id"):
        raise AssertionError("review/source asset identity mismatch")

    target_spec = review.get("target", {})
    if target_spec.get("component_name") != EXPECTED_TARGET["name"]:
        raise AssertionError("review target component drift")
    if target_spec.get("component_kind") != EXPECTED_TARGET["kind"]:
        raise AssertionError("review target kind drift")
    if target_spec.get("component_role") != EXPECTED_TARGET["role"]:
        raise AssertionError("review target role drift")
    if target_spec.get("review_surface_selector") != "source_local_min_y_face":
        raise AssertionError("front service-panel UV review must stay on source_local_min_y_face")
    if target_spec.get("source_surface_identity_owned") is not False:
        raise AssertionError("review must not claim source-owned face identity")
    if target_spec.get("source_material_slot_authored") is not False:
        raise AssertionError("review must not claim a source material slot")

    source_result = build_case(source)
    components = source_result["components"]
    matches = [component for component in components if component["name"] == EXPECTED_TARGET["name"]]
    if len(matches) != 1:
        raise AssertionError("expected exactly one front_service_panel component")
    target = matches[0]
    if target.get("kind") != EXPECTED_TARGET["kind"] or target.get("role") != EXPECTED_TARGET["role"]:
        raise AssertionError("source target semantics drift")
    if not _same_float_list(target["center_m"], EXPECTED_TARGET["center_m"]):
        raise AssertionError(f"front_service_panel center drift: {target['center_m']}")
    if not _same_float_list(target["size_m"], EXPECTED_TARGET["size_m"]):
        raise AssertionError(f"front_service_panel size drift: {target['size_m']}")

    materials = _normalized_materials(profile)
    role_materials = profile.get("role_materials", {})
    rendered_components = []
    for component in components:
        role = component["role"]
        material_id = role_materials.get(role)
        if material_id not in materials:
            raise AssertionError(f"missing material mapping for source role {role!r}")
        row = dict(component)
        row["candidate_material"] = material_id
        rendered_components.append(row)

    target_material_id = target_spec.get("material_id")
    if role_materials.get(target["role"]) != target_material_id:
        raise AssertionError("front_service_panel material identity drift")
    service_material = materials[target_material_id]

    uv_candidate = review.get("uv_candidate", {})
    negative = review.get("negative_control", {})
    if uv_candidate.get("basis") != "SOURCE_LOCAL_X_TO_U__SOURCE_LOCAL_Z_TO_V":
        raise AssertionError("unsupported UV basis")
    if uv_candidate.get("origin") != "SOURCE_FACE_MIN_X_MIN_Z":
        raise AssertionError("unsupported UV origin")
    if uv_candidate.get("diagnostic_pattern") != "PROCEDURAL_CHECKER_FROM_UV_NO_TEXTURE_ASSET":
        raise AssertionError("diagnostic must remain procedural/no-texture")
    if review.get("provenance", {}).get("external_textures") not in ([], None):
        raise AssertionError("external textures are forbidden in this bounded review")

    candidate_u_m = float(uv_candidate["meters_per_uv_unit_u"])
    candidate_v_m = float(uv_candidate["meters_per_uv_unit_v"])
    negative_u_m = float(negative["meters_per_uv_unit_u"])
    negative_v_m = float(negative["meters_per_uv_unit_v"])
    if min(candidate_u_m, candidate_v_m, negative_u_m, negative_v_m) <= 0.0:
        raise AssertionError("UV physical scales must be positive")
    if not _close(candidate_u_m, 0.05) or not _close(candidate_v_m, 0.05):
        raise AssertionError("candidate must stay at the declared isotropic 0.05 m/UV scale")
    if not _close(negative_u_m, 0.05) or not _close(negative_v_m, 1.0 / 60.0):
        raise AssertionError("negative control must stay at the declared 3x V-density defect")

    width_m = float(target["size_m"][0])
    height_m = float(target["size_m"][2])
    face_area_m2 = width_m * height_m
    candidate_u_span = width_m / candidate_u_m
    candidate_v_span = height_m / candidate_v_m
    negative_u_span = width_m / negative_u_m
    negative_v_span = height_m / negative_v_m
    candidate_anisotropy = max(candidate_u_m, candidate_v_m) / min(candidate_u_m, candidate_v_m)
    negative_anisotropy = max(negative_u_m, negative_v_m) / min(negative_u_m, negative_v_m)
    if not _close(candidate_anisotropy, 1.0):
        raise AssertionError("candidate UV density is not isotropic")
    if not _close(negative_anisotropy, 3.0):
        raise AssertionError("negative UV density is not the intended 3x anisotropy")
    if not math.isclose(face_area_m2, 0.073008, rel_tol=0.0, abs_tol=1e-12):
        raise AssertionError(f"front face area drift: {face_area_m2}")

    truth_boundary = dict(review.get("truth_boundary", {}))
    forbidden_true = (
        "source_geometry_changed",
        "source_surface_identity_owned",
        "source_material_slot_authored",
        "production_uv_authored",
        "texture_asset_authored",
        "decal_art_authored",
        "material_scalars_changed",
        "arbitrary_surface_unwrap_proven",
        "final_texel_density_accepted",
        "target_import_transport_accepted",
        "runtime_cost_accepted",
        "art_direction_accepted",
        "visual_qa_accepted",
        "canon",
        "production_ready",
    )
    for key in forbidden_true:
        if truth_boundary.get(key) is not False:
            raise AssertionError(f"truth-boundary drift: {key}")

    diagnostic = _checker_tints(service_material["albedo"])
    payload = {
        "schema": PAYLOAD_SCHEMA,
        "exact_materials_head": exact_head,
        "asset_id": source["asset_id"],
        "source_sha256": source_sha,
        "material_profile_sha256": profile_sha,
        "review_contract_sha256": sha256(review_path),
        "components": rendered_components,
        "materials": materials,
        "target": {
            "component_name": target["name"],
            "component_role": target["role"],
            "component_kind": target["kind"],
            "center_m": target["center_m"],
            "size_m": target["size_m"],
            "review_surface_selector": target_spec["review_surface_selector"],
            "material_id": target_material_id,
            "front_face_area_m2": face_area_m2,
        },
        "uv_candidate": {
            "basis": uv_candidate["basis"],
            "origin": uv_candidate["origin"],
            "meters_per_uv_unit_u": candidate_u_m,
            "meters_per_uv_unit_v": candidate_v_m,
            "u_span": candidate_u_span,
            "v_span": candidate_v_span,
            "density_anisotropy": candidate_anisotropy,
        },
        "negative_control": {
            "id": negative["id"],
            "meters_per_uv_unit_u": negative_u_m,
            "meters_per_uv_unit_v": negative_v_m,
            "u_span": negative_u_span,
            "v_span": negative_v_span,
            "density_anisotropy": negative_anisotropy,
        },
        "diagnostic_material": {
            "kind": "PROCEDURAL_UV_CHECKER_REVIEW_ONLY",
            "dark_rgba": diagnostic["dark_rgba"],
            "light_rgba": diagnostic["light_rgba"],
            "metallic": service_material["metallic"],
            "roughness": service_material["roughness"],
            "external_texture_asset": False,
        },
        "camera_contexts": review["camera_contexts"],
        "truth_boundary": truth_boundary,
    }
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "result": "PASS_SOURCE_BOUND_FRONT_SERVICE_PANEL_ISOTROPIC_UV_REVIEW_PACKET",
        "exact_materials_head": exact_head,
        "source_sha256": source_sha,
        "material_profile_sha256": profile_sha,
        "review_contract_sha256": sha256(review_path),
        "component_name": target["name"],
        "component_role": target["role"],
        "review_surface_selector": target_spec["review_surface_selector"],
        "source_surface_identity_owned": False,
        "source_material_slot_authored": False,
        "material_id": target_material_id,
        "front_face_width_m": width_m,
        "front_face_height_m": height_m,
        "front_face_area_m2": face_area_m2,
        "candidate_meters_per_uv_unit": [candidate_u_m, candidate_v_m],
        "candidate_uv_span": [candidate_u_span, candidate_v_span],
        "candidate_density_anisotropy": candidate_anisotropy,
        "negative_meters_per_uv_unit": [negative_u_m, negative_v_m],
        "negative_uv_span": [negative_u_span, negative_v_span],
        "negative_density_anisotropy": negative_anisotropy,
        "camera_contexts": review["camera_contexts"],
        "external_texture_assets": [],
        "material_scalars_changed": False,
        "source_geometry_changed": False,
        "production_uv_adopted": False,
        "truth_boundary": truth_boundary,
    }
    return payload, receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="assets/modular-equipment-case-001/source.json")
    parser.add_argument("--profile", default="lookdev/object_material_profile_001.json")
    parser.add_argument("--review", default="lookdev/front_service_panel_uv_review_001.json")
    parser.add_argument("--out", default="lookdev-proof/generated")
    parser.add_argument("--exact-head", default="UNSPECIFIED")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    payload, receipt = build_payload(Path(args.source), Path(args.profile), Path(args.review), args.exact_head)
    (out / "front_service_panel_uv_payload.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out / "front_service_panel_uv_build_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
