from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

SCHEMA = "axm.object-hinge-knuckle-owner-partition-successor-rebind/v0.1"
RESULT = "PASS_BOUNDED_HINGE_KNUCKLE_OWNER_PARTITION_SUCCESSOR002_REBIND"
DECISION = "PASS_EXACT_SUCCESSOR002_OWNER_PARTITIONS__PREDECESSOR_FAMILY_PRESERVED__NO_SOURCE_RIG_OR_DOWNSTREAM_ADOPTION"
EXPECTED_PREDECESSOR_HEAD = "e08b5aacd97e16f3fe8feea4995db2d0885b68a2"
EXPECTED_PREDECESSOR_FAMILY_DIGEST = "39973aae8bc433b92a4d84152e5e16f0bf916a8f6aef4d9db69050569b145522"


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
        "rig_parenting_authorized",
        "animation_authorized",
        "technical_art_adoption_authorized",
        "runtime_or_physics_authorized",
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
    observed = set(predecessor.get("variant_mesh_digests", {}))
    if observed != expected:
        raise AssertionError("Procedural predecessor variant identity set drift")
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


def _load_donor_successor(contract: dict, donor_root: Path) -> tuple[dict, dict, dict, dict, dict, dict, object]:
    paths = {key: donor_root / rel for key, rel in contract["donor_paths"].items()}
    host = _load_json(paths["host"])
    owner = _load_json(paths["owner_stack_contract"])
    bore = _load_json(paths["bore_contract"])
    annular = _load_json(paths["annular_mesh_contract"])
    predecessor_successor = _load_json(paths["predecessor_successor_contract"])
    successor = _load_json(paths["phase_invariant_successor_contract"])

    donor_root_text = str(donor_root.resolve())
    donor_tools_text = str((donor_root / "tools").resolve())
    original_path = list(sys.path)
    sys.path.insert(0, donor_root_text)
    sys.path.insert(0, donor_tools_text)
    try:
        verifier = _load_module(
            paths["phase_invariant_successor_verifier"],
            "axm_hard_surface_phase_invariant_successor_donor",
        )
    finally:
        sys.path[:] = original_path
    return host, owner, bore, annular, predecessor_successor, successor, verifier


