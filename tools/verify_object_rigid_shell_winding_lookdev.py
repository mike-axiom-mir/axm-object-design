from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from build_modular_case import build as build_case

CONTRACT_SCHEMA = "axm.object-material-rigid-shell-winding-lookdev/v0.1"
PAYLOAD_SCHEMA = "axm.object-material-rigid-shell-winding-lookdev-payload/v0.1"
BUILD_SCHEMA = "axm.object-material-rigid-shell-winding-lookdev-build/v0.1"
RUNTIME_SCHEMA = "axm.object-material-rigid-shell-winding-lookdev-runtime/v0.1"
EXPECTED_SOURCE_SHA = "49b1f9ed9865893d6de6f1ec8f069576732df694853fde4e3fcff366de32644a"
EXPECTED_PROFILE_SHA = "dc200229d6c25fa84063aa51f66103abc022efa54b2167e4432a5b47fc40360c"
EXPECTED_GEOMETRY_HEAD = "606d8189a3bf4502141d8038f08d35d421829dde"
EXPECTED_GEOMETRY_RESULT = "PASS_DERIVED_RIGID_SHELL_OUTWARD_ORIENTATION_CANDIDATE"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rgba(hex_value: str) -> list[float]:
    if len(hex_value) != 9 or not hex_value.startswith("#"):
        raise AssertionError(f"invalid RGBA hex {hex_value!r}")
    return [int(hex_value[i : i + 2], 16) / 255.0 for i in (1, 3, 5, 7)]


def parse_obj(path: Path) -> tuple[list[list[float]], list[list[int]], list[str]]:
    vertices: list[list[float]] = []
    faces: list[list[int]] = []
    labels: list[str] = []
    current_group = ""
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("v "):
            values = line.split()
            if len(values) != 4:
                raise AssertionError("candidate OBJ vertex arity drift")
            vertices.append([float(values[1]), float(values[2]), float(values[3])])
        elif line.startswith("g "):
            current_group = line[2:].strip()
            if not current_group:
                raise AssertionError("candidate OBJ empty group")
        elif line.startswith("f "):
            values = line.split()
            if len(values) != 4 or not current_group:
                raise AssertionError("candidate OBJ face/group drift")
            face: list[int] = []
            for token in values[1:]:
                if "/" in token:
                    raise AssertionError("candidate OBJ unexpectedly carries UV/normal indices")
                face.append(int(token) - 1)
            faces.append(face)
            labels.append(current_group)
    return vertices, faces, labels


def normalized_materials(profile: dict[str, Any], roles: set[str]) -> tuple[dict[str, Any], dict[str, str]]:
    if profile.get("schema") != "axm.object-material-profile/v0.1":
        raise AssertionError("material profile schema drift")
    mapping = profile.get("role_materials", {})
    if not isinstance(mapping, dict):
        raise AssertionError("material role mapping missing")
    missing = sorted(roles - set(mapping))
    if missing:
        raise AssertionError(f"material role coverage drift missing={missing}")
    candidate = profile.get("candidate", {})
    normalized: dict[str, Any] = {}
    for material_id, spec in candidate.items():
        metallic = float(spec["metallic"])
        roughness = float(spec["roughness"])
        if not (0.0 <= metallic <= 1.0 and 0.0 <= roughness <= 1.0):
            raise AssertionError("material scalar out of range")
        normalized[material_id] = {
            "albedo": rgba(str(spec["albedo"])),
            "albedo_hex": str(spec["albedo"]),
            "metallic": metallic,
            "roughness": roughness,
        }
    for role, material_id in mapping.items():
        if material_id not in normalized:
            raise AssertionError(f"unknown material {material_id!r} for role {role!r}")
    if profile.get("provenance", {}).get("external_textures") not in ([], None):
        raise AssertionError("external texture provenance not allowed in bounded receiver")
    return normalized, {str(k): str(v) for k, v in mapping.items()}


