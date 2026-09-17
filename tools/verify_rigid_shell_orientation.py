from __future__ import annotations

import argparse
import collections
import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from tools.build_modular_case import build

POLICY_SCHEMA = "axm.object-geometry-rigid-shell-orientation-review/v0.1"
RECEIPT_SCHEMA = "axm.object-geometry-rigid-shell-orientation-receipt/v0.1"
EXPECTED_ASSET_ID = "modular-equipment-case-001"
EXPECTED_SOURCE_SHA256 = "49b1f9ed9865893d6de6f1ec8f069576732df694853fde4e3fcff366de32644a"
EXPECTED_VERTEX_COUNT = 468
EXPECTED_TRIANGLE_COUNT = 812
EXPECTED_GROUP_COUNT = 31
EPS_AREA = 1e-12
EPS_VOLUME = 1e-15


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def triangle_area(vertices: list[tuple[float, float, float]], face: tuple[int, int, int]) -> float:
    a, b, c = (vertices[index] for index in face)
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    cx, cy, cz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    return 0.5 * math.sqrt(cx * cx + cy * cy + cz * cz)


def signed_volume(vertices: list[tuple[float, float, float]], faces: list[tuple[int, int, int]]) -> float:
    total = 0.0
    for ia, ib, ic in faces:
        a, b, c = vertices[ia], vertices[ib], vertices[ic]
        total += (
            a[0] * (b[1] * c[2] - b[2] * c[1])
            + a[1] * (b[2] * c[0] - b[0] * c[2])
            + a[2] * (b[0] * c[1] - b[1] * c[0])
        )
    return total / 6.0


def _edge_records(faces: list[tuple[int, int, int]]) -> dict[tuple[int, int], list[tuple[int, int, int]]]:
    records: dict[tuple[int, int], list[tuple[int, int, int]]] = collections.defaultdict(list)
    for face_index, (a, b, c) in enumerate(faces):
        for start, end in ((a, b), (b, c), (c, a)):
            records[tuple(sorted((start, end)))].append((face_index, start, end))
    return records


def orientation_conflict_edges(faces: list[tuple[int, int, int]]) -> int:
    conflicts = 0
    for records in _edge_records(faces).values():
        if len(records) != 2:
            continue
        _, a0, b0 = records[0]
        _, a1, b1 = records[1]
        if a0 == a1 and b0 == b1:
            conflicts += 1
    return conflicts


def _face_component_count(faces: list[tuple[int, int, int]]) -> int:
    edge_records = _edge_records(faces)
    adjacency: dict[int, set[int]] = {index: set() for index in range(len(faces))}
    for records in edge_records.values():
        for left in range(len(records)):
            for right in range(left + 1, len(records)):
                a = records[left][0]
                b = records[right][0]
                adjacency[a].add(b)
                adjacency[b].add(a)
    unseen = set(adjacency)
    components = 0
    while unseen:
        components += 1
        seed = unseen.pop()
        stack = [seed]
        while stack:
            current = stack.pop()
            for neighbor in adjacency[current]:
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    stack.append(neighbor)
    return components


