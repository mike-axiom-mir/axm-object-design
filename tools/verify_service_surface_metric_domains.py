from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from build_modular_case import build

SCHEMA = "axm.object-hard-surface-service-surface-metric-domain/v0.1"
FRAME_SCHEMA = "axm.object-hard-surface-service-surface-reference-frames/v0.1"
IDENTITY_SCHEMA = "axm.object-hard-surface-surface-identity/v0.1"
MATERIALS_SCHEMA = "axm.object-service-dark-atlas-pack-review/v0.1"
RESULT = "PASS_SOURCE_OWNED_SERVICE_SURFACE_METRIC_DOMAINS"
EXPECTED_MATERIALS_HEAD = "0515a2d5ad2c7a1eb545f2b7b327b7367530dfca"
EXPECTED_MATERIALS_BLOB = "2b95fcc1fcc523576eca08dbf47a140a727ab598"
TOL = 1e-12

EXPECTED = {
    "lid_inner_service_surface": {
        "component_name": "lid_shell",
        "role": "lid_shell",
        "selector": "source_local_min_z_face",
        "primary_axis": [1.0, 0.0, 0.0],
        "secondary_axis": [0.0, 1.0, 0.0],
        "normal": [0.0, 0.0, -1.0],
        "parity": -1,
    },
    "front_service_panel_outer_service_surface": {
        "component_name": "front_service_panel",
        "role": "service_panel",
        "selector": "source_local_min_y_face",
        "primary_axis": [1.0, 0.0, 0.0],
        "secondary_axis": [0.0, 0.0, 1.0],
        "normal": [0.0, -1.0, 0.0],
        "parity": 1,
    },
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def close(a: float, b: float) -> bool:
    return abs(float(a) - float(b)) <= TOL


def same_vector(a: list[float], b: list[float]) -> bool:
    return len(a) == len(b) == 3 and max(abs(float(a[i]) - float(b[i])) for i in range(3)) <= TOL


def dot(a: list[float], b: list[float]) -> float:
    return sum(float(a[i]) * float(b[i]) for i in range(3))


def cross(a: list[float], b: list[float]) -> list[float]:
    return [
        float(a[1]) * float(b[2]) - float(a[2]) * float(b[1]),
        float(a[2]) * float(b[0]) - float(a[0]) * float(b[2]),
        float(a[0]) * float(b[1]) - float(a[1]) * float(b[0]),
    ]


def component_bounds(component: dict[str, Any]) -> list[tuple[float, float]]:
    if component.get("kind") != "box":
        raise AssertionError(f"metric-domain owner must remain a box: {component.get('name')}")
    center = [float(v) for v in component["center_m"]]
    size = [float(v) for v in component["size_m"]]
    return [(center[i] - size[i] / 2.0, center[i] + size[i] / 2.0) for i in range(3)]


def selected_face_center(component: dict[str, Any], selector: str) -> list[float]:
    center = [float(v) for v in component["center_m"]]
    bounds = component_bounds(component)
    if selector == "source_local_min_z_face":
        center[2] = bounds[2][0]
    elif selector == "source_local_min_y_face":
        center[1] = bounds[1][0]
    else:
        raise AssertionError(f"unsupported bounded metric-domain selector: {selector}")
    return center


def axis_extent(component: dict[str, Any], axis: list[float]) -> float:
    size = [float(v) for v in component["size_m"]]
    return sum(abs(float(axis[i])) * size[i] for i in range(3))


def verify(
    host: dict[str, Any],
    metric_contract: dict[str, Any],
    frame_contract: dict[str, Any],
    identities: dict[str, dict[str, Any]],
    materials_review: dict[str, Any],
    *,
    host_sha: str,
    metric_contract_sha: str,
    frame_contract_sha: str,
    identity_shas: dict[str, str],
) -> dict[str, Any]:
    if metric_contract.get("schema") != SCHEMA:
        raise AssertionError("unsupported service-surface metric-domain schema")
    if metric_contract.get("asset_id") != host.get("asset_id"):
        raise AssertionError("metric-domain asset identity mismatch")
    if metric_contract.get("host_source_sha256") != host_sha:
        raise AssertionError("metric-domain host source identity mismatch")
    if metric_contract.get("coordinate_system") != "+X right, +Y forward, +Z up":
        raise AssertionError("metric-domain source coordinate-system drift")

    frame_ref = metric_contract.get("reference_frame_contract", {})
    if frame_ref.get("path") != "assets/modular-equipment-case-001/service-surface-reference-frames-001.json":
        raise AssertionError("reference-frame contract path drift")
    if frame_ref.get("required_schema") != FRAME_SCHEMA:
        raise AssertionError("reference-frame schema requirement drift")
    if frame_contract.get("schema") != FRAME_SCHEMA:
        raise AssertionError("actual reference-frame schema drift")
    if frame_contract.get("asset_id") != host.get("asset_id") or frame_contract.get("host_source_sha256") != host_sha:
        raise AssertionError("reference-frame source identity drift")

    authority = metric_contract.get("authority", {})
    if authority.get("hard_surface_owns_surface_metric_domain") is not True:
        raise AssertionError("metric-domain source ownership must remain explicit")
    for key in (
        "hard_surface_authors_uv",
        "hard_surface_selects_texel_density",
        "hard_surface_selects_atlas_dimensions",
        "hard_surface_selects_atlas_rectangles",
        "hard_surface_assigns_material",
        "technical_art_transport_adopted",
        "runtime_representation_adopted",
    ):
        if authority.get(key) is not False:
            raise AssertionError(f"Hard Surface metric-domain authority widened unexpectedly: {key}")

    observation = metric_contract.get("downstream_physical_size_observation", {})
    if observation.get("repository") != "mike-axiom-mir/axm-object-design" or observation.get("pull_request") != 6:
        raise AssertionError("Materials observation repository/PR drift")
    if observation.get("head") != EXPECTED_MATERIALS_HEAD:
        raise AssertionError("Materials observation head drift")
    if observation.get("path") != "lookdev/service_dark_atlas_pack_review_001.json":
        raise AssertionError("Materials observation path drift")
    if observation.get("git_blob_sha") != EXPECTED_MATERIALS_BLOB:
        raise AssertionError("Materials observation blob drift")
    if observation.get("schema") != MATERIALS_SCHEMA:
        raise AssertionError("Materials observation schema drift")

    if materials_review.get("schema") != MATERIALS_SCHEMA or materials_review.get("asset_id") != host.get("asset_id"):
        raise AssertionError("Materials atlas review identity drift")
    material_rows = {str(row.get("surface_id")): row for row in materials_review.get("surfaces", [])}
    if set(material_rows) != set(EXPECTED):
        raise AssertionError("Materials physical-size surface set drift")
    materials_truth = materials_review.get("truth_boundary", {})
    if materials_truth.get("source_geometry_changed") is not False:
        raise AssertionError("Materials must not rewrite source geometry")
    if materials_truth.get("source_surface_identities_changed") is not False:
        raise AssertionError("Materials must not rewrite source surface identities")
    if materials_truth.get("source_uv_authored") is not False or materials_truth.get("production_uv_adopted") is not False:
        raise AssertionError("Materials observation must remain non-authoritative for source/production UV")

    domains = metric_contract.get("domains", [])
    if not isinstance(domains, list) or len(domains) != 2:
        raise AssertionError("metric-domain family must remain exactly two service surfaces")
    domain_map = {str(row.get("surface_id")): row for row in domains}
    if set(domain_map) != set(EXPECTED) or len(domain_map) != len(domains):
        raise AssertionError("metric-domain surface identity set drift")

    frames = frame_contract.get("frames", [])
    frame_map = {str(row.get("surface_id")): row for row in frames}
    if set(frame_map) != set(EXPECTED) or len(frame_map) != len(frames):
        raise AssertionError("reference-frame surface identity set drift")
    if set(identities) != set(EXPECTED):
        raise AssertionError("surface identity donor set drift")

    built = build(host)
    components = {row["name"]: row for row in built["components"]}
    evidence_domains: list[dict[str, Any]] = []

    for surface_id in sorted(EXPECTED):
        expected = EXPECTED[surface_id]
        domain = domain_map[surface_id]
        frame = frame_map[surface_id]
        identity = identities[surface_id]
        material = material_rows[surface_id]

        if identity.get("schema") != IDENTITY_SCHEMA:
            raise AssertionError(f"{surface_id}: surface-identity schema drift")
        if identity.get("surface_id") != surface_id or identity.get("host_source_sha256") != host_sha:
            raise AssertionError(f"{surface_id}: surface-identity source drift")
        if identity.get("component_name") != expected["component_name"] or identity.get("required_role") != expected["role"]:
            raise AssertionError(f"{surface_id}: surface-identity component/role drift")
        if identity.get("selector", {}).get("policy") != expected["selector"]:
            raise AssertionError(f"{surface_id}: surface-identity selector drift")
        if identity.get("truth_boundary", {}).get("surface_identity_source_owned") is not True:
            raise AssertionError(f"{surface_id}: source-owned surface identity lost")

        component = components.get(expected["component_name"])
        if component is None:
            raise AssertionError(f"{surface_id}: source component missing")
        if component.get("kind") != "box" or component.get("role") != expected["role"]:
            raise AssertionError(f"{surface_id}: built component kind/role drift")

        if frame.get("component_name") != expected["component_name"] or frame.get("selector") != expected["selector"]:
            raise AssertionError(f"{surface_id}: source reference-frame owner/selector drift")
        primary = [float(v) for v in frame.get("primary_axis", [])]
        secondary = [float(v) for v in frame.get("secondary_axis", [])]
        normal = [float(v) for v in frame.get("outward_normal", [])]
        if not same_vector(primary, expected["primary_axis"]):
            raise AssertionError(f"{surface_id}: source primary axis drift")
        if not same_vector(secondary, expected["secondary_axis"]):
            raise AssertionError(f"{surface_id}: source secondary axis drift")
        if not same_vector(normal, expected["normal"]):
            raise AssertionError(f"{surface_id}: source outward normal drift")
        parity_value = dot(cross(primary, secondary), normal)
        parity = 1 if parity_value > 0.0 else -1
        if abs(abs(parity_value) - 1.0) > TOL or parity != expected["parity"] or int(frame.get("orientation_parity", 0)) != expected["parity"]:
            raise AssertionError(f"{surface_id}: source frame orientation parity drift")

        if domain.get("component_name") != expected["component_name"] or domain.get("selector") != expected["selector"]:
            raise AssertionError(f"{surface_id}: metric-domain owner/selector drift")
        if domain.get("origin_policy") != "selected_face_center" or domain.get("domain_units") != "meters":
            raise AssertionError(f"{surface_id}: metric-domain origin/units drift")
        if domain.get("boundary_semantics") != "CLOSED_RECTANGLE_ON_SELECTED_SOURCE_FACE":
            raise AssertionError(f"{surface_id}: metric-domain boundary semantics drift")

        primary_extent = axis_extent(component, primary)
        secondary_extent = axis_extent(component, secondary)
        area = primary_extent * secondary_extent
        expected_primary_bounds = [-primary_extent / 2.0, primary_extent / 2.0]
        expected_secondary_bounds = [-secondary_extent / 2.0, secondary_extent / 2.0]

        if not close(domain.get("primary_extent_m"), primary_extent):
            raise AssertionError(f"{surface_id}: primary metric extent drift")
        if not close(domain.get("secondary_extent_m"), secondary_extent):
            raise AssertionError(f"{surface_id}: secondary metric extent drift")
        if not close(domain.get("area_m2"), area):
            raise AssertionError(f"{surface_id}: metric-domain area drift")

        primary_bounds = [float(v) for v in domain.get("primary_bounds_m", [])]
        secondary_bounds = [float(v) for v in domain.get("secondary_bounds_m", [])]
        if len(primary_bounds) != 2 or len(secondary_bounds) != 2:
            raise AssertionError(f"{surface_id}: metric-domain bounds missing")
        if not all(close(primary_bounds[i], expected_primary_bounds[i]) for i in range(2)):
            raise AssertionError(f"{surface_id}: primary metric bounds drift")
        if not all(close(secondary_bounds[i], expected_secondary_bounds[i]) for i in range(2)):
            raise AssertionError(f"{surface_id}: secondary metric bounds drift")

        physical_size = [float(v) for v in material.get("physical_size_m", [])]
        if len(physical_size) != 2:
            raise AssertionError(f"{surface_id}: Materials physical-size record missing")
        if not close(physical_size[0], primary_extent) or not close(physical_size[1], secondary_extent):
            raise AssertionError(f"{surface_id}: Materials physical-size observation drift from source metric domain")

        evidence_domains.append(
            {
                "surface_id": surface_id,
                "component_name": expected["component_name"],
                "surface_identity_sha256": identity_shas[surface_id],
                "origin_m": selected_face_center(component, expected["selector"]),
                "primary_axis": primary,
                "secondary_axis": secondary,
                "outward_normal": normal,
                "orientation_parity": parity,
                "primary_extent_m": primary_extent,
                "secondary_extent_m": secondary_extent,
                "primary_bounds_m": expected_primary_bounds,
                "secondary_bounds_m": expected_secondary_bounds,
                "area_m2": area,
                "materials_physical_size_m": physical_size,
            }
        )

    truth = metric_contract.get("truth_boundary", {})
    if truth.get("host_source_geometry_changed") is not False:
        raise AssertionError("metric-domain contract must preserve host source geometry")
    if truth.get("existing_surface_identities_changed") is not False or truth.get("existing_surface_reference_frames_changed") is not False:
        raise AssertionError("metric-domain contract must preserve existing surface identities/reference frames")
    if truth.get("surface_metric_domains_source_owned") is not True:
        raise AssertionError("metric-domain source-owned truth flag missing")
    for key in (
        "uv_assignment",
        "texel_density_acceptance",
        "atlas_layout_acceptance",
        "material_assignment",
        "texture_assignment",
        "tangent_space_acceptance",
        "engine_import_acceptance",
        "runtime_performance_acceptance",
        "art_direction_acceptance",
        "visual_qa_acceptance",
        "manufacturing_validity",
        "canon",
        "production_readiness",
    ):
        if truth.get(key) is not False:
            raise AssertionError(f"metric-domain truth boundary widened unexpectedly: {key}")

    total_area = sum(float(row["area_m2"]) for row in evidence_domains)
    return {
        "schema": "axm.object-hard-surface-service-surface-metric-domain-evidence/v0.1",
        "result": RESULT,
        "asset_id": host["asset_id"],
        "host_source_sha256": host_sha,
        "metric_domain_contract_sha256": metric_contract_sha,
        "metric_domain_contract_digest": canonical_digest(metric_contract),
        "reference_frame_contract_sha256": frame_contract_sha,
        "reference_frame_contract_digest": canonical_digest(frame_contract),
        "host_mesh_digest": canonical_digest(built["mesh"]),
        "host_vertices": len(built["mesh"]["vertices"]),
        "host_triangles": len(built["mesh"]["faces"]),
        "domain_count": len(evidence_domains),
        "domains": evidence_domains,
        "total_service_surface_area_m2": total_area,
        "materials_observation": observation,
        "materials_physical_sizes_match_source_domains": True,
        "source_geometry_changed": False,
        "production_uv_authored": False,
        "atlas_policy_adopted": False,
        "material_assignment_authored": False,
        "technical_art_transport_accepted": False,
        "runtime_representation_accepted": False,
        "truth_boundary": truth,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=Path, required=True)
    parser.add_argument("--metric-contract", type=Path, required=True)
    parser.add_argument("--frame-contract", type=Path, required=True)
    parser.add_argument("--lid-identity", type=Path, required=True)
    parser.add_argument("--front-identity", type=Path, required=True)
    parser.add_argument("--materials-review", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    host = json.loads(args.host.read_text(encoding="utf-8"))
    metric_contract = json.loads(args.metric_contract.read_text(encoding="utf-8"))
    frame_contract = json.loads(args.frame_contract.read_text(encoding="utf-8"))
    lid_identity = json.loads(args.lid_identity.read_text(encoding="utf-8"))
    front_identity = json.loads(args.front_identity.read_text(encoding="utf-8"))
    materials_review = json.loads(args.materials_review.read_text(encoding="utf-8"))

    receipt = verify(
        host,
        metric_contract,
        frame_contract,
        {
            "lid_inner_service_surface": lid_identity,
            "front_service_panel_outer_service_surface": front_identity,
        },
        materials_review,
        host_sha=sha256(args.host),
        metric_contract_sha=sha256(args.metric_contract),
        frame_contract_sha=sha256(args.frame_contract),
        identity_shas={
            "lid_inner_service_surface": sha256(args.lid_identity),
            "front_service_panel_outer_service_surface": sha256(args.front_identity),
        },
    )

    args.out.mkdir(parents=True, exist_ok=True)
    output = args.out / "service-surface-metric-domains-evidence.json"
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
