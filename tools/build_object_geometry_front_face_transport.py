from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any

from tools.build_modular_case import build as build_case, verify as verify_case

GEOMETRY_HEAD = "606d8189a3bf4502141d8038f08d35d421829dde"
HARD_SURFACE_HEAD = "77a4058b305fab7fd04dab94781b9460f089727e"
EXPECTED_SOURCE_SHA256 = "49b1f9ed9865893d6de6f1ec8f069576732df694853fde4e3fcff366de32644a"
EXPECTED_TRIANGLES = 812
EXPECTED_VERTICES = 468
EXPECTED_GROUPS = 31
RECEIPT_SCHEMA = "axm.object-technical-art-front-face-transport/v0.1"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_head(root: Path) -> str:
    return subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()


def git_blob(root: Path, relative_path: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), "hash-object", relative_path], text=True
    ).strip()


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def source_to_uc(point: list[float] | tuple[float, float, float]) -> list[float]:
    x, y, z = (float(value) for value in point)
    return [x, z, y]


def sub(a: list[float] | tuple[float, float, float], b: list[float] | tuple[float, float, float]) -> list[float]:
    return [float(a[i]) - float(b[i]) for i in range(3)]


def normal(a: list[float], b: list[float], c: list[float]) -> list[float]:
    ab = [b[i] - a[i] for i in range(3)]
    ac = [c[i] - a[i] for i in range(3)]
    cross = [
        ab[1] * ac[2] - ab[2] * ac[1],
        ab[2] * ac[0] - ab[0] * ac[2],
        ab[0] * ac[1] - ab[1] * ac[0],
    ]
    length = math.sqrt(sum(value * value for value in cross))
    if length <= 1e-12:
        raise AssertionError("degenerate triangle")
    return [value / length for value in cross]


def dot(a: list[float], b: list[float]) -> float:
    return sum(a[i] * b[i] for i in range(3))


def parse_candidate_obj(path: Path) -> dict[str, Any]:
    vertices: list[list[float]] = []
    faces: list[tuple[int, int, int]] = []
    groups: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if parts[0] == "v":
            if len(parts) != 4:
                raise AssertionError("candidate OBJ vertex must have xyz only")
            vertices.append([float(parts[1]), float(parts[2]), float(parts[3])])
        elif parts[0] == "g":
            if len(parts) != 2:
                raise AssertionError("candidate OBJ group must have one name")
            if current is not None:
                current["face_count"] = len(faces) - int(current["first_face"])
            current = {"name": parts[1], "first_face": len(faces), "face_count": 0}
            groups.append(current)
        elif parts[0] == "f":
            if current is None:
                raise AssertionError("candidate OBJ face appears before a group")
            if len(parts) != 4:
                raise AssertionError("candidate OBJ must contain triangles only")
            tri = []
            for token in parts[1:]:
                if "/" in token:
                    raise AssertionError("candidate OBJ must use position-only indices")
                index = int(token)
                if index <= 0:
                    raise AssertionError("candidate OBJ must use positive one-based indices")
                tri.append(index - 1)
            faces.append(tuple(tri))
        else:
            raise AssertionError(f"unexpected candidate OBJ record: {parts[0]}")
    if current is not None:
        current["face_count"] = len(faces) - int(current["first_face"])
    if len(vertices) != EXPECTED_VERTICES or len(faces) != EXPECTED_TRIANGLES or len(groups) != EXPECTED_GROUPS:
        raise AssertionError(
            f"candidate size drift vertices={len(vertices)} faces={len(faces)} groups={len(groups)}"
        )
    if len({group["name"] for group in groups}) != len(groups):
        raise AssertionError("candidate group names are not unique")
    return {"vertices": vertices, "faces": faces, "groups": groups}


