from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from tools.build_modular_case import build

CONTRACT_SCHEMA = "axm.object-rigid-shell-exterior-intent/v0.1"
RECEIPT_SCHEMA = "axm.object-rigid-shell-exterior-intent-receipt/v0.1"
EXPECTED_ASSET_ID = "modular-equipment-case-001"
EXPECTED_SOURCE_SHA256 = "49b1f9ed9865893d6de6f1ec8f069576732df694853fde4e3fcff366de32644a"
EXPECTED_BUILDER_BLOB = "55c03ceb38e337b2bdc31bb66795d25f5bfbac10"
EXPECTED_GEOMETRY_HEAD = "606d8189a3bf4502141d8038f08d35d421829dde"
EXPECTED_COMPONENTS = 31
EXPECTED_VERTICES = 468
EXPECTED_TRIANGLES = 812
EXPECTED_STORED_ALIGNED = 304
EXPECTED_STORED_OPPOSED = 508
EPS_AREA2 = 1e-18
EPS_SIDE = 1e-15


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def git_blob_sha1(path: Path) -> str:
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode("utf-8")
    return hashlib.sha1(header + data).hexdigest()


def sub(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def cross(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def dot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def magnitude_sq(v: tuple[float, float, float]) -> float:
    return dot(v, v)


def canonical_face_for_exterior(
    vertices: list[tuple[float, float, float]],
    face: tuple[int, int, int],
    interior_reference: list[float] | tuple[float, float, float],
) -> tuple[tuple[int, int, int], float]:
    a, b, c = (vertices[index] for index in face)
    normal = cross(sub(b, a), sub(c, a))
    if magnitude_sq(normal) <= EPS_AREA2:
        raise AssertionError("degenerate source triangle in rigid-shell exterior-intent scope")
    centroid = (
        (a[0] + b[0] + c[0]) / 3.0,
        (a[1] + b[1] + c[1]) / 3.0,
        (a[2] + b[2] + c[2]) / 3.0,
    )
    radial = (
        centroid[0] - float(interior_reference[0]),
        centroid[1] - float(interior_reference[1]),
        centroid[2] - float(interior_reference[2]),
    )
    side = dot(normal, radial)
    if abs(side) <= EPS_SIDE:
        raise AssertionError("ambiguous triangle plane relative to source-owned primitive interior reference")
    if side > 0.0:
        return face, side
    return (face[0], face[2], face[1]), side


def validate_contract(contract: dict[str, Any], source_sha256: str, builder_blob: str) -> None:
    if contract.get("schema") != CONTRACT_SCHEMA:
        raise AssertionError("unexpected rigid-shell exterior-intent schema")
    if contract.get("asset_id") != EXPECTED_ASSET_ID:
        raise AssertionError("unexpected rigid-shell exterior-intent asset")
    if source_sha256 != EXPECTED_SOURCE_SHA256 or contract.get("source_sha256") != source_sha256:
        raise AssertionError("exact Object source SHA-256 drift")
    if builder_blob != EXPECTED_BUILDER_BLOB:
        raise AssertionError("exact Object source builder Git blob drift")
    if contract.get("source_builder", {}).get("git_blob") != builder_blob:
        raise AssertionError("contract/source-builder identity mismatch")

    scope = contract.get("component_scope", {})
    if scope.get("expected_components") != EXPECTED_COMPONENTS:
        raise AssertionError("component-count contract drift")
    if scope.get("expected_vertices") != EXPECTED_VERTICES:
        raise AssertionError("vertex-count contract drift")
    if scope.get("expected_triangles") != EXPECTED_TRIANGLES:
        raise AssertionError("triangle-count contract drift")

    reference = contract.get("interior_reference", {})
    if reference.get("kind") != "deterministic_primitive_center":
        raise AssertionError("source exterior intent requires the pinned primitive-center reference")

    rule = contract.get("exterior_side_rule", {})
    if rule.get("stored_triangle_winding_authoritative") is not False:
        raise AssertionError("stored triangle winding may not self-authorize source exterior intent")
    if rule.get("renderer_front_face_authoritative") is not False:
        raise AssertionError("source exterior intent may not choose target renderer front-face policy")
    if rule.get("automatic_source_winding_rewrite") is not False:
        raise AssertionError("source exterior-intent contract may not silently rewrite winding")

    probe = contract.get("geometry_compatibility_probe", {})
    if probe.get("exact_head") != EXPECTED_GEOMETRY_HEAD:
        raise AssertionError("Geometry compatibility donor identity drift")
    if probe.get("authority") != "evidence_only_no_source_adoption":
        raise AssertionError("Geometry compatibility probe may not authorize source adoption")

    authority = contract.get("authority", {})
    required_authority_keys = (
        "hard_surface",
        "geometry_topology",
        "technical_art",
        "materials_art_qa",
        "runtime",
        "physics_gameplay",
    )
    if any(not authority.get(key) for key in required_authority_keys):
        raise AssertionError("authority boundary is incomplete")


def parse_obj_faces(path: Path) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]], list[str]]:
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int]] = []
    groups: list[str] = []
    current_group = ""
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("v "):
            parts = line.split()
            if len(parts) != 4:
                raise AssertionError("unexpected OBJ vertex record")
            vertices.append((float(parts[1]), float(parts[2]), float(parts[3])))
        elif line.startswith("g "):
            current_group = line[2:].strip()
        elif line.startswith("f "):
            parts = line.split()
            if len(parts) != 4:
                raise AssertionError("candidate OBJ must remain triangulated")
            indices: list[int] = []
            for token in parts[1:]:
                head = token.split("/", 1)[0]
                index = int(head)
                if index <= 0:
                    raise AssertionError("candidate OBJ must use positive absolute indices")
                indices.append(index - 1)
            faces.append(tuple(indices))
            groups.append(current_group)
    return vertices, faces, groups


