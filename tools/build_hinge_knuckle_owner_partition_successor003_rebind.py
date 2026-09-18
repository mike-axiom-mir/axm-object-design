from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

SCHEMA = "axm.object-hinge-knuckle-owner-partition-successor003-rebind/v0.1"
RESULT = "PASS_BOUNDED_HINGE_KNUCKLE_OWNER_PARTITION_SUCCESSOR003_REBIND"
DECISION = "PASS_EXACT_SUCCESSOR003_OWNER_PARTITIONS__BODY_IDENTITY_PRESERVED__LID_AND_FULL_PHASE_CHANGED__SUCCESSOR002_FAMILY_PRESERVED__NO_SOURCE_RIG_VISUAL_OR_DOWNSTREAM_ADOPTION"
EXPECTED_PREDECESSOR_HEAD = "9b6956d9e913bd3b34ce3d1b41cf718dda17d8e8"
EXPECTED_PREDECESSOR_FAMILY_DIGEST = "33cce498a91de77ece64bda50bc6b70caca2f76ccadc06d1fd8f29b7c62e2782"


def _canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _digest(value) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot import module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _validate_authority(contract: dict) -> None:
    authority = contract.get("authority", {})
    required_false = (
        "hard_surface_source_successor_rewritten",
        "procedural_predecessor_rewritten",
        "automatic_default_replacement",
        "materials_adoption_authorized",
        "rig_parenting_authorized",
        "animation_authorized",
        "technical_art_adoption_authorized",
        "runtime_or_physics_authorized",
        "visual_acceptance_authorized",
        "automatic_downstream_adoption",
    )
    promoted = [key for key in required_false if authority.get(key) is not False]
    if promoted:
        raise AssertionError(f"authority expansion forbidden: {promoted}")


def _validate_predecessor(contract: dict) -> dict:
    predecessor = contract.get("procedural_predecessor", {})
    if predecessor.get("exact_head") != EXPECTED_PREDECESSOR_HEAD:
        raise AssertionError("Procedural predecessor head drift")
    if predecessor.get("family_digest") != EXPECTED_PREDECESSOR_FAMILY_DIGEST:
        raise AssertionError("Procedural predecessor family digest drift")
    expected = {"full", "body-only", "lid-only"}
    if set(predecessor.get("variant_mesh_digests", {})) != expected:
        raise AssertionError("Procedural predecessor variant identity set drift")
    if predecessor.get("artifact_id") != 10528058522:
        raise AssertionError("Procedural predecessor artifact identity drift")
    if predecessor.get("artifact_sha256") != "37c44b0365e44888825a2e66dd399030932a710249090ef11568b7ddca4febd3":
        raise AssertionError("Procedural predecessor artifact digest drift")
    return predecessor


def _verify_donor_identity(contract: dict, donor_root: Path) -> dict[str, str]:
    if _git(donor_root, "rev-parse", "HEAD") != contract["hard_surface_owner_head"]:
        raise AssertionError("Hard-Surface owner head drift")
    observed: dict[str, str] = {}
    for key, rel in contract["donor_paths"].items():
        blob = _git(donor_root, "rev-parse", f"HEAD:{rel}")
        if blob != contract["donor_git_blobs"][key]:
            raise AssertionError(f"donor blob drift: {key}")
        observed[key] = blob
    return observed


def _normalize_phase_groups_for_existing_partition(
    full_mesh: dict,
    ordered_knuckles: list[dict],
) -> tuple[dict, list[dict]]:
    normalized = copy.deepcopy(full_mesh)
    groups = normalized.get("groups", [])
    if len(groups) != len(ordered_knuckles):
        raise AssertionError("relative-phase donor group count drift")

    aliases: list[dict] = []
    for row, group in zip(ordered_knuckles, groups):
        expected_source = f"hinge_{row['owner']}_{row['id']}_relative_phase_candidate"
        if group.get("name") != expected_source:
            raise AssertionError(
                f"relative-phase donor group identity drift: {group.get('name')} != {expected_source}"
            )
        canonical_partition_name = f"hinge_{row['owner']}_{row['id']}_annular_candidate"
        aliases.append({
            "knuckle_id": row["id"],
            "owner": row["owner"],
            "source_group": expected_source,
            "partition_compatibility_group": canonical_partition_name,
        })
        group["name"] = canonical_partition_name
    return normalized, aliases


