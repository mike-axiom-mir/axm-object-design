from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path

try:
    from tools.build_hinge_pin_annular_mesh import _build_candidate, _inspect_face_range, _write_obj
    from tools.verify_hinge_bored_knuckle_source_successor import (
        _git_blob_sha1,
        _sha256,
        evaluate as evaluate_predecessor,
    )
except ModuleNotFoundError:  # direct execution from tools/
    from build_hinge_pin_annular_mesh import _build_candidate, _inspect_face_range, _write_obj
    from verify_hinge_bored_knuckle_source_successor import (
        _git_blob_sha1,
        _sha256,
        evaluate as evaluate_predecessor,
    )

SCHEMA = "axm.object-hinge-bored-knuckle-phase-invariant-source-successor/v0.1"
RESULT = "PASS_SOURCE_OWNED_PHASE_INVARIANT_BORED_HINGE_KNUCKLE_SUCCESSOR"
EXPECTED_SEMANTICS = "SOURCE_OWNED_ALTERNATE_PHASE_INVARIANT_HINGE_KNUCKLE_GEOMETRY_EXPLICIT_RECEIVER_REBIND_REQUIRED"
EXPECTED_SCOPE = "CONCENTRIC_REGULAR_12_GON_RADIAL_CROSS_SECTION_ONLY"
EXPECTED_PREDECESSOR_HEAD = "178d93e8976a741271d7f47ab4865519de925657"
EXPECTED_RIGGING_HEAD = "38f32efe4a1b053f77255c31bee021646156e4ad"
EXPECTED_RIGGING_WORKFLOW = 35291646970


def _close(a: float, b: float, tol: float = 1e-12) -> bool:
    return abs(a - b) <= tol


def _expected_phase_invariant_bore_radius(pin_circumradius: float, minimum_radial_clearance: float, segments: int) -> float:
    # For any relative phase, the regular bore contains its centered incircle.
    # The regular pin is contained by its circumcircle. Requiring the bore
    # inradius minus pin circumradius to meet the declared gap is therefore a
    # phase-independent radial lower bound.
    return (pin_circumradius + minimum_radial_clearance) / math.cos(math.pi / segments)


