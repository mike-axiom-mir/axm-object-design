from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any

from build_modular_case import _write_obj, build as build_case, build_uc_socket_package, verify as verify_case
from verify_service_module_fit import build_local_mesh, verify as verify_module_fit

HANDOFF_SCHEMA = "axm.object-uc-target-handoff/v0.1"
UC_COMMIT = "646c69df21eb3b1f85ab4b005368bda827b37a14"
SOURCE_COORDINATES = "+X right, +Y forward, +Z up"
TARGET_COORDINATES = "+X right, +Y up, +Z forward"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def git_head(root: Path) -> str:
    return subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()


def _vec3(value: Any, label: str) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise AssertionError(f"{label} must contain three values")
    result = [float(x) for x in value]
    if any(not math.isfinite(x) for x in result):
        raise AssertionError(f"{label} must be finite")
    return result


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _cross(a: list[float], b: list[float]) -> list[float]:
    return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]


def _length(v: list[float]) -> float:
    return math.sqrt(_dot(v, v))


def _source_basis(socket: dict[str, Any]) -> tuple[list[float], list[float], list[float]]:
    normal = _vec3(socket["frame_basis"]["normal"], "socket.normal")
    up = _vec3(socket["frame_basis"]["up"], "socket.up")
    lateral = _cross(up, normal)
    if abs(_length(normal) - 1.0) > 1e-9 or abs(_length(up) - 1.0) > 1e-9:
        raise AssertionError("source socket basis vectors must be normalized")
    if abs(_dot(normal, up)) > 1e-9 or abs(_length(lateral) - 1.0) > 1e-9:
        raise AssertionError("source socket basis must be orthonormal")
    handed = _cross(normal, lateral)
    if max(abs(handed[i] - up[i]) for i in range(3)) > 1e-9:
        raise AssertionError("source socket basis is not right handed")
    return normal, lateral, up


def bind_source_frame_to_compiled_socket(source_socket: dict[str, Any], compiled_socket_atom: dict[str, Any]) -> dict[str, Any]:
    if compiled_socket_atom.get("kind") != "socket":
        raise AssertionError("compiled atom is not a socket")
    payload = compiled_socket_atom.get("payload")
    if not isinstance(payload, dict):
        raise AssertionError("compiled socket payload missing")
    source_descriptor = source_socket["uc_descriptor"]
    if payload.get("name") != source_descriptor.get("name"):
        raise AssertionError("compiled socket name drift")
    compiled_transform = payload.get("transform")
    source_transform = source_descriptor.get("transform")
    if not isinstance(compiled_transform, dict) or not isinstance(source_transform, dict):
        raise AssertionError("socket transform missing")
    if _vec3(compiled_transform.get("position"), "compiled socket position") != _vec3(source_transform.get("position"), "source socket position"):
        raise AssertionError("compiled socket position drift")
    if _vec3(compiled_transform.get("scale"), "compiled socket scale") != _vec3(source_transform.get("scale"), "source socket scale"):
        raise AssertionError("compiled socket scale drift")
    if payload.get("accepts") != source_descriptor.get("accepts"):
        raise AssertionError("compiled socket accepts drift")
    if bool(payload.get("required")) != bool(source_descriptor.get("required")):
        raise AssertionError("compiled socket required-state drift")
    normal, lateral, up = _source_basis(source_socket)
    return {
        "socket_name": payload["name"],
        "compiled_position": [float(x) for x in compiled_transform["position"]],
        "source_normal": normal,
        "source_lateral": lateral,
        "source_up": up,
        "compiled_rotation_euler_retained_not_interpreted": copy.deepcopy(compiled_transform.get("rotation_euler")),
    }


def transform_module_to_source_world(
    module_mesh: dict[str, Any], source_socket: dict[str, Any], compiled_socket_atom: dict[str, Any]
) -> dict[str, Any]:
    binding = bind_source_frame_to_compiled_socket(source_socket, compiled_socket_atom)
    origin = binding["compiled_position"]
    normal = binding["source_normal"]
    lateral = binding["source_lateral"]
    up = binding["source_up"]
    vertices: list[list[float]] = []
    for local in module_mesh["vertices"]:
        x, y, z = _vec3(local, "module local vertex")
        vertices.append([
            origin[i] + normal[i] * x + lateral[i] * y + up[i] * z
            for i in range(3)
        ])
    return {"vertices": vertices, "faces": [list(face) for face in module_mesh["faces"]], "binding": binding}


