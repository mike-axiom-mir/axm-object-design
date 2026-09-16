from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from build_modular_case import build

SCHEMA = "axm.object-hard-surface-surface-identity/v0.1"
REVIEW_SCHEMA = "axm.object-inner-lid-material-review/v0.1"
RESULT = "PASS_SOURCE_OWNED_LID_INNER_SURFACE_IDENTITY"
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
        raise AssertionError("unsupported lid surface identity schema")
    if contract.get("asset_id") != host.get("asset_id"):
        raise AssertionError("asset identity mismatch")
    if contract.get("host_source_sha256") != host_sha:
        raise AssertionError("host source identity mismatch")
    if contract.get("surface_id") != "lid_inner_service_surface":
        raise AssertionError("surface identity drift")
    if contract.get("component_name") != "lid_shell":
        raise AssertionError("v0.1 component identity drift")
    if contract.get("required_role") != "lid_shell" or contract.get("required_kind") != "box":
        raise AssertionError("lid component contract drift")
    if contract.get("surface_semantics") != "interior_service_surface":
        raise AssertionError("surface semantics drift")

    selector = contract.get("selector", {})
    if selector.get("policy") != "source_local_min_z_face":
        raise AssertionError("surface selector drift")
    if selector.get("expected_triangle_count") != 2 or selector.get("expected_unique_vertex_count") != 4:
        raise AssertionError("surface cardinality contract drift")

    authority = contract.get("material_authority", {})
    if authority.get("hard_surface_assigns_material") is not False:
        raise AssertionError("Hard Surface must not assign final material")
    if authority.get("source_material_assignment") != "UNASSIGNED":
        raise AssertionError("source material assignment must remain unassigned")
    if authority.get("review_material_candidate_adopted") is not False:
        raise AssertionError("Materials review candidate must remain unadopted")

    provenance = contract.get("review_provenance", {})
    if review.get("schema") != REVIEW_SCHEMA or provenance.get("review_schema") != REVIEW_SCHEMA:
        raise AssertionError("Materials review schema drift")
    if review.get("asset_id") != host.get("asset_id"):
        raise AssertionError("Materials review asset drift")
    surface_review = review.get("surface_review", {})
    if surface_review.get("component_name") != contract.get("component_name"):
        raise AssertionError("Materials review component drift")
    if surface_review.get("required_role") != contract.get("required_role"):
        raise AssertionError("Materials review role drift")
    if surface_review.get("required_kind") != contract.get("required_kind"):
        raise AssertionError("Materials review kind drift")
    if surface_review.get("surface_selector") != selector.get("policy"):
        raise AssertionError("Materials review selector drift")
    if provenance.get("review_selector") != selector.get("policy"):
        raise AssertionError("declared review selector drift")
    truth = review.get("truth_boundary", {})
    if truth.get("source_geometry_changed") is not False or truth.get("source_material_slot_authored") is not False:
        raise AssertionError("Materials review truth boundary drift")

    result = build(host)
    components = {row["name"]: row for row in result["components"]}
    lid = components.get(contract["component_name"])
    body = components.get("body_shell")
    if lid is None or body is None:
        raise AssertionError("required lid/body source component missing")
    if lid.get("role") != contract.get("required_role") or lid.get("kind") != contract.get("required_kind"):
        raise AssertionError("source lid role/kind drift")

    groups = [g for g in result["mesh"]["groups"] if g.get("name") == contract["component_name"]]
    if len(groups) != 1:
        raise AssertionError("expected exactly one lid mesh group")
    group = groups[0]
    if int(group.get("face_count", -1)) != 12:
        raise AssertionError("lid box face-count drift")

    vertices = result["mesh"]["vertices"]
    faces = result["mesh"]["faces"]
    first_face = int(group["first_face"])
    lid_faces = faces[first_face:first_face + int(group["face_count"])]
    lid_bounds = _bounds(lid)
    body_bounds = _bounds(body)
    min_z = lid_bounds[2][0]
    max_z = lid_bounds[2][1]
    body_top_z = body_bounds[2][1]
    body_gap = min_z - body_top_z
    expected_gap = float(host["dimensions_m"]["split_gap"])
    if abs(body_gap - expected_gap) > TOL or body_gap <= 0.0:
        raise AssertionError("lid inward-face/body gap drift")

    selected_offsets = []
    selected_global = []
    selected_faces = []
    for offset, face in enumerate(lid_faces):
        zs = [vertices[i][2] for i in face]
        if all(abs(z - min_z) <= TOL for z in zs):
            selected_offsets.append(offset)
            selected_global.append(first_face + offset)
            selected_faces.append(face)

    if len(selected_faces) != selector["expected_triangle_count"]:
        raise AssertionError("inner surface triangle-count drift")
    selected_vertex_indices = sorted({i for face in selected_faces for i in face})
    if len(selected_vertex_indices) != selector["expected_unique_vertex_count"]:
        raise AssertionError("inner surface vertex-count drift")

    selected_points = [vertices[i] for i in selected_vertex_indices]
    expected_points = [
        (lid_bounds[0][0], lid_bounds[1][0], min_z),
        (lid_bounds[0][1], lid_bounds[1][0], min_z),
        (lid_bounds[0][1], lid_bounds[1][1], min_z),
        (lid_bounds[0][0], lid_bounds[1][1], min_z),
    ]
    unmatched = list(selected_points)
    for expected in expected_points:
        for idx, observed in enumerate(unmatched):
            if _same_point(expected, observed):
                unmatched.pop(idx)
                break
        else:
            raise AssertionError("inner surface corner-set drift")
    if unmatched:
        raise AssertionError("unexpected inner surface corner")

    area = sum(_triangle_area(*(vertices[i] for i in face)) for face in selected_faces)
    expected_area = float(lid["size_m"][0]) * float(lid["size_m"][1])
    if abs(area - expected_area) > TOL:
        raise AssertionError("inner surface area drift")

    # The opposite local-Z face must remain distinct; this prevents a broad whole-lid
    # material interpretation from being smuggled into the source-owned identity.
    opposite_faces = [
        face for face in lid_faces
        if all(abs(vertices[i][2] - max_z) <= TOL for i in face)
    ]
    if len(opposite_faces) != 2:
        raise AssertionError("lid opposite-face identity drift")
    if {i for face in opposite_faces for i in face} & set(selected_vertex_indices):
        raise AssertionError("inner surface leaked into outer lid face")

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
        "lid_group_first_face": first_face,
        "lid_group_face_count": int(group["face_count"]),
        "selected_face_offsets": selected_offsets,
        "selected_global_face_indices": selected_global,
        "selected_triangle_count": len(selected_faces),
        "selected_unique_vertex_count": len(selected_vertex_indices),
        "selected_vertex_indices": selected_vertex_indices,
        "selected_plane_z_m": min_z,
        "opposite_plane_z_m": max_z,
        "selected_surface_area_m2": area,
        "lid_to_body_gap_m": body_gap,
        "materials_review_selector_matches": True,
        "host_geometry_changed": False,
        "material_assignment_authored": False,
        "materials_review_candidate_adopted": False,
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
    (args.out / "lid-inner-surface-identity-evidence.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
