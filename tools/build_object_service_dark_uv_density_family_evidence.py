from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

BASE_SCHEMA = "axm.object-inner-lid-material-lookdev-payload/v0.1"
CONTRACT_SCHEMA = "axm.object-service-dark-uv-density-family-review/v0.1"
PANEL_REBIND_SCHEMA = "axm.object-front-service-panel-uv-source-identity-rebind/v0.1"
PAYLOAD_SCHEMA = "axm.object-service-dark-uv-density-family-payload/v0.1"
RECEIPT_SCHEMA = "axm.object-service-dark-uv-density-family-receipt/v0.1"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def close(a: float, b: float, tol: float = 1e-12) -> bool:
    return abs(float(a) - float(b)) <= tol


def checker_tints(base_rgba: list[float]) -> dict[str, list[float]]:
    rgb = [float(v) for v in base_rgba[:3]]
    alpha = float(base_rgba[3])
    return {
        "dark_rgba": [max(0.0, min(1.0, v * 0.55)) for v in rgb] + [alpha],
        "light_rgba": [max(0.0, min(1.0, v * 1.85 + 0.08)) for v in rgb] + [alpha],
    }


def build_payload(
    base_path: Path,
    contract_path: Path,
    panel_rebind_path: Path,
    exact_head: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    base = load_json(base_path)
    contract = load_json(contract_path)
    panel = load_json(panel_rebind_path)

    if base.get("schema") != BASE_SCHEMA:
        raise AssertionError("inner-lid base payload schema drift")
    if contract.get("schema") != CONTRACT_SCHEMA:
        raise AssertionError("service-dark UV family contract schema drift")
    if panel.get("schema") != PANEL_REBIND_SCHEMA:
        raise AssertionError("front service-panel UV rebind schema drift")
    if base.get("asset_id") != contract.get("asset_id") or panel.get("asset_id") != contract.get("asset_id"):
        raise AssertionError("asset identity drift across service-dark UV family")

    family = contract.get("family", {})
    if family.get("material_id") != "service_dark":
        raise AssertionError("family material must remain service_dark")
    if family.get("policy") != "PHYSICAL_ISOTROPIC_DENSITY_PER_SOURCE_LOCAL_SURFACE_AXES__REVIEW_ONLY":
        raise AssertionError("service-dark UV family policy drift")
    if family.get("diagnostic_pattern") != "PROCEDURAL_CHECKER_FROM_UV_NO_TEXTURE_ASSET":
        raise AssertionError("diagnostic must remain procedural/no-texture")
    family_u = float(family.get("meters_per_uv_unit_u"))
    family_v = float(family.get("meters_per_uv_unit_v"))
    if not close(family_u, 0.05) or not close(family_v, 0.05):
        raise AssertionError("shared service-dark review density must remain 0.05 m/UV isotropic")

    panel_ref = contract.get("front_service_panel_reference", {})
    if panel_ref.get("schema") != PANEL_REBIND_SCHEMA:
        raise AssertionError("front service-panel reference schema drift")
    binding = panel.get("binding", {})
    owner = panel.get("surface_owner", {})
    if binding.get("source_surface_id") != panel_ref.get("source_surface_id"):
        raise AssertionError("front service-panel source surface identity drift")
    if owner.get("surface_semantics") != panel_ref.get("surface_semantics"):
        raise AssertionError("front service-panel surface semantics drift")
    if binding.get("component_name") != panel_ref.get("component_name"):
        raise AssertionError("front service-panel component drift")
    if binding.get("material_id") != panel_ref.get("material_id") or binding.get("material_id") != "service_dark":
        raise AssertionError("front service-panel material family drift")
    if binding.get("uv_candidate_basis") != panel_ref.get("basis"):
        raise AssertionError("front service-panel UV basis drift")
    if not close(float(binding.get("meters_per_uv_unit_u")), family_u):
        raise AssertionError("front service-panel U density no longer matches service-dark family")
    if not close(float(binding.get("meters_per_uv_unit_v")), family_v):
        raise AssertionError("front service-panel V density no longer matches service-dark family")
    authority = panel.get("authority", {})
    if authority.get("source_uv_assignment") != "UNASSIGNED" or authority.get("production_uv_adopted") is not False:
        raise AssertionError("front service-panel production UV must remain unassigned/unadopted")

    target = contract.get("inner_lid_target", {})
    if target.get("source_surface_id") != "lid_inner_service_surface":
        raise AssertionError("inner-lid source surface id drift")
    if target.get("surface_semantics") != "interior_service_surface":
        raise AssertionError("inner-lid surface semantics drift")
    if target.get("component_name") != "lid_shell" or target.get("component_role") != "lid_shell":
        raise AssertionError("inner-lid component/role drift")
    if target.get("component_kind") != "box":
        raise AssertionError("inner-lid family review requires source box representation")
    if target.get("selector") != "source_local_min_z_face":
        raise AssertionError("inner-lid selector drift")
    if target.get("material_id") != "service_dark":
        raise AssertionError("inner-lid family material drift")
    if target.get("basis") != "SOURCE_LOCAL_X_TO_U__SOURCE_LOCAL_Y_TO_V":
        raise AssertionError("inner-lid UV basis drift")
    if target.get("origin") != "SOURCE_FACE_MIN_X_MIN_Y":
        raise AssertionError("inner-lid UV origin drift")

    source_identity = base.get("source_surface_identity", {})
    if source_identity.get("surface_id") != target.get("source_surface_id"):
        raise AssertionError("inner-lid base/source-owned surface mismatch")
    if source_identity.get("component_name") != target.get("component_name"):
        raise AssertionError("inner-lid base component mismatch")
    if source_identity.get("surface_semantics") != target.get("surface_semantics"):
        raise AssertionError("inner-lid base surface semantics mismatch")
    if source_identity.get("selector", {}).get("policy") != target.get("selector"):
        raise AssertionError("inner-lid base selector mismatch")
    if source_identity.get("material_assignment") != "UNASSIGNED":
        raise AssertionError("inner-lid source material assignment must remain UNASSIGNED")
    if source_identity.get("materials_candidate_adopted_by_source") is not False:
        raise AssertionError("inner-lid Materials candidate must remain unadopted by source owner")

    surface_review = base.get("surface_review", {})
    if surface_review.get("component_name") != target.get("component_name"):
        raise AssertionError("inner-lid Materials review component drift")
    if surface_review.get("candidate_material_id") != target.get("material_id"):
        raise AssertionError("inner-lid existing-family material drift")
    if surface_review.get("surface_selector") != target.get("selector"):
        raise AssertionError("inner-lid Materials selector drift")

    materials = base.get("materials", {}).get("candidate", {})
    service = materials.get("service_dark")
    if not isinstance(service, dict):
        raise AssertionError("service_dark material missing from exact Materials family")
    rgba = service.get("albedo")
    if not isinstance(rgba, list) or len(rgba) != 4:
        raise AssertionError("service_dark normalized albedo missing")
    if not (0.0 <= float(service.get("metallic")) <= 1.0 and 0.0 <= float(service.get("roughness")) <= 1.0):
        raise AssertionError("service_dark PBR scalars invalid")

    components = [c for c in base.get("components", []) if c.get("name") == target.get("component_name")]
    if len(components) != 1:
        raise AssertionError("inner-lid component must resolve exactly once")
    component = components[0]
    if component.get("kind") != "box" or component.get("role") != "lid_shell":
        raise AssertionError("inner-lid source component semantics drift")
    size = [float(v) for v in component.get("size_m", [])]
    if len(size) != 3 or min(size) <= 0.0:
        raise AssertionError("inner-lid source size invalid")

    # source_local_min_z_face spans source X and Y.
    width_m = size[0]
    depth_m = size[1]
    area_m2 = width_m * depth_m
    candidate_u_span = width_m / family_u
    candidate_v_span = depth_m / family_v
    candidate_anisotropy = max(family_u, family_v) / min(family_u, family_v)
    if not close(candidate_anisotropy, 1.0):
        raise AssertionError("service-dark family candidate is not isotropic")

    negative = contract.get("negative_control", {})
    neg_u = float(negative.get("meters_per_uv_unit_u"))
    neg_v = float(negative.get("meters_per_uv_unit_v"))
    if not close(neg_u, 0.05) or not close(neg_v, 1.0 / 60.0):
        raise AssertionError("inner-lid negative control must stay at 3x V density")
    neg_u_span = width_m / neg_u
    neg_v_span = depth_m / neg_v
    neg_anisotropy = max(neg_u, neg_v) / min(neg_u, neg_v)
    if not close(neg_anisotropy, 3.0):
        raise AssertionError("inner-lid negative control anisotropy drift")

    if list(target.get("pose_ids", [])) != ["mid_open", "peak_open"]:
        raise AssertionError("inner-lid UV family review pose set drift")
    if set(target.get("camera_contexts", [])) != {"three_quarter", "front_interior"}:
        raise AssertionError("inner-lid UV family review camera set drift")
    if [p.get("id") for p in base.get("poses", [])] != ["mid_open", "peak_open"]:
        raise AssertionError("base inner-lid payload pose identity drift")
    if set(base.get("camera_contexts", [])) != {"three_quarter", "front_interior"}:
        raise AssertionError("base inner-lid payload camera identity drift")

    provenance = contract.get("provenance", {})
    if provenance.get("external_textures") not in ([], None) or provenance.get("external_material_assets") not in ([], None):
        raise AssertionError("external assets are forbidden in this bounded review")

    truth = contract.get("truth_boundary", {})
    required_truth = {
        "source_geometry_changed": False,
        "source_surface_identities_owned": True,
        "source_material_slots_authored": False,
        "production_uv_authored": False,
        "production_uv_adopted": False,
        "texture_asset_authored": False,
        "decal_art_authored": False,
        "wear_authored": False,
        "normal_or_ao_map_authored": False,
        "material_scalars_changed": False,
        "arbitrary_surface_unwrap_proven": False,
        "final_texel_density_accepted": False,
        "target_import_transport_accepted": False,
        "runtime_cost_accepted": False,
        "art_direction_accepted": False,
        "visual_qa_accepted": False,
        "canon": False,
        "production_ready": False,
    }
    for key, expected in required_truth.items():
        if truth.get(key) is not expected:
            raise AssertionError(f"truth-boundary drift: {key}")

    tints = checker_tints([float(v) for v in rgba])
    payload = dict(base)
    payload["schema"] = PAYLOAD_SCHEMA
    payload["exact_materials_head"] = exact_head
    payload["service_dark_uv_family_contract_sha256"] = sha256(contract_path)
    payload["front_service_panel_uv_rebind_sha256"] = sha256(panel_rebind_path)
    payload["uv_family_review"] = {
        "material_id": "service_dark",
        "policy": family["policy"],
        "diagnostic_pattern": family["diagnostic_pattern"],
        "front_service_panel_reference": {
            "source_surface_id": binding["source_surface_id"],
            "surface_semantics": owner["surface_semantics"],
            "basis": binding["uv_candidate_basis"],
            "meters_per_uv_unit_u": float(binding["meters_per_uv_unit_u"]),
            "meters_per_uv_unit_v": float(binding["meters_per_uv_unit_v"]),
            "production_uv_adopted": False,
        },
        "inner_lid_target": {
            "source_surface_id": source_identity["surface_id"],
            "surface_semantics": source_identity["surface_semantics"],
            "component_name": component["name"],
            "selector": target["selector"],
            "basis": target["basis"],
            "origin": target["origin"],
            "face_width_m": width_m,
            "face_depth_m": depth_m,
            "face_area_m2": area_m2,
            "candidate_meters_per_uv_unit": [family_u, family_v],
            "candidate_uv_span": [candidate_u_span, candidate_v_span],
            "candidate_density_anisotropy": candidate_anisotropy,
            "negative_meters_per_uv_unit": [neg_u, neg_v],
            "negative_uv_span": [neg_u_span, neg_v_span],
            "negative_density_anisotropy": neg_anisotropy,
        },
        "diagnostic_material": {
            "kind": "PROCEDURAL_UV_CHECKER_REVIEW_ONLY",
            "dark_rgba": tints["dark_rgba"],
            "light_rgba": tints["light_rgba"],
            "metallic": float(service["metallic"]),
            "roughness": float(service["roughness"]),
            "external_texture_asset": False,
        },
    }
    payload["truth_boundary"] = truth

    receipt = {
        "schema": RECEIPT_SCHEMA,
        "result": "PASS_OBJECT_SERVICE_DARK_TWO_SURFACE_PHYSICAL_UV_DENSITY_FAMILY_PACKET",
        "exact_materials_head": exact_head,
        "asset_id": contract["asset_id"],
        "service_dark_uv_family_contract_sha256": payload["service_dark_uv_family_contract_sha256"],
        "front_service_panel_uv_rebind_sha256": payload["front_service_panel_uv_rebind_sha256"],
        "front_service_panel_source_surface_id": binding["source_surface_id"],
        "inner_lid_source_surface_id": source_identity["surface_id"],
        "material_id": "service_dark",
        "shared_meters_per_uv_unit": [family_u, family_v],
        "family_density_ratio_front_to_inner": [1.0, 1.0],
        "inner_lid_face_width_m": width_m,
        "inner_lid_face_depth_m": depth_m,
        "inner_lid_face_area_m2": area_m2,
        "inner_lid_candidate_uv_span": [candidate_u_span, candidate_v_span],
        "inner_lid_candidate_density_anisotropy": candidate_anisotropy,
        "inner_lid_negative_uv_span": [neg_u_span, neg_v_span],
        "inner_lid_negative_density_anisotropy": neg_anisotropy,
        "pose_ids": target["pose_ids"],
        "camera_contexts": target["camera_contexts"],
        "source_material_assignments_authored": False,
        "production_uv_adopted": False,
        "material_scalars_changed": False,
        "external_texture_assets": [],
        "truth_boundary": truth,
    }
    return payload, receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="lookdev-proof/generated/object_inner_lid_material_payload.json")
    parser.add_argument("--contract", default="lookdev/service_dark_uv_density_family_001.json")
    parser.add_argument("--panel-rebind", default="lookdev/front_service_panel_uv_source_identity_rebind_001.json")
    parser.add_argument("--out", default="lookdev-proof/generated")
    parser.add_argument("--exact-head", default="UNSPECIFIED")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    payload, receipt = build_payload(
        Path(args.base),
        Path(args.contract),
        Path(args.panel_rebind),
        args.exact_head,
    )
    (out / "object_service_dark_uv_density_family_payload.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out / "service_dark_uv_density_family_build_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
