from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

import verify_service_module_fit as base_fit
import verify_service_module_registration_key as registration_fit

FAMILY_SCHEMA = "axm.object-service-module-configuration-family/v0.1"
CONFIG_SCHEMA = "axm.object-service-module-configuration/v0.1"
SUMMARY_SCHEMA = "axm.object-service-module-configuration-family-evidence/v0.1"


def sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest_json(value) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_json(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_family(profile, host, module, registration, *, host_sha: str, module_sha: str, registration_sha: str):
    if profile.get("schema") != FAMILY_SCHEMA:
        raise AssertionError("configuration family schema mismatch")

    identity = profile["source_identity"]
    if identity["host_asset_id"] != host.get("asset_id"):
        raise AssertionError("configuration family host asset identity mismatch")
    if identity["module_asset_id"] != module.get("asset_id"):
        raise AssertionError("configuration family module asset identity mismatch")
    if identity["registration_asset_id"] != registration.get("asset_id"):
        raise AssertionError("configuration family registration asset identity mismatch")
    if identity["host_source_sha256"] != host_sha:
        raise AssertionError("configuration family host source identity mismatch")
    if identity["module_source_sha256"] != module_sha:
        raise AssertionError("configuration family module source identity mismatch")
    if identity["registration_source_sha256"] != registration_sha:
        raise AssertionError("configuration family registration source identity mismatch")

    contract = profile["parameter_contract"]
    allowed = contract["allowed_socket_names"]
    if len(allowed) != len(set(allowed)) or not allowed:
        raise AssertionError("configuration family allowed socket list is invalid")
    host_names = [socket["uc_descriptor"]["name"] for socket in host["sockets"]]
    if allowed != host_names:
        raise AssertionError("configuration family socket ordering/identity drift")
    if int(contract["maximum_instances"]) != len(allowed):
        raise AssertionError("configuration family maximum instance bound drift")
    if contract["receiving_scale"] != "FORBIDDEN" or contract["extra_rotation"] != "FORBIDDEN":
        raise AssertionError("configuration family hidden transform authority")
    if contract["placement"] != "EXACT_SOURCE_FRAME_ONLY":
        raise AssertionError("configuration family placement contract drift")

    base_receipt = base_fit.verify(host, module, base_fit.build_local_mesh(module))
    registration_receipt = registration_fit.verify(
        host,
        module,
        registration,
        host_sha=host_sha,
        module_sha=module_sha,
    )
    if base_receipt["result"] != "PASS_BILATERAL_SERVICE_MODULE_FIT_PROOF":
        raise AssertionError("configuration family base fit prerequisite failed")
    if registration_receipt["result"] != "PASS_ASYMMETRIC_REGISTRATION_KEY_PROOF":
        raise AssertionError("configuration family registration prerequisite failed")
    return base_receipt, registration_receipt


def socket_basis(socket):
    normal, lateral, up = registration_fit.validate_frame(socket)
    origin = [float(x) for x in socket["uc_descriptor"]["transform"]["position"]]
    return origin, [float(x) for x in normal], [float(x) for x in lateral], [float(x) for x in up]


def transform_point(socket, local_point):
    origin, normal, lateral, up = socket_basis(socket)
    outward, local_lateral, local_up = map(float, local_point)
    return [
        origin[i] + normal[i] * outward + lateral[i] * local_lateral + up[i] * local_up
        for i in range(3)
    ]


def canonical_slots(profile, occupied_socket_names):
    if not isinstance(occupied_socket_names, list):
        raise AssertionError("occupied socket names must be a list")
    if any(not isinstance(name, str) for name in occupied_socket_names):
        raise AssertionError("occupied socket names must be strings")
    if len(occupied_socket_names) != len(set(occupied_socket_names)):
        raise AssertionError("duplicate socket occupancy is not allowed")

    contract = profile["parameter_contract"]
    allowed = contract["allowed_socket_names"]
    unknown = [name for name in occupied_socket_names if name not in allowed]
    if unknown:
        raise AssertionError("unknown socket occupancy: " + ",".join(sorted(unknown)))
    if len(occupied_socket_names) > int(contract["maximum_instances"]):
        raise AssertionError("maximum module instance bound exceeded")
    return [name for name in allowed if name in occupied_socket_names]


def build_configuration(host, module, registration, profile, occupied_socket_names, *, source_hashes):
    ordered_slots = canonical_slots(profile, occupied_socket_names)
    sockets = {socket["uc_descriptor"]["name"]: socket for socket in host["sockets"]}
    local_mesh = base_fit.build_local_mesh(module)

    vertices = []
    faces = []
    instances = []
    for slot_name in ordered_slots:
        socket = sockets[slot_name]
        start = len(vertices)
        world_vertices = [transform_point(socket, vertex) for vertex in local_mesh["vertices"]]
        vertices.extend(world_vertices)
        faces.extend([[start + int(index) for index in face] for face in local_mesh["faces"]])
        mins = [min(vertex[i] for vertex in world_vertices) for i in range(3)]
        maxs = [max(vertex[i] for vertex in world_vertices) for i in range(3)]
        origin, normal, lateral, up = socket_basis(socket)
        instances.append(
            {
                "slot_name": slot_name,
                "socket_id": socket["id"],
                "source_position_m": origin,
                "source_frame_basis": {"normal": normal, "lateral": lateral, "up": up},
                "receiving_scale": [1.0, 1.0, 1.0],
                "extra_rotation_degrees": 0.0,
                "world_aabb_m": {"min": mins, "max": maxs},
                "vertex_count": len(world_vertices),
                "triangle_count": len(local_mesh["faces"]),
            }
        )

    mesh = {"vertices": vertices, "faces": faces}
    receipt_core = {
        "schema": CONFIG_SCHEMA,
        "family_id": profile["family_id"],
        "host_asset_id": host["asset_id"],
        "module_asset_id": module["asset_id"],
        "registration_asset_id": registration["asset_id"],
        "occupied_socket_names": ordered_slots,
        "module_instance_count": len(instances),
        "instances": instances,
        "mesh": mesh,
        "mesh_digest": digest_json(mesh),
        "source_identity": copy.deepcopy(source_hashes),
        "result": "PASS_EXACT_SOURCE_FRAME_CONFIGURATION",
        "truth_boundary": {
            "deterministic_source_space_assembly": True,
            "exact_existing_fit_prerequisite": True,
            "exact_existing_registration_prerequisite": True,
            "receiving_scale_or_extra_rotation": False,
            "runtime_attach_detach": False,
            "physics_constraint": False,
            "full_mesh_collision_solver": False,
            "engineering_load_or_retention": False,
            "gameplay_acceptance": False,
            "visual_acceptance": False,
        },
    }
    digest_basis = copy.deepcopy(receipt_core)
    digest_basis.pop("result")
    receipt_core["configuration_digest"] = digest_json(digest_basis)
    return receipt_core


def write_obj(path: str | Path, receipt):
    lines = [
        "# service-module configuration family output",
        "# source-space transformed utility-module-001 bodies only; host geometry is not duplicated",
    ]
    mesh = receipt["mesh"]
    for vertex in mesh["vertices"]:
        lines.append("v %.9f %.9f %.9f" % tuple(vertex))
    for face in mesh["faces"]:
        lines.append("f %d %d %d" % tuple(int(index) + 1 for index in face))
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def retained_negative_controls(host, module, registration, profile, source_hashes):
    controls = []

    def hold(control_id, call, expected_fragment):
        try:
            call()
        except AssertionError as exc:
            reason = str(exc)
            if expected_fragment not in reason:
                raise AssertionError(f"negative control {control_id} failed for unexpected reason: {reason}")
            controls.append({"control_id": control_id, "result": "HOLD_INVALID_CONFIGURATION", "reason": reason})
            return
        raise AssertionError(f"negative control {control_id} unexpectedly produced a configuration")

    hold(
        "unknown-socket",
        lambda: build_configuration(host, module, registration, profile, ["roof_service"], source_hashes=source_hashes),
        "unknown socket occupancy",
    )
    hold(
        "duplicate-socket",
        lambda: build_configuration(host, module, registration, profile, ["left_service", "left_service"], source_hashes=source_hashes),
        "duplicate socket occupancy",
    )

    drifted = copy.deepcopy(profile)
    drifted["source_identity"]["host_source_sha256"] = "0" * 64
    hold(
        "source-identity-drift",
        lambda: validate_family(
            drifted,
            host,
            module,
            registration,
            host_sha=source_hashes["host_source_sha256"],
            module_sha=source_hashes["module_source_sha256"],
            registration_sha=source_hashes["registration_source_sha256"],
        ),
        "host source identity mismatch",
    )
    return controls


def build_evidence(host_path, module_path, registration_path, profile_path, out_dir):
    host = load_json(host_path)
    module = load_json(module_path)
    registration = load_json(registration_path)
    profile = load_json(profile_path)
    source_hashes = {
        "host_source_sha256": sha256_file(host_path),
        "module_source_sha256": sha256_file(module_path),
        "registration_source_sha256": sha256_file(registration_path),
        "prerequisite_head": profile["source_identity"]["prerequisite_head"],
    }
    base_receipt, registration_receipt = validate_family(
        profile,
        host,
        module,
        registration,
        host_sha=source_hashes["host_source_sha256"],
        module_sha=source_hashes["module_source_sha256"],
        registration_sha=source_hashes["registration_source_sha256"],
    )

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    receipts = []
    seen_ids = set()
    for entry in profile["retained_configurations"]:
        configuration_id = entry["configuration_id"]
        if configuration_id in seen_ids:
            raise AssertionError("duplicate retained configuration id")
        seen_ids.add(configuration_id)
        receipt = build_configuration(
            host,
            module,
            registration,
            profile,
            entry["occupied_socket_names"],
            source_hashes=source_hashes,
        )
        receipt["configuration_id"] = configuration_id
        json_path = out / f"configuration-{configuration_id}.json"
        obj_path = out / f"configuration-{configuration_id}.obj"
        json_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        write_obj(obj_path, receipt)
        receipt["retained_json_sha256"] = sha256_file(json_path)
        receipt["retained_obj_sha256"] = sha256_file(obj_path)
        receipts.append(receipt)

    configuration_digests = [receipt["configuration_digest"] for receipt in receipts]
    mesh_digests = [receipt["mesh_digest"] for receipt in receipts]
    if len(configuration_digests) < 4 or len(set(configuration_digests)) != len(configuration_digests):
        raise AssertionError("retained configurations are not materially distinct by configuration digest")
    if len(set(mesh_digests)) != len(mesh_digests):
        raise AssertionError("retained configurations are not materially distinct by transformed mesh digest")
    if [receipt["module_instance_count"] for receipt in receipts] != [0, 1, 1, 2]:
        raise AssertionError("retained configuration occupancy pressure drift")

    controls = retained_negative_controls(host, module, registration, profile, source_hashes)
    summary = {
        "schema": SUMMARY_SCHEMA,
        "result": "PASS_BOUNDED_SERVICE_MODULE_CONFIGURATION_FAMILY",
        "family_id": profile["family_id"],
        "source_identity": source_hashes,
        "base_fit_result": base_receipt["result"],
        "registration_result": registration_receipt["result"],
        "retained_configuration_count": len(receipts),
        "retained_configuration_ids": [receipt["configuration_id"] for receipt in receipts],
        "retained_instance_counts": [receipt["module_instance_count"] for receipt in receipts],
        "distinct_configuration_digests": len(set(configuration_digests)),
        "distinct_mesh_digests": len(set(mesh_digests)),
        "negative_controls": controls,
        "failure_policy": "FAIL_CLOSED_NO_FALLBACK_SOCKET_NO_BOUND_WIDENING",
        "truth_boundary": {
            "object_local_parametric_assembly": True,
            "multiple_materially_different_outputs": True,
            "bounded_fail_closed_controls_retained": True,
            "universal_attachment_fitter": False,
            "runtime_swap_system": False,
            "physics_attachment": False,
            "production_readiness": False,
            "canon": False,
        },
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--module", required=True)
    parser.add_argument("--registration", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    summary = build_evidence(args.host, args.module, args.registration, args.profile, args.out)
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