def orient_closed_group(
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, int, int]],
) -> tuple[list[tuple[int, int, int]], dict[str, Any]]:
    if not faces:
        raise AssertionError("rigid group has no faces")
    for face in faces:
        if len(set(face)) != 3:
            raise AssertionError("triangle repeats a vertex index")
        if any(index < 0 or index >= len(vertices) for index in face):
            raise AssertionError("triangle index out of bounds")
        if triangle_area(vertices, face) <= EPS_AREA:
            raise AssertionError("degenerate triangle in rigid group")

    edge_records = _edge_records(faces)
    boundary_edges = sum(len(records) == 1 for records in edge_records.values())
    nonmanifold_edges = sum(len(records) > 2 for records in edge_records.values())
    if boundary_edges or nonmanifold_edges:
        raise AssertionError(
            f"rigid group must be closed 2-manifold before orientation repair: "
            f"boundary={boundary_edges}, nonmanifold={nonmanifold_edges}"
        )
    if any(len(records) != 2 for records in edge_records.values()):
        raise AssertionError("rigid group has invalid edge incidence")
    if _face_component_count(faces) != 1:
        raise AssertionError("rigid group must be face-connected")

    adjacency: dict[int, list[tuple[int, bool]]] = collections.defaultdict(list)
    for records in edge_records.values():
        (face_a, a0, b0), (face_b, a1, b1) = records
        same_direction = a0 == a1 and b0 == b1
        adjacency[face_a].append((face_b, same_direction))
        adjacency[face_b].append((face_a, same_direction))

    flip_flags: list[bool | None] = [None] * len(faces)
    flip_flags[0] = False
    queue = collections.deque([0])
    while queue:
        current = queue.popleft()
        assert flip_flags[current] is not None
        for neighbor, must_differ in adjacency[current]:
            expected = bool(flip_flags[current]) ^ must_differ
            if flip_flags[neighbor] is None:
                flip_flags[neighbor] = expected
                queue.append(neighbor)
            elif flip_flags[neighbor] != expected:
                raise AssertionError("rigid group is not consistently orientable")
    if any(flag is None for flag in flip_flags):
        raise AssertionError("rigid group orientation graph is disconnected")

    candidate = [
        (face[0], face[2], face[1]) if bool(flag) else face
        for face, flag in zip(faces, flip_flags)
    ]
    candidate_volume = signed_volume(vertices, candidate)
    if abs(candidate_volume) <= EPS_VOLUME:
        raise AssertionError("rigid group has near-zero signed volume")
    if candidate_volume < 0.0:
        candidate = [(face[0], face[2], face[1]) for face in candidate]
        flip_flags = [not bool(flag) for flag in flip_flags]
        candidate_volume = -candidate_volume

    if orientation_conflict_edges(candidate) != 0:
        raise AssertionError("candidate still has shared-edge orientation conflicts")
    if any(sorted(source_face) != sorted(candidate_face) for source_face, candidate_face in zip(faces, candidate)):
        raise AssertionError("orientation candidate changed triangle vertex membership")

    referenced = {index for face in faces for index in face}
    edge_count = len(edge_records)
    euler_characteristic = len(referenced) - edge_count + len(faces)
    genus_numerator = 2 - euler_characteristic
    genus = genus_numerator // 2 if genus_numerator >= 0 and genus_numerator % 2 == 0 else None

    return candidate, {
        "vertices": len(referenced),
        "triangles": len(faces),
        "edges": edge_count,
        "boundary_edges": boundary_edges,
        "nonmanifold_edges": nonmanifold_edges,
        "face_components": 1,
        "euler_characteristic": euler_characteristic,
        "genus_if_closed_orientable": genus,
        "source_orientation_conflict_edges": orientation_conflict_edges(faces),
        "source_signed_volume_m3": signed_volume(vertices, faces),
        "candidate_orientation_conflict_edges": 0,
        "candidate_signed_volume_m3": candidate_volume,
        "flipped_faces": sum(bool(flag) for flag in flip_flags),
    }


def validate_policy(policy: dict[str, Any], source_sha256: str) -> None:
    if policy.get("schema") != POLICY_SCHEMA:
        raise AssertionError("unexpected Geometry orientation policy schema")
    if policy.get("asset_id") != EXPECTED_ASSET_ID:
        raise AssertionError("unexpected Geometry orientation policy asset")
    if policy.get("source_sha256") != source_sha256:
        raise AssertionError("Geometry orientation policy source identity drift")
    if policy.get("source_geometry_changed") is not False:
        raise AssertionError("Geometry orientation review may not relabel source geometry as changed")
    if policy.get("source_adopted") is not False:
        raise AssertionError("Geometry orientation review may not self-authorize source adoption")
    if policy.get("candidate_authority") != "geometry_topology_structural_review_only":
        raise AssertionError("Geometry orientation authority boundary drift")
    for key in (
        "hard_surface_authority_preserved",
        "technical_art_scene_graph_authority_preserved",
        "runtime_authority_preserved",
        "gameplay_collision_authority_preserved",
    ):
        if policy.get(key) is not True:
            raise AssertionError(f"authority boundary weakened: {key}")


