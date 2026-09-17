from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from build_modular_case import build

SCHEMA = "axm.object-hard-surface-service-surface-reference-frames/v0.1"
IDENTITY_SCHEMA = "axm.object-hard-surface-surface-identity/v0.1"
MATERIALS_SCHEMA = "axm.object-service-dark-atlas-pack-review/v0.1"
RESULT = "PASS_SOURCE_OWNED_SERVICE_SURFACE_REFERENCE_FRAMES"
TOL = 1e-12

EXPECTED_SURFACES = {
    "lid_inner_service_surface": {
        "component_name": "lid_shell",
        "required_role": "lid_shell",
        "selector": "source_local_min_z_face",
        "normal": [0.0, 0.0, -1.0],
    },
    "front_service_panel_outer_service_surface": {
        "component_name": "front_service_panel",
        "required_role": "service_panel",
        "selector": "source_local_min_y_face",
        "normal": [0.0, -1.0, 0.0],
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


def dot(a, b) -> float:
    return sum(float(a[i]) * float(b[i]) for i in range(3))


def cross(a, b) -> list[float]:
    return [
        float(a[1]) * float(b[2]) - float(a[2]) * float(b[1]),
        float(a[2]) * float(b[0]) - float(a[0]) * float(b[2]),
        float(a[0]) * float(b[1]) - float(a[1]) * float(b[0]),
    ]


def norm(a) -> float:
    return math.sqrt(dot(a, a))


def same_vector(a, b) -> bool:
    return len(a) == 3 and len(b) == 3 and max(abs(float(a[i]) - float(b[i])) for i in range(3)) <= TOL


def axis_token(axis) -> str:
    cardinal = {
        (1.0, 0.0, 0.0): "X",
        (0.0, 1.0, 0.0): "Y",
        (0.0, 0.0, 1.0): "Z",
    }
    key = tuple(float(v) for v in axis)
    if key not in cardinal:
        raise AssertionError(f"reference tangent axis must remain positive source cardinal: {axis}")
    return cardinal[key]


def component_bounds(component: dict[str, Any]) -> list[tuple[float, float]]:
    if component.get("kind") != "box":
        raise AssertionError(f"reference-frame owner must remain a box: {component.get('name')}")
    center = [float(v) for v in component["center_m"]]
    size = [float(v) for v in component["size_m"]]
    return [(center[i] - size[i] / 2.0, center[i] + size[i] / 2.0) for i in range(3)]


def face_center(component: dict[str, Any], selector: str) -> list[float]:
    center = [float(v) for v in component["center_m"]]
    bounds = component_bounds(component)
    if selector == "source_local_min_z_face":
        center[2] = bounds[2][0]
    elif selector == "source_local_min_y_face":
        center[1] = bounds[1][0]
    else:
        raise AssertionError(f"unsupported bounded reference-frame selector: {selector}")
    return center


def axis_extent(component: dict[str, Any], axis) -> float:
    size = [float(v) for v in component["size_m"]]
    return sum(abs(float(axis[i])) * size[i] for i in range(3))


def verify(
    host: dict[str, Any],
    contract: dict[str, Any],
    identities: dict[str, dict[str, Any]],
    materials_review: dict[str, Any],
    *,
    host_sha: str,
    contract_sha: str,
    identity_shas: dict[str, str],
) -> dict[str, Any]:
    if contract.get("schema") != SCHEMA:
        raise AssertionError("unsupported service-surface reference-frame schema")
    if contract.get("asset_id") != host.get("asset_id"):
        raise AssertionError("asset identity mismatch")
    if contract.get("host_source_sha256") != host_sha:
        raise AssertionError("host source identity mismatch")
    if contract.get("coordinate_system") != "+X right, +Y forward, +Z up":
        raise AssertionError("source coordinate-system drift")

    authority = contract.get("authority", {})
    if authority.get("hard_surface_owns_surface_reference_frame") is not True:
        raise AssertionError("source reference-frame ownership must remain explicit")
    if authority.get("hard_surface_authors_uv") is not False or authority.get("source_uv_assignment") != "UNASSIGNED":
        raise AssertionError("Hard Surface must not author production UVs")
    if authority.get("hard_surface_assigns_material") is not False or authority.get("source_material_assignment") != "UNASSIGNED":
        raise AssertionError("Hard Surface must not assign final materials")
    if authority.get("materials_basis_adopted_as_source_uv") is not False:
        raise AssertionError("Materials basis must not be silently adopted as source UV")
    if authority.get("technical_art_transport_adopted") is not False:
        raise AssertionError("Technical Art transport must remain independently owned")

    frames = contract.get("frames", [])
    if not isinstance(frames, list) or len(frames) != 2:
        raise AssertionError("reference-frame family must remain exactly two bounded service surfaces")
    frame_map = {str(row.get("surface_id")): row for row in frames}
    if set(frame_map) != set(EXPECTED_SURFACES) or len(frame_map) != len(frames):
        raise AssertionError("service-surface reference-frame identity set drift")
    if set(identities) != set(EXPECTED_SURFACES):
        raise AssertionError("surface identity donor set drift")

    observation = contract.get("downstream_basis_observation", {})
    if observation.get("schema") != MATERIALS_SCHEMA:
        raise AssertionError("downstream Materials observation schema drift")
    expected_basis = observation.get("expected_materials_basis", {})
    if set(expected_basis) != set(EXPECTED_SURFACES):
        raise AssertionError("declared Materials-basis observation set drift")

    if materials_review.get("schema") != MATERIALS_SCHEMA or materials_review.get("asset_id") != host.get("asset_id"):
        raise AssertionError("Materials atlas-review identity drift")
    materials_rows = {str(row.get("surface_id")): row for row in materials_review.get("surfaces", [])}
    if set(materials_rows) != set(EXPECTED_SURFACES):
        raise AssertionError("Materials atlas surface set drift")
    materials_truth = materials_review.get("truth_boundary", {})
    if materials_truth.get("source_geometry_changed") is not False:
        raise AssertionError("Materials review source-geometry boundary drift")
    if materials_truth.get("source_surface_identities_changed") is not False:
        raise AssertionError("Materials review source-surface boundary drift")
    if materials_truth.get("source_uv_authored") is not False or materials_truth.get("production_uv_adopted") is not False:
        raise AssertionError("Materials review must remain non-authoritative for source/production UV")

    built = build(host)
    components = {row["name"]: row for row in built["components"]}
    evidence_frames: list[dict[str, Any]] = []

    for surface_id in sorted(EXPECTED_SURFACES):
        expected = EXPECTED_SURFACES[surface_id]
        frame = frame_map[surface_id]
        identity = identities[surface_id]
        material = materials_rows[surface_id]

        if identity.get("schema") != IDENTITY_SCHEMA:
            raise AssertionError(f"{surface_id}: surface-identity schema drift")
        if identity.get("asset_id") != host.get("asset_id") or identity.get("host_source_sha256") != host_sha:
            raise AssertionError(f"{surface_id}: surface-identity source drift")
        if identity.get("surface_id") != surface_id:
            raise AssertionError(f"{surface_id}: donor surface identity drift")
        if identity.get("component_name") != expected["component_name"] or identity.get("required_role") != expected["required_role"]:
            raise AssertionError(f"{surface_id}: donor component/role drift")
        if identity.get("required_kind") != "box":
            raise AssertionError(f"{surface_id}: donor component kind drift")
        if identity.get("selector", {}).get("policy") != expected["selector"]:
            raise AssertionError(f"{surface_id}: donor selector drift")
        if identity.get("truth_boundary", {}).get("surface_identity_source_owned") is not True:
            raise AssertionError(f"{surface_id}: donor source ownership lost")

        if frame.get("component_name") != expected["component_name"] or frame.get("required_role") != expected["required_role"]:
            raise AssertionError(f"{surface_id}: frame component/role drift")
        if frame.get("selector") != expected["selector"]:
            raise AssertionError(f"{surface_id}: frame selector drift")
        if frame.get("origin_policy") != "selected_face_center":
            raise AssertionError(f"{surface_id}: frame origin policy drift")
        if frame.get("identity_contract_path") != (
            "assets/modular-equipment-case-001/lid-inner-surface-identity-001.json"
            if surface_id == "lid_inner_service_surface"
            else "assets/modular-equipment-case-001/front-service-panel-outer-surface-identity-001.json"
        ):
            raise AssertionError(f"{surface_id}: identity-contract path drift")

        component = components.get(expected["component_name"])
        if component is None:
            raise AssertionError(f"{surface_id}: source component missing")
        if component.get("role") != expected["required_role"] or component.get("kind") != "box":
            raise AssertionError(f"{surface_id}: built component role/kind drift")

        primary = [float(v) for v in frame.get("primary_axis", [])]
        secondary = [float(v) for v in frame.get("secondary_axis", [])]
        normal_axis = [float(v) for v in frame.get("outward_normal", [])]
        if len(primary) != 3 or len(secondary) != 3 or len(normal_axis) != 3:
            raise AssertionError(f"{surface_id}: frame axes must remain 3D")
        if not same_vector(normal_axis, expected["normal"]):
            raise AssertionError(f"{surface_id}: selector/outward-normal disagreement")
        if abs(norm(primary) - 1.0) > TOL or abs(norm(secondary) - 1.0) > TOL or abs(norm(normal_axis) - 1.0) > TOL:
            raise AssertionError(f"{surface_id}: reference axes must remain unit length")
        if abs(dot(primary, secondary)) > TOL or abs(dot(primary, normal_axis)) > TOL or abs(dot(secondary, normal_axis)) > TOL:
            raise AssertionError(f"{surface_id}: reference axes must remain orthogonal and tangent")

        # Restrict the current bounded source contract to positive source-cardinal tangent axes.
        # This keeps orientation explicit and prevents a consumer from silently mirroring one surface.
        primary_token = axis_token(primary)
        secondary_token = axis_token(secondary)
        parity_value = dot(cross(primary, secondary), normal_axis)
        if abs(abs(parity_value) - 1.0) > TOL:
            raise AssertionError(f"{surface_id}: frame orientation parity is not orthonormal")
        parity = 1 if parity_value > 0 else -1
        if int(frame.get("orientation_parity", 0)) != parity:
            raise AssertionError(f"{surface_id}: declared frame orientation parity drift")

        origin = face_center(component, expected["selector"])
        primary_extent = axis_extent(component, primary)
        secondary_extent = axis_extent(component, secondary)
        if primary_extent <= 0.0 or secondary_extent <= 0.0:
            raise AssertionError(f"{surface_id}: source reference-frame extent collapsed")

        expected_materials_basis = f"SOURCE_LOCAL_{primary_token}_TO_U__SOURCE_LOCAL_{secondary_token}_TO_V"
        if expected_basis.get(surface_id) != expected_materials_basis:
            raise AssertionError(f"{surface_id}: declared downstream basis observation no longer matches source frame")
        if material.get("basis") != expected_materials_basis:
            raise AssertionError(f"{surface_id}: Materials basis no longer matches source-owned reference frame")
        if material.get("component_name") != expected["component_name"]:
            raise AssertionError(f"{surface_id}: Materials component identity drift")
        if material.get("semantic") != identity.get("surface_semantics"):
            raise AssertionError(f"{surface_id}: Materials/source surface semantic drift")
        physical_size = [float(v) for v in material.get("physical_size_m", [])]
        if len(physical_size) != 2:
            raise AssertionError(f"{surface_id}: Materials physical-size record missing")
        if abs(physical_size[0] - primary_extent) > TOL or abs(physical_size[1] - secondary_extent) > TOL:
            raise AssertionError(f"{surface_id}: Materials physical-size axes drift from source reference frame")

        evidence_frames.append(
            {
                "surface_id": surface_id,
                "component_name": expected["component_name"],
                "surface_identity_sha256": identity_shas[surface_id],
                "selector": expected["selector"],
                "origin_m": origin,
                "primary_axis": primary,
                "secondary_axis": secondary,
                "outward_normal": normal_axis,
                "orientation_parity": parity,
                "primary_extent_m": primary_extent,
                "secondary_extent_m": secondary_extent,
                "materials_basis_observed": material["basis"],
                "materials_physical_size_m": physical_size,
            }
        )

    truth = contract.get("truth_boundary", {})
    if truth.get("host_source_geometry_changed") is not False or truth.get("existing_surface_identities_changed") is not False:
        raise AssertionError("reference-frame contract must preserve existing source geometry/identities")
    if truth.get("surface_reference_frames_source_owned") is not True:
        raise AssertionError("source-owned reference-frame truth flag missing")
    for key in (
        "uv_assignment",
        "material_assignment",
        "texture_assignment",
        "decal_assignment",
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
            raise AssertionError(f"truth boundary widened unexpectedly: {key}")

    return {
        "schema": "axm.object-hard-surface-service-surface-reference-frames-evidence/v0.1",
        "result": RESULT,
        "asset_id": host["asset_id"],
        "host_source_sha256": host_sha,
        "reference_frame_contract_sha256": contract_sha,
        "reference_frame_contract_digest": canonical_digest(contract),
        "host_mesh_digest": canonical_digest(built["mesh"]),
        "host_vertices": len(built["mesh"]["vertices"]),
        "host_triangles": len(built["mesh"]["faces"]),
        "frame_count": len(evidence_frames),
        "frames": evidence_frames,
        "materials_observation": observation,
        "materials_basis_matches_source_frames": True,
        "source_geometry_changed": False,
        "surface_identities_changed": False,
        "production_uv_authored": False,
        "material_assignment_authored": False,
        "technical_art_transport_accepted": False,
        "truth_boundary": truth,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--lid-identity", type=Path, required=True)
    parser.add_argument("--front-identity", type=Path, required=True)
    parser.add_argument("--materials-review", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    host = json.loads(args.host.read_text(encoding="utf-8"))
    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    lid_identity = json.loads(args.lid_identity.read_text(encoding="utf-8"))
    front_identity = json.loads(args.front_identity.read_text(encoding="utf-8"))
    materials_review = json.loads(args.materials_review.read_text(encoding="utf-8"))
    identities = {
        "lid_inner_service_surface": lid_identity,
        "front_service_panel_outer_service_surface": front_identity,
    }
    identity_shas = {
        "lid_inner_service_surface": sha256(args.lid_identity),
        "front_service_panel_outer_service_surface": sha256(args.front_identity),
    }
    receipt = verify(
        host,
        contract,
        identities,
        materials_review,
        host_sha=sha256(args.host),
        contract_sha=sha256(args.contract),
        identity_shas=identity_shas,
    )
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "service-surface-reference-frames-evidence.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
