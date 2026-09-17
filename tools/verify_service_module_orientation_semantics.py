from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
from pathlib import Path

SCHEMA = "axm.object-service-module-orientation-semantics-guard/v0.1"
RESULT = "PASS_SERVICE_MODULE_ORIENTATION_SEMANTICS_GUARD"
DECISION = "PASS_LEGACY_GENERATED_MESHES_UNCHANGED__ALGEBRAIC_SIGN_ONLY__NO_SOURCE_EXTERIOR_OR_RENDERER_FRONT_FACE_TRANSFER"
EXPECTED_CONFIGS = ("empty", "left-only", "right-only", "bilateral")
EXPECTED_LEGACY_RESULT = "PASS_BOUNDED_SERVICE_MODULE_ORIENTED_CONFIGURATION_SUCCESSOR"
EXPECTED_LEGACY_DECISION = "PASS_WINDING_ONLY_GENERATED_SHELL_REBIND__NO_SOURCE_OR_DOWNSTREAM_ADOPTION"
EXPECTED_SIGN_INTERPRETATION = "ALGEBRAIC_ORIENTATION_IN_THE_EXACT_GENERATED_MESH_COORDINATE_FRAME_ONLY"
EXPECTED_HARD_SURFACE_SCOPE = "HOST_SOURCE_EXTERIOR_INTENT_AUTHORITY_BOUNDARY_ONLY__NOT_UTILITY_MODULE_PROOF_BODY_ADOPTION"


