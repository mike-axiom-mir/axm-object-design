from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
from pathlib import Path

import build_service_module_configuration_family as base

GUARD_SCHEMA = "axm.object-service-module-standoff-reference-guard/v0.1"
SUMMARY_SCHEMA = "axm.object-service-module-standoff-reference-guard-evidence/v0.1"
RESULT = "PASS_PROCEDURAL_CONFIGURATION_STANDOFF_SEMANTIC_GUARD"
HOLD = "HOLD_STANDOFF_SEMANTIC_GUARD"


def load_json(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git_value(repo_root: str | Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def exact_owner_policy(owner_root: str | Path, guard: dict) -> tuple[dict, dict]:
    owner_root = Path(owner_root).resolve()
    owner = guard["owner"]
    observed_head = git_value(owner_root, "rev-parse", "HEAD")
    if observed_head != owner["exact_head"]:
        raise AssertionError(f"Hard Surface owner head drift: {observed_head} != {owner['exact_head']}")
    policy_path = owner_root / owner["policy_path"]
    if not policy_path.is_file():
        raise AssertionError(f"Hard Surface standoff policy missing: {policy_path}")
    observed_blob = git_value(owner_root, "rev-parse", f"HEAD:{owner['policy_path']}")
    if observed_blob != owner["policy_git_blob"]:
        raise AssertionError(
            f"Hard Surface standoff policy blob drift: {observed_blob} != {owner['policy_git_blob']}"
        )
    return load_json(policy_path), {
        "repository": owner["repository"],
        "head": observed_head,
        "policy_path": owner["policy_path"],
        "policy_git_blob": observed_blob,
    }


def _close(a: float, b: float, tol: float = 1e-12) -> bool:
    return abs(float(a) - float(b)) <= tol


def validate_guard(
    guard: dict,
    host: dict,
    module: dict,
    profile: dict,
    policy: dict,
    *,
    host_sha256: str,
    module_sha256: str,
    owner_identity: dict,
) -> dict:
    if guard.get("schema") != GUARD_SCHEMA:
        raise AssertionError("standoff guard schema mismatch")

    owner = guard["owner"]
    if owner_identity["repository"] != owner["repository"]:
        raise AssertionError("standoff guard owner repository drift")
    if owner_identity["head"] != owner["exact_head"]:
        raise AssertionError("standoff guard owner head drift")
    if owner_identity["policy_path"] != owner["policy_path"]:
        raise AssertionError("standoff guard owner policy path drift")
    if owner_identity["policy_git_blob"] != owner["policy_git_blob"]:
        raise AssertionError("standoff guard owner policy blob drift")

    source = guard["source_contract"]
    if host.get("asset_id") != source["host_asset_id"]:
        raise AssertionError("standoff guard host identity drift")
    if module.get("asset_id") != source["module_asset_id"]:
        raise AssertionError("standoff guard module identity drift")
    if host_sha256 != source["host_source_sha256"]:
        raise AssertionError("standoff guard host source drift")
    if module_sha256 != source["module_source_sha256"]:
        raise AssertionError("standoff guard module source drift")

    if policy.get("schema") != owner["policy_schema"]:
        raise AssertionError("Hard Surface standoff policy schema drift")
    if policy.get("host_asset_id") != source["host_asset_id"]:
        raise AssertionError("Hard Surface standoff policy host drift")
    if policy.get("module_asset_id") != source["module_asset_id"]:
        raise AssertionError("Hard Surface standoff policy module drift")
    bindings = policy.get("source_bindings", {})
    if bindings.get("host_source_sha256") != host_sha256:
        raise AssertionError("Hard Surface standoff policy host source binding drift")
    if bindings.get("module_source_sha256") != module_sha256:
        raise AssertionError("Hard Surface standoff policy module source binding drift")

    if policy.get("field_path") != source["field_path"]:
        raise AssertionError("standoff field path drift")
    if policy.get("reference_feature") != source["reference_feature"]:
        raise AssertionError("standoff reference feature drift")
    if policy.get("axis_semantics") != source["axis_semantics"]:
        raise AssertionError("standoff axis semantics drift")

    authority = policy.get("authority", {})
    if authority.get("source_reference_feature_owned_by_hard_surface") is not True:
        raise AssertionError("Hard Surface reference-feature authority drift")
    for key in (
        "source_geometry_changed",
        "module_source_changed",
        "host_source_changed",
        "downstream_rebind_authorized",
        "runtime_attachment_authorized",
    ):
        if authority.get(key) is not False:
            raise AssertionError(f"Hard Surface authority expansion: {key}")

    guard_authority = guard.get("authority", {})
    if guard_authority.get("hard_surface_owns_reference_feature_semantics") is not True:
        raise AssertionError("Procedural guard ownership drift")
    for key in (
        "procedural_may_rewrite_source_geometry",
        "procedural_may_reinterpret_standoff_reference_feature",
        "procedural_may_change_owner_policy",
        "automatic_downstream_rebind",
        "runtime_attachment_adoption",
    ):
        if guard_authority.get(key) is not False:
            raise AssertionError(f"Procedural guard authority expansion: {key}")

    expected = policy.get("expected", {})
    stand = float(module["interface"]["standoff_from_socket_origin_m"])
    depth = float(module["body"]["depth_m"])
    if not _close(stand, source["standoff_m"]) or not _close(stand, expected.get("standoff_m")):
        raise AssertionError("standoff value drift")
    if not _close(depth, source["body_depth_m"]) or not _close(depth, expected.get("body_depth_m")):
        raise AssertionError("module body depth drift")

    local_mesh = base.base_fit.build_local_mesh(copy.deepcopy(module))
    xs = [float(v[0]) for v in local_mesh["vertices"]]
    observed_interval = [min(xs), max(xs)]
    declared_interval = [float(v) for v in source["body_local_x_interval_m"]]
    owner_interval = [float(v) for v in expected.get("body_local_x_interval_m", [])]
    if len(owner_interval) != 2:
        raise AssertionError("Hard Surface body interval cardinality drift")
    if any(not _close(a, b) for a, b in zip(observed_interval, declared_interval)):
        raise AssertionError("Procedural generated body interval disagrees with guard")
    if any(not _close(a, b) for a, b in zip(observed_interval, owner_interval)):
        raise AssertionError("Procedural generated body interval disagrees with Hard Surface policy")
    if not _close(observed_interval[0], stand):
        raise AssertionError("generated module no longer uses nearest body face as standoff reference")

    socket_names = [s["uc_descriptor"]["name"] for s in host["sockets"]]
    if socket_names != source["socket_names"] or socket_names != list(expected.get("socket_names", [])):
        raise AssertionError("standoff guard socket identity/order drift")

    clearances = []
    for socket in host["sockets"]:
        plate = float(socket["plate_thickness"])
        clearance = stand - plate
        if not _close(plate, source["socket_plate_thickness_m"]):
            raise AssertionError("socket plate thickness drift")
        if not _close(plate, expected.get("socket_plate_thickness_m")):
            raise AssertionError("Hard Surface policy plate thickness drift")
        if not _close(clearance, source["physical_body_clearance_beyond_plate_m"]):
            raise AssertionError("physical body clearance drift")
        if not _close(clearance, expected.get("physical_body_clearance_beyond_plate_m")):
            raise AssertionError("Hard Surface policy physical clearance drift")
        clearances.append(
            {
                "socket_name": socket["uc_descriptor"]["name"],
                "plate_thickness_m": plate,
                "nearest_body_face_offset_m": stand,
                "physical_body_clearance_beyond_plate_m": clearance,
            }
        )

    family = guard["configuration_family_contract"]
    if profile.get("family_id") != family["family_id"]:
        raise AssertionError("configuration family identity drift")
    ids = [entry["configuration_id"] for entry in profile["retained_configurations"]]
    if ids != family["retained_configuration_ids"]:
        raise AssertionError("retained configuration identity/order drift")

    return {
        "reference_feature": source["reference_feature"],
        "observed_body_local_x_interval_m": observed_interval,
        "socket_clearances": clearances,
        "owner_identity": owner_identity,
    }


def retained_negative_controls(
    guard: dict,
    host: dict,
    module: dict,
    profile: dict,
    policy: dict,
    *,
    host_sha256: str,
    module_sha256: str,
    owner_identity: dict,
) -> list[dict]:
    controls = []

    def hold(control_id: str, fn, expected_fragment: str) -> None:
        try:
            fn()
        except AssertionError as exc:
            reason = str(exc)
            if expected_fragment not in reason:
                raise AssertionError(
                    f"negative control {control_id} failed for unexpected reason: {reason}"
                )
            controls.append({"control_id": control_id, "result": HOLD, "reason": reason})
            return
        raise AssertionError(f"negative control {control_id} unexpectedly passed")

    owner_head_drift = copy.deepcopy(owner_identity)
    owner_head_drift["head"] = "0" * 40
    hold(
        "owner-head-drift",
        lambda: validate_guard(
            guard, host, module, profile, policy,
            host_sha256=host_sha256, module_sha256=module_sha256,
            owner_identity=owner_head_drift,
        ),
        "owner head drift",
    )

    owner_blob_drift = copy.deepcopy(owner_identity)
    owner_blob_drift["policy_git_blob"] = "0" * 40
    hold(
        "owner-policy-blob-drift",
        lambda: validate_guard(
            guard, host, module, profile, policy,
            host_sha256=host_sha256, module_sha256=module_sha256,
            owner_identity=owner_blob_drift,
        ),
        "owner policy blob drift",
    )

    feature_drift = copy.deepcopy(policy)
    feature_drift["reference_feature"] = "module_body_center"
    hold(
        "reference-feature-relabel",
        lambda: validate_guard(
            guard, host, module, profile, feature_drift,
            host_sha256=host_sha256, module_sha256=module_sha256,
            owner_identity=owner_identity,
        ),
        "reference feature drift",
    )

    interval_drift = copy.deepcopy(policy)
    interval_drift["expected"]["body_local_x_interval_m"] = [0.02, 0.115]
    hold(
        "body-interval-drift",
        lambda: validate_guard(
            guard, host, module, profile, interval_drift,
            host_sha256=host_sha256, module_sha256=module_sha256,
            owner_identity=owner_identity,
        ),
        "Hard Surface policy",
    )

    authority_drift = copy.deepcopy(policy)
    authority_drift["authority"]["downstream_rebind_authorized"] = True
    hold(
        "downstream-rebind-authority-expansion",
        lambda: validate_guard(
            guard, host, module, profile, authority_drift,
            host_sha256=host_sha256, module_sha256=module_sha256,
            owner_identity=owner_identity,
        ),
        "authority expansion",
    )

    module_drift = copy.deepcopy(module)
    module_drift["interface"]["standoff_from_socket_origin_m"] = 0.04
    hold(
        "source-standoff-drift",
        lambda: validate_guard(
            guard, host, module_drift, profile, policy,
            host_sha256=host_sha256, module_sha256=module_sha256,
            owner_identity=owner_identity,
        ),
        "standoff value drift",
    )
    return controls


def build_evidence(
    *,
    host_path: str | Path,
    module_path: str | Path,
    registration_path: str | Path,
    profile_path: str | Path,
    guard_path: str | Path,
    sticker_root: str | Path,
    owner_root: str | Path,
    out_dir: str | Path,
) -> dict:
    host = load_json(host_path)
    module = load_json(module_path)
    registration = load_json(registration_path)
    profile = load_json(profile_path)
    guard = load_json(guard_path)

    shared_placement, shared_identity = base.load_shared_placement(sticker_root)
    policy, owner_identity = exact_owner_policy(owner_root, guard)

    source_hashes = {
        "host_source_sha256": sha256_file(host_path),
        "module_source_sha256": sha256_file(module_path),
        "registration_source_sha256": sha256_file(registration_path),
        "prerequisite_head": profile["source_identity"]["prerequisite_head"],
    }
    base_fit_receipt, registration_receipt = base.validate_family(
        profile,
        host,
        module,
        registration,
        host_sha=source_hashes["host_source_sha256"],
        module_sha=source_hashes["module_source_sha256"],
        registration_sha=source_hashes["registration_source_sha256"],
    )
    semantic = validate_guard(
        guard,
        host,
        module,
        profile,
        policy,
        host_sha256=source_hashes["host_source_sha256"],
        module_sha256=source_hashes["module_source_sha256"],
        owner_identity=owner_identity,
    )
    negative_controls = retained_negative_controls(
        guard,
        host,
        module,
        profile,
        policy,
        host_sha256=source_hashes["host_source_sha256"],
        module_sha256=source_hashes["module_source_sha256"],
        owner_identity=owner_identity,
    )

    outputs = []
    for entry in profile["retained_configurations"]:
        output = base.build_configuration(
            host,
            module,
            registration,
            profile,
            entry["occupied_socket_names"],
            source_hashes=source_hashes,
            shared_placement=shared_placement,
        )
        outputs.append(
            {
                "configuration_id": entry["configuration_id"],
                "occupied_socket_names": output["occupied_socket_names"],
                "module_instance_count": output["module_instance_count"],
                "configuration_digest": output["configuration_digest"],
                "mesh_digest": output["mesh_digest"],
            }
        )

    family = guard["configuration_family_contract"]
    if [row["module_instance_count"] for row in outputs] != family["retained_instance_counts"]:
        raise AssertionError("retained configuration instance-count pressure drift")
    if len({row["configuration_digest"] for row in outputs}) != len(outputs):
        raise AssertionError("retained configurations are not distinct")
    if len({row["mesh_digest"] for row in outputs}) != len(outputs):
        raise AssertionError("retained meshes are not distinct")
    for row in outputs:
        expected_digest = family["expected_mesh_digests"][row["configuration_id"]]
        if row["mesh_digest"] != expected_digest:
            raise AssertionError(f"retained mesh regression: {row['configuration_id']}")

    reverse = base.build_configuration(
        host,
        module,
        registration,
        profile,
        ["right_service", "left_service"],
        source_hashes=source_hashes,
        shared_placement=shared_placement,
    )
    bilateral = outputs[-1]
    if reverse["configuration_digest"] != bilateral["configuration_digest"]:
        raise AssertionError("bilateral parameter ordering lost determinism")
    if reverse["mesh_digest"] != bilateral["mesh_digest"]:
        raise AssertionError("bilateral parameter ordering changed retained mesh")

    summary = {
        "schema": SUMMARY_SCHEMA,
        "result": RESULT,
        "decision": "PASS_EXISTING_CONFIGURATION_FAMILY_WITH_EXPLICIT_HARD_SURFACE_STANDOFF_REFERENCE_GUARD__NO_SOURCE_REWRITE_OR_ADOPTION",
        "guard_id": guard["guard_id"],
        "owner_identity": owner_identity,
        "shared_placement_identity": shared_identity,
        "base_fit_result": base_fit_receipt["result"],
        "registration_result": registration_receipt["result"],
        "reference_feature": semantic["reference_feature"],
        "observed_body_local_x_interval_m": semantic["observed_body_local_x_interval_m"],
        "socket_clearances": semantic["socket_clearances"],
        "retained_outputs": outputs,
        "retained_output_count": len(outputs),
        "distinct_configuration_digests": len({row["configuration_digest"] for row in outputs}),
        "distinct_mesh_digests": len({row["mesh_digest"] for row in outputs}),
        "canonical_reverse_bilateral_match": True,
        "negative_controls": negative_controls,
        "negative_control_count": len(negative_controls),
        "failure_policy": guard["failure_policy"],
        "truth_boundary": {
            "existing_parametric_family_reused": True,
            "hard_surface_reference_feature_authority_preserved": True,
            "source_geometry_rewritten": False,
            "standoff_semantics_reinterpreted": False,
            "automatic_downstream_rebind": False,
            "runtime_attachment_adoption": False,
            "production_readiness": False,
            "canon": False,
        },
    }

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "hard-surface-standoff-policy.json").write_text(
        json.dumps(policy, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", required=True)
    ap.add_argument("--module", required=True)
    ap.add_argument("--registration", required=True)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--guard", required=True)
    ap.add_argument("--sticker-root", required=True)
    ap.add_argument("--owner-root", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    summary = build_evidence(
        host_path=args.host,
        module_path=args.module,
        registration_path=args.registration,
        profile_path=args.profile,
        guard_path=args.guard,
        sticker_root=args.sticker_root,
        owner_root=args.owner_root,
        out_dir=args.out,
    )
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