def evaluate(
    host: dict,
    bore_contract: dict,
    annular_contract: dict,
    owner_contract: dict,
    predecessor_successor: dict,
    successor: dict,
    *,
    observed_host_sha256: str,
    observed_bore_blob_sha1: str,
    observed_annular_blob_sha1: str,
    observed_owner_blob_sha1: str,
    observed_predecessor_successor_blob_sha1: str,
) -> tuple[dict, dict]:
    if successor.get("schema") != SCHEMA:
        raise AssertionError("unsupported phase-invariant successor schema")
    if successor.get("asset_id") != host.get("asset_id"):
        raise AssertionError("asset identity drift")
    if observed_host_sha256 != successor.get("legacy_host_source_sha256"):
        raise AssertionError("legacy host source identity drift")
    if successor.get("predecessor_successor_head") != EXPECTED_PREDECESSOR_HEAD:
        raise AssertionError("predecessor successor head drift")
    if observed_predecessor_successor_blob_sha1 != successor.get("predecessor_successor_contract_git_blob_sha1"):
        raise AssertionError("predecessor successor identity drift")
    if observed_bore_blob_sha1 != successor.get("predecessor_bore_clearance_contract_git_blob_sha1"):
        raise AssertionError("predecessor bore-clearance identity drift")
    if observed_annular_blob_sha1 != successor.get("predecessor_annular_mesh_contract_git_blob_sha1"):
        raise AssertionError("predecessor annular identity drift")
    if observed_owner_blob_sha1 != successor.get("owner_stack_contract_git_blob_sha1"):
        raise AssertionError("owner-stack identity drift")
    if successor.get("successor_semantics") != EXPECTED_SEMANTICS:
        raise AssertionError("phase-invariant successor semantics drift")
    if successor.get("replacement_scope") != "HINGE_KNUCKLE_BORE_GEOMETRY_ONLY":
        raise AssertionError("phase-invariant successor replacement scope expanded")
    if successor.get("phase_invariant_claim_scope") != EXPECTED_SCOPE:
        raise AssertionError("phase-invariant claim scope drift")

    rigging_return = successor.get("rigging_return", {})
    if rigging_return.get("exact_head") != EXPECTED_RIGGING_HEAD:
        raise AssertionError("Rigging return head drift")
    if rigging_return.get("workflow") != EXPECTED_RIGGING_WORKFLOW:
        raise AssertionError("Rigging return workflow drift")

    predecessor_receipt = evaluate_predecessor(
        host,
        bore_contract,
        annular_contract,
        owner_contract,
        predecessor_successor,
        observed_host_sha256=observed_host_sha256,
        observed_bore_blob_sha1=observed_bore_blob_sha1,
        observed_annular_blob_sha1=observed_annular_blob_sha1,
        observed_owner_blob_sha1=observed_owner_blob_sha1,
    )
    if predecessor_receipt.get("result") != "PASS_SOURCE_OWNED_BORED_HINGE_KNUCKLE_SUCCESSOR":
        raise AssertionError("predecessor source-successor prerequisite did not pass")

    source_owned = successor.get("source_owned_successor", {})
    authority = successor.get("authority", {})
    if source_owned.get("automatic_default_replacement") is not False:
        raise AssertionError("automatic default replacement forbidden")
    if source_owned.get("automatic_downstream_adoption") is not False:
        raise AssertionError("automatic downstream adoption forbidden")
    if source_owned.get("legacy_host_source_rewritten") is not False:
        raise AssertionError("legacy source rewrite forbidden")
    if source_owned.get("predecessor_source_successor_rewritten") is not False:
        raise AssertionError("predecessor source-successor rewrite forbidden")
    if source_owned.get("pin_relative_axial_phase") != "UNSPECIFIED":
        raise AssertionError("pin relative axial phase must remain unspecified")
    if source_owned.get("pin_physical_owner") != "UNSPECIFIED":
        raise AssertionError("pin physical owner must remain unspecified")
    if authority.get("hard_surface_source_successor_authorized") is not True:
        raise AssertionError("source-owner successor decision missing")
    forbidden = [
        "rig_parenting_authorized",
        "animation_authorized",
        "runtime_or_physics_authorized",
        "manufacturing_fit_class_authorized",
        "bearing_friction_lubrication_authorized",
        "load_strength_wear_authorized",
        "visual_acceptance_authorized",
        "uc_or_profession_fabric_promotion_authorized",
    ]
    if any(authority.get(key) is not False for key in forbidden):
        raise AssertionError("authority expansion forbidden")

    hinge = host["hinge"]
    segments = int(hinge["segments"])
    pin_radius = float(hinge["pin_radius"])
    outer_radius = float(hinge["knuckle_radius"])
    if segments != int(source_owned["segments"]) or segments != 12:
        raise AssertionError("source segmentation drift")
    if not _close(pin_radius, float(source_owned["source_pin_circumradius_m"])):
        raise AssertionError("source pin radius drift")
    if not _close(outer_radius, float(source_owned["knuckle_outer_circumradius_m"])):
        raise AssertionError("knuckle outer radius drift")

    minimum_phase_clearance = float(source_owned["minimum_phase_independent_radial_clearance_m"])
    bore_radius = float(source_owned["bore_circumradius_m"])
    expected_bore_radius = _expected_phase_invariant_bore_radius(pin_radius, minimum_phase_clearance, segments)
    if not _close(bore_radius, expected_bore_radius):
        raise AssertionError("phase-invariant bore radius drift")

    facet_factor = math.cos(math.pi / segments)
    old_bore_radius = float(annular_contract["mesh_bore_radius_m"])
    old_phase_clearance = old_bore_radius * facet_factor - pin_radius
    phase_independent_clearance = bore_radius * facet_factor - pin_radius
    same_phase_clearance = (bore_radius - pin_radius) * facet_factor
    minimum_faceted_wall = (outer_radius - bore_radius) * facet_factor

    if not _close(
        old_phase_clearance,
        float(rigging_return["predecessor_phase_independent_radial_clearance_m"]),
    ):
        raise AssertionError("Rigging predecessor clearance return drift")
    if not _close(
        expected_bore_radius,
        float(rigging_return["required_bore_circumradius_for_0_001m_phase_independent_clearance_m"]),
    ):
        raise AssertionError("Rigging required bore return drift")
    if phase_independent_clearance < minimum_phase_clearance - 1e-12:
        raise AssertionError("phase-independent radial clearance below contract")
    if not _close(same_phase_clearance, float(source_owned["same_phase_radial_clearance_m"])):
        raise AssertionError("same-phase clearance drift")
    if minimum_faceted_wall < float(source_owned["minimum_required_faceted_knuckle_wall_m"]) - 1e-12:
        raise AssertionError("faceted knuckle wall below contract")
    if bore_radius <= old_bore_radius:
        raise AssertionError("phase-invariant successor does not enlarge predecessor bore")
    if bore_radius >= outer_radius:
        raise AssertionError("phase-invariant bore consumes knuckle shell")

    mesh, groups = _build_candidate(host, {"mesh_bore_radius_m": bore_radius})
    group_receipts = []
    for group in groups:
        topology = _inspect_face_range(mesh, group["first_face"], group["face_count"])
        if topology["boundary_edges"] != 0:
            raise AssertionError(f"{group['name']} has boundary edges")
        if topology["non_manifold_edges"] != 0:
            raise AssertionError(f"{group['name']} has non-manifold edges")
        if topology["orientation_conflicts"] != 0:
            raise AssertionError(f"{group['name']} has orientation conflicts")
        if topology["degenerate_triangles"] != 0:
            raise AssertionError(f"{group['name']} has degenerate triangles")
        if topology["triangle_components"] != 1:
            raise AssertionError(f"{group['name']} is not one edge-connected shell")
        group_receipts.append({"name": group["name"], **topology})

    aggregate = _inspect_face_range(mesh, 0, len(mesh["faces"]))
    if aggregate["triangle_components"] != len(groups):
        raise AssertionError("aggregate phase-invariant successor component count drift")
    if aggregate["boundary_edges"] or aggregate["non_manifold_edges"]:
        raise AssertionError("aggregate phase-invariant successor manifold topology drift")
    if aggregate["orientation_conflicts"] or aggregate["degenerate_triangles"]:
        raise AssertionError("aggregate phase-invariant successor orientation/degeneracy drift")

    owner_sequence = predecessor_receipt["owner_sequence"]
    if owner_sequence != ["body", "lid", "body", "lid", "body"]:
        raise AssertionError("owner-stack prerequisite drift")

    receipt = {
        "schema": "axm.object-hinge-bored-knuckle-phase-invariant-source-successor-receipt/v0.1",
        "result": RESULT,
        "asset_id": host["asset_id"],
        "successor_id": successor["successor_id"],
        "successor_semantics": successor["successor_semantics"],
        "phase_invariant_claim_scope": successor["phase_invariant_claim_scope"],
        "legacy_host_source_sha256": observed_host_sha256,
        "predecessor_successor_head": successor["predecessor_successor_head"],
        "predecessor_successor_contract_git_blob_sha1": observed_predecessor_successor_blob_sha1,
        "rigging_return_head": rigging_return["exact_head"],
        "rigging_return_workflow": rigging_return["workflow"],
        "segments": segments,
        "knuckle_count": len(groups),
        "owner_sequence": owner_sequence,
        "source_pin_circumradius_m": pin_radius,
        "source_knuckle_outer_circumradius_m": outer_radius,
        "predecessor_bore_circumradius_m": old_bore_radius,
        "successor_bore_circumradius_m": bore_radius,
        "bore_circumradius_increase_m": bore_radius - old_bore_radius,
        "predecessor_phase_independent_radial_clearance_m": old_phase_clearance,
        "successor_phase_independent_radial_clearance_m": phase_independent_clearance,
        "phase_independent_clearance_increase_m": phase_independent_clearance - old_phase_clearance,
        "successor_same_phase_radial_clearance_m": same_phase_clearance,
        "successor_minimum_faceted_knuckle_wall_m": minimum_faceted_wall,
        "candidate_vertices": len(mesh["vertices"]),
        "candidate_triangles": len(mesh["faces"]),
        "candidate_triangle_components": aggregate["triangle_components"],
        "candidate_boundary_edges": aggregate["boundary_edges"],
        "candidate_non_manifold_edges": aggregate["non_manifold_edges"],
        "candidate_orientation_conflicts": aggregate["orientation_conflicts"],
        "candidate_degenerate_triangles": aggregate["degenerate_triangles"],
        "knuckle_topology": group_receipts,
        "pin_relative_axial_phase": source_owned["pin_relative_axial_phase"],
        "pin_physical_owner": source_owned["pin_physical_owner"],
        "legacy_source_default_preserved": True,
        "predecessor_successor_preserved": True,
        "automatic_downstream_adoption": False,
        "manufacturing_fit_class_authorized": False,
        "hard_surface_source_successor_authorized": True,
        "reusable_rule": successor["reusable_rule"],
        "truth_boundary": successor["truth_boundary"],
    }
    return receipt, mesh


