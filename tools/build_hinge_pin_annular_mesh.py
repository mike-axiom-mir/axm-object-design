from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from collections import defaultdict, deque
from pathlib import Path

try:
    from tools.verify_hinge_pin_bore_clearance import evaluate as evaluate_bore_clearance
except ModuleNotFoundError:  # direct `python tools/...py` execution
    from verify_hinge_pin_bore_clearance import evaluate as evaluate_bore_clearance

SCHEMA = "axm.object-hinge-pin-annular-mesh/v0.1"
RESULT = "PASS_DERIVED_ANNULAR_KNUCKLE_MESH_FACET_CLEARANCE"
TOPOLOGY_RESULT = "PASS_CLOSED_ORIENTED_ANNULAR_KNUCKLE_TOPOLOGY"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _close(a: float, b: float, tol: float = 1e-12) -> bool:
    return abs(a - b) <= tol


def _triangle_area(a, b, c) -> float:
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    cx, cy, cz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    return 0.5 * math.sqrt(cx * cx + cy * cy + cz * cz)


def _add_annular_cylinder_x(mesh: dict, name: str, center, length: float, outer_radius: float, inner_radius: float, segments: int) -> dict:
    cx, cy, cz = center
    rings: dict[str, list[int]] = {}
    for key, x, radius in (
        ("left_outer", cx - length / 2.0, outer_radius),
        ("right_outer", cx + length / 2.0, outer_radius),
        ("left_inner", cx - length / 2.0, inner_radius),
        ("right_inner", cx + length / 2.0, inner_radius),
    ):
        start = len(mesh["vertices"])
        for i in range(segments):
            a = 2.0 * math.pi * i / segments
            mesh["vertices"].append((x, cy + radius * math.cos(a), cz + radius * math.sin(a)))
        rings[key] = list(range(start, start + segments))

    first_face = len(mesh["faces"])
    lo = rings["left_outer"]
    ro = rings["right_outer"]
    li = rings["left_inner"]
    ri = rings["right_inner"]
    for i in range(segments):
        j = (i + 1) % segments

        # Outer wall: normals point radially away from the hinge axis.
        mesh["faces"].append((lo[i], lo[j], ro[i]))
        mesh["faces"].append((lo[j], ro[j], ro[i]))

        # Inner wall: normals point into the bore.
        mesh["faces"].append((li[i], ri[i], li[j]))
        mesh["faces"].append((li[j], ri[i], ri[j]))

        # Left annular end face: outward normal -X.
        mesh["faces"].append((lo[i], li[i], lo[j]))
        mesh["faces"].append((lo[j], li[i], li[j]))

        # Right annular end face: outward normal +X.
        mesh["faces"].append((ro[i], ro[j], ri[i]))
        mesh["faces"].append((ro[j], ri[j], ri[i]))

    group = {
        "name": name,
        "first_face": first_face,
        "face_count": len(mesh["faces"]) - first_face,
        "vertex_indices": sorted({idx for face in mesh["faces"][first_face:] for idx in face}),
    }
    mesh["groups"].append(group)
    return group


