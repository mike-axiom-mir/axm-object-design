from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

SCHEMA = "axm.object-hinge-knuckle-owner-partition-family/v0.1"
RESULT = "PASS_BOUNDED_HINGE_KNUCKLE_OWNER_PARTITION_FAMILY"
DECISION = "PASS_DERIVED_OWNER_PARTITIONS_ONLY__NO_SOURCE_RIG_OR_DOWNSTREAM_ADOPTION"


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
        raise AssertionError(f"cannot import donor module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _validate_selector(owners: list[str], allowlist: list[str]) -> tuple[str, ...]:
    if not owners:
        raise AssertionError("owner selector is empty")
    if len(set(owners)) != len(owners):
        raise AssertionError("duplicate owner selector")
    unknown = sorted(set(owners) - set(allowlist))
    if unknown:
        raise AssertionError(f"unknown owner selector: {unknown}")
    # Canonicalize by declared owner allowlist, not request order.
    return tuple(owner for owner in allowlist if owner in set(owners))


def _partition_mesh(full_mesh: dict, ordered_knuckles: list[dict], owners: list[str], allowlist: list[str]) -> dict:
    selected_owners = _validate_selector(owners, allowlist)
    selected_rows = [row for row in ordered_knuckles if row["owner"] in selected_owners]
    expected_names = [f"hinge_{row['owner']}_{row['id']}_annular_candidate" for row in selected_rows]
    groups_by_name = {group["name"]: group for group in full_mesh["groups"]}
    if len(groups_by_name) != len(full_mesh["groups"]):
        raise AssertionError("duplicate donor mesh group name")
    missing = [name for name in expected_names if name not in groups_by_name]
    if missing:
        raise AssertionError(f"donor mesh group missing: {missing}")

    vertices: list[list[float]] = []
    faces: list[list[int]] = []
    groups: list[dict] = []
    selected_ids: list[str] = []

    for row, name in zip(selected_rows, expected_names):
        group = groups_by_name[name]
        first = int(group["first_face"])
        count = int(group["face_count"])
        source_faces = full_mesh["faces"][first:first + count]
        old_vertices = sorted({int(index) for face in source_faces for index in face})
        remap = {old: len(vertices) + offset for offset, old in enumerate(old_vertices)}
        first_face = len(faces)
        vertices.extend([list(full_mesh["vertices"][old]) for old in old_vertices])
        faces.extend([[remap[int(index)] for index in face] for face in source_faces])
        groups.append({
            "name": name,
            "owner": row["owner"],
            "knuckle_id": row["id"],
            "first_face": first_face,
            "face_count": len(source_faces),
            "vertex_count": len(old_vertices),
        })
        selected_ids.append(row["id"])

    return {
        "owners": list(selected_owners),
        "knuckle_ids": selected_ids,
        "vertices": vertices,
        "faces": faces,
        "groups": groups,
    }


def _validate_authority(contract: dict) -> None:
    authority = contract.get("authority", {})
    required_false = (
        "source_geometry_changed",
        "annular_candidate_adopted",
        "rig_parenting_authorized",
        "animation_authorized",
        "technical_art_adoption_authorized",
        "automatic_downstream_adoption",
    )
    promoted = [key for key in required_false if authority.get(key) is not False]
    if promoted:
        raise AssertionError(f"authority expansion forbidden: {promoted}")


def _verify_donor_identity(contract: dict, donor_root: Path) -> dict:
    if _git(donor_root, "rev-parse", "HEAD") != contract["hard_surface_owner_head"]:
        raise AssertionError("Hard-Surface owner head drift")
    observed_blobs = {}
    for key, rel in contract["donor_paths"].items():
        observed = _git(donor_root, "rev-parse", f"HEAD:{rel}")
        expected = contract["donor_git_blobs"][key]
        if observed != expected:
            raise AssertionError(f"donor blob drift: {key}")
        observed_blobs[key] = observed
    return observed_blobs


def build_family(contract: dict, donor_root: Path) -> tuple[dict, dict[str, dict]]:
    if contract.get("schema") != SCHEMA:
        raise AssertionError(f"unsupported family schema: {contract.get('schema')}")
    _validate_authority(contract)
    donor_blobs = _verify_donor_identity(contract, donor_root)

    paths = {key: donor_root / rel for key, rel in contract["donor_paths"].items()}
    host = _load_json(paths["host"])
    owner_contract = _load_json(paths["owner_stack_contract"])
    bore_contract = _load_json(paths["bore_contract"])
    annular_contract = _load_json(paths["annular_mesh_contract"])

    donor_tools = donor_root / "tools"
    sys.path.insert(0, str(donor_root))
    sys.path.insert(0, str(donor_tools))
    try:
        owner_mod = _load_module(donor_tools / "verify_hinge_knuckle_owner_stack.py", "axm_owner_stack_donor")
        annular_mod = _load_module(donor_tools / "build_hinge_pin_annular_mesh.py", "axm_annular_mesh_donor")
    finally:
        sys.path = [entry for entry in sys.path if entry not in (str(donor_root), str(donor_tools))]

    owner_receipt = owner_mod.evaluate(host, owner_contract, observed_host_sha256=annular_contract["host_source_sha256"])
    annular_receipt, full_mesh = annular_mod.evaluate_mesh(
        host,
        bore_contract,
        annular_contract,
        observed_host_sha256=annular_contract["host_source_sha256"],
        observed_bore_contract_sha256=annular_contract["bore_clearance_contract_sha256"],
    )
    if owner_receipt["result"] != "PASS_SOURCE_OWNED_HINGE_KNUCKLE_OWNER_STACK":
        raise AssertionError("owner-stack prerequisite did not pass")
    if annular_receipt["result"] != "PASS_DERIVED_ANNULAR_KNUCKLE_MESH_FACET_CLEARANCE":
        raise AssertionError("annular-mesh prerequisite did not pass")

    allowlist = list(contract["owner_allowlist"])
    ordered_knuckles = list(owner_contract["ordered_knuckles"])
    outputs: dict[str, dict] = {}
    variant_rows: list[dict] = []
    for spec in contract["variants"]:
        variant = _partition_mesh(full_mesh, ordered_knuckles, list(spec["owners"]), allowlist)
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
        outputs[spec["id"]] = variant
        variant_rows.append({
            "id": spec["id"],
            "owners": variant["owners"],
            "knuckle_ids": variant["knuckle_ids"],
            **observed,
            "mesh_digest": mesh_digest,
        })

    if len({row["mesh_digest"] for row in variant_rows}) != len(variant_rows):
        raise AssertionError("materially distinct owner partitions collapsed to duplicate mesh identities")

    full_forward = _partition_mesh(full_mesh, ordered_knuckles, ["body", "lid"], allowlist)
    full_reverse = _partition_mesh(full_mesh, ordered_knuckles, ["lid", "body"], allowlist)
    if _digest(full_forward) != _digest(full_reverse):
        raise AssertionError("owner-selector request order changed canonical full output")

    family_digest = _digest(variant_rows)
    summary = {
        "schema": "axm.object-hinge-knuckle-owner-partition-family-summary/v0.1",
        "result": RESULT,
        "decision": DECISION,
        "family_id": contract["family_id"],
        "asset_id": contract["asset_id"],
        "hard_surface_owner_head": contract["hard_surface_owner_head"],
        "donor_git_blobs": donor_blobs,
        "owner_stack_result": owner_receipt["result"],
        "annular_mesh_result": annular_receipt["result"],
        "source_owner_sequence": owner_receipt["owner_sequence"],
        "variants": variant_rows,
        "materially_distinct_mesh_count": len({row["mesh_digest"] for row in variant_rows}),
        "request_order_canonicalization": "PASS_BODY_LID_EQUALS_LID_BODY",
        "family_digest": family_digest,
        "source_geometry_changed": False,
        "annular_candidate_adopted": False,
        "rig_parenting_authorized": False,
        "automatic_downstream_adoption": False,
        "failure_policy": contract["failure_policy"],
        "truth_boundary": contract["truth_boundary"],
    }
    return summary, outputs


def _negative_controls(contract: dict, donor_root: Path) -> dict[str, str]:
    controls: dict[str, str] = {}

    def expect_hold(name: str, mutated: dict) -> None:
        try:
            build_family(mutated, donor_root)
        except AssertionError as exc:
            controls[name] = f"HOLD:{exc}"
        else:
            raise AssertionError(f"negative control unexpectedly passed: {name}")

    bad = copy.deepcopy(contract)
    bad["hard_surface_owner_head"] = "0" * 40
    expect_hold("owner_head_drift", bad)

    bad = copy.deepcopy(contract)
    bad["donor_git_blobs"]["owner_stack_contract"] = "0" * 40
    expect_hold("owner_stack_blob_drift", bad)

    bad = copy.deepcopy(contract)
    bad["donor_git_blobs"]["annular_mesh_contract"] = "0" * 40
    expect_hold("annular_contract_blob_drift", bad)

    for key in ("rig_parenting_authorized", "automatic_downstream_adoption"):
        bad = copy.deepcopy(contract)
        bad["authority"][key] = True
        expect_hold(f"authority_{key}", bad)

    try:
        _validate_selector(["body", "body"], list(contract["owner_allowlist"]))
    except AssertionError as exc:
        controls["duplicate_owner_selector"] = f"HOLD:{exc}"
    else:
        raise AssertionError("duplicate selector negative control unexpectedly passed")

    try:
        _validate_selector(["frame"], list(contract["owner_allowlist"]))
    except AssertionError as exc:
        controls["unknown_owner_selector"] = f"HOLD:{exc}"
    else:
        raise AssertionError("unknown selector negative control unexpectedly passed")

    return controls


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", required=True)
    parser.add_argument("--donor-root", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    contract_path = Path(args.contract)
    donor_root = Path(args.donor_root)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    contract = _load_json(contract_path)
    summary, outputs = build_family(contract, donor_root)
    summary["negative_controls"] = _negative_controls(contract, donor_root)
    summary["negative_control_count"] = len(summary["negative_controls"])
    summary["contract_blob_sha256"] = hashlib.sha256(contract_path.read_bytes()).hexdigest()

    for variant_id, mesh in outputs.items():
        (out / f"{variant_id}.mesh.json").write_text(
            json.dumps(mesh, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    (out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(RESULT)
    print(json.dumps({
        "family_digest": summary["family_digest"],
        "variants": [{"id": row["id"], "knuckles": row["knuckles"], "vertices": row["vertices"], "triangles": row["triangles"]} for row in summary["variants"]],
        "negative_control_count": summary["negative_control_count"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