def _source_to_uc(point: list[float]) -> list[float]:
    x_right, y_forward, z_up = _vec3(point, "source point")
    return [x_right, z_up, y_forward]


def _face_normal(a: list[float], b: list[float], c: list[float]) -> list[float]:
    u = [b[i] - a[i] for i in range(3)]
    v = [c[i] - a[i] for i in range(3)]
    n = _cross(u, v)
    length = _length(n)
    if length <= 1e-12:
        raise AssertionError("degenerate target triangle")
    return [value / length for value in n]


def make_uc_surface_group(
    group_id: str,
    source_vertices: list[Any],
    source_faces: list[Any],
    *,
    color: str,
    metallic: float,
    roughness: float,
) -> dict[str, Any]:
    positions: list[list[float]] = []
    normals: list[list[float]] = []
    indices: list[int] = []
    for face in source_faces:
        if not isinstance(face, (list, tuple)) or len(face) != 3:
            raise AssertionError("source face must be a triangle")
        a, b, c = [int(i) for i in face]
        if any(i < 0 or i >= len(source_vertices) for i in (a, b, c)):
            raise AssertionError("source face index out of range")
        tri = [_source_to_uc(source_vertices[i]) for i in (a, c, b)]
        normal = _face_normal(*tri)
        start = len(positions)
        positions.extend(tri)
        normals.extend([normal, normal, normal])
        indices.extend([start, start + 1, start + 2])
    return {
        "id": group_id,
        "positions": positions,
        "normals": normals,
        "indices": indices,
        "material": {"color": color, "metallic": metallic, "roughness": roughness},
    }