def _inspect_face_range(mesh: dict, first_face: int, face_count: int) -> dict:
    vertices = mesh["vertices"]
    faces = mesh["faces"][first_face:first_face + face_count]
    edge_uses: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)
    edge_faces: dict[tuple[int, int], list[int]] = defaultdict(list)
    degenerate = 0

    for local_fi, face in enumerate(faces):
        if len(set(face)) != 3 or _triangle_area(*(vertices[i] for i in face)) <= 1e-12:
            degenerate += 1
        for a, b in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
            key = tuple(sorted((a, b)))
            edge_uses[key].append((a, b))
            edge_faces[key].append(local_fi)

    boundary = sum(1 for uses in edge_uses.values() if len(uses) == 1)
    non_manifold = sum(1 for uses in edge_uses.values() if len(uses) > 2)
    orientation_conflicts = 0
    for uses in edge_uses.values():
        if len(uses) == 2:
            (a, b), (c, d) = uses
            if not (a == d and b == c):
                orientation_conflicts += 1

    adjacency = [set() for _ in faces]
    for face_ids in edge_faces.values():
        if len(face_ids) == 2:
            a, b = face_ids
            adjacency[a].add(b)
            adjacency[b].add(a)

    components = 0
    seen: set[int] = set()
    for start in range(len(faces)):
        if start in seen:
            continue
        components += 1
        seen.add(start)
        queue = deque([start])
        while queue:
            current = queue.popleft()
            for nxt in adjacency[current]:
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)

    return {
        "vertices_referenced": len({idx for face in faces for idx in face}),
        "triangles": len(faces),
        "unique_edges": len(edge_uses),
        "boundary_edges": boundary,
        "non_manifold_edges": non_manifold,
        "orientation_conflicts": orientation_conflicts,
        "degenerate_triangles": degenerate,
        "triangle_components": components,
    }


def _build_candidate(host: dict, mesh_contract: dict) -> tuple[dict, list[dict]]:
    hinge = host["hinge"]
    dimensions = host["dimensions_m"]
    hy = float(dimensions["depth"]) / 2.0 + float(hinge["offset_y"])
    hz = float(dimensions["body_height"]) + float(hinge["offset_z"])

    mesh = {"vertices": [], "faces": [], "groups": []}
    groups = []
    for knuckle in sorted(hinge["knuckles"], key=lambda row: float(row["center_x"])):
        groups.append(_add_annular_cylinder_x(
            mesh,
            f"hinge_{knuckle['owner']}_{knuckle['id']}_annular_candidate",
            (float(knuckle["center_x"]), hy, hz),
            float(knuckle["length"]),
            float(hinge["knuckle_radius"]),
            float(mesh_contract["mesh_bore_radius_m"]),
            int(hinge["segments"]),
        ))
    return mesh, groups


def _expected_mesh_bore_radius(pin_radius: float, minimum_surface_clearance: float, segments: int) -> float:
    # Source and candidate use the same angular phase. Their regular n-gon edges
    # are parallel; the minimum boundary-to-boundary separation is the
    # circumradius delta multiplied by cos(pi/n).
    return pin_radius + minimum_surface_clearance / math.cos(math.pi / segments)


