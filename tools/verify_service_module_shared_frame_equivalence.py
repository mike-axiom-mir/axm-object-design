#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

import build_service_module_configuration_family as family

ROOT = Path(__file__).resolve().parents[1]
HOST_PATH = ROOT / "assets/modular-equipment-case-001/source.json"
MODULE_PATH = ROOT / "assets/modular-equipment-case-001/utility-module-001.json"
REGISTRATION_PATH = ROOT / "assets/modular-equipment-case-001/utility-module-registration-key-001.json"
PROFILE_PATH = ROOT / "assets/modular-equipment-case-001/service-module-configuration-family-001.json"
PINNED_UC_HEAD = "bd51542bc68534a6e6f3a11d421dc70216b2abf9"
UC_PLACEMENT_PATH = Path("src/axm_stickers/placement.py")
SOCKET_KIND = "axm-object-neutral-rigid-frame-equivalence-probe"
EXPECTED_CONFIGURATION_IDS = ["empty", "left-only", "right-only", "bilateral"]


def sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_module(path: str | Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"unable to load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git_head(repo_root: str | Path) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def target_frame(socket):
    origin, normal, lateral, up = family.socket_basis(socket)
    return [
        float(normal[0]), float(lateral[0]), float(up[0]), float(origin[0]),
        float(normal[1]), float(lateral[1]), float(up[1]), float(origin[1]),
        float(normal[2]), float(lateral[2]), float(up[2]), float(origin[2]),
        0.0, 0.0, 0.0, 1.0,
    ]


def apply_matrix(matrix, point):
    x, y, z = [float(value) for value in point]
    return [
        matrix[0] * x + matrix[1] * y + matrix[2] * z + matrix[3],
        matrix[4] * x + matrix[5] * y + matrix[6] * z + matrix[7],
        matrix[8] * x + matrix[9] * y + matrix[10] * z + matrix[11],
    ]


def exact_neutral_attachment_matrix(shared, frame):
    identity = shared.identity()
    definition = {
        "attachment": {
            "space": "3d",
            "socket": SOCKET_KIND,
            "anchor": identity,
        }
    }
    placed = {"placement": {"offset": identity, "scale": 1.0}}
    target = {"space": "3d", "socket": SOCKET_KIND, "frame": frame}
    matrix = shared.attachment_matrix(definition, placed, target)
    if matrix != frame:
        raise ValueError("shared neutral attachment matrix changed the exact target frame")
    return matrix


def shared_mesh_for_configuration(shared, host, module, profile, occupied_socket_names):
    ordered_slots = family.canonical_slots(profile, occupied_socket_names)
    sockets = {socket["uc_descriptor"]["name"]: socket for socket in host["sockets"]}
    local_mesh = family.base_fit.build_local_mesh(module)

    vertices = []
    faces = []
    frame_rows = []
    for slot_name in ordered_slots:
        socket = sockets[slot_name]
        frame = target_frame(socket)
        matrix = exact_neutral_attachment_matrix(shared, frame)
        world_vertices = [apply_matrix(matrix, point) for point in local_mesh["vertices"]]
        start = len(vertices)
        vertices.extend(world_vertices)
        faces.extend([[start + int(index) for index in face] for face in local_mesh["faces"]])
        frame_rows.append(
            {
                "slot_name": slot_name,
                "socket_id": socket["id"],
                "target_frame": frame,
                "target_frame_digest": family.digest_json(frame),
                "shared_instance_vertices_digest": family.digest_json(world_vertices),
            }
        )

    return {"vertices": vertices, "faces": faces}, frame_rows


def maximum_position_residual(existing_vertices, shared_vertices):
    if len(existing_vertices) != len(shared_vertices):
        return float("inf")
    if not existing_vertices:
        return 0.0
    return max(
        abs(float(observed) - float(expected))
        for observed_vertex, expected_vertex in zip(shared_vertices, existing_vertices)
        for observed, expected in zip(observed_vertex, expected_vertex)
    )


def negative_controls(shared, valid_frame):
    controls = {}

    reflected = list(valid_frame)
    reflected[0] *= -1.0
    reflected[4] *= -1.0
    reflected[8] *= -1.0
    try:
        exact_neutral_attachment_matrix(shared, reflected)
        controls["reflected_target_frame"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        controls["reflected_target_frame"] = "HOLD: " + str(exc)

    definition = {
        "attachment": {
            "space": "3d",
            "socket": SOCKET_KIND,
            "anchor": shared.identity(),
        }
    }
    placed = {"placement": {"offset": shared.identity(), "scale": 1.0}}
    wrong_target = {
        "space": "3d",
        "socket": SOCKET_KIND + "-wrong",
        "frame": valid_frame,
    }
    try:
        shared.attachment_matrix(definition, placed, wrong_target)
        controls["socket_identity_mismatch"] = "UNEXPECTED_PASS"
    except ValueError as exc:
        controls["socket_identity_mismatch"] = "HOLD: " + str(exc)

    scaled = shared.attachment_matrix(
        definition,
        {"placement": {"offset": shared.identity(), "scale": 1.001}},
        {"space": "3d", "socket": SOCKET_KIND, "frame": valid_frame},
    )
    if scaled == valid_frame:
        controls["non_unit_scale_changes_frame"] = "UNEXPECTED_PASS"
    else:
        controls["non_unit_scale_changes_frame"] = (
            "HOLD: non-unit scale is not exact neutral placement"
        )

    if any(not result.startswith("HOLD:") for result in controls.values()):
        raise ValueError("shared-frame equivalence negative control unexpectedly passed")
    return controls


def build(uc_root: str | Path):
    uc_root = Path(uc_root).resolve()
    observed_uc_head = git_head(uc_root)
    if observed_uc_head != PINNED_UC_HEAD:
        raise ValueError(
            f"shared-frame donor head drift: {observed_uc_head} != {PINNED_UC_HEAD}"
        )

    shared_path = uc_root / UC_PLACEMENT_PATH
    if not shared_path.is_file():
        raise ValueError(f"shared placement module missing: {shared_path}")
    shared = load_module(shared_path, "axm_object_shared_placement_probe")

    host = family.load_json(HOST_PATH)
    module = family.load_json(MODULE_PATH)
    registration = family.load_json(REGISTRATION_PATH)
    profile = family.load_json(PROFILE_PATH)
    source_hashes = {
        "host_source_sha256": family.sha256_file(HOST_PATH),
        "module_source_sha256": family.sha256_file(MODULE_PATH),
        "registration_source_sha256": family.sha256_file(REGISTRATION_PATH),
        "prerequisite_head": profile["source_identity"]["prerequisite_head"],
    }

    base_receipt, registration_receipt = family.validate_family(
        profile,
        host,
        module,
        registration,
        host_sha=source_hashes["host_source_sha256"],
        module_sha=source_hashes["module_source_sha256"],
        registration_sha=source_hashes["registration_source_sha256"],
    )
    if base_receipt["result"] != "PASS_BILATERAL_SERVICE_MODULE_FIT_PROOF":
        raise ValueError("Object base fit prerequisite is not PASS")
    if registration_receipt["result"] != "PASS_ASYMMETRIC_REGISTRATION_KEY_PROOF":
        raise ValueError("Object asymmetric registration prerequisite is not PASS")

    entries = profile["retained_configurations"]
    configuration_ids = [entry["configuration_id"] for entry in entries]
    if configuration_ids != EXPECTED_CONFIGURATION_IDS:
        raise ValueError(
            f"retained Object configuration identity drift: {configuration_ids}"
        )

    rows = []
    all_frame_rows = []
    for entry in entries:
        existing = family.build_configuration(
            host,
            module,
            registration,
            profile,
            entry["occupied_socket_names"],
            source_hashes=source_hashes,
        )
        shared_mesh, frame_rows = shared_mesh_for_configuration(
            shared,
            host,
            module,
            profile,
            entry["occupied_socket_names"],
        )
        shared_mesh_digest = family.digest_json(shared_mesh)
        exact_mesh = shared_mesh == existing["mesh"]
        exact_digest = shared_mesh_digest == existing["mesh_digest"]
        residual = maximum_position_residual(
            existing["mesh"]["vertices"], shared_mesh["vertices"]
        )
        if not exact_mesh or not exact_digest or residual != 0.0:
            raise ValueError(
                f"{entry['configuration_id']}: shared rigid-frame path is not exact "
                f"(mesh={exact_mesh}, digest={exact_digest}, residual={residual})"
            )

        rows.append(
            {
                "configuration_id": entry["configuration_id"],
                "occupied_socket_names": existing["occupied_socket_names"],
                "module_instance_count": existing["module_instance_count"],
                "existing_configuration_digest": existing["configuration_digest"],
                "existing_mesh_digest": existing["mesh_digest"],
                "shared_mesh_digest": shared_mesh_digest,
                "exact_mesh_match": exact_mesh,
                "exact_mesh_digest_match": exact_digest,
                "maximum_position_residual_m": residual,
                "target_frames": frame_rows,
            }
        )
        all_frame_rows.extend(frame_rows)

    if [row["module_instance_count"] for row in rows] != [0, 1, 1, 2]:
        raise ValueError("Object retained occupancy pressure drift")
    if len({row["existing_mesh_digest"] for row in rows}) != 4:
        raise ValueError("Object retained configurations lost distinct mesh identities")
    if len({row["shared_mesh_digest"] for row in rows}) != 4:
        raise ValueError("shared path did not retain four distinct configuration meshes")

    nonempty = [row for row in rows if row["module_instance_count"] > 0]
    if len(nonempty) != 3:
        raise ValueError("expected three non-empty Object configurations")
    unique_target_frames = {
        frame_row["target_frame_digest"] for frame_row in all_frame_rows
    }
    if len(unique_target_frames) != 2:
        raise ValueError("expected exactly two distinct Object source-owned target frames")

    socket_frame_by_name = {}
    for socket in host["sockets"]:
        name = socket["uc_descriptor"]["name"]
        frame = target_frame(socket)
        socket_frame_by_name[name] = {
            "socket_id": socket["id"],
            "target_frame": frame,
            "target_frame_digest": family.digest_json(frame),
        }
    valid_frame = socket_frame_by_name["left_service"]["target_frame"]
    controls = negative_controls(shared, valid_frame)

    return {
        "schema": "axm.object-shared-rigid-frame-equivalence-evidence/v0.1",
        "result": "PASS_EXACT_SHARED_RIGID_FRAME_EQUIVALENCE_OBJECT_CONFIGURATIONS",
        "authority": "RECEIVING_DOMAIN_EQUIVALENCE_PROBE_ONLY",
        "consolidation_decision": "READY_FOR_CAPABILITY_CARTOGRAPHY_REVIEW_NO_CONSUMER_MIGRATION",
        "object_head": git_head(ROOT),
        "object_family_id": profile["family_id"],
        "object_family_result": "PASS_BOUNDED_SERVICE_MODULE_CONFIGURATION_FAMILY",
        "object_base_fit_result": base_receipt["result"],
        "object_registration_result": registration_receipt["result"],
        "object_source_identity": source_hashes,
        "shared_donor_repo": "mike-axiom-mir/axm-universal-creation",
        "shared_donor_head": observed_uc_head,
        "shared_donor_module": str(UC_PLACEMENT_PATH),
        "shared_donor_module_sha256": sha256(shared_path),
        "shared_capability": "renderer-independent rigid 3D attachment matrix",
        "probe_socket_kind": SOCKET_KIND,
        "source_anchor": "identity",
        "local_offset": "identity",
        "scale": 1.0,
        "exact_configuration_equivalence_count": sum(
            row["exact_mesh_match"] and row["exact_mesh_digest_match"] for row in rows
        ),
        "exact_nonempty_configuration_equivalence_count": sum(
            row["exact_mesh_match"] and row["exact_mesh_digest_match"]
            for row in nonempty
        ),
        "distinct_target_frame_digests": len(unique_target_frames),
        "distinct_shared_configuration_mesh_digests": len(
            {row["shared_mesh_digest"] for row in rows}
        ),
        "maximum_position_residual_m": max(
            row["maximum_position_residual_m"] for row in rows
        ),
        "socket_frames": socket_frame_by_name,
        "configurations": rows,
        "negative_controls": controls,
        "truth_boundary": (
            "This proves only that the exact existing Object empty/left/right/bilateral "
            "utility-module configuration outputs are reproduced byte-semantically at the "
            "retained mesh JSON/digest contract by the pinned standalone axm_stickers neutral "
            "rigid-frame matrix path using identity source anchor, identity offset and unit "
            "scale. Three non-empty configurations exercise the two exact source-owned service "
            "socket frames. Object keeps socket allowlists, occupancy canonicalization, fit, "
            "asymmetric registration, source identities and acceptance semantics. This does "
            "not migrate the Object generator, authorize deletion of local code, move Object "
            "product semantics into Universal Creation, create a universal attachment schema, "
            "prove runtime attachment/physics/gameplay, or establish CANON/production readiness."
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--uc-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()

    summary = build(args.uc_root)
    print(json.dumps(summary, indent=2, sort_keys=True))
    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