def build_payload(
    contract_path: Path,
    source_path: Path,
    profile_path: Path,
    geometry_receipt_path: Path,
    candidate_obj_path: Path,
    exact_materials_head: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    source = json.loads(source_path.read_text(encoding="utf-8"))
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    geometry_receipt = json.loads(geometry_receipt_path.read_text(encoding="utf-8"))

    if contract.get("schema") != CONTRACT_SCHEMA:
        raise AssertionError("lookdev contract schema drift")
    if sha256(source_path) != EXPECTED_SOURCE_SHA or contract.get("source_sha256") != EXPECTED_SOURCE_SHA:
        raise AssertionError("source identity drift")
    if sha256(profile_path) != EXPECTED_PROFILE_SHA or contract.get("material_profile_sha256") != EXPECTED_PROFILE_SHA:
        raise AssertionError("material profile identity drift")
    owner = contract.get("geometry_owner", {})
    if owner.get("exact_head") != EXPECTED_GEOMETRY_HEAD:
        raise AssertionError("Geometry owner head drift")
    if geometry_receipt.get("result") != EXPECTED_GEOMETRY_RESULT:
        raise AssertionError("Geometry candidate prerequisite did not PASS")
    if geometry_receipt.get("source_vertices") != 468 or geometry_receipt.get("source_triangles") != 812:
        raise AssertionError("Geometry candidate source shape drift")
    if geometry_receipt.get("source_rigid_groups") != 31:
        raise AssertionError("Geometry candidate rigid-group count drift")
    if geometry_receipt.get("source_orientation_conflict_edges") != 304:
        raise AssertionError("Geometry source orientation observation drift")
    if geometry_receipt.get("candidate_orientation_conflict_edges") != 0:
        raise AssertionError("Geometry candidate retains orientation conflicts")
    if geometry_receipt.get("candidate_flipped_faces") != 508:
        raise AssertionError("Geometry candidate face-flip count drift")
    if geometry_receipt.get("source_adopted") is not False:
        raise AssertionError("Geometry candidate may not self-authorize source adoption")

    result = build_case(source)
    mesh = result["mesh"]
    components = result["components"]
    vertices = [[float(x) for x in v] for v in mesh["vertices"]]
    source_faces = [[int(x) for x in f] for f in mesh["faces"]]
    groups = mesh["groups"]
    if len(vertices) != 468 or len(source_faces) != 812 or len(groups) != 31 or len(components) != 31:
        raise AssertionError("current Object source shape drift")
    if [g["name"] for g in groups] != [c["name"] for c in components]:
        raise AssertionError("group/component identity drift")

    obj_vertices, owner_faces, labels = parse_obj(candidate_obj_path)
    if len(obj_vertices) != len(vertices) or len(owner_faces) != len(source_faces) or len(labels) != len(source_faces):
        raise AssertionError("Geometry candidate OBJ shape drift")
    max_vertex_delta = 0.0
    for expected, observed in zip(vertices, obj_vertices):
        for a, b in zip(expected, observed):
            max_vertex_delta = max(max_vertex_delta, abs(a - b))
    if max_vertex_delta > 1e-8:
        raise AssertionError(f"Geometry candidate OBJ position drift {max_vertex_delta}")
    membership_mismatches = sum(sorted(a) != sorted(b) for a, b in zip(source_faces, owner_faces))
    if membership_mismatches:
        raise AssertionError(f"Geometry candidate changed triangle membership: {membership_mismatches}")

    roles = {str(c["role"]) for c in components}
    materials, role_materials = normalized_materials(profile, roles)
    component_by_name = {str(c["name"]): c for c in components}
    payload_groups: list[dict[str, Any]] = []
    cursor = 0
    for group in groups:
        name = str(group["name"])
        start = int(group["first_face"])
        count = int(group["face_count"])
        if start != cursor or count <= 0:
            raise AssertionError("source group range drift")
        if any(label != name for label in labels[start : start + count]):
            raise AssertionError(f"Geometry candidate OBJ group-label drift for {name}")
        role = str(component_by_name[name]["role"])
        payload_groups.append({
            "name": name,
            "role": role,
            "material_id": role_materials[role],
            "first_face": start,
            "face_count": count,
        })
        cursor += count
    if cursor != len(source_faces):
        raise AssertionError("source group ranges do not cover every face")

    host_reversed_faces = [[face[0], face[2], face[1]] for face in owner_faces]
    payload = {
        "schema": PAYLOAD_SCHEMA,
        "asset_id": contract["asset_id"],
        "exact_materials_head": exact_materials_head,
        "exact_geometry_owner_head": EXPECTED_GEOMETRY_HEAD,
        "geometry_owner_result": EXPECTED_GEOMETRY_RESULT,
        "source_sha256": EXPECTED_SOURCE_SHA,
        "material_profile_sha256": EXPECTED_PROFILE_SHA,
        "vertices": vertices,
        "owner_faces": owner_faces,
        "host_reversed_faces": host_reversed_faces,
        "groups": payload_groups,
        "materials": materials,
        "camera_contexts": contract["receiver"]["camera_contexts"],
        "position_map": contract["receiver"]["source_to_host_position_map"],
        "position_map_determinant": contract["receiver"]["source_to_host_transform_determinant"],
        "normal_policy": contract["comparison"]["normal_policy"],
        "truth_boundary": contract["truth_boundary"],
    }
    build_receipt = {
        "schema": BUILD_SCHEMA,
        "result": "PASS_SOURCE_BOUND_OBJECT_RIGID_SHELL_WINDING_LOOKDEV_PAYLOAD",
        "exact_materials_head": exact_materials_head,
        "exact_geometry_owner_head": EXPECTED_GEOMETRY_HEAD,
        "source_sha256": EXPECTED_SOURCE_SHA,
        "material_profile_sha256": EXPECTED_PROFILE_SHA,
        "vertices": len(vertices),
        "triangles": len(owner_faces),
        "rigid_groups": len(payload_groups),
        "candidate_obj_max_position_delta": max_vertex_delta,
        "candidate_triangle_membership_mismatches": membership_mismatches,
        "geometry_source_orientation_conflict_edges": geometry_receipt["source_orientation_conflict_edges"],
        "geometry_candidate_orientation_conflict_edges": geometry_receipt["candidate_orientation_conflict_edges"],
        "geometry_candidate_flipped_faces": geometry_receipt["candidate_flipped_faces"],
        "material_scalars_changed": False,
        "source_geometry_changed": False,
        "source_geometry_adopted": False,
        "geometry_candidate_adopted": False,
        "host_winding_adapter_adopted": False,
        "truth_boundary": contract["truth_boundary"],
    }
    return payload, build_receipt


def verify_runtime(path: Path) -> dict[str, Any]:
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if receipt.get("schema") != RUNTIME_SCHEMA:
        raise AssertionError("runtime receipt schema drift")
    if receipt.get("state") != "PASS_EVIDENCE":
        raise AssertionError(f"runtime evidence did not complete: {receipt.get('state')}")
    if receipt.get("exact_geometry_owner_head") != EXPECTED_GEOMETRY_HEAD:
        raise AssertionError("runtime Geometry owner drift")
    if receipt.get("material_profile_sha256") != EXPECTED_PROFILE_SHA:
        raise AssertionError("runtime material profile drift")
    comparisons = receipt.get("comparisons", {})
    if set(comparisons) != {"front_service", "three_quarter", "rear_hinge"}:
        raise AssertionError("runtime camera set drift")
    if receipt.get("unshaded_two_sided_coverage_identity_all_contexts") is not True:
        raise AssertionError("unshaded cull-disabled winding coverage control is not identical")
    owner_total = 0
    reversed_total = 0
    winding_visible = 0
    for context, row in comparisons.items():
        coverage = row["unshaded_two_sided_owner_vs_host_reversed"]
        if int(coverage["changed_pixels_raw"]) != 0 or int(coverage["changed_pixels_gt_1lsb"]) != 0:
            raise AssertionError(f"unshaded coverage control changed pixels in {context}: {coverage}")
        owner = row["owner_order_back_vs_two_sided"]
        reversed_row = row["host_reversed_back_vs_two_sided"]
        winding = row["owner_order_back_vs_host_reversed_back"]
        owner_total += int(owner["changed_pixels_gt_1lsb"])
        reversed_total += int(reversed_row["changed_pixels_gt_1lsb"])
        winding_visible += int(winding["changed_pixels_gt_1lsb"])
    if winding_visible <= 0:
        raise AssertionError("backface receiver did not respond to winding change")
    if int(receipt.get("aggregate_owner_order_back_vs_two_sided_gt1", -1)) != owner_total:
        raise AssertionError("owner-order aggregate drift")
    if int(receipt.get("aggregate_host_reversed_back_vs_two_sided_gt1", -1)) != reversed_total:
        raise AssertionError("host-reversed aggregate drift")
    decision = str(receipt.get("decision", ""))
    allowed = {
        "PASS_HOST_REVERSED_ORDER_CLOSER_TO_TWO_SIDED_REFERENCE",
        "PASS_OWNER_ORDER_CLOSER_TO_TWO_SIDED_REFERENCE",
        "HOLD_NO_CLEAR_CULL_COHERENCE_WIN",
    }
    if decision not in allowed:
        raise AssertionError(f"unexpected runtime decision {decision!r}")
    if decision == "PASS_HOST_REVERSED_ORDER_CLOSER_TO_TWO_SIDED_REFERENCE" and not reversed_total < owner_total:
        raise AssertionError("host-reversed PASS is not supported by aggregate evidence")
    if decision == "PASS_OWNER_ORDER_CLOSER_TO_TWO_SIDED_REFERENCE" and not owner_total < reversed_total:
        raise AssertionError("owner-order PASS is not supported by aggregate evidence")
    if decision == "HOLD_NO_CLEAR_CULL_COHERENCE_WIN" and owner_total != reversed_total:
        raise AssertionError("HOLD does not match equal aggregate evidence")
    for key in ("source_geometry_adopted", "geometry_candidate_adopted", "host_winding_adapter_adopted"):
        if receipt.get("truth_boundary", {}).get(key) is not False:
            raise AssertionError(f"authority boundary weakened: {key}")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", default="lookdev/object_rigid_shell_winding_lookdev_001.json")
    parser.add_argument("--source", default="assets/modular-equipment-case-001/source.json")
    parser.add_argument("--profile", default="lookdev/object_material_profile_001.json")
    parser.add_argument("--geometry-receipt", default="lookdev-proof/generated/object-geometry-orientation-receipt.json")
    parser.add_argument("--candidate-obj", default="lookdev-proof/generated/object-geometry-orientation-candidate.obj")
    parser.add_argument("--out", default="lookdev-proof/generated")
    parser.add_argument("--exact-head", default="")
    parser.add_argument("--runtime-receipt")
    args = parser.parse_args()

    if args.runtime_receipt:
        print(json.dumps(verify_runtime(Path(args.runtime_receipt)), indent=2, sort_keys=True))
        return
    if not args.exact_head:
        raise AssertionError("--exact-head is required for payload build")
    payload, receipt = build_payload(
        Path(args.contract), Path(args.source), Path(args.profile), Path(args.geometry_receipt), Path(args.candidate_obj), args.exact_head
    )
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "object_rigid_shell_winding_lookdev_payload.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "object_rigid_shell_winding_lookdev_build_receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
