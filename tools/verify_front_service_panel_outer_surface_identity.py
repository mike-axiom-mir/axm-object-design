from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from build_modular_case import build

SCHEMA = "axm.object-hard-surface-surface-identity/v0.1"
REVIEW_SCHEMA = "axm.object-front-service-panel-uv-review/v0.1"
RESULT = "PASS_SOURCE_OWNED_FRONT_SERVICE_PANEL_OUTER_SURFACE_IDENTITY"
TOL = 1e-12


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _canonical_digest(value) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _bounds(component):
    if component.get("kind") != "box":
        raise AssertionError(f"expected box component: {component.get('name')}")
    center = component["center_m"]
    size = component["size_m"]
    return tuple((center[i] - size[i] / 2.0, center[i] + size[i] / 2.0) for i in range(3))


def _triangle_area(a, b, c):
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    cx, cy, cz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    return 0.5 * (cx * cx + cy * cy + cz * cz) ** 0.5


def _same_point(a, b):
    return max(abs(float(a[i]) - float(b[i])) for i in range(3)) <= TOL


def verify(host, contract, review, *, host_sha, contract_sha):
    if contract.get("schema") != SCHEMA:
        raise AssertionError("unsupported service-panel surface identity schema")
    if contract.get("asset_id") != host.get("asset_id"):
        raise AssertionError("asset identity mismatch")
    if contract.get("host_source_sha256") != host_sha:
        raise AssertionError("host source identity mismatch")
    if contract.get("surface_id") != "front_service_panel_outer_service_surface":
        raise AssertionError("surface identity drift")
    if contract.get("component_name") != "front_service_panel":
        raise AssertionError("component identity drift")
    if contract.get("required_role") != "service_panel" or contract.get("required_kind") != "box":
        raise AssertionError("service-panel component contract drift")
    if contract.get("surface_semantics") != "exterior_service_surface":
        raise AssertionError("surface semantics drift")

    selector = contract.get("selector", {})
    if selector.get("policy") != "source_local_min_y_face":
        raise AssertionError("surface selector drift")
    if selector.get("expected_triangle_count") != 2 or selector.get("expected_unique_vertex_count") != 4:
        raise AssertionError("surface cardinality contract drift")

    material_authority = contract.get("material_authority", {})
    if material_authority.get("hard_surface_assigns_material") is not False:
        raise AssertionError("Hard Surface must not assign final material")
    if material_authority.get("source_material_assignment") != "UNASSIGNED":
        raise AssertionError("source material assignment must remain unassigned")

    uv_authority = contract.get("uv_authority", {})
    if uv_authority.get("hard_surface_authors_uv") is not False:
        raise AssertionError("Hard Surface must not author production UVs")
    if uv_authority.get("source_uv_assignment") != "UNASSIGNED":
        raise AssertionError("source UV assignment must remain unassigned")
    if uv_authority.get("review_uv_candidate_adopted") is not False:
        raise AssertionError("Materials UV review candidate must remain unadopted")

    provenance = contract.get("review_provenance", {})
    if review.get("schema") != REVIEW_SCHEMA or provenance.get("review_schema") != REVIEW_SCHEMA:
        raise AssertionError("Materials UV review schema drift")
    if review.get("asset_id") != host.get("asset_id"):
        raise AssertionError("Materials UV review asset drift")
    target = review.get("target", {})
    if target.get("component_name") != contract.get("component_name"):
        raise AssertionError("Materials UV review component drift")
    if target.get("component_role") != contract.get("required_role"):
        raise AssertionError("Materials UV review role drift")
    if target.get("component_kind") != contract.get("required_kind"):
        raise AssertionError("Materials UV review kind drift")
    if target.get("review_surface_selector") != selector.get("policy"):
        raise AssertionError("Materials UV review selector drift")
    if provenance.get("review_selector") != selector.get("policy"):
        raise AssertionError("declared review selector drift")
    if target.get("source_surface_identity_owned") is not False:
        raise AssertionError("Materials review must not pre-own source surface identity")
    if target.get("source_material_slot_authored") is not False:
        raise AssertionError("Materials review must not author source material slot")
    review_truth = review.get("truth_boundary", {})
    if review_truth.get("source_geometry_changed") is not False:
        raise AssertionError("Materials UV review geometry truth boundary drift")
    if review_truth.get("source_surface_identity_owned") is not False:
        raise AssertionError("Materials UV review surface ownership truth boundary drift")
    if review_truth.get("source_material_slot_authored") is not False:
        raise AssertionError("Materials UV review slot truth boundary drift")
    if review_truth.get("production_uv_authored") is not False:
        raise AssertionError("Materials UV review production-UV truth boundary drift")

    result = build(host)
    components = {row["name"]: row for row in result["components"]}
    panel = components.get(contract["component_name"])
    body = components.get("body_shell")
    if panel is None or body is None:
        raise AssertionError("required service-panel/body source component missing")
    if panel.get("role") != contract.get("required_role") or panel.get("kind") != contract.get("required_kind"):
        raise AssertionError("source service-panel role/kind drift")

    groups = [g for g in result["mesh"]["groups"] if g.get("name") == contract["component_name"]]
    if len(groups) != 1:
        raise AssertionError("expected exactly one service-panel mesh group")
    group = groups[0]
    if int(group.get("face_count", -1)) != 12:
        raise AssertionError("service-panel box face-count drift")

    vertices = result["mesh"]["vertices"]
    faces = result["mesh"]["faces"]
    first_face = int(group["first_face"])
    panel_faces = faces[first_face:first_face + int(group["face_count"])]
    panel_bounds = _bounds(panel)
    body_bounds = _bounds(body)
    min_y = panel_bounds[1][0]
    max_y = panel_bounds[1][1]
    body_front_y = body_bounds[1][0]

    # The panel is source-authored flush against the body's front plane on its
    # local +Y face. Therefore local -Y is the exact outward service face.
    contact_residual = max_y - body_front_y
    if abs(contact_residual) > TOL:
        raise AssertionError("service-panel/body contact plane drift")
    outward_offset = body_front_y - min_y
    expected_depth = float(host["front_panel"]["depth"])
    if abs(outward_offset - expected_depth) > TOL or outward_offset <= 0.0:
        raise AssertionError("service-panel outward-face depth relation drift")

    selected_offsets = []
    selected_global = []
    selected_faces = []
    for offset, face in enumerate(panel_faces):
        ys = [vertices[i][1] for i in face]
        if all(abs(y - min_y) <= TOL for y in ys):
            selected_offsets.append(offset)
            selected_global.append(first_face + offset)
            selected_faces.append(face)

    if len(selected_faces) != selector["expected_triangle_count"]:
        raise AssertionError("outer service surface triangle-count drift")
    selected_vertex_indices = sorted({i for face in selected_faces for i in face})
    if len(selected_vertex_indices) != selector["expected_unique_vertex_count"]:
        raise AssertionError("outer service surface vertex-count drift")

    selected_points = [vertices[i] for i in selected_vertex_indices]
    expected_points = [
        (panel_bounds[0][0], min_y, panel_bounds[2][0]),
        (panel_bounds[0][1], min_y, panel_bounds[2][0]),
        (panel_bounds[0][1], min_y, panel_bounds[2][1]),
        (panel_bounds[0][0], min_y, panel_bounds[2][1]),
    ]
    unmatched = list(selected_points)
    for expected in expected_points:
        for idx, observed in enumerate(unmatched):
            if _same_point(expected, observed):
                unmatched.pop(idx)
                break
        else:
            raise AssertionError("outer service surface corner-set drift")
    if unmatched:
        raise AssertionError("unexpected outer service surface corner")

    area = sum(_triangle_area(*(vertices[i] for i in face)) for face in selected_faces)
    expected_area = float(panel["size_m"][0]) * float(panel["size_m"][2])
    if abs(area - expected_area) > TOL:
        raise AssertionError("outer service surface area drift")

    opposite_faces = [
        face for face in panel_faces
        if all(abs(vertices[i][1] - max_y) <= TOL for i in face)
    ]
    if len(opposite_faces) != 2:
        raise AssertionError("service-panel opposite-face identity drift")
    if {i for face in opposite_faces for i in face} & set(selected_vertex_indices):
        raise AssertionError("outer surface leaked into body-contact face")

    return {
        "schema": "axm.object-hard-surface-surface-identity-evidence/v0.1",
        "result": RESULT,
        "asset_id": host["asset_id"],
        "host_source_sha256": host_sha,
        "surface_contract_sha256": contract_sha,
        "host_mesh_digest": _canonical_digest(result["mesh"]),
        "host_vertices": len(vertices),
        "host_triangles": len(faces),
        "surface_id": contract["surface_id"],
        "surface_semantics": contract["surface_semantics"],
        "component_name": contract["component_name"],
        "selector": selector["policy"],
        "panel_group_first_face": first_face,
        "panel_group_face_count": int(group["face_count"]),
        "selected_face_offsets": selected_offsets,
        "selected_global_face_indices": selected_global,
        "selected_triangle_count": len(selected_faces),
        "selected_unique_vertex_count": len(selected_vertex_indices),
        "selected_vertex_indices": selected_vertex_indices,
        "selected_plane_y_m": min_y,
        "opposite_plane_y_m": max_y,
        "body_front_plane_y_m": body_front_y,
        "selected_surface_area_m2": area,
        "panel_depth_m": outward_offset,
        "body_contact_residual_m": contact_residual,
        "materials_review_selector_matches": True,
        "host_geometry_changed": False,
        "material_assignment_authored": False,
        "production_uv_authored": False,
        "materials_uv_candidate_adopted": False,
        "review_provenance": provenance,
        "truth_boundary": contract.get("truth_boundary", {}),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--materials-review", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    host = json.loads(args.host.read_text(encoding="utf-8"))
    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    review = json.loads(args.materials_review.read_text(encoding="utf-8"))
    receipt = verify(
        host,
        contract,
        review,
        host_sha=sha256(args.host),
        contract_sha=sha256(args.contract),
    )
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "front-service-panel-outer-surface-identity-evidence.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
