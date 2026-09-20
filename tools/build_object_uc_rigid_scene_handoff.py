from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any

from build_modular_case import build as build_case, verify as verify_case


HANDOFF_SCHEMA = "axm.object-uc-rigid-scene-handoff/v0.1"
UC_COMMIT = "6dc465987e01362264f88b7cef4213609ae50763"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def git_head(root: Path) -> str:
    return subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()


def _source_to_uc(point: list[float] | tuple[float, float, float]) -> list[float]:
    x, y, z = [float(value) for value in point]
    return [x, z, y]


def _sub(a: list[float] | tuple[float, float, float], b: list[float] | tuple[float, float, float]) -> list[float]:
    return [float(a[i]) - float(b[i]) for i in range(3)]


def _face_normal(a: list[float], b: list[float], c: list[float]) -> list[float]:
    u = [b[i] - a[i] for i in range(3)]
    v = [c[i] - a[i] for i in range(3)]
    cross = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
    length = math.sqrt(sum(value * value for value in cross))
    if length <= 1e-12:
        raise AssertionError("degenerate source triangle")
    return [value / length for value in cross]


def _group_faces(mesh: dict[str, Any], group: dict[str, Any]) -> list[tuple[int, int, int]]:
    first = int(group["first_face"])
    count = int(group["face_count"])
    faces = mesh["faces"][first:first + count]
    if len(faces) != count:
        raise AssertionError(f"group face range exceeds mesh: {group['name']}")
    return [tuple(int(index) for index in face) for face in faces]


def make_component_surface_group(
    mesh: dict[str, Any],
    group: dict[str, Any],
    *,
    local_origin_source: list[float] | None,
) -> tuple[dict[str, Any], float]:
    positions: list[list[float]] = []
    normals: list[list[float]] = []
    indices: list[int] = []
    max_static_error = 0.0
    for face in _group_faces(mesh, group):
        if any(index < 0 or index >= len(mesh["vertices"]) for index in face):
            raise AssertionError(f"group face index out of range: {group['name']}")
        original_source = [mesh["vertices"][index] for index in face]
        local_source = [
            _sub(point, local_origin_source) if local_origin_source is not None else [float(value) for value in point]
            for point in original_source
        ]
        # +Y forward -> +Z forward swaps Y/Z and flips handedness, so reverse triangle winding.
        tri = [_source_to_uc(local_source[index]) for index in (0, 2, 1)]
        expected_world = [_source_to_uc(original_source[index]) for index in (0, 2, 1)]
        if local_origin_source is not None:
            origin_uc = _source_to_uc(local_origin_source)
            reconstructed = [[point[i] + origin_uc[i] for i in range(3)] for point in tri]
        else:
            reconstructed = tri
        for observed, expected in zip(reconstructed, expected_world):
            max_static_error = max(max_static_error, max(abs(observed[i] - expected[i]) for i in range(3)))
        normal = _face_normal(*tri)
        start = len(positions)
        positions.extend(tri)
        normals.extend([normal, normal, normal])
        indices.extend([start, start + 1, start + 2])
    return {
        "id": group["name"],
        "positions": positions,
        "normals": normals,
        "indices": indices,
        "material": {"color": "#717981FF", "metallic": 0.18, "roughness": 0.66},
    }, max_static_error


def _validate_ownership(source_path: Path, ownership: dict[str, Any], result: dict[str, Any]) -> tuple[list[str], list[str]]:
    if ownership.get("schema") != "axm.object-front-latch-ownership/v0.1":
        raise AssertionError("front latch ownership donor schema mismatch")
    observed_source_sha = sha256_file(source_path)
    if ownership.get("host_source_sha256") != observed_source_sha:
        raise AssertionError("front latch ownership donor is not bound to this exact source")
    component_names = {component["name"] for component in result["components"]}
    keepers: list[str] = []
    levers: list[str] = []
    for station in ownership.get("stations", []):
        keeper = station.get("keeper_component")
        lever = station.get("lever_component")
        if station.get("keeper_owner_component") != "lid_shell":
            raise AssertionError("keeper donor ownership is not lid_shell")
        if station.get("lever_owner_component") != "front_service_panel":
            raise AssertionError("lever donor ownership is not front_service_panel")
        if keeper not in component_names or lever not in component_names:
            raise AssertionError("ownership donor references a component absent from exact source build")
        keepers.append(keeper)
        levers.append(lever)
    if len(keepers) != 2 or len(levers) != 2:
        raise AssertionError("bounded proof expects exactly two keeper/lever stations")
    return sorted(keepers), sorted(levers)