def _load_donor_successor003(contract: dict, donor_root: Path):
    paths = {key: donor_root / rel for key, rel in contract["donor_paths"].items()}
    host = _load_json(paths["host"])
    successor002 = _load_json(paths["successor002_contract"])
    owner = _load_json(paths["owner_stack_contract"])
    axial_stop = _load_json(paths["axial_stop_contract"])
    capture = _load_json(paths["capture_contract"])
    bracket = _load_json(paths["bracket_contract"])
    successor003 = _load_json(paths["successor003_contract"])

    original_path = list(sys.path)
    sys.path.insert(0, str(donor_root.resolve()))
    sys.path.insert(0, str((donor_root / "tools").resolve()))
    try:
        verifier = _load_module(
            paths["successor003_verifier"],
            "axm_hard_surface_relative_facet_phase_successor003_donor",
        )
    finally:
        sys.path[:] = original_path
    return host, successor002, owner, axial_stop, capture, bracket, successor003, verifier


def build_family(contract: dict, donor_root: Path, partition_module_path: Path) -> tuple[dict, dict[str, dict]]:
    if contract.get("schema") != SCHEMA:
        raise AssertionError(f"unsupported family schema: {contract.get('schema')}")
    _validate_authority(contract)
    predecessor = _validate_predecessor(contract)
    donor_blobs = _verify_donor_identity(contract, donor_root)

    host, successor002, owner_contract, axial_stop, capture, bracket, successor003, verifier = _load_donor_successor003(contract, donor_root)
    partition_mod = _load_module(partition_module_path, "axm_existing_owner_partition_helper_successor003")

    receipt, full_mesh = verifier.evaluate(
        host,
        successor002,
        owner_contract,
        axial_stop,
        capture,
        bracket,
        successor003,
        observed_host_sha256=successor003["prerequisite_identity"]["legacy_host_source_sha256"],
        observed_successor002_blob_sha1=donor_blobs["successor002_contract"],
        observed_owner_stack_blob_sha1=donor_blobs["owner_stack_contract"],
        observed_axial_stop_blob_sha1=donor_blobs["axial_stop_contract"],
        observed_capture_blob_sha1=donor_blobs["capture_contract"],
        observed_bracket_blob_sha1=donor_blobs["bracket_contract"],
    )
    if receipt.get("result") != "PASS_SOURCE_OWNED_HINGE_RELATIVE_FACET_PHASE_SUCCESSOR":
        raise AssertionError("relative-facet-phase Hard-Surface prerequisite did not pass")

    expected_successor = contract["expected_source_successor"]
    if receipt.get("successor_id") != expected_successor["successor_id"]:
        raise AssertionError("source successor identity drift")
    for key in ("body_phase_deg", "lid_phase_deg", "relative_lid_minus_body_phase_deg"):
        if abs(float(receipt[key]) - float(expected_successor[key])) > 1e-12:
            raise AssertionError(f"source successor {key} drift")
    if int(receipt["segments"]) != int(expected_successor["segments"]):
        raise AssertionError("source successor segment count drift")
    if int(receipt["body_owned_knuckles"]) != 3 or int(receipt["lid_owned_knuckles"]) != 2:
        raise AssertionError("source successor owner counts drift")

    ordered_knuckles = list(owner_contract["ordered_knuckles"])
    observed_owner_sequence = [row["owner"] for row in ordered_knuckles]
    if observed_owner_sequence != expected_successor["owner_sequence"]:
        raise AssertionError("source successor owner sequence drift")

    normalized_mesh, group_aliases = _normalize_phase_groups_for_existing_partition(full_mesh, ordered_knuckles)
    allowlist = list(contract["owner_allowlist"])
    outputs: dict[str, dict] = {}
    variant_rows: list[dict] = []

    for spec in contract["variants"]:
        variant = partition_mod._partition_mesh(
            normalized_mesh,
            ordered_knuckles,
            list(spec["owners"]),
            allowlist,
        )
        if variant["knuckle_ids"] != spec["expected_knuckle_ids"]:
            raise AssertionError(f"{spec['id']} knuckle identity drift")
        observed = {
            "knuckles": len(variant["groups"]),
            "vertices": len(variant["vertices"]),
            "triangles": len(variant["faces"]),
        }
        expected = {
            "knuckles": int(spec["expected_knuckles"]),
            "vertices": int(spec["expected_vertices"]),
            "triangles": int(spec["expected_triangles"]),
        }
        if observed != expected:
            raise AssertionError(f"{spec['id']} count drift: {observed} != {expected}")

        mesh_digest = _digest({
            "vertices": variant["vertices"],
            "faces": variant["faces"],
            "groups": variant["groups"],
        })
        old_digest = predecessor["variant_mesh_digests"][spec["id"]]
        changed = mesh_digest != old_digest
        expected_changed = bool(spec["expected_changed_from_successor002"])
        if changed != expected_changed:
            state = "changed" if changed else "unchanged"
            wanted = "changed" if expected_changed else "unchanged"
            raise AssertionError(f"{spec['id']} successor002 relation drift: {state}, expected {wanted}")

        outputs[spec["id"]] = variant
        variant_rows.append({
            "id": spec["id"],
            "owners": variant["owners"],
            "knuckle_ids": variant["knuckle_ids"],
            **observed,
            "mesh_digest": mesh_digest,
            "successor002_mesh_digest": old_digest,
            "changed_from_successor002": changed,
        })

    if len({row["mesh_digest"] for row in variant_rows}) != len(variant_rows):
        raise AssertionError("materially distinct successor003 owner partitions collapsed")

    full_forward = partition_mod._partition_mesh(normalized_mesh, ordered_knuckles, ["body", "lid"], allowlist)
    full_reverse = partition_mod._partition_mesh(normalized_mesh, ordered_knuckles, ["lid", "body"], allowlist)
    if _digest(full_forward) != _digest(full_reverse):
        raise AssertionError("owner selector request order changed canonical successor003 output")

    rows_by_id = {row["id"]: row for row in variant_rows}
    if rows_by_id["body-only"]["changed_from_successor002"]:
        raise AssertionError("body-only identity changed despite frozen zero-phase body geometry")
    if not rows_by_id["lid-only"]["changed_from_successor002"]:
        raise AssertionError("lid-only identity did not capture +15 degree source phase")
    if not rows_by_id["full"]["changed_from_successor002"]:
        raise AssertionError("full identity did not capture +15 degree lid source phase")

    family_digest = _digest(variant_rows)
    if family_digest == predecessor["family_digest"]:
        raise AssertionError("successor003 family identity collapsed to successor002 family")

    summary = {
        "schema": "axm.object-hinge-knuckle-owner-partition-successor003-rebind-summary/v0.1",
        "result": RESULT,
        "decision": DECISION,
        "family_id": contract["family_id"],
        "asset_id": contract["asset_id"],
        "hard_surface_owner_head": contract["hard_surface_owner_head"],
        "donor_git_blobs": donor_blobs,
        "source_successor_result": receipt["result"],
        "source_successor_id": receipt["successor_id"],
        "source_segments": receipt["segments"],
        "source_body_phase_deg": receipt["body_phase_deg"],
        "source_lid_phase_deg": receipt["lid_phase_deg"],
        "source_relative_lid_minus_body_phase_deg": receipt["relative_lid_minus_body_phase_deg"],
        "source_owner_sequence": observed_owner_sequence,
        "source_group_aliases_for_existing_partition_helper": group_aliases,
        "procedural_predecessor": predecessor,
        "variants": variant_rows,
        "materially_distinct_mesh_count": len({row["mesh_digest"] for row in variant_rows}),
        "body_partition_identity_preserved_from_successor002": not rows_by_id["body-only"]["changed_from_successor002"],
        "lid_partition_identity_changed_from_successor002": rows_by_id["lid-only"]["changed_from_successor002"],
        "full_partition_identity_changed_from_successor002": rows_by_id["full"]["changed_from_successor002"],
        "request_order_canonicalization": "PASS_BODY_LID_EQUALS_LID_BODY",
        "family_digest": family_digest,
        "hard_surface_source_successor_rewritten": False,
        "procedural_predecessor_rewritten": False,
        "rig_parenting_authorized": False,
        "visual_acceptance_authorized": False,
        "automatic_downstream_adoption": False,
        "failure_policy": contract["failure_policy"],
        "truth_boundary": contract["truth_boundary"],
    }
    return summary, outputs


