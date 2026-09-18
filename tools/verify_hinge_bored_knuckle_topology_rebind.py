from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict, deque
from pathlib import Path

try:
    from tools.build_hinge_pin_annular_mesh import evaluate_mesh
except ModuleNotFoundError:  # direct `python tools/...py` execution
    from build_hinge_pin_annular_mesh import evaluate_mesh

SCHEMA = "axm.object-hinge-bored-knuckle-topology-rebind/v0.1"
RESULT = "PASS_OBJECT_BORED_KNUCKLE_SUCCESSOR_GENUS1_TOPOLOGY_REBIND"
RULE = "SOURCE_OWNED_THROUGH_BORE_REQUIRES_CLOSED_VERTEX_MANIFOLD_AND_EXPECTED_EULER_GENUS_EVIDENCE_BEFORE_GEOMETRY_REBIND"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_blob_sha1(path: Path) -> str:
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def _triangle_area(vertices, face) -> float:
    a, b, c = (vertices[i] for i in face)
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    cx, cy, cz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    return 0.5 * math.sqrt(cx * cx + cy * cy + cz * cz)


def _component_count(adjacency: list[set[int]]) -> int:
    seen: set[int] = set()
    count = 0
    for start in range(len(adjacency)):
        if start in seen:
            continue
        count += 1
        seen.add(start)
        queue = deque([start])
        while queue:
            current = queue.popleft()
            for nxt in adjacency[current]:
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
    return count


def inspect_topology(vertices, faces, vertex_indices=None) -> dict:
    faces = [tuple(face) for face in faces]
    referenced = sorted({idx for face in faces for idx in face})
    declared_vertices = sorted(set(referenced if vertex_indices is None else vertex_indices))
    edge_uses: dict[tuple[int, int], list[tuple[int, int, int]]] = defaultdict(list)
    degenerate = 0

    for fi, face in enumerate(faces):
        if len(face) != 3 or len(set(face)) != 3 or _triangle_area(vertices, face) <= 1e-12:
            degenerate += 1
        for a, b in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
            edge_uses[tuple(sorted((a, b)))].append((a, b, fi))

    boundary = sum(1 for uses in edge_uses.values() if len(uses) == 1)
    non_manifold = sum(1 for uses in edge_uses.values() if len(uses) > 2)
    orientation_conflicts = 0
    triangle_adjacency = [set() for _ in faces]
    for uses in edge_uses.values():
        if len(uses) == 2:
            (a, b, fa), (c, d, fb) = uses
            triangle_adjacency[fa].add(fb)
            triangle_adjacency[fb].add(fa)
            if not (a == d and b == c):
                orientation_conflicts += 1

    fan_counts: dict[int, int] = {}
    for vertex in declared_vertices:
        incident = [fi for fi, face in enumerate(faces) if vertex in face]
        if not incident:
            fan_counts[vertex] = 0
            continue
        local_index = {fi: i for i, fi in enumerate(incident)}
        local_adj = [set() for _ in incident]
        for edge, uses in edge_uses.items():
            if vertex not in edge:
                continue
            local_faces = [entry[2] for entry in uses if entry[2] in local_index]
            for i, fa in enumerate(local_faces):
                for fb in local_faces[i + 1:]:
                    ia, ib = local_index[fa], local_index[fb]
                    local_adj[ia].add(ib)
                    local_adj[ib].add(ia)
        fan_counts[vertex] = _component_count(local_adj)

    isolated = sum(1 for count in fan_counts.values() if count == 0)
    max_fans = max(fan_counts.values(), default=0)
    v = len(referenced)
    e = len(edge_uses)
    f = len(faces)
    chi = v - e + f
    triangle_components = _component_count(triangle_adjacency)

    closed_orientable_vertex_manifold = (
        boundary == 0
        and non_manifold == 0
        and orientation_conflicts == 0
        and degenerate == 0
        and isolated == 0
        and max_fans == 1
        and triangle_components == 1
    )
    genus = None
    if closed_orientable_vertex_manifold:
        numerator = 2 - chi
        if numerator < 0 or numerator % 2 != 0:
            raise AssertionError(f"invalid orientable closed-surface Euler characteristic: {chi}")
        genus = numerator // 2

    return {
        "vertices": v,
        "triangles": f,
        "unique_edges": e,
        "triangle_components": triangle_components,
        "boundary_edges": boundary,
        "non_manifold_edges": non_manifold,
        "orientation_conflicts": orientation_conflicts,
        "degenerate_triangles": degenerate,
        "isolated_vertices": isolated,
        "max_vertex_fan_components": max_fans,
        "euler_characteristic": chi,
        "orientable_genus": genus,
        "closed_orientable_vertex_manifold": closed_orientable_vertex_manifold,
    }