def validate_owner_receipts(
    source_path: Path,
    geometry_receipt_path: Path,
    hard_surface_receipt_path: Path,
    candidate: dict[str, Any],
    source_result: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    source_sha = sha256_file(source_path)
    if source_sha != EXPECTED_SOURCE_SHA256:
        raise AssertionError(f"source SHA-256 drift: {source_sha}")
    geometry = json.loads(geometry_receipt_path.read_text(encoding="utf-8"))
    if geometry.get("result") != "PASS_DERIVED_RIGID_SHELL_OUTWARD_ORIENTATION_CANDIDATE":
        raise AssertionError("Geometry donor receipt is not green")
    if geometry.get("source_sha256") != source_sha:
        raise AssertionError("Geometry donor source identity drift")
    if int(geometry.get("source_vertices", -1)) != EXPECTED_VERTICES:
        raise AssertionError("Geometry donor vertex-count drift")
    if int(geometry.get("source_triangles", -1)) != EXPECTED_TRIANGLES:
        raise AssertionError("Geometry donor triangle-count drift")
    if int(geometry.get("source_rigid_groups", -1)) != EXPECTED_GROUPS:
        raise AssertionError("Geometry donor group-count drift")
    if int(geometry.get("candidate_orientation_conflict_edges", -1)) != 0:
        raise AssertionError("Geometry candidate still has orientation conflicts")
    if int(geometry.get("candidate_positive_signed_volume_groups", -1)) != EXPECTED_GROUPS:
        raise AssertionError("Geometry candidate does not have positive volume for every group")
    if bool(geometry.get("source_adopted")):
        raise AssertionError("Geometry donor unexpectedly claims source adoption")

    hard_surface = json.loads(hard_surface_receipt_path.read_text(encoding="utf-8"))
    if hard_surface.get("result") != "PASS_SOURCE_OWNED_RIGID_SHELL_EXTERIOR_INTENT":
        raise AssertionError("Hard-Surface exterior-intent receipt is not green")
    if hard_surface.get("source_sha256") != source_sha:
        raise AssertionError("Hard-Surface source identity drift")
    compatibility = hard_surface.get("geometry_compatibility_probe", {})
    if compatibility.get("geometry_candidate_exact_head") != GEOMETRY_HEAD:
        raise AssertionError("Hard-Surface comparison does not bind exact Geometry donor")
    if int(compatibility.get("geometry_candidate_faces_matching_source_exterior_intent", -1)) != EXPECTED_TRIANGLES:
        raise AssertionError("Geometry candidate is not exact source exterior intent")
    if int(compatibility.get("geometry_candidate_face_mismatches", -1)) != 0:
        raise AssertionError("Geometry candidate/exterior-intent mismatch")

    built = source_result["mesh"]
    if len(built["vertices"]) != len(candidate["vertices"]):
        raise AssertionError("candidate/source vertex-count mismatch")
    max_position_error = 0.0
    for source_vertex, candidate_vertex in zip(built["vertices"], candidate["vertices"]):
        max_position_error = max(
            max_position_error,
            max(abs(float(source_vertex[i]) - float(candidate_vertex[i])) for i in range(3)),
        )
    if max_position_error > 1e-9:
        raise AssertionError(f"candidate moved source positions: {max_position_error}")
    source_group_names = [group["name"] for group in built["groups"]]
    candidate_group_names = [group["name"] for group in candidate["groups"]]
    if source_group_names != candidate_group_names:
        raise AssertionError("candidate group order diverges from source component groups")
    for source_group, candidate_group in zip(built["groups"], candidate["groups"]):
        if int(source_group["first_face"]) != int(candidate_group["first_face"]) or int(source_group["face_count"]) != int(candidate_group["face_count"]):
            raise AssertionError(f"candidate group range drift: {source_group['name']}")
    return geometry, hard_surface


def validate_ownership(source_path: Path, ownership: dict[str, Any], source_result: dict[str, Any]) -> tuple[list[str], list[str]]:
    if ownership.get("schema") != "axm.object-front-latch-ownership/v0.1":
        raise AssertionError("front-latch ownership schema drift")
    if ownership.get("host_source_sha256") != sha256_file(source_path):
        raise AssertionError("front-latch ownership source identity drift")
    component_names = {component["name"] for component in source_result["components"]}
    keepers: list[str] = []
    levers: list[str] = []
    for station in ownership.get("stations", []):
        keeper = station.get("keeper_component")
        lever = station.get("lever_component")
        if station.get("keeper_owner_component") != "lid_shell":
            raise AssertionError("keeper ownership drift")
        if station.get("lever_owner_component") != "front_service_panel":
            raise AssertionError("lever ownership drift")
        if keeper not in component_names or lever not in component_names:
            raise AssertionError("ownership references missing component")
        keepers.append(str(keeper))
        levers.append(str(lever))
    if len(keepers) != 2 or len(levers) != 2:
        raise AssertionError("bounded Object proof expects two keeper/lever stations")
    return sorted(keepers), sorted(levers)


def make_surface(
    candidate: dict[str, Any],
    source_result: dict[str, Any],
    *,
    pivot_source: list[float],
    lid_local_names: set[str],
    parity_correct: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    primitives: list[dict[str, Any]] = []
    min_alignment = 1.0
    max_alignment = -1.0
    max_static_error = 0.0
    corrected_faces = 0
    for group in candidate["groups"]:
        name = str(group["name"])
        start_face = int(group["first_face"])
        end_face = start_face + int(group["face_count"])
        local_origin = pivot_source if name in lid_local_names else None
        positions: list[list[float]] = []
        normals: list[list[float]] = []
        indices: list[int] = []
        for face in candidate["faces"][start_face:end_face]:
            original = [candidate["vertices"][index] for index in face]
            local = [sub(point, local_origin) if local_origin is not None else list(point) for point in original]
            order = (0, 2, 1) if parity_correct else (0, 1, 2)
            tri = [source_to_uc(local[index]) for index in order]
            observed_normal = normal(*tri)
            expected_normal = source_to_uc(normal(*[list(point) for point in original]))
            alignment = dot(observed_normal, expected_normal)
            min_alignment = min(min_alignment, alignment)
            max_alignment = max(max_alignment, alignment)
            if parity_correct:
                corrected_faces += 1
            expected_world = [source_to_uc(original[index]) for index in order]
            reconstructed = tri
            if local_origin is not None:
                origin_uc = source_to_uc(local_origin)
                reconstructed = [[point[i] + origin_uc[i] for i in range(3)] for point in tri]
            for observed, expected in zip(reconstructed, expected_world):
                max_static_error = max(
                    max_static_error,
                    max(abs(observed[i] - expected[i]) for i in range(3)),
                )
            base = len(positions)
            positions.extend(tri)
            normals.extend([observed_normal, observed_normal, observed_normal])
            indices.extend([base, base + 1, base + 2])
        primitives.append(
            {
                "id": name,
                "positions": positions,
                "normals": normals,
                "indices": indices,
                "material": {"color": "#BFC7D0FF", "metallic": 0.0, "roughness": 1.0},
            }
        )
    return {
        "schema": "axm.surface-3d/v0.1",
        "name": "modular-equipment-case-001-geometry33-front-face-transport",
        "primitives": primitives,
    }, {
        "parity_corrected": parity_correct,
        "source_to_uc_position_map": "[x,y,z] -> [x,z,y]",
        "source_to_uc_position_map_determinant": -1,
        "winding_reversal_faces": corrected_faces,
        "minimum_face_normal_alignment_to_mapped_source_exterior": min_alignment,
        "maximum_face_normal_alignment_to_mapped_source_exterior": max_alignment,
        "closed_static_localization_max_error_m": max_static_error,
    }


def export_variant(
    surface: dict[str, Any],
    manifest: dict[str, Any],
    out_path: Path,
    uc_root: Path,
) -> dict[str, Any]:
    sys.path.insert(0, str(uc_root / "src"))
    from axm_uc.procedural_3d import build_glb, verify_glb  # noqa: E402
    from axm_uc.rigid_scene_graph import rebind_rigid_scene_graph, verify_rigid_scene_graph  # noqa: E402

    baseline = build_glb(surface)
    rebound = rebind_rigid_scene_graph(
        baseline["body"], manifest, expected_spec_digest=baseline["specification_sha256"]
    )
    flat = verify_glb(baseline["body"], expected_spec_digest=baseline["specification_sha256"])
    rebound_verify = verify_glb(rebound["body"], expected_spec_digest=baseline["specification_sha256"])
    graph = verify_rigid_scene_graph(
        rebound["body"], expected_manifest_digest=rebound["manifest_sha256"]
    )
    if int(flat["triangles"]) != EXPECTED_TRIANGLES or int(rebound_verify["triangles"]) != EXPECTED_TRIANGLES:
        raise AssertionError("UC triangle-count drift")
    if rebound["receipt"]["binary_geometry_payload_identical"] is not True:
        raise AssertionError("UC rigid-scene rebind changed binary geometry")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(rebound["body"])
    return {
        "glb_sha256": hashlib.sha256(rebound["body"]).hexdigest(),
        "glb_bytes": len(rebound["body"]),
        "surface_digest": canonical_digest(surface),
        "surface_specification_sha256": baseline["specification_sha256"],
        "manifest_sha256": rebound["manifest_sha256"],
        "flat_verification": flat,
        "rebound_verification": rebound_verify,
        "graph_verification": graph,
        "uc_rebind_receipt": rebound["receipt"],
    }


def build_evidence(
    source_path: Path,
    ownership_path: Path,
    geometry_candidate_obj: Path,
    geometry_receipt_path: Path,
    hard_surface_receipt_path: Path,
    uc_root: Path,
    expected_uc_commit: str,
    out_dir: Path,
) -> dict[str, Any]:
    if git_head(uc_root) != expected_uc_commit:
        raise AssertionError("current UC checkout identity drift")
    if git_head(Path.cwd()) == GEOMETRY_HEAD or git_head(Path.cwd()) == HARD_SURFACE_HEAD:
        raise AssertionError("Technical Art proof must run from its own receiving lane")

    source = json.loads(source_path.read_text(encoding="utf-8"))
    ownership = json.loads(ownership_path.read_text(encoding="utf-8"))
    source_result = build_case(source)
    structural = verify_case(source, source_result)
    if structural.get("result") != "PASS_STRUCTURAL_INTERFACE_PROOF":
        raise AssertionError("Object structural prerequisite is not green")

    candidate = parse_candidate_obj(geometry_candidate_obj)
    geometry_receipt, hard_surface_receipt = validate_owner_receipts(
        source_path, geometry_receipt_path, hard_surface_receipt_path, candidate, source_result
    )
    keepers, levers = validate_ownership(source_path, ownership, source_result)

    hinge_lid_groups = sorted(
        f"hinge_lid_{knuckle['id']}"
        for knuckle in source["hinge"]["knuckles"]
        if knuckle.get("owner") == "lid"
    )
    lid_children = sorted(keepers + hinge_lid_groups)
    lid_local_names = {"lid_shell", *lid_children}
    pivot_source = [float(value) for value in source_result["hinge_axis"]["origin_m"]]
    pivot_uc = source_to_uc(pivot_source)

    manifest = {
        "schema": "axm.rigid-scene-graph/v0.1",
        "nodes": [
            {"name": "lid_shell", "parent": None, "translation": pivot_uc},
            *[
                {"name": name, "parent": "lid_shell", "translation": [0.0, 0.0, 0.0]}
                for name in lid_children
            ],
        ],
    }

    corrected_surface, corrected_metrics = make_surface(
        candidate,
        source_result,
        pivot_source=pivot_source,
        lid_local_names=lid_local_names,
        parity_correct=True,
    )
    unadapted_surface, unadapted_metrics = make_surface(
        candidate,
        source_result,
        pivot_source=pivot_source,
        lid_local_names=lid_local_names,
        parity_correct=False,
    )

    if corrected_metrics["winding_reversal_faces"] != EXPECTED_TRIANGLES:
        raise AssertionError("parity-correct path did not reverse every outward candidate triangle")
    if corrected_metrics["minimum_face_normal_alignment_to_mapped_source_exterior"] < 1.0 - 1e-12:
        raise AssertionError("parity-correct transport does not preserve mapped source exterior orientation")
    if unadapted_metrics["maximum_face_normal_alignment_to_mapped_source_exterior"] > -1.0 + 1e-12:
        raise AssertionError("negative control did not invert mapped source exterior orientation")
    if corrected_metrics["closed_static_localization_max_error_m"] > 1e-12:
        raise AssertionError("corrected localization drift")
    if unadapted_metrics["closed_static_localization_max_error_m"] > 1e-12:
        raise AssertionError("negative localization drift")

    out_dir.mkdir(parents=True, exist_ok=True)
    corrected_path = out_dir / "geometry33-parity-corrected-rebound.glb"
    unadapted_path = out_dir / "geometry33-unadapted-rebound.glb"
    corrected_export = export_variant(corrected_surface, manifest, corrected_path, uc_root)
    unadapted_export = export_variant(unadapted_surface, manifest, unadapted_path, uc_root)

    for keeper in keepers:
        if corrected_export["graph_verification"]["parent_by_child"].get(keeper) != "lid_shell":
            raise AssertionError(f"keeper parentage drift in corrected transport: {keeper}")
        if unadapted_export["graph_verification"]["parent_by_child"].get(keeper) != "lid_shell":
            raise AssertionError(f"keeper parentage drift in unadapted control: {keeper}")
    for lever in levers:
        if lever in corrected_export["graph_verification"]["parent_by_child"]:
            raise AssertionError(f"lever unexpectedly parented in corrected transport: {lever}")

    receipt = {
        "schema": RECEIPT_SCHEMA,
        "result": "PASS_OBJECT_GEOMETRY33_SOURCE_EXTERIOR_TO_CURRENT_UC_GLTF_PARITY_BRIDGE_READY",
        "technical_art_repository_head": git_head(Path.cwd()),
        "geometry_repository": "mike-axiom-mir/axm-object-design",
        "geometry_pr": 33,
        "geometry_exact_head": GEOMETRY_HEAD,
        "hard_surface_pr": 34,
        "hard_surface_exact_head": HARD_SURFACE_HEAD,
        "source_sha256": sha256_file(source_path),
        "geometry_candidate_obj_sha256": sha256_file(geometry_candidate_obj),
        "geometry_receipt_sha256": sha256_file(geometry_receipt_path),
        "hard_surface_receipt_sha256": sha256_file(hard_surface_receipt_path),
        "geometry_owner_result": geometry_receipt["result"],
        "hard_surface_owner_result": hard_surface_receipt["result"],
        "hard_surface_geometry_faces_matching_exterior_intent": hard_surface_receipt["geometry_compatibility_probe"][
            "geometry_candidate_faces_matching_source_exterior_intent"
        ],
        "hard_surface_geometry_face_mismatches": hard_surface_receipt["geometry_compatibility_probe"][
            "geometry_candidate_face_mismatches"
        ],
        "source_vertices": EXPECTED_VERTICES,
        "source_triangles": EXPECTED_TRIANGLES,
        "source_rigid_groups": EXPECTED_GROUPS,
        "source_owned_keeper_children": keepers,
        "source_owned_fixed_levers": levers,
        "hinge_pivot_source_m": pivot_source,
        "hinge_pivot_uc_m": pivot_uc,
        "uc_repository": "mike-axiom-mir/axm-universal-creation",
        "uc_exact_head": expected_uc_commit,
        "uc_procedural_3d_git_blob": git_blob(uc_root, "src/axm_uc/procedural_3d.py"),
        "uc_rigid_scene_graph_git_blob": git_blob(uc_root, "src/axm_uc/rigid_scene_graph.py"),
        "corrected_transport": {**corrected_metrics, **corrected_export},
        "unadapted_negative_control": {**unadapted_metrics, **unadapted_export},
        "target_host_observed": False,
        "truth_boundary": {
            "hard_surface_owns_exterior_intent": True,
            "geometry_owns_orientation_candidate": True,
            "technical_art_owns_transport_parity_adaptation": True,
            "uc_inferred_object_winding_policy": False,
            "uc_modified": False,
            "materials_or_visual_qa_acceptance": False,
            "runtime_or_target_device_acceptance": False,
            "source_geometry_adopted": False,
            "canon_or_production_readiness": False,
        },
    }
    (out_dir / "front-face-transport-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out_dir / "transport-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="assets/modular-equipment-case-001/source.json", type=Path)
    parser.add_argument("--ownership", default="assets/modular-equipment-case-001/front-latch-ownership-001.json", type=Path)
    parser.add_argument("--geometry-candidate-obj", required=True, type=Path)
    parser.add_argument("--geometry-receipt", required=True, type=Path)
    parser.add_argument("--hard-surface-receipt", required=True, type=Path)
    parser.add_argument("--uc-root", required=True, type=Path)
    parser.add_argument("--expected-uc-commit", required=True)
    parser.add_argument("--out", default="rigid-proof/front-face-generated", type=Path)
    args = parser.parse_args()
    receipt = build_evidence(
        args.source.resolve(),
        args.ownership.resolve(),
        args.geometry_candidate_obj.resolve(),
        args.geometry_receipt.resolve(),
        args.hard_surface_receipt.resolve(),
        args.uc_root.resolve(),
        args.expected_uc_commit,
        args.out.resolve(),
    )
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