def build_handoff(source_path: Path, ownership_path: Path, uc_root: Path, expected_uc_commit: str, out_dir: Path) -> dict[str, Any]:
    observed_uc_commit = git_head(uc_root)
    if observed_uc_commit != expected_uc_commit:
        raise AssertionError(f"UC head mismatch expected={expected_uc_commit} observed={observed_uc_commit}")

    source = json.loads(source_path.read_text(encoding="utf-8"))
    ownership = json.loads(ownership_path.read_text(encoding="utf-8"))
    result = build_case(source)
    structural = verify_case(source, result)
    if structural.get("result") != "PASS_STRUCTURAL_INTERFACE_PROOF":
        raise AssertionError("exact Object structural prerequisite is not green")
    keepers, levers = _validate_ownership(source_path, ownership, result)

    group_names = [group["name"] for group in result["mesh"]["groups"]]
    if len(group_names) != len(set(group_names)):
        raise AssertionError("source mesh group names are not unique")
    if set(group_names) != {component["name"] for component in result["components"]}:
        raise AssertionError("source component and mesh-group identities diverge")

    hinge_lid_groups = sorted(
        f"hinge_lid_{knuckle['id']}" for knuckle in source["hinge"]["knuckles"] if knuckle.get("owner") == "lid"
    )
    lid_owned_children = sorted(keepers + hinge_lid_groups)
    if any(name not in group_names for name in ["lid_shell", *lid_owned_children, *levers]):
        raise AssertionError("required rigid component group missing from exact source mesh")

    pivot_source = [float(value) for value in result["hinge_axis"]["origin_m"]]
    pivot_uc = _source_to_uc(pivot_source)
    surface_groups: list[dict[str, Any]] = []
    max_closed_static_error = 0.0
    for group in result["mesh"]["groups"]:
        name = group["name"]
        localized = name == "lid_shell" or name in lid_owned_children
        surface_group, static_error = make_component_surface_group(
            result["mesh"], group, local_origin_source=pivot_source if localized else None
        )
        surface_groups.append(surface_group)
        max_closed_static_error = max(max_closed_static_error, static_error)
    if max_closed_static_error > 1e-12:
        raise AssertionError(f"closed static localization drift: {max_closed_static_error}")

    surface = {
        "schema": "axm.surface-3d/v0.1",
        "name": "modular-equipment-case-001-rigid-component-proof",
        "primitives": surface_groups,
    }
    manifest = {
        "schema": "axm.rigid-scene-graph/v0.1",
        "nodes": [
            {"name": "lid_shell", "parent": None, "translation": pivot_uc},
            *[
                {"name": name, "parent": "lid_shell", "translation": [0.0, 0.0, 0.0]}
                for name in lid_owned_children
            ],
        ],
    }

    sys.path.insert(0, str(uc_root / "src"))
    from axm_uc.procedural_3d import build_glb, verify_glb  # noqa: E402
    from axm_uc.rigid_scene_graph import rebind_rigid_scene_graph, verify_rigid_scene_graph  # noqa: E402

    baseline = build_glb(surface)
    rebound = rebind_rigid_scene_graph(
        baseline["body"], manifest, expected_spec_digest=baseline["specification_sha256"]
    )
    flat_verification = verify_glb(baseline["body"], expected_spec_digest=baseline["specification_sha256"])
    rebound_verification = verify_glb(rebound["body"], expected_spec_digest=baseline["specification_sha256"])
    graph_verification = verify_rigid_scene_graph(
        rebound["body"], expected_manifest_digest=rebound["manifest_sha256"]
    )
    expected_triangles = len(result["mesh"]["faces"])
    if flat_verification["triangles"] != expected_triangles or rebound_verification["triangles"] != expected_triangles:
        raise AssertionError("triangle count drift across UC flat/rebound path")
    for keeper in keepers:
        if graph_verification["parent_by_child"].get(keeper) != "lid_shell":
            raise AssertionError(f"keeper did not survive as a lid child: {keeper}")
    for lever in levers:
        if lever in graph_verification["parent_by_child"]:
            raise AssertionError(f"body-owned lever was unexpectedly parented: {lever}")

    out_dir.mkdir(parents=True, exist_ok=True)
    surface_path = out_dir / "object-rigid-components.surface.json"
    manifest_path = out_dir / "object-rigid-scene-graph.json"
    flat_path = out_dir / "object-rigid-components-flat.glb"
    rebound_path = out_dir / "object-rigid-components-rebound.glb"
    surface_path.write_text(json.dumps(surface, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest_path.write_text(json.dumps(rebound["manifest"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    flat_path.write_bytes(baseline["body"])
    rebound_path.write_bytes(rebound["body"])

    receipt = {
        "schema": HANDOFF_SCHEMA,
        "result": "PASS_OBJECT_SOURCE_OWNED_RIGID_PARTS_THROUGH_UC_SCENE_GRAPH",
        "source_repository": "mike-axiom-mir/axm-object-design",
        "source_repository_head": git_head(Path.cwd()),
        "source_sha256": sha256_file(source_path),
        "ownership_sha256": sha256_file(ownership_path),
        "structural_prerequisite": structural.get("result"),
        "uc_repository": "mike-axiom-mir/axm-universal-creation",
        "expected_uc_commit": expected_uc_commit,
        "observed_uc_commit": observed_uc_commit,
        "uc_surface_schema": surface["schema"],
        "uc_surface_digest": canonical_digest(surface),
        "uc_surface_specification_sha256": baseline["specification_sha256"],
        "flat_glb_sha256": hashlib.sha256(baseline["body"]).hexdigest(),
        "rebound_glb_sha256": hashlib.sha256(rebound["body"]).hexdigest(),
        "rigid_manifest_sha256": rebound["manifest_sha256"],
        "binary_chunk_sha256": rebound["receipt"]["binary_chunk_sha256"],
        "binary_geometry_payload_identical": rebound["receipt"]["binary_geometry_payload_identical"],
        "triangles": expected_triangles,
        "mesh_nodes": rebound_verification["nodes"],
        "hinge_pivot_source_m": pivot_source,
        "hinge_pivot_uc_m": pivot_uc,
        "lid_owned_children": lid_owned_children,
        "source_owned_keeper_children": keepers,
        "source_owned_fixed_levers": levers,
        "closed_static_localization_max_error_m": max_closed_static_error,
        "graph_verification": graph_verification,
        "flat_uc_verification": flat_verification,
        "rebound_uc_verification": rebound_verification,
        "uc_rebind_receipt": rebound["receipt"],
        "truth_boundary": {
            "object_source_owns_component_geometry": True,
            "object_sources_own_latch_and_hinge_ownership": True,
            "uc_inferred_object_domain_semantics": False,
            "uc_binary_geometry_payload_preserved": True,
            "source_closed_geometry_preserved_by_localization": True,
            "target_host_import_observed": False,
            "animation_clip_authored": False,
            "runtime_controller_or_gameplay_proven": False,
            "collision_physics_or_mechanical_retention_proven": False,
            "final_visual_acceptance": False,
        },
    }
    receipt_path = out_dir / "uc-rigid-scene-handoff-receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="assets/modular-equipment-case-001/source.json")
    parser.add_argument("--ownership", default="assets/modular-equipment-case-001/front-latch-ownership-001.json")
    parser.add_argument("--uc-root", required=True)
    parser.add_argument("--expected-uc-commit", default=UC_COMMIT)
    parser.add_argument("--out", default="rigid-proof/generated")
    args = parser.parse_args()
    receipt = build_handoff(
        Path(args.source).resolve(),
        Path(args.ownership).resolve(),
        Path(args.uc_root).resolve(),
        args.expected_uc_commit,
        Path(args.out).resolve(),
    )
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
