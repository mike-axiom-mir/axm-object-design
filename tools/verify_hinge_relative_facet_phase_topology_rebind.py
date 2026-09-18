from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict
from copy import deepcopy
from pathlib import Path

try:
    from tools.verify_hinge_bored_knuckle_relative_facet_phase_successor import _build_candidate
except ModuleNotFoundError:
    from verify_hinge_bored_knuckle_relative_facet_phase_successor import _build_candidate

SCHEMA = "axm.object-hinge-relative-facet-phase-topology-rebind/v0.1"
RESULT = "PASS_OBJECT_RELATIVE_FACET_PHASE_SUCCESSOR_GENUS1_TOPOLOGY_REBIND"
RULE = "OWNER_GROUP_FACET_PHASE_CHANGE_PRESERVES_THROUGH_BORE_TOPOLOGY_ONLY_AFTER_EXACT_SOURCE_SUCCESSOR_REBIND__STRUCTURAL_CLASS_DOES_NOT_TRANSFER_RECEIVER_ACCEPTANCE"
TOL = 1e-12


def _blob(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


def _components(nodes, adjacency):
    left = set(nodes)
    count = 0
    while left:
        count += 1
        stack = [left.pop()]
        while stack:
            current = stack.pop()
            for nxt in adjacency.get(current, ()):
                if nxt in left:
                    left.remove(nxt)
                    stack.append(nxt)
    return count


def inspect(vertices, faces, declared_vertices=None):
    faces = [tuple(face) for face in faces]
    refs = sorted({idx for face in faces for idx in face})
    declared = refs if declared_vertices is None else list(declared_vertices)
    edges = defaultdict(list)
    tri_adj = defaultdict(set)
    degenerate = 0
    for fi, face in enumerate(faces):
        a, b, c = (vertices[idx] for idx in face)
        ux, uy, uz = b[0]-a[0], b[1]-a[1], b[2]-a[2]
        vx, vy, vz = c[0]-a[0], c[1]-a[1], c[2]-a[2]
        cross = (uy*vz-uz*vy, uz*vx-ux*vz, ux*vy-uy*vx)
        if len(set(face)) != 3 or sum(value*value for value in cross) <= 4e-24:
            degenerate += 1
        for x, y in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
            edges[tuple(sorted((x, y)))].append((x, y, fi))
    conflicts = 0
    for uses in edges.values():
        if len(uses) == 2:
            (a, b, fa), (c, d, fb) = uses
            tri_adj[fa].add(fb)
            tri_adj[fb].add(fa)
            conflicts += int(not (a == d and b == c))
    fan_counts = {}
    for vertex in declared:
        incident = [i for i, face in enumerate(faces) if vertex in face]
        fan_adj = defaultdict(set)
        for edge, uses in edges.items():
            if vertex not in edge:
                continue
            ids = [row[2] for row in uses if row[2] in incident]
            for i in range(len(ids)):
                for j in range(i + 1, len(ids)):
                    fan_adj[ids[i]].add(ids[j])
                    fan_adj[ids[j]].add(ids[i])
        fan_counts[vertex] = _components(incident, fan_adj) if incident else 0
    boundary = sum(len(uses) == 1 for uses in edges.values())
    nonmanifold = sum(len(uses) > 2 for uses in edges.values())
    isolated = sum(value == 0 for value in fan_counts.values())
    max_fans = max(fan_counts.values(), default=0)
    chi = len(refs) - len(edges) + len(faces)
    tri_components = _components(range(len(faces)), tri_adj)
    closed = (
        boundary == 0
        and nonmanifold == 0
        and conflicts == 0
        and degenerate == 0
        and isolated == 0
        and max_fans == 1
        and tri_components == 1
    )
    genus = (2 - chi) // 2 if closed and (2 - chi) >= 0 and (2 - chi) % 2 == 0 else None
    return {
        "vertices": len(refs),
        "triangles": len(faces),
        "unique_edges": len(edges),
        "triangle_components": tri_components,
        "boundary_edges": boundary,
        "non_manifold_edges": nonmanifold,
        "orientation_conflicts": conflicts,
        "degenerate_triangles": degenerate,
        "isolated_vertices": isolated,
        "max_vertex_fan_components": max_fans,
        "euler_characteristic": chi,
        "orientable_genus": genus,
        "closed_orientable_vertex_manifold": closed,
    }


def require(report, expected, label):
    for key, value in expected.items():
        if report.get(key) != value:
            raise AssertionError(f"{label} topology drift: {key}: {report.get(key)!r} != {value!r}")
    if report["closed_orientable_vertex_manifold"] is not True:
        raise AssertionError(f"{label} is not a closed orientable vertex-manifold")


def _group_vertices(group):
    rings = group["rings"]
    return [index for key in ("left_outer", "right_outer", "left_inner", "right_inner") for index in rings[key]]


def _group_identity(receipts):
    return [(row["id"], row["owner"], row["group"]["name"], row["group"]["face_count"]) for row in receipts]


def evaluate(host_path, successor002_path, successor003_path, topology_path, source_verifier_path):
    host = json.loads(Path(host_path).read_text())
    successor002 = json.loads(Path(successor002_path).read_text())
    successor003 = json.loads(Path(successor003_path).read_text())
    contract = json.loads(Path(topology_path).read_text())

    if contract.get("schema") != SCHEMA or contract.get("reusable_rule") != RULE:
        raise AssertionError("Geometry contract identity drift")
    if contract.get("asset_id") != host.get("asset_id") or contract.get("successor_id") != successor003.get("successor_id"):
        raise AssertionError("asset/source-successor identity drift")
    source_identity = contract["source_identity"]
    if _blob(Path(successor002_path)) != source_identity["successor002_contract_git_blob_sha1"]:
        raise AssertionError("successor002 blob drift")
    if _blob(Path(successor003_path)) != source_identity["successor003_contract_git_blob_sha1"]:
        raise AssertionError("successor003 blob drift")
    if _blob(Path(source_verifier_path)) != source_identity["successor003_builder_verifier_git_blob_sha1"]:
        raise AssertionError("successor003 builder/verifier blob drift")

    if successor003.get("schema") != "axm.object-hinge-bored-knuckle-relative-facet-phase-source-successor/v0.1":
        raise AssertionError("successor003 schema drift")
    if successor003["prerequisite_identity"]["successor002_contract_git_blob_sha1"] != source_identity["successor002_contract_git_blob_sha1"]:
        raise AssertionError("successor003 predecessor binding drift")
    if successor003["source_owned_successor"].get("automatic_downstream_adoption") is not False:
        raise AssertionError("source-owner automatic adoption drift")
    if successor003["authority"].get("geometry_adoption_authorized") is not False:
        raise AssertionError("source owner pre-authorized Geometry adoption")

    authority = contract["geometry_authority"]
    if authority.get("historical_pass_transferred") is not False:
        raise AssertionError("historical Geometry PASS transfer is forbidden")
    if any(value is not False for value in authority.values()):
        raise AssertionError("Geometry authority expansion")

    expected_phase = contract["expected_phase"]
    phase = successor003["source_owned_successor"]["owner_group_phase_deg"]
    if abs(float(phase["body"]) - float(expected_phase["body_deg"])) > TOL:
        raise AssertionError("body facet phase drift")
    if abs(float(phase["lid"]) - float(expected_phase["lid_deg"])) > TOL:
        raise AssertionError("lid facet phase drift")
    if abs(float(successor003["source_owned_successor"]["relative_lid_minus_body_phase_deg"]) - float(expected_phase["relative_lid_minus_body_deg"])) > TOL:
        raise AssertionError("relative facet phase drift")
    if successor003["source_owned_successor"].get("rotate_outer_and_bore_cross_sections_together") is not True:
        raise AssertionError("complete annular cross-section phase rotation lost")

    zero_phase_contract = deepcopy(successor003)
    zero_phase_contract["source_owned_successor"]["owner_group_phase_deg"] = {"body": 0.0, "lid": 0.0}
    predecessor_mesh, predecessor_receipts = _build_candidate(host, successor002, zero_phase_contract)
    candidate_mesh, candidate_receipts = _build_candidate(host, successor002, successor003)

    if predecessor_mesh["faces"] != candidate_mesh["faces"]:
        raise AssertionError("facet phase changed face connectivity")
    if _group_identity(predecessor_receipts) != _group_identity(candidate_receipts):
        raise AssertionError("facet phase changed group order/ownership")

    deltas = [math.dist(a, b) for a, b in zip(predecessor_mesh["vertices"], candidate_mesh["vertices"])]
    changed = sum(delta > 1e-15 for delta in deltas)
    unchanged = len(deltas) - changed
    maximum = max(deltas, default=0.0)
    expected_delta = contract["expected_delta_from_successor002"]
    if unchanged != expected_delta["unchanged_vertex_positions"] or changed != expected_delta["changed_vertex_positions"]:
        raise AssertionError("facet-phase changed/unchanged vertex-count drift")
    if abs(maximum - float(expected_delta["maximum_vertex_position_delta_m"])) > 1e-12:
        raise AssertionError("facet-phase maximum vertex delta drift")
    if expected_delta.get("face_connectivity_identical") is not True or expected_delta.get("group_order_and_ownership_identical") is not True:
        raise AssertionError("contract weakened structural continuity requirements")

    reports = []
    predecessor_reports = []
    for mesh, receipts, output in (
        (predecessor_mesh, predecessor_receipts, predecessor_reports),
        (candidate_mesh, candidate_receipts, reports),
    ):
        for row in receipts:
            group = row["group"]
            face_slice = mesh["faces"][group["first_face"]:group["first_face"] + group["face_count"]]
            report = inspect(mesh["vertices"], face_slice, _group_vertices(group))
            require(report, contract["expected_per_knuckle"], row["id"])
            output.append({"id": row["id"], "owner": row["owner"], "phase_deg": row["phase_deg"], **report})

    def aggregate(mesh, rows):
        return {
            "vertices": len(mesh["vertices"]),
            "triangles": len(mesh["faces"]),
            "unique_edges": sum(row["unique_edges"] for row in rows),
            "triangle_components": len(rows),
            "euler_characteristic_sum": sum(row["euler_characteristic"] for row in rows),
            "orientable_genus_sum": sum(row["orientable_genus"] for row in rows),
        }

    predecessor_aggregate = aggregate(predecessor_mesh, predecessor_reports)
    candidate_aggregate = aggregate(candidate_mesh, reports)
    for label, observed in (("successor002-reconstructed", predecessor_aggregate), ("successor003", candidate_aggregate)):
        for key, value in contract["expected_aggregate"].items():
            if observed.get(key) != value:
                raise AssertionError(f"{label} aggregate topology drift: {key}")

    body = [row for row in reports if row["owner"] == "body"]
    lid = [row for row in reports if row["owner"] == "lid"]
    if len(body) != 3 or len(lid) != 2:
        raise AssertionError("owner-group cardinality drift")
    if any(abs(row["phase_deg"]) > TOL for row in body) or any(abs(row["phase_deg"] - 15.0) > TOL for row in lid):
        raise AssertionError("owner-group phase assignment drift")

    return {
        "schema": "axm.object-hinge-relative-facet-phase-topology-rebind-receipt/v0.1",
        "result": RESULT,
        "asset_id": contract["asset_id"],
        "successor_id": contract["successor_id"],
        "hard_surface_donor_head": contract["hard_surface_donor_head"],
        "predecessor_geometry_head": contract["predecessor_geometry_head"],
        "historical_pass_transferred": False,
        "source_successor_mutated": False,
        "successor002_reconstructed_aggregate": predecessor_aggregate,
        "successor003_aggregate": candidate_aggregate,
        "successor003_group_reports": reports,
        "changed_vertex_positions": changed,
        "unchanged_vertex_positions": unchanged,
        "maximum_vertex_position_delta_m": maximum,
        "face_connectivity_identical_to_successor002": True,
        "group_order_and_ownership_identical_to_successor002": True,
        "technical_art_successor003_receiver_revalidated": False,
        "rigging_successor003_revalidated": False,
        "materials_successor003_adopted": False,
        "automatic_downstream_adoption": False,
        "reusable_rule": RULE,
        "truth_boundary": contract["truth_boundary"],
    }


def main():
    parser = argparse.ArgumentParser()
    for name in ("host", "successor002", "successor003", "topology-contract", "source-verifier", "out"):
        parser.add_argument(f"--{name}", required=True)
    args = parser.parse_args()
    receipt = evaluate(
        args.host,
        args.successor002,
        args.successor003,
        args.topology_contract,
        args.source_verifier,
    )
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "hinge-relative-facet-phase-topology-rebind-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    )
    print(receipt["result"])


if __name__ == "__main__":
    main()