def analyze_result(source: dict[str, Any], result: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    if source.get("asset_id") != EXPECTED_ASSET_ID:
        raise AssertionError("unexpected Object source asset")
    mesh = result["mesh"]
    vertices = mesh["vertices"]
    faces = mesh["faces"]
    groups = mesh["groups"]
    components = result["components"]
    if len(vertices) != EXPECTED_VERTEX_COUNT:
        raise AssertionError(f"source vertex-count drift: {len(vertices)}")
    if len(faces) != EXPECTED_TRIANGLE_COUNT:
        raise AssertionError(f"source triangle-count drift: {len(faces)}")
    if len(groups) != EXPECTED_GROUP_COUNT or len(components) != EXPECTED_GROUP_COUNT:
        raise AssertionError("source rigid-component-count drift")
    if [group["name"] for group in groups] != [component["name"] for component in components]:
        raise AssertionError("source group/component identity drift")

    cursor = 0
    used_vertices: set[int] = set()
    candidate_faces = list(faces)
    group_receipts: list[dict[str, Any]] = []
    total_source_conflicts = 0
    total_flipped = 0
    negative_signed_volume_groups_before = 0

    for group in groups:
        if group["first_face"] != cursor or group["face_count"] <= 0:
            raise AssertionError("rigid group ranges must be contiguous and non-empty")
        start = group["first_face"]
        end = start + group["face_count"]
        if end > len(faces):
            raise AssertionError("rigid group face range exceeds source mesh")
        group_faces = list(faces[start:end])
        group_vertices = {index for face in group_faces for index in face}
        overlap = used_vertices.intersection(group_vertices)
        if overlap:
            raise AssertionError("rigid component groups share source vertex indices")
        used_vertices.update(group_vertices)

        oriented_faces, metrics = orient_closed_group(vertices, group_faces)
        candidate_faces[start:end] = oriented_faces
        metrics["name"] = group["name"]
        metrics["first_face"] = start
        metrics["face_count"] = group["face_count"]
        group_receipts.append(metrics)
        total_source_conflicts += metrics["source_orientation_conflict_edges"]
        total_flipped += metrics["flipped_faces"]
        if metrics["source_signed_volume_m3"] < 0.0:
            negative_signed_volume_groups_before += 1
        cursor = end

    if cursor != len(faces):
        raise AssertionError("rigid group ranges do not cover every source triangle")
    if used_vertices != set(range(len(vertices))):
        raise AssertionError("rigid group partition does not cover every source vertex exactly once")
    if any(sorted(source_face) != sorted(candidate_face) for source_face, candidate_face in zip(faces, candidate_faces)):
        raise AssertionError("candidate changed source triangle membership")

    candidate_mesh = copy.deepcopy(mesh)
    candidate_mesh["faces"] = candidate_faces
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "asset_id": EXPECTED_ASSET_ID,
        "result": "PASS_DERIVED_RIGID_SHELL_OUTWARD_ORIENTATION_CANDIDATE",
        "pattern": "RIGID_COMPONENT_GROUPS_REQUIRE_CLOSED_ORIENTABLE_OUTWARD_WINDING_BEFORE_INDEPENDENT_SCENE_GRAPH_CARRIAGE",
        "source_vertices": len(vertices),
        "source_triangles": len(faces),
        "source_rigid_groups": len(groups),
        "source_orientation_conflict_edges": total_source_conflicts,
        "source_negative_signed_volume_groups": negative_signed_volume_groups_before,
        "candidate_orientation_conflict_edges": sum(
            orientation_conflict_edges(candidate_faces[group["first_face"] : group["first_face"] + group["face_count"]])
            for group in groups
        ),
        "candidate_positive_signed_volume_groups": sum(
            1 for metrics in group_receipts if metrics["candidate_signed_volume_m3"] > EPS_VOLUME
        ),
        "candidate_flipped_faces": total_flipped,
        "positions_changed": False,
        "triangle_vertex_sets_changed": False,
        "triangle_order_changed": False,
        "group_partition_changed": False,
        "source_geometry_changed": False,
        "source_adopted": False,
        "technical_art_scene_graph_adopted": False,
        "runtime_adopted": False,
        "gameplay_collision_adopted": False,
        "groups": group_receipts,
        "limitations": [
            "derived orientation candidate only; source builder/output is not adopted or rewritten",
            "signed-volume outwardness is certified only for the exact closed orientable component groups in this source",
            "no production normals, tangents, UVs, materials, shading or renderer culling acceptance",
            "no Technical Art scene-graph adoption, Runtime acceptance, physics or gameplay collision claim",
            "no CANON, production readiness, game readiness or Geometry mastery claim",
        ],
    }
    if receipt["candidate_orientation_conflict_edges"] != 0:
        raise AssertionError("candidate aggregate orientation conflicts remain")
    if receipt["candidate_positive_signed_volume_groups"] != EXPECTED_GROUP_COUNT:
        raise AssertionError("not every candidate rigid group has positive signed volume")
    return receipt, candidate_mesh


def write_obj(path: Path, candidate_mesh: dict[str, Any]) -> None:
    lines = ["# derived Geometry orientation candidate; source not adopted"]
    for vertex in candidate_mesh["vertices"]:
        lines.append("v %.9f %.9f %.9f" % tuple(vertex))
    groups_by_first = {group["first_face"]: group for group in candidate_mesh["groups"]}
    for face_index, face in enumerate(candidate_mesh["faces"]):
        if face_index in groups_by_first:
            lines.append("g " + groups_by_first[face_index]["name"])
        lines.append("f %d %d %d" % tuple(index + 1 for index in face))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_evidence(source_path: Path, policy_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    source_sha256 = sha256_file(source_path)
    if source_sha256 != EXPECTED_SOURCE_SHA256:
        raise AssertionError(f"exact source SHA-256 drift: {source_sha256}")
    source = json.loads(source_path.read_text(encoding="utf-8"))
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    validate_policy(policy, source_sha256)
    result = build(source)
    receipt, candidate_mesh = analyze_result(source, result)
    receipt["source_sha256"] = source_sha256
    receipt["source_owner"] = policy["source_owner"]
    receipt["policy_schema"] = policy["schema"]
    receipt["truth_boundary"] = policy["truth_boundary"]
    return receipt, candidate_mesh


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        default="assets/modular-equipment-case-001/source.json",
        type=Path,
    )
    parser.add_argument(
        "--policy",
        default="assets/modular-equipment-case-001/rigid-shell-orientation-review-001.json",
        type=Path,
    )
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--obj", type=Path)
    args = parser.parse_args()

    receipt, candidate_mesh = build_evidence(args.source, args.policy)
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.obj:
        write_obj(args.obj, candidate_mesh)
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