def evaluate_mesh(
    host: dict,
    bore_contract: dict,
    mesh_contract: dict,
    *,
    observed_host_sha256: str | None = None,
    observed_bore_contract_sha256: str | None = None,
) -> tuple[dict, dict]:
    if mesh_contract.get("schema") != SCHEMA:
        raise AssertionError(f"unsupported mesh contract schema: {mesh_contract.get('schema')}")
    if host.get("asset_id") != mesh_contract.get("asset_id"):
        raise AssertionError("asset identity drift")
    if observed_host_sha256 is not None and observed_host_sha256 != mesh_contract.get("host_source_sha256"):
        raise AssertionError("host source identity drift")
    if observed_bore_contract_sha256 is not None and observed_bore_contract_sha256 != mesh_contract.get("bore_clearance_contract_sha256"):
        raise AssertionError("bore-clearance prerequisite identity drift")

    # The prior analytic review envelope remains a prerequisite rather than
    # being silently replaced by this faceted mesh proof.
    analytic_receipt = evaluate_bore_clearance(
        host,
        bore_contract,
        observed_host_sha256=observed_host_sha256,
    )

    hinge = host["hinge"]
    segments = int(hinge["segments"])
    if segments != int(mesh_contract["expected_segments"]):
        raise AssertionError("hinge segmentation drift")
    if len(hinge["knuckles"]) != int(mesh_contract["expected_knuckle_count"]):
        raise AssertionError("knuckle count drift")

    pin_radius = float(hinge["pin_radius"])
    outer_radius = float(hinge["knuckle_radius"])
    if not _close(pin_radius, float(mesh_contract["source_pin_radius_m"])):
        raise AssertionError("source pin radius drift")
    if not _close(float(bore_contract["bore_radius_m"]), float(mesh_contract["analytic_review_bore_radius_m"])):
        raise AssertionError("analytic review bore identity drift")

    minimum_surface_clearance = float(mesh_contract["minimum_mesh_surface_clearance_m"])
    mesh_bore_radius = float(mesh_contract["mesh_bore_radius_m"])
    expected_mesh_bore = _expected_mesh_bore_radius(pin_radius, minimum_surface_clearance, segments)
    if not _close(mesh_bore_radius, expected_mesh_bore):
        raise AssertionError(
            f"mesh bore circumradius does not preserve declared faceted clearance: "
            f"{mesh_bore_radius} != {expected_mesh_bore}"
        )
    if mesh_bore_radius >= outer_radius:
        raise AssertionError("mesh bore consumes knuckle outer shell")

    facet_factor = math.cos(math.pi / segments)
    uncompensated_surface_clearance = (float(bore_contract["bore_radius_m"]) - pin_radius) * facet_factor
    minimum_faceted_surface_clearance = (mesh_bore_radius - pin_radius) * facet_factor
    minimum_faceted_wall = (outer_radius - mesh_bore_radius) * facet_factor
    if minimum_faceted_surface_clearance < minimum_surface_clearance - 1e-12:
        raise AssertionError("faceted pin-to-bore surface clearance below contract")
    if minimum_faceted_wall < float(mesh_contract["minimum_mesh_knuckle_wall_m"]) - 1e-12:
        raise AssertionError("faceted knuckle wall below contract")

    mesh, groups = _build_candidate(host, mesh_contract)
    group_receipts = []
    for group in groups:
        topology = _inspect_face_range(mesh, group["first_face"], group["face_count"])
        if topology["boundary_edges"] != 0:
            raise AssertionError(f"{group['name']} has boundary edges")
        if topology["non_manifold_edges"] != 0:
            raise AssertionError(f"{group['name']} has non-manifold edges")
        if topology["orientation_conflicts"] != 0:
            raise AssertionError(f"{group['name']} has orientation conflicts")
        if topology["degenerate_triangles"] != 0:
            raise AssertionError(f"{group['name']} has degenerate triangles")
        if topology["triangle_components"] != 1:
            raise AssertionError(f"{group['name']} is not one edge-connected shell")
        group_receipts.append({"name": group["name"], **topology})

    aggregate = _inspect_face_range(mesh, 0, len(mesh["faces"]))
    if aggregate["triangle_components"] != len(groups):
        raise AssertionError("aggregate annular candidate component count drift")

    receipt = {
        "schema": "axm.object-hinge-pin-annular-mesh-receipt/v0.1",
        "result": RESULT,
        "topology_result": TOPOLOGY_RESULT,
        "asset_id": host["asset_id"],
        "host_source_sha256": mesh_contract["host_source_sha256"],
        "bore_clearance_contract_sha256": mesh_contract["bore_clearance_contract_sha256"],
        "analytic_prerequisite_result": analytic_receipt["result"],
        "candidate_semantics": mesh_contract["candidate_semantics"],
        "segments": segments,
        "knuckle_count": len(groups),
        "source_pin_radius_m": pin_radius,
        "source_knuckle_outer_radius_m": outer_radius,
        "analytic_review_bore_radius_m": float(bore_contract["bore_radius_m"]),
        "mesh_bore_radius_m": mesh_bore_radius,
        "faceting_compensation_delta_m": mesh_bore_radius - float(bore_contract["bore_radius_m"]),
        "uncompensated_same_phase_faceted_surface_clearance_m": uncompensated_surface_clearance,
        "minimum_mesh_surface_clearance_m": minimum_faceted_surface_clearance,
        "minimum_mesh_knuckle_wall_m": minimum_faceted_wall,
        "candidate_vertices": len(mesh["vertices"]),
        "candidate_triangles": len(mesh["faces"]),
        "candidate_triangle_components": aggregate["triangle_components"],
        "candidate_boundary_edges": aggregate["boundary_edges"],
        "candidate_non_manifold_edges": aggregate["non_manifold_edges"],
        "candidate_orientation_conflicts": aggregate["orientation_conflicts"],
        "candidate_degenerate_triangles": aggregate["degenerate_triangles"],
        "knuckle_topology": group_receipts,
        "host_source_geometry_changed": False,
        "source_adoption": False,
        "faceting_policy": mesh_contract["faceting_policy"],
        "truth_boundary": mesh_contract["truth_boundary"],
    }
    return receipt, mesh