def analyze_source_intent(
    source: dict[str, Any],
    contract: dict[str, Any],
    result: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[tuple[int, int, int]], list[str]]:
    if source.get("asset_id") != EXPECTED_ASSET_ID:
        raise AssertionError("unexpected Object source asset")
    result = build(source) if result is None else result
    mesh = result["mesh"]
    vertices = mesh["vertices"]
    faces = mesh["faces"]
    groups = mesh["groups"]
    components = result["components"]

    if len(vertices) != EXPECTED_VERTICES:
        raise AssertionError(f"source vertex-count drift: {len(vertices)}")
    if len(faces) != EXPECTED_TRIANGLES:
        raise AssertionError(f"source triangle-count drift: {len(faces)}")
    if len(groups) != EXPECTED_COMPONENTS or len(components) != EXPECTED_COMPONENTS:
        raise AssertionError("source rigid-component-count drift")
    if [group["name"] for group in groups] != [component["name"] for component in components]:
        raise AssertionError("source group/component identity drift")

    cursor = 0
    stored_aligned = 0
    stored_opposed = 0
    canonical_faces: list[tuple[int, int, int]] = list(faces)
    face_groups: list[str] = [""] * len(faces)
    component_receipts: list[dict[str, Any]] = []
    canonical_digest_lines: list[str] = []

    for component, group in zip(components, groups):
        start = group["first_face"]
        count = group["face_count"]
        end = start + count
        if start != cursor or count <= 0 or end > len(faces):
            raise AssertionError("rigid component face ranges must be contiguous and non-empty")
        center = component.get("center_m")
        if not isinstance(center, list) or len(center) != 3:
            raise AssertionError("every rigid primitive requires an exact source center_m")
        component_aligned = 0
        component_opposed = 0
        min_abs_side = None
        for face_index in range(start, end):
            face = faces[face_index]
            canonical, raw_side = canonical_face_for_exterior(vertices, face, center)
            canonical_faces[face_index] = canonical
            face_groups[face_index] = group["name"]
            abs_side = abs(raw_side)
            min_abs_side = abs_side if min_abs_side is None else min(min_abs_side, abs_side)
            if canonical == face:
                stored_aligned += 1
                component_aligned += 1
            else:
                stored_opposed += 1
                component_opposed += 1
            canonical_digest_lines.append(
                f"{group['name']}|{face_index}|{canonical[0]},{canonical[1]},{canonical[2]}"
            )
        component_receipts.append(
            {
                "name": group["name"],
                "kind": component["kind"],
                "role": component["role"],
                "interior_reference_m": [float(v) for v in center],
                "first_face": start,
                "face_count": count,
                "stored_faces_already_exterior_aligned": component_aligned,
                "stored_faces_opposed_to_exterior_intent": component_opposed,
                "minimum_absolute_plane_side_measure": min_abs_side,
            }
        )
        cursor = end

    if cursor != len(faces):
        raise AssertionError("rigid component groups do not cover all source triangles")

    observation = contract.get("exact_source_observation", {})
    if stored_aligned != observation.get("stored_faces_already_exterior_aligned"):
        raise AssertionError("stored exterior-aligned face observation drift")
    if stored_opposed != observation.get("stored_faces_opposed_to_exterior_intent"):
        raise AssertionError("stored opposed face observation drift")
    if observation.get("ambiguous_face_planes") != 0:
        raise AssertionError("contract must remain fail-closed on ambiguous face planes")
    if stored_aligned != EXPECTED_STORED_ALIGNED or stored_opposed != EXPECTED_STORED_OPPOSED:
        raise AssertionError("exact source exterior-intent observation drift")

    canonical_digest = hashlib.sha256(
        ("\n".join(canonical_digest_lines) + "\n").encode("utf-8")
    ).hexdigest()
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "asset_id": EXPECTED_ASSET_ID,
        "result": "PASS_SOURCE_OWNED_RIGID_SHELL_EXTERIOR_INTENT",
        "pattern": "SOURCE_OWNED_MANUFACTURED_EXTERIOR_INTENT_PRECEDES_TRIANGLE_WINDING_AND_RECEIVER_FRONT_FACE_POLICY",
        "source_vertices": len(vertices),
        "source_triangles": len(faces),
        "source_rigid_components": len(components),
        "stored_faces_already_exterior_aligned": stored_aligned,
        "stored_faces_opposed_to_exterior_intent": stored_opposed,
        "ambiguous_face_planes": 0,
        "canonical_exterior_face_order_digest": canonical_digest,
        "source_triangle_winding_rewritten": False,
        "geometry_candidate_adopted": False,
        "renderer_front_face_selected": False,
        "technical_art_transport_adopted": False,
        "runtime_adopted": False,
        "physics_gameplay_adopted": False,
        "components": component_receipts,
        "limitations": [
            "source exterior/interior side semantics only; stored source triangle winding remains historical representation",
            "convex primitive-center half-space rule is exact only for this deterministic Object source construction",
            "no automatic Geometry candidate adoption or source winding rewrite",
            "no target renderer front-face, culling, normals, tangents, UV, material or shading acceptance",
            "no Technical Art transport, Runtime, physics, gameplay, CANON or production-readiness claim",
        ],
    }
    return receipt, canonical_faces, face_groups


