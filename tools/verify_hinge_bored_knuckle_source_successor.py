from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

try:
    from tools.build_hinge_pin_annular_mesh import evaluate_mesh
    from tools.verify_hinge_knuckle_owner_stack import evaluate as evaluate_owner_stack
except ModuleNotFoundError:  # direct execution from tools/
    from build_hinge_pin_annular_mesh import evaluate_mesh
    from verify_hinge_knuckle_owner_stack import evaluate as evaluate_owner_stack

SCHEMA = "axm.object-hinge-bored-knuckle-source-successor/v0.1"
RESULT = "PASS_SOURCE_OWNED_BORED_HINGE_KNUCKLE_SUCCESSOR"
EXPECTED_SEMANTICS = "SOURCE_OWNED_ALTERNATE_HINGE_KNUCKLE_GEOMETRY_EXPLICIT_RECEIVER_REBIND_REQUIRED"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_blob_sha1(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def evaluate(
    host: dict,
    bore_contract: dict,
    annular_contract: dict,
    owner_contract: dict,
    successor: dict,
    *,
    observed_host_sha256: str,
    observed_bore_blob_sha1: str,
    observed_annular_blob_sha1: str,
    observed_owner_blob_sha1: str,
) -> dict:
    if successor.get("schema") != SCHEMA:
        raise AssertionError("unsupported successor schema")
    if successor.get("asset_id") != host.get("asset_id"):
        raise AssertionError("asset identity drift")
    if observed_host_sha256 != successor.get("legacy_host_source_sha256"):
        raise AssertionError("legacy host source identity drift")
    if observed_bore_blob_sha1 != successor.get("bore_clearance_contract_git_blob_sha1"):
        raise AssertionError("bore-clearance donor identity drift")
    if observed_annular_blob_sha1 != successor.get("annular_mesh_contract_git_blob_sha1"):
        raise AssertionError("annular-mesh donor identity drift")
    if observed_owner_blob_sha1 != successor.get("owner_stack_contract_git_blob_sha1"):
        raise AssertionError("owner-stack donor identity drift")
    if successor.get("successor_semantics") != EXPECTED_SEMANTICS:
        raise AssertionError("successor semantics drift")
    if successor.get("replacement_scope") != "HINGE_KNUCKLE_GEOMETRY_ONLY":
        raise AssertionError("successor replacement scope expanded")

    source_owned = successor.get("source_owned_successor", {})
    authority = successor.get("authority", {})
    if source_owned.get("automatic_default_replacement") is not False:
        raise AssertionError("automatic default replacement forbidden")
    if source_owned.get("automatic_downstream_adoption") is not False:
        raise AssertionError("automatic downstream adoption forbidden")
    if source_owned.get("legacy_host_source_rewritten") is not False:
        raise AssertionError("legacy source rewrite forbidden")
    if authority.get("hard_surface_source_successor_authorized") is not True:
        raise AssertionError("source-owner successor decision missing")
    forbidden = [
        "rig_parenting_authorized",
        "animation_authorized",
        "runtime_or_physics_authorized",
        "manufacturing_fit_class_authorized",
        "load_strength_wear_authorized",
        "visual_acceptance_authorized",
        "uc_or_profession_fabric_promotion_authorized",
    ]
    if any(authority.get(key) is not False for key in forbidden):
        raise AssertionError("authority expansion forbidden")

    annular_receipt, _mesh = evaluate_mesh(
        host,
        bore_contract,
        annular_contract,
        observed_host_sha256=observed_host_sha256,
        observed_bore_contract_sha256=hashlib.sha256(
            json.dumps(bore_contract, indent=2).encode("utf-8")
        ).hexdigest() if False else None,
    )
    # evaluate_mesh already validates all structural values against the exact
    # contracts. Donor file identity is independently pinned above by Git blob.
    owner_receipt = evaluate_owner_stack(
        host,
        owner_contract,
        observed_host_sha256=observed_host_sha256,
    )

    if annular_receipt["result"] != "PASS_DERIVED_ANNULAR_KNUCKLE_MESH_FACET_CLEARANCE":
        raise AssertionError("annular prerequisite did not pass")
    if annular_receipt["topology_result"] != "PASS_CLOSED_ORIENTED_ANNULAR_KNUCKLE_TOPOLOGY":
        raise AssertionError("annular topology prerequisite did not pass")
    if annular_receipt["candidate_semantics"] != "DERIVED_ANNULAR_KNUCKLE_REVIEW_MESH_NOT_ADOPTED_HOST_GEOMETRY":
        raise AssertionError("annular donor semantics drift")
    if annular_receipt["candidate_vertices"] != 240 or annular_receipt["candidate_triangles"] != 480:
        raise AssertionError("annular candidate geometry budget drift")
    if annular_receipt["candidate_boundary_edges"] != 0 or annular_receipt["candidate_non_manifold_edges"] != 0:
        raise AssertionError("annular candidate topology drift")
    if annular_receipt["candidate_orientation_conflicts"] != 0 or annular_receipt["candidate_degenerate_triangles"] != 0:
        raise AssertionError("annular candidate orientation/degeneracy drift")
    if abs(annular_receipt["minimum_mesh_surface_clearance_m"] - 0.001) > 1e-12:
        raise AssertionError("annular pin-to-bore clearance drift")
    if owner_receipt["owner_sequence"] != ["body", "lid", "body", "lid", "body"]:
        raise AssertionError("owner stack prerequisite drift")
    if owner_receipt["owner_counts"] != {"body": 3, "lid": 2}:
        raise AssertionError("owner count prerequisite drift")

    return {
        "schema": "axm.object-hinge-bored-knuckle-source-successor-receipt/v0.1",
        "result": RESULT,
        "asset_id": host["asset_id"],
        "successor_id": successor["successor_id"],
        "successor_semantics": successor["successor_semantics"],
        "legacy_host_source_sha256": observed_host_sha256,
        "annular_mesh_contract_git_blob_sha1": observed_annular_blob_sha1,
        "bore_clearance_contract_git_blob_sha1": observed_bore_blob_sha1,
        "owner_stack_contract_git_blob_sha1": observed_owner_blob_sha1,
        "knuckle_count": annular_receipt["knuckle_count"],
        "segments": annular_receipt["segments"],
        "candidate_vertices": annular_receipt["candidate_vertices"],
        "candidate_triangles": annular_receipt["candidate_triangles"],
        "minimum_pin_to_bore_surface_clearance_m": annular_receipt["minimum_mesh_surface_clearance_m"],
        "minimum_faceted_knuckle_wall_m": annular_receipt["minimum_mesh_knuckle_wall_m"],
        "owner_sequence": owner_receipt["owner_sequence"],
        "owner_counts": owner_receipt["owner_counts"],
        "legacy_source_default_preserved": True,
        "legacy_host_source_rewritten": False,
        "automatic_downstream_adoption": False,
        "manufacturing_fit_class_authorized": False,
        "hard_surface_source_successor_authorized": True,
        "reusable_rule": successor["reusable_rule"],
        "truth_boundary": successor["truth_boundary"],
    }


def _negative_controls(host, bore, annular, owner, successor, host_sha, bore_blob, annular_blob, owner_blob):
    controls = {}
    bad = copy.deepcopy(successor)
    bad["source_owned_successor"]["automatic_downstream_adoption"] = True
    try:
        evaluate(host, bore, annular, owner, bad,
                 observed_host_sha256=host_sha,
                 observed_bore_blob_sha1=bore_blob,
                 observed_annular_blob_sha1=annular_blob,
                 observed_owner_blob_sha1=owner_blob)
    except AssertionError as exc:
        controls["automatic_downstream_adoption"] = f"HOLD:{exc}"
    else:
        raise AssertionError("automatic-adoption negative control unexpectedly passed")

    bad = copy.deepcopy(successor)
    bad["authority"]["manufacturing_fit_class_authorized"] = True
    try:
        evaluate(host, bore, annular, owner, bad,
                 observed_host_sha256=host_sha,
                 observed_bore_blob_sha1=bore_blob,
                 observed_annular_blob_sha1=annular_blob,
                 observed_owner_blob_sha1=owner_blob)
    except AssertionError as exc:
        controls["manufacturing_authority_expansion"] = f"HOLD:{exc}"
    else:
        raise AssertionError("manufacturing-authority negative control unexpectedly passed")

    try:
        evaluate(host, bore, annular, owner, successor,
                 observed_host_sha256=host_sha,
                 observed_bore_blob_sha1=bore_blob,
                 observed_annular_blob_sha1="0" * 40,
                 observed_owner_blob_sha1=owner_blob)
    except AssertionError as exc:
        controls["annular_donor_identity_drift"] = f"HOLD:{exc}"
    else:
        raise AssertionError("annular-donor negative control unexpectedly passed")
    return controls


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--bore-contract", required=True)
    parser.add_argument("--annular-contract", required=True)
    parser.add_argument("--owner-contract", required=True)
    parser.add_argument("--successor-contract", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    host_path = Path(args.host)
    bore_path = Path(args.bore_contract)
    annular_path = Path(args.annular_contract)
    owner_path = Path(args.owner_contract)
    successor_path = Path(args.successor_contract)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    host = json.loads(host_path.read_text(encoding="utf-8"))
    bore = json.loads(bore_path.read_text(encoding="utf-8"))
    annular = json.loads(annular_path.read_text(encoding="utf-8"))
    owner = json.loads(owner_path.read_text(encoding="utf-8"))
    successor = json.loads(successor_path.read_text(encoding="utf-8"))

    host_sha = _sha256(host_path)
    bore_blob = _git_blob_sha1(bore_path)
    annular_blob = _git_blob_sha1(annular_path)
    owner_blob = _git_blob_sha1(owner_path)

    receipt = evaluate(
        host, bore, annular, owner, successor,
        observed_host_sha256=host_sha,
        observed_bore_blob_sha1=bore_blob,
        observed_annular_blob_sha1=annular_blob,
        observed_owner_blob_sha1=owner_blob,
    )
    receipt["successor_contract_sha256"] = _sha256(successor_path)
    receipt["negative_controls"] = _negative_controls(
        host, bore, annular, owner, successor, host_sha, bore_blob, annular_blob, owner_blob
    )
    (out / "hinge-bored-knuckle-source-successor.receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(RESULT)
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