def load_json(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def digest_json(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def git_value(root: str | Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(Path(root).resolve()), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def git_head(root: str | Path) -> str:
    return git_value(root, "rev-parse", "HEAD")


def git_blob_at(root: str | Path, ref: str, path: str) -> str:
    return git_value(root, "rev-parse", f"{ref}:{path}")


def git_is_ancestor(root: str | Path, ancestor: str) -> bool:
    proc = subprocess.run(
        ["git", "-C", str(Path(root).resolve()), "merge-base", "--is-ancestor", ancestor, "HEAD"],
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0


def validate_contract_static(contract: dict) -> None:
    if contract.get("schema") != SCHEMA:
        raise AssertionError("orientation semantics guard schema mismatch")

    legacy = contract["legacy_oriented_family"]
    if legacy.get("family_schema") != "axm.object-service-module-oriented-configuration-family/v0.1":
        raise AssertionError("legacy oriented family schema drift")
    expected = legacy.get("expected_candidate_mesh_digests", {})
    if tuple(expected.keys()) != EXPECTED_CONFIGS:
        raise AssertionError("legacy candidate configuration identity/order drift")
    if len(set(expected.values())) != 4:
        raise AssertionError("legacy candidate mesh identities are not four distinct outputs")

    boundary = contract["hard_surface_boundary_evidence"]
    if boundary.get("scope") != EXPECTED_HARD_SURFACE_SCOPE:
        raise AssertionError("Hard Surface authority boundary scope drift")

    semantics = contract["orientation_semantics"]
    if semantics.get("positive_signed_volume_interpretation") != EXPECTED_SIGN_INTERPRETATION:
        raise AssertionError("positive signed-volume interpretation drift")
    for key in (
        "source_exterior_intent_claimed",
        "source_exterior_intent_consumed",
        "hard_surface_authority_transferred",
        "renderer_front_face_selected",
        "receiver_culling_adopted",
        "automatic_source_or_downstream_adoption",
    ):
        if semantics.get(key) is not False:
            raise AssertionError(f"orientation semantic boundary weakened: {key}")

    if tuple(contract.get("retained_configuration_ids", [])) != EXPECTED_CONFIGS:
        raise AssertionError("retained configuration IDs drift")


def validate_repo_provenance(contract: dict, repo_root: str | Path, hard_surface_root: str | Path) -> dict:
    validate_contract_static(contract)
    legacy = contract["legacy_oriented_family"]
    boundary = contract["hard_surface_boundary_evidence"]

    if not git_is_ancestor(repo_root, legacy["procedural_head"]):
        raise AssertionError("legacy Procedural oriented-family head is not an ancestor of current guard")

    historical_generator_blob = git_blob_at(repo_root, legacy["procedural_head"], legacy["generator_path"])
    historical_contract_blob = git_blob_at(repo_root, legacy["procedural_head"], legacy["contract_path"])
    current_generator_blob = git_blob_at(repo_root, "HEAD", legacy["generator_path"])
    current_contract_blob = git_blob_at(repo_root, "HEAD", legacy["contract_path"])
    if historical_generator_blob != legacy["generator_git_blob"]:
        raise AssertionError("legacy oriented generator blob drift")
    if historical_contract_blob != legacy["contract_git_blob"]:
        raise AssertionError("legacy oriented contract blob drift")
    if current_generator_blob != historical_generator_blob:
        raise AssertionError("semantic repair mutated the reusable oriented generator")
    if current_contract_blob != historical_contract_blob:
        raise AssertionError("semantic repair mutated the historical oriented family contract")

    observed_hs_head = git_head(hard_surface_root)
    if observed_hs_head != boundary["head"]:
        raise AssertionError("Hard Surface boundary head drift")
    observed_hs_blob = git_blob_at(hard_surface_root, "HEAD", boundary["contract_path"])
    if observed_hs_blob != boundary["contract_git_blob"]:
        raise AssertionError("Hard Surface exterior-intent contract blob drift")

    return {
        "legacy_procedural_head": legacy["procedural_head"],
        "legacy_generator_git_blob": historical_generator_blob,
        "legacy_contract_git_blob": historical_contract_blob,
        "current_generator_git_blob": current_generator_blob,
        "current_contract_git_blob": current_contract_blob,
        "hard_surface_boundary_head": observed_hs_head,
        "hard_surface_boundary_contract_git_blob": observed_hs_blob,
    }


def validate_hard_surface_boundary(contract: dict, hard_surface_contract: dict) -> dict:
    if hard_surface_contract.get("schema") != "axm.object-rigid-shell-exterior-intent/v0.1":
        raise AssertionError("Hard Surface exterior-intent schema drift")
    if hard_surface_contract.get("asset_id") != contract.get("asset_id"):
        raise AssertionError("Hard Surface exterior-intent asset drift")

    rule = hard_surface_contract["exterior_side_rule"]
    if rule.get("stored_triangle_winding_authoritative") is not False:
        raise AssertionError("Hard Surface unexpectedly promotes stored triangle winding")
    if rule.get("renderer_front_face_authoritative") is not False:
        raise AssertionError("Hard Surface unexpectedly promotes renderer front-face authority")
    if rule.get("automatic_source_winding_rewrite") is not False:
        raise AssertionError("Hard Surface unexpectedly authorizes automatic source winding rewrite")

    probe = hard_surface_contract["geometry_compatibility_probe"]
    if probe.get("authority") != "evidence_only_no_source_adoption":
        raise AssertionError("Hard Surface Geometry compatibility authority drift")

    scope = hard_surface_contract["component_scope"]
    if int(scope.get("expected_components", -1)) != 31:
        raise AssertionError("Hard Surface exact host component scope drift")

    return {
        "hard_surface_schema": hard_surface_contract["schema"],
        "hard_surface_asset_id": hard_surface_contract["asset_id"],
        "hard_surface_component_count": int(scope["expected_components"]),
        "stored_triangle_winding_authoritative": False,
        "renderer_front_face_authoritative": False,
        "automatic_source_winding_rewrite": False,
        "geometry_compatibility_authority": probe["authority"],
    }


def validate_legacy_summary(contract: dict, legacy_summary: dict) -> dict:
    legacy = contract["legacy_oriented_family"]
    if legacy_summary.get("result") != EXPECTED_LEGACY_RESULT:
        raise AssertionError("legacy oriented-family result drift")
    if legacy_summary.get("decision") != EXPECTED_LEGACY_DECISION:
        raise AssertionError("legacy oriented-family decision drift")
    if legacy_summary.get("family_digest") != legacy["family_digest"]:
        raise AssertionError("legacy oriented-family digest drift")
    if legacy_summary.get("reverse_generation_family_digest") != legacy["family_digest"]:
        raise AssertionError("legacy reverse-generation family digest drift")
    if legacy_summary.get("generation_order_independent") is not True:
        raise AssertionError("legacy family generation-order proof missing")
    if int(legacy_summary.get("retained_configuration_count", -1)) != 4:
        raise AssertionError("legacy retained configuration count drift")
    if int(legacy_summary.get("distinct_candidate_mesh_digest_count", -1)) != 4:
        raise AssertionError("legacy candidate mesh variation pressure drift")
    if int(legacy_summary.get("nonempty_configuration_count", -1)) != 3:
        raise AssertionError("legacy nonempty configuration count drift")
    if int(legacy_summary.get("total_generated_module_instances", -1)) != 4:
        raise AssertionError("legacy module instance count drift")
    if int(legacy_summary.get("total_flipped_faces", -1)) != 48:
        raise AssertionError("legacy flipped-face count drift")

    rows = legacy_summary.get("configurations", [])
    by_id = {row["configuration_id"]: row for row in rows}
    if tuple(row["configuration_id"] for row in rows) != EXPECTED_CONFIGS:
        raise AssertionError("legacy configuration order drift")
    if set(by_id) != set(EXPECTED_CONFIGS):
        raise AssertionError("legacy configuration identity drift")

    expected_digests = legacy["expected_candidate_mesh_digests"]
    observed_digests = {}
    for config_id in EXPECTED_CONFIGS:
        row = by_id[config_id]
        observed = row["candidate_mesh_digest"]
        if observed != expected_digests[config_id]:
            raise AssertionError(f"legacy candidate mesh digest drift: {config_id}")
        observed_digests[config_id] = observed

        groups = row.get("groups", [])
        if config_id == "empty":
            if groups:
                raise AssertionError("empty configuration unexpectedly contains generated shell groups")
            if row["predecessor_mesh_digest"] != row["candidate_mesh_digest"]:
                raise AssertionError("empty configuration mesh identity drift")
            continue

        if not groups:
            raise AssertionError(f"nonempty configuration lost generated shell groups: {config_id}")
        for group in groups:
            if int(group.get("source_orientation_conflict_edges", -1)) != 0:
                raise AssertionError("legacy predecessor generated shell orientation-conflict drift")
            if int(group.get("candidate_orientation_conflict_edges", -1)) != 0:
                raise AssertionError("legacy candidate generated shell orientation-conflict drift")
            if int(group.get("boundary_edges", -1)) != 0 or int(group.get("nonmanifold_edges", -1)) != 0:
                raise AssertionError("legacy candidate generated shell closure drift")
            if float(group.get("source_signed_volume_m3", 0.0)) >= 0.0:
                raise AssertionError("legacy predecessor generated shell sign drift")
            if float(group.get("candidate_signed_volume_m3", 0.0)) <= 0.0:
                raise AssertionError("legacy candidate generated shell positive-sign drift")

    if len(set(observed_digests.values())) != 4:
        raise AssertionError("legacy candidate mesh identities are no longer materially distinct")

    return {
        "family_digest": legacy_summary["family_digest"],
        "configuration_ids": list(EXPECTED_CONFIGS),
        "candidate_mesh_digests": observed_digests,
        "materially_distinct_candidate_mesh_count": len(set(observed_digests.values())),
        "nonempty_configuration_count": 3,
        "total_generated_module_instances": int(legacy_summary["total_generated_module_instances"]),
        "total_flipped_faces": int(legacy_summary["total_flipped_faces"]),
    }


def _expect_hold(controls: list[dict], control_id: str, call, fragment: str) -> None:
    try:
        call()
    except AssertionError as exc:
        reason = str(exc)
        if fragment not in reason:
            raise AssertionError(f"negative control {control_id} failed for unexpected reason: {reason}")
        controls.append({"control_id": control_id, "result": "HOLD_FAIL_CLOSED", "reason": reason})
        return
    raise AssertionError(f"negative control {control_id} unexpectedly passed")


def negative_controls(contract: dict, legacy_summary: dict, hard_surface_contract: dict) -> list[dict]:
    controls: list[dict] = []

    drift = copy.deepcopy(contract)
    drift["orientation_semantics"]["source_exterior_intent_claimed"] = True
    _expect_hold(
        controls,
        "promote-algebraic-sign-to-source-exterior",
        lambda: validate_contract_static(drift),
        "source_exterior_intent_claimed",
    )

    drift = copy.deepcopy(contract)
    drift["orientation_semantics"]["renderer_front_face_selected"] = True
    _expect_hold(
        controls,
        "promote-algebraic-sign-to-renderer-front-face",
        lambda: validate_contract_static(drift),
        "renderer_front_face_selected",
    )

    drift = copy.deepcopy(contract)
    drift["orientation_semantics"]["hard_surface_authority_transferred"] = True
    _expect_hold(
        controls,
        "transfer-hard-surface-authority",
        lambda: validate_contract_static(drift),
        "hard_surface_authority_transferred",
    )

    drift_summary = copy.deepcopy(legacy_summary)
    drift_summary["family_digest"] = "0" * 64
    _expect_hold(
        controls,
        "legacy-family-digest-drift",
        lambda: validate_legacy_summary(contract, drift_summary),
        "legacy oriented-family digest drift",
    )

    drift_summary = copy.deepcopy(legacy_summary)
    drift_summary["configurations"][1]["candidate_mesh_digest"] = "0" * 64
    _expect_hold(
        controls,
        "legacy-candidate-mesh-digest-drift",
        lambda: validate_legacy_summary(contract, drift_summary),
        "legacy candidate mesh digest drift",
    )

    drift_hs = copy.deepcopy(hard_surface_contract)
    drift_hs["exterior_side_rule"]["renderer_front_face_authoritative"] = True
    _expect_hold(
        controls,
        "hard-surface-renderer-authority-inflation",
        lambda: validate_hard_surface_boundary(contract, drift_hs),
        "renderer front-face authority",
    )

    return controls


def build_guard_summary(contract: dict, legacy_summary: dict, hard_surface_contract: dict, provenance: dict) -> dict:
    validate_contract_static(contract)
    legacy_observation = validate_legacy_summary(contract, legacy_summary)
    hard_surface_observation = validate_hard_surface_boundary(contract, hard_surface_contract)
    controls = negative_controls(contract, legacy_summary, hard_surface_contract)

    core = {
        "schema": "axm.object-service-module-orientation-semantics-guard-evidence/v0.1",
        "result": RESULT,
        "decision": DECISION,
        "guard_id": contract["guard_id"],
        "legacy_family_artifact_id": contract["legacy_oriented_family"]["artifact_id"],
        "legacy_family_artifact_sha256": contract["legacy_oriented_family"]["artifact_sha256"],
        "legacy_observation": legacy_observation,
        "candidate_mesh_outputs_unchanged_from_legacy": True,
        "orientation_semantics": copy.deepcopy(contract["orientation_semantics"]),
        "hard_surface_boundary": hard_surface_observation,
        "hard_surface_boundary_scope": contract["hard_surface_boundary_evidence"]["scope"],
        "provenance": provenance,
        "negative_controls": controls,
        "truth_boundary": contract["truth_boundary"],
    }
    digest_basis = copy.deepcopy(core)
    digest_basis.pop("negative_controls")
    core["guard_digest"] = digest_json(digest_basis)
    return core


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", required=True)
    parser.add_argument("--legacy-summary", required=True)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--hard-surface-root", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    contract = load_json(args.contract)
    legacy_summary = load_json(args.legacy_summary)
    provenance = validate_repo_provenance(contract, args.repo_root, args.hard_surface_root)
    hs_path = Path(args.hard_surface_root) / contract["hard_surface_boundary_evidence"]["contract_path"]
    hard_surface_contract = load_json(hs_path)
    summary = build_guard_summary(contract, legacy_summary, hard_surface_contract, provenance)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "guard-contract.json").write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "hard-surface-boundary-contract.json").write_text(
        json.dumps(hard_surface_contract, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(RESULT)
    print(json.dumps({
        "guard_digest": summary["guard_digest"],
        "materially_distinct_candidate_mesh_count": summary["legacy_observation"]["materially_distinct_candidate_mesh_count"],
        "negative_controls": len(summary["negative_controls"]),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