def _write_obj(path: Path, mesh: dict) -> None:
    lines = ["# derived annular hinge-knuckle candidate; host source unchanged"]
    for vertex in mesh["vertices"]:
        lines.append("v %.12f %.12f %.12f" % tuple(vertex))
    group_by_first = {g["first_face"]: g["name"] for g in mesh["groups"]}
    for face_index, face in enumerate(mesh["faces"]):
        if face_index in group_by_first:
            lines.append("g " + group_by_first[face_index])
        lines.append("f %d %d %d" % tuple(index + 1 for index in face))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _proof_svg(receipt: dict) -> str:
    width, height = 840, 500
    cx, cy = 245.0, 250.0
    scale = 7200.0
    outer = receipt["source_knuckle_outer_radius_m"] * scale
    analytic = receipt["analytic_review_bore_radius_m"] * scale
    mesh_bore = receipt["mesh_bore_radius_m"] * scale
    pin = receipt["source_pin_radius_m"] * scale
    return "\n".join([
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="28" y="34" font-family="monospace" font-size="17">hinge annular mesh — 12-gon faceting-aware clearance</text>',
        '<text x="28" y="58" font-family="monospace" font-size="12">cross-section normal to +X; derived review mesh only, host source unchanged</text>',
        f'<circle cx="{cx}" cy="{cy}" r="{outer:.3f}" fill="#e4e6e8" stroke="#222" stroke-width="2"/>',
        f'<circle cx="{cx}" cy="{cy}" r="{mesh_bore:.3f}" fill="white" stroke="#0077aa" stroke-width="3"/>',
        f'<circle cx="{cx}" cy="{cy}" r="{analytic:.3f}" fill="none" stroke="#aa7700" stroke-width="2" stroke-dasharray="6 5"/>',
        f'<circle cx="{cx}" cy="{cy}" r="{pin:.3f}" fill="#666" stroke="#111" stroke-width="2"/>',
        f'<text x="450" y="145" font-family="monospace" font-size="13">source pin circumradius = {receipt["source_pin_radius_m"]:.9f} m</text>',
        f'<text x="450" y="174" font-family="monospace" font-size="13">old analytic bore radius = {receipt["analytic_review_bore_radius_m"]:.9f} m</text>',
        f'<text x="450" y="203" font-family="monospace" font-size="13">mesh-aware bore radius = {receipt["mesh_bore_radius_m"]:.12f} m</text>',
        f'<text x="450" y="246" font-family="monospace" font-size="13">old 12-gon min gap = {receipt["uncompensated_same_phase_faceted_surface_clearance_m"]:.12f} m</text>',
        f'<text x="450" y="275" font-family="monospace" font-size="13">corrected min mesh gap = {receipt["minimum_mesh_surface_clearance_m"]:.12f} m</text>',
        f'<text x="450" y="304" font-family="monospace" font-size="13">corrected min mesh wall = {receipt["minimum_mesh_knuckle_wall_m"]:.12f} m</text>',
        '<text x="28" y="458" font-family="monospace" font-size="11">orange dashed = prior ideal-radius review envelope; blue = compensated regular-12-gon bore circumradius</text>',
        '<text x="28" y="478" font-family="monospace" font-size="11">no manufacturing tolerance, bearing fit, source adoption, full collision, runtime or visual acceptance is claimed</text>',
        '</svg>',
        '',
    ])