def compare_geometry_candidate(
    source_result: dict[str, Any],
    canonical_faces: list[tuple[int, int, int]],
    face_groups: list[str],
    candidate_obj: Path,
) -> dict[str, Any]:
    candidate_vertices, candidate_faces, candidate_groups = parse_obj_faces(candidate_obj)
    source_vertices = source_result["mesh"]["vertices"]
    if len(candidate_vertices) != len(source_vertices):
        raise AssertionError("Geometry candidate vertex-count drift")
    if len(candidate_faces) != len(canonical_faces):
        raise AssertionError("Geometry candidate triangle-count drift")
    for index, (candidate_vertex, source_vertex) in enumerate(zip(candidate_vertices, source_vertices)):
        if any(abs(candidate_vertex[axis] - float(source_vertex[axis])) > 1e-9 for axis in range(3)):
            raise AssertionError(f"Geometry candidate moved source vertex {index}")
    mismatches = [
        index
        for index, (candidate_face, intended_face) in enumerate(zip(candidate_faces, canonical_faces))
        if candidate_face != intended_face
    ]
    if mismatches:
        raise AssertionError(
            f"Geometry candidate disagrees with source-owned exterior intent at {len(mismatches)} faces; "
            f"first={mismatches[0]}"
        )
    if candidate_groups != face_groups:
        raise AssertionError("Geometry candidate group sequence drift")
    return {
        "geometry_candidate_exact_head": EXPECTED_GEOMETRY_HEAD,
        "geometry_candidate_faces_matching_source_exterior_intent": len(canonical_faces),
        "geometry_candidate_face_mismatches": 0,
        "geometry_candidate_positions_matching_source": len(source_vertices),
        "geometry_candidate_compatibility": "PASS_EXACT_FACE_ORDER_COMPATIBILITY_EVIDENCE_ONLY",
        "geometry_candidate_adopted": False,
    }


def build_evidence(
    source_path: Path,
    contract_path: Path,
    builder_path: Path,
    geometry_candidate_obj: Path | None = None,
    geometry_head: str | None = None,
) -> dict[str, Any]:
    source_sha256 = sha256_file(source_path)
    builder_blob = git_blob_sha1(builder_path)
    source = json.loads(source_path.read_text(encoding="utf-8"))
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    validate_contract(contract, source_sha256, builder_blob)
    result = build(source)
    receipt, canonical_faces, face_groups = analyze_source_intent(source, contract, result)
    receipt["source_sha256"] = source_sha256
    receipt["source_builder_git_blob"] = builder_blob
    receipt["source_owner"] = contract["source_owner"]
    receipt["truth_boundary"] = contract["truth_boundary"]

    if geometry_candidate_obj is not None:
        if geometry_head != EXPECTED_GEOMETRY_HEAD:
            raise AssertionError("Geometry comparison must name the exact pinned donor head")
        receipt["geometry_compatibility_probe"] = compare_geometry_candidate(
            result, canonical_faces, face_groups, geometry_candidate_obj
        )
    else:
        receipt["geometry_compatibility_probe"] = {
            "geometry_candidate_exact_head": EXPECTED_GEOMETRY_HEAD,
            "geometry_candidate_compatibility": "NOT_EVALUATED_IN_THIS_INVOCATION",
            "geometry_candidate_adopted": False,
        }
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        default="assets/modular-equipment-case-001/source.json",
        type=Path,
    )
    parser.add_argument(
        "--contract",
        default="assets/modular-equipment-case-001/rigid-shell-exterior-intent-001.json",
        type=Path,
    )
    parser.add_argument("--builder", default="tools/build_modular_case.py", type=Path)
    parser.add_argument("--geometry-candidate-obj", type=Path)
    parser.add_argument("--geometry-head")
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()

    receipt = build_evidence(
        args.source,
        args.contract,
        args.builder,
        geometry_candidate_obj=args.geometry_candidate_obj,
        geometry_head=args.geometry_head,
    )
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