def _negative_controls(host, bore, annular, owner, predecessor, successor, host_sha, bore_blob, annular_blob, owner_blob, predecessor_blob):
    controls = {}

    bad = copy.deepcopy(successor)
    bad["source_owned_successor"]["bore_circumradius_m"] = float(annular["mesh_bore_radius_m"])
    try:
        evaluate(host, bore, annular, owner, predecessor, bad,
                 observed_host_sha256=host_sha,
                 observed_bore_blob_sha1=bore_blob,
                 observed_annular_blob_sha1=annular_blob,
                 observed_owner_blob_sha1=owner_blob,
                 observed_predecessor_successor_blob_sha1=predecessor_blob)
    except AssertionError as exc:
        controls["predecessor_bore_not_phase_invariant"] = f"HOLD:{exc}"
    else:
        raise AssertionError("predecessor-bore negative control unexpectedly passed")

    bad = copy.deepcopy(successor)
    bad["source_owned_successor"]["automatic_downstream_adoption"] = True
    try:
        evaluate(host, bore, annular, owner, predecessor, bad,
                 observed_host_sha256=host_sha,
                 observed_bore_blob_sha1=bore_blob,
                 observed_annular_blob_sha1=annular_blob,
                 observed_owner_blob_sha1=owner_blob,
                 observed_predecessor_successor_blob_sha1=predecessor_blob)
    except AssertionError as exc:
        controls["automatic_downstream_adoption"] = f"HOLD:{exc}"
    else:
        raise AssertionError("automatic-adoption negative control unexpectedly passed")

    bad = copy.deepcopy(successor)
    bad["source_owned_successor"]["pin_relative_axial_phase"] = "FIXED_TO_BODY"
    try:
        evaluate(host, bore, annular, owner, predecessor, bad,
                 observed_host_sha256=host_sha,
                 observed_bore_blob_sha1=bore_blob,
                 observed_annular_blob_sha1=annular_blob,
                 observed_owner_blob_sha1=owner_blob,
                 observed_predecessor_successor_blob_sha1=predecessor_blob)
    except AssertionError as exc:
        controls["invented_pin_phase"] = f"HOLD:{exc}"
    else:
        raise AssertionError("invented-pin-phase negative control unexpectedly passed")

    bad = copy.deepcopy(successor)
    bad["authority"]["manufacturing_fit_class_authorized"] = True
    try:
        evaluate(host, bore, annular, owner, predecessor, bad,
                 observed_host_sha256=host_sha,
                 observed_bore_blob_sha1=bore_blob,
                 observed_annular_blob_sha1=annular_blob,
                 observed_owner_blob_sha1=owner_blob,
                 observed_predecessor_successor_blob_sha1=predecessor_blob)
    except AssertionError as exc:
        controls["manufacturing_authority_expansion"] = f"HOLD:{exc}"
    else:
        raise AssertionError("manufacturing-authority negative control unexpectedly passed")

    try:
        evaluate(host, bore, annular, owner, predecessor, successor,
                 observed_host_sha256=host_sha,
                 observed_bore_blob_sha1=bore_blob,
                 observed_annular_blob_sha1=annular_blob,
                 observed_owner_blob_sha1=owner_blob,
                 observed_predecessor_successor_blob_sha1="0" * 40)
    except AssertionError as exc:
        controls["predecessor_successor_identity_drift"] = f"HOLD:{exc}"
    else:
        raise AssertionError("predecessor-successor identity negative control unexpectedly passed")

    return controls


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--bore-contract", required=True)
    parser.add_argument("--annular-contract", required=True)
    parser.add_argument("--owner-contract", required=True)
    parser.add_argument("--predecessor-successor-contract", required=True)
    parser.add_argument("--phase-invariant-successor-contract", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    host_path = Path(args.host)
    bore_path = Path(args.bore_contract)
    annular_path = Path(args.annular_contract)
    owner_path = Path(args.owner_contract)
    predecessor_path = Path(args.predecessor_successor_contract)
    successor_path = Path(args.phase_invariant_successor_contract)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    host = json.loads(host_path.read_text(encoding="utf-8"))
    bore = json.loads(bore_path.read_text(encoding="utf-8"))
    annular = json.loads(annular_path.read_text(encoding="utf-8"))
    owner = json.loads(owner_path.read_text(encoding="utf-8"))
    predecessor = json.loads(predecessor_path.read_text(encoding="utf-8"))
    successor = json.loads(successor_path.read_text(encoding="utf-8"))

    host_sha = _sha256(host_path)
    bore_blob = _git_blob_sha1(bore_path)
    annular_blob = _git_blob_sha1(annular_path)
    owner_blob = _git_blob_sha1(owner_path)
    predecessor_blob = _git_blob_sha1(predecessor_path)

    receipt, mesh = evaluate(
        host, bore, annular, owner, predecessor, successor,
        observed_host_sha256=host_sha,
        observed_bore_blob_sha1=bore_blob,
        observed_annular_blob_sha1=annular_blob,
        observed_owner_blob_sha1=owner_blob,
        observed_predecessor_successor_blob_sha1=predecessor_blob,
    )
    receipt["successor_contract_sha256"] = _sha256(successor_path)
    receipt["negative_controls"] = _negative_controls(
        host, bore, annular, owner, predecessor, successor,
        host_sha, bore_blob, annular_blob, owner_blob, predecessor_blob,
    )

    (out / "hinge-bored-knuckle-phase-invariant-source-successor.receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _write_obj(out / "hinge-bored-knuckle-phase-invariant-source-successor.obj", mesh)
    print(RESULT)
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
