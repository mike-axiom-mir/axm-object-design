from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict, deque
from pathlib import Path

SCHEMA = "axm.object-hinge-bored-knuckle-relative-facet-phase-source-successor/v0.1"
RESULT = "PASS_SOURCE_OWNED_HINGE_RELATIVE_FACET_PHASE_SUCCESSOR"
TOPOLOGY_RESULT = "PASS_RELATIVE_FACET_PHASE_ANNULAR_KNUCKLE_TOPOLOGY"
TOL = 1e-12


def _close(a: float, b: float, tol: float = TOL) -> bool:
    return abs(float(a) - float(b)) <= tol


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_blob_sha1(path: Path) -> str:
    data = path.read_bytes()
    h = hashlib.sha1()
    h.update(f"blob {len(data)}\0".encode("ascii"))
    h.update(data)
    return h.hexdigest()


def _triangle_area(a, b, c) -> float:
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    cx, cy, cz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    return 0.5 * math.sqrt(cx * cx + cy * cy + cz * cz)


def _add_annular_cylinder_x(
    mesh: dict,
    *,
    name: str,
    center: tuple[float, float, float],
    length: float,
    outer_radius: float,
    inner_radius: float,
    segments: int,
    phase_rad: float,
) -> dict:
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
            a = phase_rad + 2.0 * math.pi * i / segments
            mesh["vertices"].append((x, cy + radius * math.cos(a), cz + radius * math.sin(a)))
        rings[key] = list(range(start, start + segments))

    first_face = len(mesh["faces"])
    lo, ro = rings["left_outer"], rings["right_outer"]
    li, ri = rings["left_inner"], rings["right_inner"]
    for i in range(segments):
        j = (i + 1) % segments
        mesh["faces"].append((lo[i], lo[j], ro[i]))
        mesh["faces"].append((lo[j], ro[j], ro[i]))
        mesh["faces"].append((li[i], ri[i], li[j]))
        mesh["faces"].append((li[j], ri[i], ri[j]))
        mesh["faces"].append((lo[i], li[i], lo[j]))
        mesh["faces"].append((lo[j], li[i], li[j]))
        mesh["faces"].append((ro[i], ro[j], ri[i]))
        mesh["faces"].append((ro[j], ri[j], ri[i]))

    group = {
        "name": name,
        "first_face": first_face,
        "face_count": len(mesh["faces"]) - first_face,
        "rings": rings,
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
        if len(set(face)) != 3 or _triangle_area(*(vertices[i] for i in face)) <= TOL:
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


def _ordered_host_knuckles(host: dict) -> list[dict]:
    return sorted(host["hinge"]["knuckles"], key=lambda row: float(row["center_x"]))


def _build_candidate(host: dict, successor002: dict, contract: dict) -> tuple[dict, list[dict]]:
    hinge = host["hinge"]
    dims = host["dimensions_m"]
    hy = float(dims["depth"]) / 2.0 + float(hinge["offset_y"])
    hz = float(dims["body_height"]) + float(hinge["offset_z"])
    segments = int(hinge["segments"])
    outer_radius = float(successor002["source_owned_successor"]["knuckle_outer_circumradius_m"])
    inner_radius = float(successor002["source_owned_successor"]["bore_circumradius_m"])
    phase = contract["source_owned_successor"]["owner_group_phase_deg"]

    mesh = {"vertices": [], "faces": [], "groups": []}
    receipts = []
    for knuckle in _ordered_host_knuckles(host):
        owner = knuckle["owner"]
        phase_deg = float(phase[owner])
        group = _add_annular_cylinder_x(
            mesh,
            name=f"hinge_{owner}_{knuckle['id']}_relative_phase_candidate",
            center=(float(knuckle["center_x"]), hy, hz),
            length=float(knuckle["length"]),
            outer_radius=outer_radius,
            inner_radius=inner_radius,
            segments=segments,
            phase_rad=math.radians(phase_deg),
        )
        receipts.append({"id": knuckle["id"], "owner": owner, "phase_deg": phase_deg, "group": group})
    return mesh, receipts


def evaluate(
    host: dict,
    successor002: dict,
    owner_stack: dict,
    axial_stop: dict,
    capture: dict,
    bracket: dict,
    contract: dict,
    *,
    observed_host_sha256: str | None = None,
    observed_successor002_blob_sha1: str | None = None,
    observed_owner_stack_blob_sha1: str | None = None,
    observed_axial_stop_blob_sha1: str | None = None,
    observed_capture_blob_sha1: str | None = None,
    observed_bracket_blob_sha1: str | None = None,
) -> tuple[dict, dict]:
    if contract.get("schema") != SCHEMA:
        raise AssertionError(f"unsupported contract schema: {contract.get('schema')}")
    if host.get("asset_id") != contract.get("asset_id"):
        raise AssertionError("asset identity drift")
    if successor002.get("schema") != "axm.object-hinge-bored-knuckle-phase-invariant-source-successor/v0.1":
        raise AssertionError("successor002 schema drift")
    if owner_stack.get("schema") != "axm.object-hinge-knuckle-owner-stack/v0.1":
        raise AssertionError("owner-stack schema drift")
    if axial_stop.get("schema") != "axm.object-hinge-pin-axial-stop/v0.1":
        raise AssertionError("axial-stop schema drift")
    if capture.get("schema") != "axm.object-hinge-bored-knuckle-axial-stop-capture/v0.1":
        raise AssertionError("capture schema drift")
    if bracket.get("schema") != "axm.object-hinge-bored-knuckle-axial-stop-bracket/v0.1":
        raise AssertionError("bracket schema drift")

    pins = contract["prerequisite_identity"]
    checks = (
        (observed_host_sha256, pins["legacy_host_source_sha256"], "host source SHA-256"),
        (observed_successor002_blob_sha1, pins["successor002_contract_git_blob_sha1"], "successor002 blob"),
        (observed_owner_stack_blob_sha1, pins["owner_stack_contract_git_blob_sha1"], "owner-stack blob"),
        (observed_axial_stop_blob_sha1, pins["axial_stop_contract_git_blob_sha1"], "axial-stop blob"),
        (observed_capture_blob_sha1, pins["radial_capture_contract_git_blob_sha1"], "capture blob"),
        (observed_bracket_blob_sha1, pins["axial_bracket_contract_git_blob_sha1"], "bracket blob"),
    )
    for observed, expected, label in checks:
        if observed is not None and observed != expected:
            raise AssertionError(f"{label} identity drift")

    if successor002.get("successor_id") != pins["successor002_id"]:
        raise AssertionError("successor002 semantic identity drift")
    if capture.get("compatibility_id") != pins["radial_capture_id"]:
        raise AssertionError("radial capture semantic identity drift")
    if bracket.get("bracket_id") != pins["axial_bracket_id"]:
        raise AssertionError("axial bracket semantic identity drift")

    art = contract["art_direction_return"]
    if art.get("direction") != 47 or art.get("request") != "ONE_LID_VS_BODY_RELATIVE_12_GON_FACET_PHASE_ONLY_SUCCESSOR":
        raise AssertionError("Art Direction 047 binding drift")
    if art.get("no_phase_sweep") is not True or art.get("single_candidate_only") is not True:
        raise AssertionError("phase search authority expanded")

    hinge = host["hinge"]
    source = successor002["source_owned_successor"]
    candidate = contract["source_owned_successor"]
    segments = int(hinge["segments"])
    if segments != 12 or int(source["segments"]) != 12 or int(candidate["segments"]) != 12:
        raise AssertionError("segment count drift")
    if list(hinge["axis"]) != [1, 0, 0] or list(candidate["hinge_axis"]) != [1, 0, 0]:
        raise AssertionError("hinge axis drift")

    ordered = _ordered_host_knuckles(host)
    observed_order = [{"id": k["id"], "owner": k["owner"]} for k in ordered]
    if observed_order != owner_stack["ordered_knuckles"]:
        raise AssertionError("owner stack/order drift")
    counts = {"body": 0, "lid": 0}
    for k in ordered:
        counts[k["owner"]] += 1
    if counts != {"body": 3, "lid": 2} or counts != owner_stack["expected_owner_counts"]:
        raise AssertionError("owner count drift")

    phase = candidate["owner_group_phase_deg"]
    body_phase = float(phase["body"])
    lid_phase = float(phase["lid"])
    relative = (lid_phase - body_phase) % (360.0 / segments)
    half_sector = 180.0 / segments
    if not _close(body_phase, 0.0):
        raise AssertionError("body owner phase must preserve successor002 zero-phase reference")
    if not _close(relative, float(candidate["relative_lid_minus_body_phase_deg"])):
        raise AssertionError("declared owner-group relative phase drift")
    if not _close(relative, half_sector):
        raise AssertionError("candidate must use exactly one half-sector relative phase")
    if _close(relative, 0.0):
        raise AssertionError("relative phase collapsed to predecessor")
    if candidate.get("phase_choice_method") != "HALF_ONE_12_GON_SECTOR_SINGLE_CANDIDATE_NO_SWEEP":
        raise AssertionError("phase choice method drift")
    if candidate.get("rotate_outer_and_bore_cross_sections_together") is not True:
        raise AssertionError("complete knuckle cross-section rotation not preserved")

    frozen = contract["frozen_geometry"]
    exact_numeric = {
        "knuckle_outer_circumradius_m": float(source["knuckle_outer_circumradius_m"]),
        "bore_circumradius_m": float(source["bore_circumradius_m"]),
        "source_pin_circumradius_m": float(source["source_pin_circumradius_m"]),
        "pin_length_m": float(hinge["pin_length"]),
        "stop_radius_m": float(capture["source_owned_compatibility"]["stop_radius_m"]),
    }
    for key, observed in exact_numeric.items():
        if not _close(float(frozen[key]), observed):
            raise AssertionError(f"frozen {key} drift")
    if frozen["knuckle_ids_centers_lengths"] != [
        {"id": k["id"], "owner": k["owner"], "center_x_m": float(k["center_x"]), "length_m": float(k["length"])}
        for k in ordered
    ]:
        raise AssertionError("knuckle axial identity drift")

    bore_r = exact_numeric["bore_circumradius_m"]
    outer_r = exact_numeric["knuckle_outer_circumradius_m"]
    pin_r = exact_numeric["source_pin_circumradius_m"]
    stop_r = exact_numeric["stop_radius_m"]
    facet = math.cos(math.pi / segments)
    bore_inradius = bore_r * facet
    outer_inradius = outer_r * facet
    phase_independent_pin_clearance = bore_inradius - pin_r
    minimum_faceted_wall = (outer_r - bore_r) * facet
    stop_bore_overlap = stop_r - bore_r
    stop_outer_containment = outer_inradius - stop_r

    required = contract["required_reproof"]
    if phase_independent_pin_clearance < float(required["minimum_pin_bore_phase_independent_clearance_m"]) - TOL:
        raise AssertionError("phase-independent pin/bore clearance below frozen requirement")
    if minimum_faceted_wall < float(required["minimum_faceted_knuckle_wall_m"]) - TOL:
        raise AssertionError("faceted knuckle wall below frozen requirement")
    if stop_bore_overlap <= TOL:
        raise AssertionError("axial-stop radial bore capture lost")
    if stop_outer_containment <= TOL:
        raise AssertionError("axial-stop outer-knuckle containment lost")

    bracket_geo = bracket["source_owned_geometry"]
    stack_min = min(float(k["center_x"]) - float(k["length"]) / 2.0 for k in ordered)
    stack_max = max(float(k["center_x"]) + float(k["length"]) / 2.0 for k in ordered)
    left_inward = float(bracket_geo["left_stop_inward_face_x_m"])
    right_inward = float(bracket_geo["right_stop_inward_face_x_m"])
    left_gap = stack_min - left_inward
    right_gap = right_inward - stack_max
    if left_gap < float(required["minimum_static_axial_gap_each_side_m"]) - TOL:
        raise AssertionError("left static axial bracket gap lost")
    if right_gap < float(required["minimum_static_axial_gap_each_side_m"]) - TOL:
        raise AssertionError("right static axial bracket gap lost")

    authority = contract["authority"]
    if authority.get("hard_surface_source_successor_authorized") is not True:
        raise AssertionError("Hard-Surface owner authority missing")
    forbidden = [key for key, value in authority.items() if key != "hard_surface_source_successor_authorized" and value is not False]
    if forbidden:
        raise AssertionError(f"downstream authority expanded: {forbidden}")
    if candidate.get("automatic_default_replacement") is not False or candidate.get("automatic_downstream_adoption") is not False:
        raise AssertionError("automatic adoption authority expanded")

    mesh, group_rows = _build_candidate(host, successor002, contract)
    per_knuckle = []
    for row in group_rows:
        g = row["group"]
        topo = _inspect_face_range(mesh, g["first_face"], g["face_count"])
        if topo["boundary_edges"] or topo["non_manifold_edges"] or topo["orientation_conflicts"] or topo["degenerate_triangles"]:
            raise AssertionError(f"{row['id']} topology defect: {topo}")
        if topo["triangle_components"] != 1 or topo["vertices_referenced"] != 48 or topo["triangles"] != 96:
            raise AssertionError(f"{row['id']} topology class drift: {topo}")
        first_outer = mesh["vertices"][g["rings"]["left_outer"][0]]
        center = next(k for k in ordered if k["id"] == row["id"])
        hy = float(host["dimensions_m"]["depth"]) / 2.0 + float(hinge["offset_y"])
        hz = float(host["dimensions_m"]["body_height"]) + float(hinge["offset_z"])
        observed_radius = math.hypot(first_outer[1] - hy, first_outer[2] - hz)
        if not _close(observed_radius, outer_r):
            raise AssertionError(f"{row['id']} outer radius drift")
        if not _close(first_outer[0], float(center["center_x"]) - float(center["length"]) / 2.0):
            raise AssertionError(f"{row['id']} axial span drift")
        per_knuckle.append({"id": row["id"], "owner": row["owner"], "phase_deg": row["phase_deg"], **topo})

    aggregate = _inspect_face_range(mesh, 0, len(mesh["faces"]))
    if len(mesh["vertices"]) != 240 or len(mesh["faces"]) != 480 or aggregate["triangle_components"] != 5:
        raise AssertionError("aggregate candidate topology/size drift")

    receipt = {
        "schema": "axm.object-hinge-bored-knuckle-relative-facet-phase-source-successor-receipt/v0.1",
        "result": RESULT,
        "topology_result": TOPOLOGY_RESULT,
        "asset_id": host["asset_id"],
        "successor_id": contract["successor_id"],
        "predecessor_successor_id": successor002["successor_id"],
        "segments": segments,
        "body_phase_deg": body_phase,
        "lid_phase_deg": lid_phase,
        "relative_lid_minus_body_phase_deg": relative,
        "sector_deg": 360.0 / segments,
        "half_sector_deg": half_sector,
        "knuckle_count": len(per_knuckle),
        "body_owned_knuckles": counts["body"],
        "lid_owned_knuckles": counts["lid"],
        "candidate_vertices": len(mesh["vertices"]),
        "candidate_triangles": len(mesh["faces"]),
        "candidate_triangle_components": aggregate["triangle_components"],
        "knuckle_topology": per_knuckle,
        "knuckle_outer_circumradius_m": outer_r,
        "bore_circumradius_m": bore_r,
        "bore_inradius_m": bore_inradius,
        "source_pin_circumradius_m": pin_r,
        "phase_independent_pin_bore_clearance_m": phase_independent_pin_clearance,
        "minimum_faceted_knuckle_wall_m": minimum_faceted_wall,
        "stop_radius_m": stop_r,
        "phase_independent_stop_bore_capture_overlap_m": stop_bore_overlap,
        "stop_to_outer_knuckle_inradius_containment_m": stop_outer_containment,
        "left_static_axial_gap_m": left_gap,
        "right_static_axial_gap_m": right_gap,
        "legacy_host_source_rewritten": False,
        "predecessor_successor_rewritten": False,
        "automatic_default_replacement": False,
        "automatic_downstream_adoption": False,
        "material_or_renderer_claim": False,
        "truth_boundary": contract["truth_boundary"],
    }
    return receipt, mesh


def _write_obj(path: Path, mesh: dict) -> None:
    lines = ["# Object hinge relative-facet-phase successor; source/default adoption false"]
    for v in mesh["vertices"]:
        lines.append("v %.12f %.12f %.12f" % tuple(v))
    group_names = {g["first_face"]: g["name"] for g in mesh["groups"]}
    for fi, face in enumerate(mesh["faces"]):
        if fi in group_names:
            lines.append("g " + group_names[fi])
        lines.append("f %d %d %d" % tuple(i + 1 for i in face))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--host", required=True, type=Path)
    p.add_argument("--successor002", required=True, type=Path)
    p.add_argument("--owner-contract", required=True, type=Path)
    p.add_argument("--axial-stop-contract", required=True, type=Path)
    p.add_argument("--capture-contract", required=True, type=Path)
    p.add_argument("--bracket-contract", required=True, type=Path)
    p.add_argument("--contract", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args()

    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    receipt, mesh = evaluate(
        load(args.host),
        load(args.successor002),
        load(args.owner_contract),
        load(args.axial_stop_contract),
        load(args.capture_contract),
        load(args.bracket_contract),
        load(args.contract),
        observed_host_sha256=_sha256(args.host),
        observed_successor002_blob_sha1=_git_blob_sha1(args.successor002),
        observed_owner_stack_blob_sha1=_git_blob_sha1(args.owner_contract),
        observed_axial_stop_blob_sha1=_git_blob_sha1(args.axial_stop_contract),
        observed_capture_blob_sha1=_git_blob_sha1(args.capture_contract),
        observed_bracket_blob_sha1=_git_blob_sha1(args.bracket_contract),
    )
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "relative-facet-phase-successor-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _write_obj(args.out / "relative-facet-phase-successor-candidate.obj", mesh)
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