def build_family(contract: dict, donor_root: Path, partition_module_path: Path) -> tuple[dict, dict[str, dict]]:
    if contract.get("schema") != SCHEMA:
        raise AssertionError(f"unsupported family schema: {contract.get('schema')}")
    _validate_authority(contract)
    predecessor = _validate_predecessor(contract)
    donor_blobs = _verify_donor_identity(contract, donor_root)

    host, owner_contract, bore_contract, annular_contract, predecessor_successor, successor, verifier = _load_donor_successor(contract, donor_root)
    partition_mod = _load_module(partition_module_path, "axm_existing_owner_partition_helper")

    receipt, full_mesh = verifier.evaluate(
        host,
        bore_contract,
        annular_contract,
        owner_contract,
        predecessor_successor,
        successor,
        observed_host_sha256=successor["legacy_host_source_sha256"],
        observed_bore_blob_sha1=donor_blobs["bore_contract"],
        observed_annular_blob_sha1=donor_blobs["annular_mesh_contract"],
        observed_owner_blob_sha1=donor_blobs["owner_stack_contract"],
        observed_predecessor_successor_blob_sha1=donor_blobs["predecessor_successor_contract"],
    )
    if receipt.get("result") != "PASS_SOURCE_OWNED_PHASE_INVARIANT_BORED_HINGE_KNUCKLE_SUCCESSOR":
        raise AssertionError("phase-invariant Hard-Surface prerequisite did not pass")

    expected_successor = contract["expected_source_successor"]
    if receipt.get("successor_id") != expected_successor["successor_id"]:
        raise AssertionError("source successor identity drift")
    if abs(float(receipt["successor_bore_circumradius_m"]) - float(expected_successor["bore_circumradius_m"])) > 1e-12:
        raise AssertionError("successor bore radius drift")
    if float(receipt["successor_phase_independent_radial_clearance_m"]) < float(expected_successor["minimum_phase_independent_radial_clearance_m"]) - 1e-12:
        raise AssertionError("successor phase-independent clearance below bound")
    if receipt.get("owner_sequence") != expected_successor["owner_sequence"]:
        raise AssertionError("successor owner sequence drift")

    ordered_knuckles = list(owner_contract["ordered_knuckles"])
    allowlist = list(contract["owner_allowlist"])
    outputs: dict[str, dict] = {}
    variant_rows: list[dict] = []
    changed_from_predecessor: dict[str, bool] = {}

    for spec in contract["variants"]:
        variant = partition_mod._partition_mesh(full_mesh, ordered_knuckles, list(spec["owners"]), allowlist)
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
        if mesh_digest == old_digest:
            raise AssertionError(f"{spec['id']} did not rebind to changed successor geometry")
        changed_from_predecessor[spec["id"]] = True
        outputs[spec["id"]] = variant
        variant_rows.append({
            "id": spec["id"],
            "owners": variant["owners"],
            "knuckle_ids": variant["knuckle_ids"],
            **observed,
            "mesh_digest": mesh_digest,
            "predecessor_mesh_digest": old_digest,
            "changed_from_predecessor": True,
        })

    if len({row["mesh_digest"] for row in variant_rows}) != len(variant_rows):
        raise AssertionError("materially distinct successor owner partitions collapsed")

    full_forward = partition_mod._partition_mesh(full_mesh, ordered_knuckles, ["body", "lid"], allowlist)
    full_reverse = partition_mod._partition_mesh(full_mesh, ordered_knuckles, ["lid", "body"], allowlist)
    if _digest(full_forward) != _digest(full_reverse):
        raise AssertionError("owner selector request order changed canonical successor output")

    family_digest = _digest(variant_rows)
    if family_digest == predecessor["family_digest"]:
        raise AssertionError("successor family identity collapsed to predecessor family")

    summary = {
        "schema": "axm.object-hinge-knuckle-owner-partition-successor-rebind-summary/v0.1",
        "result": RESULT,
        "decision": DECISION,
        "family_id": contract["family_id"],
        "asset_id": contract["asset_id"],
        "hard_surface_owner_head": contract["hard_surface_owner_head"],
        "donor_git_blobs": donor_blobs,
        "source_successor_result": receipt["result"],
        "source_successor_id": receipt["successor_id"],
        "successor_bore_circumradius_m": receipt["successor_bore_circumradius_m"],
        "successor_phase_independent_radial_clearance_m": receipt["successor_phase_independent_radial_clearance_m"],
        "source_owner_sequence": receipt["owner_sequence"],
        "procedural_predecessor": predecessor,
        "variants": variant_rows,
        "materially_distinct_mesh_count": len({row["mesh_digest"] for row in variant_rows}),
        "all_variants_changed_from_predecessor": all(changed_from_predecessor.values()),
        "request_order_canonicalization": "PASS_BODY_LID_EQUALS_LID_BODY",
        "family_digest": family_digest,
        "hard_surface_source_successor_rewritten": False,
        "procedural_predecessor_rewritten": False,
        "rig_parenting_authorized": False,
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
    bad["donor_git_blobs"]["phase_invariant_successor_contract"] = "0" * 40
    expect_hold("successor_contract_blob_drift", bad)

    bad = copy.deepcopy(contract)
    bad["procedural_predecessor"]["family_digest"] = "0" * 64
    expect_hold("procedural_predecessor_digest_drift", bad)

    for key in ("rig_parenting_authorized", "automatic_downstream_adoption"):
        bad = copy.deepcopy(contract)
        bad["authority"][key] = True
        expect_hold(f"authority_{key}", bad)

    partition_mod = _load_module(partition_module_path, "axm_existing_owner_partition_negative_helper")
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
    bad["expected_source_successor"]["bore_circumradius_m"] = 0.010035276180410082
    expect_hold("predecessor_bore_not_successor002", bad)

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
                "changed_from_predecessor": row["changed_from_predecessor"],
            }
            for row in summary["variants"]
        ],
        "negative_control_count": summary["negative_control_count"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