def _require_expected_topology(observed: dict, expected: dict, label: str) -> None:
    for key, value in expected.items():
        if observed.get(key) != value:
            raise AssertionError(f"{label} topology drift: {key}={observed.get(key)!r}, expected {value!r}")
    if not observed.get("closed_orientable_vertex_manifold"):
        raise AssertionError(f"{label} is not a closed orientable indexed vertex-manifold")


def _build_closed_solid_cylinder_control(segments: int = 12) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]]]:
    vertices: list[tuple[float, float, float]] = []
    for x in (-0.5, 0.5):
        for i in range(segments):
            a = 2.0 * math.pi * i / segments
            vertices.append((x, math.cos(a), math.sin(a)))
    left = list(range(0, segments))
    right = list(range(segments, 2 * segments))
    left_center = len(vertices)
    vertices.append((-0.5, 0.0, 0.0))
    right_center = len(vertices)
    vertices.append((0.5, 0.0, 0.0))

    faces: list[tuple[int, int, int]] = []
    for i in range(segments):
        j = (i + 1) % segments
        faces.append((left[i], left[j], right[i]))
        faces.append((left[j], right[j], right[i]))
        faces.append((left[i], left_center, left[j]))
        faces.append((right[i], right[j], right_center))
    return vertices, faces


def evaluate(
    host_path: Path,
    bore_path: Path,
    annular_path: Path,
    successor_path: Path,
    topology_contract_path: Path,
) -> dict:
    host = json.loads(host_path.read_text(encoding="utf-8"))
    bore = json.loads(bore_path.read_text(encoding="utf-8"))
    annular = json.loads(annular_path.read_text(encoding="utf-8"))
    successor = json.loads(successor_path.read_text(encoding="utf-8"))
    contract = json.loads(topology_contract_path.read_text(encoding="utf-8"))

    if contract.get("schema") != SCHEMA:
        raise AssertionError("unsupported topology-rebind schema")
    if contract.get("asset_id") != host.get("asset_id") or contract.get("asset_id") != successor.get("asset_id"):
        raise AssertionError("asset identity drift")
    if contract.get("successor_id") != successor.get("successor_id"):
        raise AssertionError("source-successor identity drift")
    if contract.get("legacy_host_source_sha256") != _sha256(host_path):
        raise AssertionError("legacy host source identity drift")
    if contract.get("successor_contract_git_blob_sha1") != _git_blob_sha1(successor_path):
        raise AssertionError("source-successor contract blob drift")
    if contract.get("annular_mesh_contract_git_blob_sha1") != _git_blob_sha1(annular_path):
        raise AssertionError("annular mesh contract blob drift")
    if successor.get("annular_mesh_contract_git_blob_sha1") != _git_blob_sha1(annular_path):
        raise AssertionError("Hard-Surface successor no longer binds the observed annular contract")
    if successor.get("source_owned_successor", {}).get("automatic_downstream_adoption") is not False:
        raise AssertionError("source successor attempts automatic downstream adoption")
    if successor.get("source_owned_successor", {}).get("legacy_host_source_rewritten") is not False:
        raise AssertionError("source successor attempts historical source rewrite")
    if successor.get("authority", {}).get("hard_surface_source_successor_authorized") is not True:
        raise AssertionError("Hard-Surface source-successor authority missing")
    authority = contract.get("geometry_authority", {})
    if authority.get("geometry_rebind_is_observation_only") is not True:
        raise AssertionError("Geometry rebind must remain observation-only")
    for key in (
        "source_successor_rewritten",
        "automatic_downstream_adoption",
        "automatic_local_helper_retirement",
        "runtime_or_physics_authorized",
        "gameplay_collision_authorized",
        "visual_acceptance_authorized",
    ):
        if authority.get(key) is not False:
            raise AssertionError(f"Geometry authority expansion: {key}")
    if contract.get("reusable_rule") != RULE:
        raise AssertionError("reusable topology rule drift")

    annular_receipt, mesh = evaluate_mesh(
        host,
        bore,
        annular,
        observed_host_sha256=_sha256(host_path),
        observed_bore_contract_sha256=_sha256(bore_path),
    )
    if annular_receipt.get("result") != "PASS_DERIVED_ANNULAR_KNUCKLE_MESH_FACET_CLEARANCE":
        raise AssertionError("Hard-Surface annular prerequisite not green")
    if len(mesh.get("groups", [])) != int(contract["expected_knuckle_count"]):
        raise AssertionError("knuckle group count drift")
    if int(annular_receipt.get("segments", -1)) != int(contract["expected_segments"]):
        raise AssertionError("segment count drift")

    group_reports = []
    total_edges = 0
    total_chi = 0
    total_genus = 0
    for group in mesh["groups"]:
        first = int(group["first_face"])
        count = int(group["face_count"])
        report = inspect_topology(
            mesh["vertices"],
            mesh["faces"][first:first + count],
            vertex_indices=group["vertex_indices"],
        )
        _require_expected_topology(report, contract["expected_per_knuckle"], group["name"])
        group_reports.append({"name": group["name"], **report})
        total_edges += report["unique_edges"]
        total_chi += report["euler_characteristic"]
        total_genus += int(report["orientable_genus"])

    aggregate = {
        "vertices": len(mesh["vertices"]),
        "triangles": len(mesh["faces"]),
        "unique_edges": total_edges,
        "triangle_components": len(group_reports),
        "euler_characteristic_sum": total_chi,
        "orientable_genus_sum": total_genus,
    }
    for key, value in contract["expected_aggregate"].items():
        if aggregate.get(key) != value:
            raise AssertionError(f"aggregate topology drift: {key}={aggregate.get(key)!r}, expected {value!r}")

    control_vertices, control_faces = _build_closed_solid_cylinder_control(int(contract["expected_segments"]))
    solid_control = inspect_topology(control_vertices, control_faces)
    if not solid_control["closed_orientable_vertex_manifold"]:
        raise AssertionError("closed-solid-cylinder control must itself be a closed orientable vertex-manifold")
    if solid_control["euler_characteristic"] != 2 or solid_control["orientable_genus"] != 0:
        raise AssertionError("closed-solid-cylinder control topology drift")
    genus_gate_rejected_closed_solid_control = False
    try:
        expected_through_bore = dict(contract["expected_per_knuckle"])
        expected_through_bore["vertices"] = solid_control["vertices"]
        expected_through_bore["triangles"] = solid_control["triangles"]
        expected_through_bore["unique_edges"] = solid_control["unique_edges"]
        _require_expected_topology(solid_control, expected_through_bore, "closed-solid-cylinder-control")
    except AssertionError:
        genus_gate_rejected_closed_solid_control = True
    if not genus_gate_rejected_closed_solid_control:
        raise AssertionError("through-bore topology gate accepted a closed genus-0 solid-cylinder control")

    return {
        "schema": "axm.object-hinge-bored-knuckle-topology-rebind-receipt/v0.1",
        "result": RESULT,
        "asset_id": contract["asset_id"],
        "successor_id": contract["successor_id"],
        "hard_surface_donor_head": contract["hard_surface_donor_head"],
        "hard_surface_annular_prerequisite": annular_receipt["result"],
        "group_reports": group_reports,
        "aggregate": aggregate,
        "closed_solid_cylinder_negative_control": {
            **solid_control,
            "expected_rejection": "CLOSED_MANIFOLD_BUT_GENUS0_NOT_THROUGH_BORE_GENUS1",
            "rejected_by_through_bore_gate": genus_gate_rejected_closed_solid_control,
        },
        "source_successor_geometry_changed": False,
        "automatic_downstream_adoption": False,
        "reusable_rule": RULE,
        "truth_boundary": contract["truth_boundary"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=Path, required=True)
    parser.add_argument("--bore-contract", type=Path, required=True)
    parser.add_argument("--annular-contract", type=Path, required=True)
    parser.add_argument("--successor-contract", type=Path, required=True)
    parser.add_argument("--topology-contract", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    receipt = evaluate(
        args.host,
        args.bore_contract,
        args.annular_contract,
        args.successor_contract,
        args.topology_contract,
    )
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "hinge-bored-knuckle-topology-rebind-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(receipt["result"])


if __name__ == "__main__":
    main()