def _negative_controls(host: dict, bore_contract: dict, mesh_contract: dict, host_sha: str, bore_sha: str) -> dict:
    controls: dict[str, object] = {}

    uncompensated = copy.deepcopy(mesh_contract)
    uncompensated["mesh_bore_radius_m"] = float(bore_contract["bore_radius_m"])
    try:
        evaluate_mesh(
            host,
            bore_contract,
            uncompensated,
            observed_host_sha256=host_sha,
            observed_bore_contract_sha256=bore_sha,
        )
    except AssertionError as exc:
        controls["uncompensated_12gon_bore"] = {
            "result": f"HOLD:{exc}",
            "observed_min_surface_clearance_m": (
                float(bore_contract["bore_radius_m"]) - float(host["hinge"]["pin_radius"])
            ) * math.cos(math.pi / int(host["hinge"]["segments"])),
        }
    else:
        raise AssertionError("uncompensated faceted-bore negative control unexpectedly passed")

    _, mesh = evaluate_mesh(
        host,
        bore_contract,
        mesh_contract,
        observed_host_sha256=host_sha,
        observed_bore_contract_sha256=bore_sha,
    )
    bad_mesh = copy.deepcopy(mesh)
    bad_mesh["faces"][0] = tuple(reversed(bad_mesh["faces"][0]))
    topology = _inspect_face_range(
        bad_mesh,
        bad_mesh["groups"][0]["first_face"],
        bad_mesh["groups"][0]["face_count"],
    )
    if topology["orientation_conflicts"] <= 0:
        raise AssertionError("winding-flip negative control unexpectedly passed")
    controls["single_triangle_winding_flip"] = {
        "result": "HOLD:orientation conflict detected",
        "orientation_conflicts": topology["orientation_conflicts"],
    }

    try:
        evaluate_mesh(
            host,
            bore_contract,
            mesh_contract,
            observed_host_sha256=host_sha,
            observed_bore_contract_sha256="0" * 64,
        )
    except AssertionError as exc:
        controls["bore_contract_identity_drift"] = f"HOLD:{exc}"
    else:
        raise AssertionError("bore-contract identity negative control unexpectedly passed")

    return controls


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--bore-contract", required=True)
    parser.add_argument("--mesh-contract", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    host_path = Path(args.host)
    bore_contract_path = Path(args.bore_contract)
    mesh_contract_path = Path(args.mesh_contract)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    host = json.loads(host_path.read_text(encoding="utf-8"))
    bore_contract = json.loads(bore_contract_path.read_text(encoding="utf-8"))
    mesh_contract = json.loads(mesh_contract_path.read_text(encoding="utf-8"))
    host_sha = _sha256(host_path)
    bore_sha = _sha256(bore_contract_path)

    receipt, mesh = evaluate_mesh(
        host,
        bore_contract,
        mesh_contract,
        observed_host_sha256=host_sha,
        observed_bore_contract_sha256=bore_sha,
    )
    receipt["mesh_contract_sha256"] = _sha256(mesh_contract_path)
    receipt["negative_controls"] = _negative_controls(
        host,
        bore_contract,
        mesh_contract,
        host_sha,
        bore_sha,
    )

    (out / "hinge-pin-annular-mesh.receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_obj(out / "hinge-pin-annular-knuckles.obj", mesh)
    (out / "hinge-pin-annular-mesh.proof.svg").write_text(_proof_svg(receipt), encoding="utf-8")

    print(RESULT)
    print(json.dumps({
        "mesh_bore_radius_m": receipt["mesh_bore_radius_m"],
        "faceting_compensation_delta_m": receipt["faceting_compensation_delta_m"],
        "minimum_mesh_surface_clearance_m": receipt["minimum_mesh_surface_clearance_m"],
        "minimum_mesh_knuckle_wall_m": receipt["minimum_mesh_knuckle_wall_m"],
        "candidate_vertices": receipt["candidate_vertices"],
        "candidate_triangles": receipt["candidate_triangles"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