def build_handoff(host_path: Path, module_path: Path, uc_root: Path, expected_uc_commit: str, out_dir: Path) -> dict[str, Any]:
    observed_uc_commit = git_head(uc_root)
    if observed_uc_commit != expected_uc_commit:
        raise AssertionError(f"UC head mismatch expected={expected_uc_commit} observed={observed_uc_commit}")

    host = json.loads(host_path.read_text(encoding="utf-8"))
    module = json.loads(module_path.read_text(encoding="utf-8"))
    host_result = build_case(host)
    structural = verify_case(host, host_result)
    if structural.get("result") != "PASS_STRUCTURAL_INTERFACE_PROOF":
        raise AssertionError("host structural prerequisite is not green")
    module_mesh = build_local_mesh(module)
    module_fit = verify_module_fit(host, module, module_mesh)
    if module_fit.get("result") != "PASS_BILATERAL_SERVICE_MODULE_FIT_PROOF":
        raise AssertionError("module fit prerequisite is not green")

    out_dir.mkdir(parents=True, exist_ok=True)
    host_obj = out_dir / "modular-equipment-case-001.obj"
    _write_obj(host_obj, host_result)
    package = build_uc_socket_package(host, host_result, sha256_file(host_obj))
    package_path = out_dir / "uc-socket-package.json"
    package_path.write_text(json.dumps(package, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    sys.path.insert(0, str(uc_root / "src"))
    from axm_uc.asset_atoms import compile_asset_package, validate_asset_package  # noqa: E402
    from axm_uc.procedural_3d import publish_glb, verify_glb  # noqa: E402

    normalized = validate_asset_package(package)
    compiled_first = compile_asset_package(package)
    compiled_second = compile_asset_package(package)
    if compiled_first != compiled_second:
        raise AssertionError("UC asset compile is nondeterministic")
    package_sockets = [atom for atom in normalized["atoms"] if atom["kind"] == "socket"]
    instance_sockets = compiled_first["instance"]["sockets"]
    if package_sockets != instance_sockets:
        raise AssertionError("UC changed or dropped socket atoms during compile")

    source_socket = next(s for s in host["sockets"] if s["uc_descriptor"]["name"] == "right_service")
    compiled_socket = next(s for s in instance_sockets if s["payload"]["name"] == "right_service")
    placed_module = transform_module_to_source_world(module_mesh, source_socket, compiled_socket)

    normal = placed_module["binding"]["source_normal"]
    origin = placed_module["binding"]["compiled_position"]
    projected = [_dot([v[i] - origin[i] for i in range(3)], normal) for v in placed_module["vertices"]]
    min_module_outward = min(projected)
    measured_clearance = min_module_outward - float(source_socket["plate_thickness"])
    expected_clearance = float(module["interface"]["standoff_from_socket_origin_m"]) - float(source_socket["plate_thickness"])
    if abs(measured_clearance - expected_clearance) > 1e-9:
        raise AssertionError("bound module clearance drift")

    surface = {
        "schema": "axm.surface-3d/v0.1",
        "name": "modular-equipment-case-001-right-service-proof",
        "primitives": [
            make_uc_surface_group(
                "equipment-case-host",
                host_result["mesh"]["vertices"],
                host_result["mesh"]["faces"],
                color="#666D72FF",
                metallic=0.18,
                roughness=0.72,
            ),
            make_uc_surface_group(
                "utility-module-right-service",
                placed_module["vertices"],
                placed_module["faces"],
                color="#39708AFF",
                metallic=0.16,
                roughness=0.58,
            ),
        ],
    }
    surface_path = out_dir / "object-right-service-assembly.surface.json"
    surface_path.write_text(json.dumps(surface, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    glb_path = out_dir / "object-right-service-assembly.glb"
    publication = publish_glb(glb_path, surface, replace=True)
    verified = verify_glb(glb_path.read_bytes(), expected_spec_digest=publication["specification_sha256"])
    expected_triangles = len(host_result["mesh"]["faces"]) + len(placed_module["faces"])
    if verified["triangles"] != expected_triangles:
        raise AssertionError("UC GLB triangle count drift")

    (out_dir / "validated-package.json").write_text(json.dumps(normalized, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "compiled-instance.json").write_text(json.dumps(compiled_first["instance"], indent=2, sort_keys=True) + "\n", encoding="utf-8")

    receipt = {
        "schema": HANDOFF_SCHEMA,
        "result": "PASS_SOURCE_FRAME_BOUND_UC_GLB_HANDOFF_READY_FOR_TARGET_IMPORT",
        "source_repository": "mike-axiom-mir/axm-object-design",
        "source_repository_head": git_head(Path.cwd()),
        "uc_repository": "mike-axiom-mir/axm-universal-creation",
        "expected_uc_commit": expected_uc_commit,
        "observed_uc_commit": observed_uc_commit,
        "source_coordinates": SOURCE_COORDINATES,
        "uc_glb_coordinates": TARGET_COORDINATES,
        "host_asset_id": host["asset_id"],
        "module_asset_id": module["asset_id"],
        "host_source_sha256": sha256_file(host_path),
        "module_source_sha256": sha256_file(module_path),
        "host_obj_sha256": sha256_file(host_obj),
        "uc_socket_package_sha256": sha256_file(package_path),
        "uc_package_digest": compiled_first["package_digest"],
        "uc_instance_digest": compiled_first["instance"]["instance_digest"],
        "socket_binding": placed_module["binding"],
        "socket_atom_preserved_exactly_by_uc_compile": True,
        "module_fit_prerequisite": module_fit["result"],
        "right_service_measured_body_clearance_m": measured_clearance,
        "assembly_surface_sha256": sha256_file(surface_path),
        "assembly_surface_digest": canonical_digest(surface),
        "assembly_glb_sha256": sha256_file(glb_path),
        "assembly_triangles": expected_triangles,
        "uc_glb_verification": verified,
        "truth_boundary": {
            "source_frame_used_for_module_orientation": True,
            "uc_compiled_socket_name_and_position_consumed": True,
            "uc_compiled_rotation_euler_interpreted_as_renderer_semantics": False,
            "uc_glb_published_and_reverified": True,
            "target_host_import_observed": False,
            "dynamic_runtime_attachment": False,
            "full_mesh_collision": False,
            "engineering_load_or_fastener_retention": False,
            "gameplay_acceptance": False,
            "final_material_or_art_direction_acceptance": False,
            "performance_acceptance": False,
        },
    }
    receipt_path = out_dir / "uc-target-handoff-receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="assets/modular-equipment-case-001/source.json")
    parser.add_argument("--module", default="assets/modular-equipment-case-001/utility-module-001.json")
    parser.add_argument("--uc-root", required=True)
    parser.add_argument("--expected-uc-commit", default=UC_COMMIT)
    parser.add_argument("--out", default="target-proof/generated")
    args = parser.parse_args()
    receipt = build_handoff(
        Path(args.host).resolve(),
        Path(args.module).resolve(),
        Path(args.uc_root).resolve(),
        args.expected_uc_commit,
        Path(args.out).resolve(),
    )
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
