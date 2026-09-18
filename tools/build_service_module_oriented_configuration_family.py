from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

try:
    from tools import build_service_module_configuration_family as predecessor
except ModuleNotFoundError:  # direct `python tools/...py` execution
    import build_service_module_configuration_family as predecessor

SCHEMA = "axm.object-service-module-oriented-configuration-family/v0.1"
RECEIPT_SCHEMA = "axm.object-service-module-oriented-configuration/v0.1"
SUMMARY_SCHEMA = "axm.object-service-module-oriented-configuration-family-evidence/v0.1"
RESULT = "PASS_BOUNDED_SERVICE_MODULE_ORIENTED_CONFIGURATION_SUCCESSOR"
DECISION = "PASS_WINDING_ONLY_GENERATED_SHELL_REBIND__NO_SOURCE_OR_DOWNSTREAM_ADOPTION"
EXPECTED_PATTERN = "RIGID_COMPONENT_GROUPS_REQUIRE_CLOSED_ORIENTABLE_OUTWARD_WINDING_BEFORE_INDEPENDENT_SCENE_GRAPH_CARRIAGE"
ROOT = Path(__file__).resolve().parents[1]


def load_json(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest_json(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def git_value(root: str | Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def git_head(root: str | Path) -> str:
    return git_value(root, "rev-parse", "HEAD")


def git_blob(root: str | Path, path: str) -> str:
    return git_value(root, "rev-parse", f"HEAD:{path}")


def git_is_ancestor(root: str | Path, ancestor: str) -> bool:
    proc = subprocess.run(
        ["git", "-C", str(root), "merge-base", "--is-ancestor", ancestor, "HEAD"],
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0


def validate_contract_static(contract: dict) -> None:
    if contract.get("schema") != SCHEMA:
        raise AssertionError("oriented configuration family schema mismatch")
    owner = contract["geometry_orientation_owner"]
    if owner.get("owned_pattern") != EXPECTED_PATTERN:
        raise AssertionError("Geometry owner pattern drift")
    if owner.get("consumption") != "REUSE_EXACT_OWNER_ORIENTATION_HELPER_FOR_PROCEDURAL_GENERATED_MODULE_GROUPS_ONLY":
        raise AssertionError("Geometry owner consumption boundary drift")

    policy = contract["orientation_contract"]
    if policy.get("candidate_operation") != "WINDING_ONLY_CLOSED_ORIENTABLE_POSITIVE_SIGNED_VOLUME_SUCCESSOR":
        raise AssertionError("orientation successor operation drift")
    for key in (
        "positions_changed",
        "triangle_vertex_membership_changed",
        "triangle_order_changed",
        "configuration_membership_changed",
        "source_module_rewritten",
        "automatic_source_adoption",
        "automatic_technical_art_adoption",
        "automatic_runtime_adoption",
        "automatic_visual_adoption",
    ):
        if policy.get(key) is not False:
            raise AssertionError(f"authority or mutation boundary weakened: {key}")


def validate_external_provenance(contract: dict, repo_root: str | Path, geometry_root: str | Path) -> dict:
    validate_contract_static(contract)
    repo_root = Path(repo_root).resolve()
    geometry_root = Path(geometry_root).resolve()
    prior = contract["predecessor"]
    owner = contract["geometry_orientation_owner"]

    if not git_is_ancestor(repo_root, prior["procedural_head"]):
        raise AssertionError("predecessor Procedural head is not an ancestor of current successor")
    observed_generator_blob = git_blob(repo_root, prior["generator_path"])
    if observed_generator_blob != prior["generator_git_blob"]:
        raise AssertionError("predecessor generator blob drift")
    observed_profile_blob = git_blob(repo_root, prior["family_profile_path"])
    if observed_profile_blob != prior["family_profile_git_blob"]:
        raise AssertionError("predecessor family profile blob drift")

    observed_owner_head = git_head(geometry_root)
    if observed_owner_head != owner["head"]:
        raise AssertionError("Geometry orientation owner head drift")
    observed_helper_blob = git_blob(geometry_root, owner["helper_path"])
    if observed_helper_blob != owner["helper_git_blob"]:
        raise AssertionError("Geometry orientation owner helper blob drift")

    return {
        "predecessor_procedural_head": prior["procedural_head"],
        "predecessor_generator_git_blob": observed_generator_blob,
        "predecessor_family_profile_git_blob": observed_profile_blob,
        "geometry_orientation_owner_head": observed_owner_head,
        "geometry_orientation_owner_helper_git_blob": observed_helper_blob,
        "geometry_orientation_owner_pattern": owner["owned_pattern"],
    }


def owner_orient_group(geometry_root: str | Path, vertices, faces):
    payload = {"vertices": vertices, "faces": faces}
    code = (
        "import json,sys; "
        "from tools.verify_rigid_shell_orientation import orient_closed_group; "
        "p=json.load(sys.stdin); "
        "f,m=orient_closed_group(p['vertices'],p['faces']); "
        "print(json.dumps({'faces':f,'metrics':m},sort_keys=True))"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(Path(geometry_root).resolve()),
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        reason = (proc.stderr or proc.stdout or "Geometry owner orientation helper rejected group").strip().splitlines()[-1]
        raise AssertionError(f"Geometry owner orientation helper rejected group: {reason}")
    data = json.loads(proc.stdout)
    return data["faces"], data["metrics"]


def orient_configuration(configuration: dict, orient_group) -> dict:
    source_mesh = configuration["mesh"]
    vertices = copy.deepcopy(source_mesh["vertices"])
    source_faces = [list(map(int, face)) for face in source_mesh["faces"]]
    candidate_faces = copy.deepcopy(source_faces)

    vertex_cursor = 0
    face_cursor = 0
    groups = []
    for instance in configuration["instances"]:
        vertex_count = int(instance["vertex_count"])
        face_count = int(instance["triangle_count"])
        vertex_end = vertex_cursor + vertex_count
        face_end = face_cursor + face_count
        if vertex_end > len(vertices) or face_end > len(source_faces):
            raise AssertionError("configuration instance range exceeds generated mesh")
        group_faces = source_faces[face_cursor:face_end]
        if any(index < vertex_cursor or index >= vertex_end for face in group_faces for index in face):
            raise AssertionError("configuration instance references vertices outside its own generated group")

        oriented_faces, metrics = orient_group(vertices, group_faces)
        normalized = [list(map(int, face)) for face in oriented_faces]
        if len(normalized) != len(group_faces):
            raise AssertionError("Geometry owner orientation changed triangle count")
        if any(sorted(a) != sorted(b) for a, b in zip(group_faces, normalized)):
            raise AssertionError("Geometry owner orientation changed triangle vertex membership")
        if int(metrics.get("source_orientation_conflict_edges", -1)) != 0:
            raise AssertionError("predecessor generated module is not already coherently orientable")
        if int(metrics.get("candidate_orientation_conflict_edges", -1)) != 0:
            raise AssertionError("oriented generated module retains orientation conflicts")
        if int(metrics.get("boundary_edges", -1)) != 0 or int(metrics.get("nonmanifold_edges", -1)) != 0:
            raise AssertionError("generated module group is not a closed 2-manifold")
        if float(metrics.get("source_signed_volume_m3", 0.0)) >= -1e-15:
            raise AssertionError("historical generated module is no longer the expected inward-wound shell")
        if float(metrics.get("candidate_signed_volume_m3", 0.0)) <= 1e-15:
            raise AssertionError("oriented generated module does not have positive signed volume")

        candidate_faces[face_cursor:face_end] = normalized
        groups.append(
            {
                "slot_name": instance["slot_name"],
                "vertex_count": vertex_count,
                "triangle_count": face_count,
                "source_orientation_conflict_edges": int(metrics["source_orientation_conflict_edges"]),
                "candidate_orientation_conflict_edges": int(metrics["candidate_orientation_conflict_edges"]),
                "boundary_edges": int(metrics["boundary_edges"]),
                "nonmanifold_edges": int(metrics["nonmanifold_edges"]),
                "source_signed_volume_m3": float(metrics["source_signed_volume_m3"]),
                "candidate_signed_volume_m3": float(metrics["candidate_signed_volume_m3"]),
                "flipped_faces": int(metrics["flipped_faces"]),
            }
        )
        vertex_cursor = vertex_end
        face_cursor = face_end

    if vertex_cursor != len(vertices) or face_cursor != len(source_faces):
        if configuration["instances"] or vertices or source_faces:
            raise AssertionError("configuration instances do not exactly cover generated mesh")

    candidate_mesh = {"vertices": vertices, "faces": candidate_faces}
    if candidate_mesh["vertices"] != source_mesh["vertices"]:
        raise AssertionError("orientation successor changed generated vertex positions")
    if len(candidate_faces) != len(source_faces):
        raise AssertionError("orientation successor changed generated triangle count")

    source_digest = predecessor.digest_json(source_mesh)
    candidate_digest = predecessor.digest_json(candidate_mesh)
    if groups and candidate_digest == source_digest:
        raise AssertionError("non-empty orientation successor did not change winding identity")
    if not groups and candidate_digest != source_digest:
        raise AssertionError("empty configuration changed unexpectedly")

    core = {
        "schema": RECEIPT_SCHEMA,
        "configuration_id": configuration.get("configuration_id"),
        "occupied_socket_names": copy.deepcopy(configuration["occupied_socket_names"]),
        "module_instance_count": int(configuration["module_instance_count"]),
        "predecessor_configuration_digest": configuration["configuration_digest"],
        "predecessor_mesh_digest": source_digest,
        "candidate_mesh_digest": candidate_digest,
        "candidate_mesh": candidate_mesh,
        "groups": groups,
        "positions_changed": False,
        "triangle_vertex_membership_changed": False,
        "triangle_order_changed": False,
        "source_module_rewritten": False,
        "automatic_source_adoption": False,
        "automatic_downstream_adoption": False,
        "result": "PASS_WINDING_ONLY_GENERATED_SHELL_ORIENTATION_SUCCESSOR",
    }
    digest_basis = copy.deepcopy(core)
    digest_basis.pop("candidate_mesh")
    digest_basis.pop("result")
    core["oriented_configuration_digest"] = digest_json(digest_basis)
    return core


def canonical_family_digest(rows: list[dict]) -> str:
    basis = [
        {
            "configuration_id": row["configuration_id"],
            "predecessor_mesh_digest": row["predecessor_mesh_digest"],
            "candidate_mesh_digest": row["candidate_mesh_digest"],
            "oriented_configuration_digest": row["oriented_configuration_digest"],
            "groups": row["groups"],
        }
        for row in sorted(rows, key=lambda item: item["configuration_id"])
    ]
    return digest_json(basis)


def build_predecessor_configuration(host, module, registration, profile, entry, source_hashes, shared_placement):
    row = predecessor.build_configuration(
        host,
        module,
        registration,
        profile,
        entry["occupied_socket_names"],
        source_hashes=source_hashes,
        shared_placement=shared_placement,
    )
    row["configuration_id"] = entry["configuration_id"]
    return row


def build_rows(host, module, registration, profile, contract, source_hashes, shared_placement, geometry_root, entries):
    expected = contract["predecessor"]["expected_mesh_digests"]
    rows = []
    predecessors = {}
    for entry in entries:
        config_id = entry["configuration_id"]
        source = build_predecessor_configuration(
            host, module, registration, profile, entry, source_hashes, shared_placement
        )
        if source["mesh_digest"] != expected.get(config_id):
            raise AssertionError(f"historical predecessor mesh digest drift: {config_id}")
        predecessors[config_id] = source
        row = orient_configuration(
            source,
            lambda vertices, faces: owner_orient_group(geometry_root, vertices, faces),
        )
        rows.append(row)
    return rows, predecessors


def write_obj(path: str | Path, receipt: dict) -> None:
    predecessor.write_obj(path, {"mesh": receipt["candidate_mesh"]})


def negative_controls(contract, repo_root, geometry_root, left_predecessor):
    controls = []

    def expect_hold(control_id, call, fragment):
        try:
            call()
        except AssertionError as exc:
            reason = str(exc)
            if fragment not in reason:
                raise AssertionError(f"negative control {control_id} failed for unexpected reason: {reason}")
            controls.append({"control_id": control_id, "result": "HOLD_FAIL_CLOSED", "reason": reason})
            return
        raise AssertionError(f"negative control {control_id} unexpectedly passed")

    drift = copy.deepcopy(contract)
    drift["predecessor"]["generator_git_blob"] = "0" * 40
    expect_hold(
        "predecessor-generator-blob-drift",
        lambda: validate_external_provenance(drift, repo_root, geometry_root),
        "predecessor generator blob drift",
    )

    drift = copy.deepcopy(contract)
    drift["geometry_orientation_owner"]["head"] = "0" * 40
    expect_hold(
        "geometry-owner-head-drift",
        lambda: validate_external_provenance(drift, repo_root, geometry_root),
        "Geometry orientation owner head drift",
    )

    drift = copy.deepcopy(contract)
    drift["orientation_contract"]["automatic_source_adoption"] = True
    expect_hold(
        "automatic-source-adoption",
        lambda: validate_contract_static(drift),
        "automatic_source_adoption",
    )

    opened = copy.deepcopy(left_predecessor)
    opened["mesh"]["faces"] = opened["mesh"]["faces"][:-1]
    opened["instances"][0]["triangle_count"] -= 1
    expect_hold(
        "open-generated-shell",
        lambda: orient_configuration(
            opened,
            lambda vertices, faces: owner_orient_group(geometry_root, vertices, faces),
        ),
        "Geometry owner orientation helper rejected group",
    )

    return controls


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--module", required=True)
    parser.add_argument("--registration", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--contract", required=True)
    parser.add_argument("--sticker-root", required=True)
    parser.add_argument("--geometry-root", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    repo_root = ROOT
    contract = load_json(args.contract)
    external_identity = validate_external_provenance(contract, repo_root, args.geometry_root)

    host = load_json(args.host)
    module = load_json(args.module)
    registration = load_json(args.registration)
    profile = load_json(args.profile)
    if profile.get("schema") != contract["predecessor"]["family_schema"]:
        raise AssertionError("predecessor family schema drift")

    shared_placement, shared_identity = predecessor.load_shared_placement(args.sticker_root)
    source_hashes = {
        "host_source_sha256": sha256_file(args.host),
        "module_source_sha256": sha256_file(args.module),
        "registration_source_sha256": sha256_file(args.registration),
        "prerequisite_head": profile["source_identity"]["prerequisite_head"],
    }
    predecessor.validate_family(
        profile,
        host,
        module,
        registration,
        host_sha=source_hashes["host_source_sha256"],
        module_sha=source_hashes["module_source_sha256"],
        registration_sha=source_hashes["registration_source_sha256"],
    )

    retained_ids = [entry["configuration_id"] for entry in profile["retained_configurations"]]
    if retained_ids != contract["retained_configuration_ids"]:
        raise AssertionError("retained configuration identity/order drift")

    rows, predecessors = build_rows(
        host,
        module,
        registration,
        profile,
        contract,
        source_hashes,
        shared_placement,
        args.geometry_root,
        profile["retained_configurations"],
    )
    reverse_rows, _ = build_rows(
        host,
        module,
        registration,
        profile,
        contract,
        source_hashes,
        shared_placement,
        args.geometry_root,
        list(reversed(profile["retained_configurations"])),
    )
    family_digest = canonical_family_digest(rows)
    reverse_digest = canonical_family_digest(reverse_rows)
    if family_digest != reverse_digest:
        raise AssertionError("oriented configuration family digest depends on generation order")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for row in rows:
        config_id = row["configuration_id"]
        json_path = out / f"oriented-configuration-{config_id}.json"
        obj_path = out / f"oriented-configuration-{config_id}.obj"
        json_path.write_text(json.dumps(row, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        write_obj(obj_path, row)

    nonempty = [row for row in rows if row["groups"]]
    if len({row["candidate_mesh_digest"] for row in rows}) != len(rows):
        raise AssertionError("oriented retained mesh identities are not all distinct")
    if len({row["oriented_configuration_digest"] for row in rows}) != len(rows):
        raise AssertionError("oriented retained configuration identities are not all distinct")

    controls = negative_controls(contract, repo_root, args.geometry_root, predecessors["left-only"])
    summary = {
        "schema": SUMMARY_SCHEMA,
        "result": RESULT,
        "decision": DECISION,
        "family_id": contract["family_id"],
        "family_digest": family_digest,
        "reverse_generation_family_digest": reverse_digest,
        "generation_order_independent": True,
        "retained_configuration_count": len(rows),
        "distinct_candidate_mesh_digest_count": len({row["candidate_mesh_digest"] for row in rows}),
        "distinct_oriented_configuration_digest_count": len({row["oriented_configuration_digest"] for row in rows}),
        "nonempty_configuration_count": len(nonempty),
        "total_generated_module_instances": sum(row["module_instance_count"] for row in rows),
        "total_flipped_faces": sum(group["flipped_faces"] for row in rows for group in row["groups"]),
        "predecessor_outputs_retained_unchanged": True,
        "external_identity": external_identity,
        "shared_placement_identity": shared_identity,
        "source_identity": source_hashes,
        "configurations": [
            {
                "configuration_id": row["configuration_id"],
                "occupied_socket_names": row["occupied_socket_names"],
                "module_instance_count": row["module_instance_count"],
                "predecessor_mesh_digest": row["predecessor_mesh_digest"],
                "candidate_mesh_digest": row["candidate_mesh_digest"],
                "oriented_configuration_digest": row["oriented_configuration_digest"],
                "groups": row["groups"],
            }
            for row in rows
        ],
        "negative_controls": controls,
        "truth_boundary": contract["truth_boundary"],
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(RESULT)
    print(json.dumps({
        "family_digest": family_digest,
        "retained_configurations": len(rows),
        "module_instances": summary["total_generated_module_instances"],
        "flipped_faces": summary["total_flipped_faces"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