def _negative_controls(contract: dict, donor_root: Path, partition_module_path: Path) -> dict[str, str]:
    controls: dict[str, str] = {}

    def expect_hold(name: str, mutated: dict) -> None:
        try:
            build_family(mutated, donor_root, partition_module_path)
        except AssertionError as exc:
            controls[name] = f"HOLD:{exc}"
        else:
            raise AssertionError(f"negative control unexpectedly passed: {name}")

    bad = copy.deepcopy(contract)
    bad["hard_surface_owner_head"] = "0" * 40
    expect_hold("hard_surface_owner_head_drift", bad)

    bad = copy.deepcopy(contract)
    bad["donor_git_blobs"]["successor003_contract"] = "0" * 40
    expect_hold("successor003_contract_blob_drift", bad)

    bad = copy.deepcopy(contract)
    bad["procedural_predecessor"]["family_digest"] = "0" * 64
    expect_hold("procedural_predecessor_digest_drift", bad)

    for key in ("rig_parenting_authorized", "visual_acceptance_authorized", "automatic_downstream_adoption"):
        bad = copy.deepcopy(contract)
        bad["authority"][key] = True
        expect_hold(f"authority_{key}", bad)

    partition_mod = _load_module(partition_module_path, "axm_existing_owner_partition_negative_helper_successor003")
    try:
        partition_mod._validate_selector(["body", "body"], list(contract["owner_allowlist"]))
    except AssertionError as exc:
        controls["duplicate_owner_selector"] = f"HOLD:{exc}"
    else:
        raise AssertionError("duplicate owner selector negative control unexpectedly passed")

    try:
        partition_mod._validate_selector(["frame"], list(contract["owner_allowlist"]))
    except AssertionError as exc:
        controls["unknown_owner_selector"] = f"HOLD:{exc}"
    else:
        raise AssertionError("unknown owner selector negative control unexpectedly passed")

    bad = copy.deepcopy(contract)
    bad["expected_source_successor"]["lid_phase_deg"] = 0.0
    expect_hold("phase_collapse_not_successor003", bad)

    bad = copy.deepcopy(contract)
    for spec in bad["variants"]:
        if spec["id"] == "body-only":
            spec["expected_changed_from_successor002"] = True
    expect_hold("body_partition_false_change_claim", bad)

    bad = copy.deepcopy(contract)
    for spec in bad["variants"]:
        if spec["id"] == "lid-only":
            spec["expected_changed_from_successor002"] = False
    expect_hold("lid_partition_false_stability_claim", bad)

    return controls


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", required=True)
    parser.add_argument("--donor-root", required=True)
    parser.add_argument("--partition-module", default="tools/build_hinge_knuckle_owner_partition_family.py")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    contract_path = Path(args.contract)
    donor_root = Path(args.donor_root)
    partition_module_path = Path(args.partition_module)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    contract = _load_json(contract_path)
    summary, outputs = build_family(contract, donor_root, partition_module_path)
    summary["negative_controls"] = _negative_controls(contract, donor_root, partition_module_path)
    summary["negative_control_count"] = len(summary["negative_controls"])
    summary["contract_blob_sha256"] = hashlib.sha256(contract_path.read_bytes()).hexdigest()
    summary["partition_helper_blob_sha256"] = hashlib.sha256(partition_module_path.read_bytes()).hexdigest()

    for variant_id, mesh in outputs.items():
        (out / f"{variant_id}.mesh.json").write_text(
            json.dumps(mesh, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    (out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(RESULT)
    print(json.dumps({
        "family_digest": summary["family_digest"],
        "variants": [
            {
                "id": row["id"],
                "knuckles": row["knuckles"],
                "vertices": row["vertices"],
                "triangles": row["triangles"],
                "changed_from_successor002": row["changed_from_successor002"],
            }
            for row in summary["variants"]
        ],
        "negative_control_count": summary["negative_control_count"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
