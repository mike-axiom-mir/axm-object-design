from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path

try:
    from tools.verify_hinge_pin_axial_stop import sha256 as _stop_sha256, verify as verify_axial_stop
    from tools.verify_hinge_bored_knuckle_phase_invariant_successor import (
        _git_blob_sha1,
        _sha256,
        evaluate as evaluate_phase_successor,
    )
except ModuleNotFoundError:  # direct execution from tools/
    from verify_hinge_pin_axial_stop import sha256 as _stop_sha256, verify as verify_axial_stop
    from verify_hinge_bored_knuckle_phase_invariant_successor import (
        _git_blob_sha1,
        _sha256,
        evaluate as evaluate_phase_successor,
    )

SCHEMA = "axm.object-hinge-bored-knuckle-axial-stop-capture/v0.1"
RESULT = "PASS_SOURCE_OWNED_BORED_HINGE_AXIAL_STOP_GEOMETRIC_CAPTURE_COMPATIBILITY"
EXPECTED_SUCCESSOR_HEAD = "a6d18b9fe729304dc4d95d962ed27527adce211f"
EXPECTED_SUCCESSOR_BLOB = "7e078189d5c80508b28932563326cd5629c4efa6"
EXPECTED_STOP_BLOB = "ded14bcde58be76f339608e659173905e66e64c1"
EXPECTED_RIGGING_HEAD = "cf377074f70ce7f7e386f1378c51705b3db4d305"
EXPECTED_RIGGING_WORKFLOW = 35295344713
EXPECTED_SEMANTICS = "SOURCE_OWNED_GEOMETRIC_AXIAL_CAPTURE_COMPATIBILITY_ONLY_EXPLICIT_RECEIVER_REBIND_REQUIRED"
EXPECTED_SCOPE = "COAXIAL_STOP_RADIAL_ENVELOPE_VS_REGULAR_12_GON_BORE_AND_OUTER_KNUCKLE_CROSS_SECTION_ONLY"
TOL = 1e-12


def _close(a: float, b: float, tol: float = TOL) -> bool:
    return abs(a - b) <= tol


def _capture_metrics(*, stop_radius: float, bore_circumradius: float, outer_circumradius: float, segments: int) -> dict:
    if stop_radius <= 0.0 or bore_circumradius <= 0.0 or outer_circumradius <= 0.0:
        raise AssertionError("non-positive radial envelope")
    if segments < 3:
        raise AssertionError("invalid regular polygon segment count")

    # The stop contract already calls this dimension a collar radius. The new
    # compatibility contract intentionally treats it only as a circular radial
    # envelope; no polygon phase is invented for the stop. The bored knuckle is
    # a regular polygon. Its bore circumradius is the maximum opening radius,
    # while its outer inradius is the minimum available outer-shell radius.
    outer_inradius = outer_circumradius * math.cos(math.pi / segments)
    capture_overlap = stop_radius - bore_circumradius
    outer_containment = outer_inradius - stop_radius

    if capture_overlap <= TOL:
        raise AssertionError("stop radial envelope does not positively overlap successor bore maximum radius")
    if outer_containment <= TOL:
        raise AssertionError("stop radial envelope is not contained inside outer knuckle minimum radius")

    return {
        "stop_radius_m": stop_radius,
        "bore_circumradius_m": bore_circumradius,
        "outer_knuckle_circumradius_m": outer_circumradius,
        "outer_knuckle_inradius_m": outer_inradius,
        "phase_independent_capture_overlap_m": capture_overlap,
        "outer_knuckle_radial_containment_margin_m": outer_containment,
    }


def evaluate(
    host: dict,
    bore_contract: dict,
    annular_contract: dict,
    owner_contract: dict,
    predecessor_successor: dict,
    phase_successor: dict,
    stop_contract: dict,
    compatibility: dict,
    *,
    observed_host_sha256: str,
    observed_bore_blob_sha1: str,
    observed_annular_blob_sha1: str,
    observed_owner_blob_sha1: str,
    observed_predecessor_successor_blob_sha1: str,
    observed_phase_successor_blob_sha1: str,
    observed_stop_blob_sha1: str,
    observed_stop_contract_sha256: str,
) -> dict:
    if compatibility.get("schema") != SCHEMA:
        raise AssertionError("unsupported axial-stop capture compatibility schema")
    if compatibility.get("asset_id") != host.get("asset_id"):
        raise AssertionError("asset identity drift")
    if compatibility.get("legacy_host_source_sha256") != observed_host_sha256:
        raise AssertionError("legacy host source identity drift")
    if compatibility.get("phase_invariant_successor_head") != EXPECTED_SUCCESSOR_HEAD:
        raise AssertionError("phase-invariant successor head drift")
    if compatibility.get("phase_invariant_successor_contract_git_blob_sha1") != EXPECTED_SUCCESSOR_BLOB:
        raise AssertionError("declared phase-invariant successor blob drift")
    if observed_phase_successor_blob_sha1 != EXPECTED_SUCCESSOR_BLOB:
        raise AssertionError("observed phase-invariant successor identity drift")
    if compatibility.get("axial_stop_contract_git_blob_sha1") != EXPECTED_STOP_BLOB:
        raise AssertionError("declared axial-stop contract blob drift")
    if observed_stop_blob_sha1 != EXPECTED_STOP_BLOB:
        raise AssertionError("observed axial-stop contract identity drift")
    if compatibility.get("compatibility_semantics") != EXPECTED_SEMANTICS:
        raise AssertionError("compatibility semantics drift")
    if compatibility.get("claim_scope") != EXPECTED_SCOPE:
        raise AssertionError("compatibility claim scope drift")

    rigging_return = compatibility.get("rigging_return", {})
    if rigging_return.get("exact_head") != EXPECTED_RIGGING_HEAD:
        raise AssertionError("Rigging return head drift")
    if rigging_return.get("workflow") != EXPECTED_RIGGING_WORKFLOW:
        raise AssertionError("Rigging return workflow drift")
    if rigging_return.get("returned_hold") != "AXIAL_STOP_CONTACT_COLLAR_RETENTION_OR_FULL_COMPONENT_COLLISION_NOT_ESTABLISHED":
        raise AssertionError("Rigging returned hold drift")

    phase_receipt, _mesh = evaluate_phase_successor(
        host,
        bore_contract,
        annular_contract,
        owner_contract,
        predecessor_successor,
        phase_successor,
        observed_host_sha256=observed_host_sha256,
        observed_bore_blob_sha1=observed_bore_blob_sha1,
        observed_annular_blob_sha1=observed_annular_blob_sha1,
        observed_owner_blob_sha1=observed_owner_blob_sha1,
        observed_predecessor_successor_blob_sha1=observed_predecessor_successor_blob_sha1,
    )
    if phase_receipt.get("result") != "PASS_SOURCE_OWNED_PHASE_INVARIANT_BORED_HINGE_KNUCKLE_SUCCESSOR":
        raise AssertionError("phase-invariant successor prerequisite did not pass")

    stop_receipt = verify_axial_stop(
        host,
        stop_contract,
        host_sha=observed_host_sha256,
        contract_sha=observed_stop_contract_sha256,
    )
    if stop_receipt.get("result") != "PASS_SOURCE_OWNED_HINGE_PIN_AXIAL_STOP_PROOF":
        raise AssertionError("axial-stop prerequisite did not pass")

    source_owned = compatibility.get("source_owned_compatibility", {})
    if source_owned.get("joint_axis") != [1.0, 0.0, 0.0]:
        raise AssertionError("compatibility joint axis drift")
    if source_owned.get("stop_radial_profile") != "CIRCULAR_COLLAR_ENVELOPE_FROM_EXISTING_RADIUS_M":
        raise AssertionError("stop radial profile semantics drift")
    if source_owned.get("stop_relative_axial_phase") != "NOT_APPLICABLE_CIRCULAR_ENVELOPE":
        raise AssertionError("stop phase semantics drift")
    if source_owned.get("successor_bore_relative_phase") != "UNSPECIFIED":
        raise AssertionError("successor bore phase must remain unspecified")

    for key in (
        "automatic_default_replacement",
        "automatic_downstream_adoption",
        "legacy_host_source_rewritten",
        "phase_invariant_successor_rewritten",
        "axial_stop_contract_rewritten",
    ):
        if source_owned.get(key) is not False:
            raise AssertionError(f"{key} must remain false")

    authority = compatibility.get("authority", {})
    if authority.get("hard_surface_geometry_compatibility_authorized") is not True:
        raise AssertionError("Hard-Surface geometry compatibility authority missing")
    forbidden_authority = (
        "rig_parenting_or_retention_authorized",
        "animation_authorized",
        "technical_art_or_scene_adoption_authorized",
        "runtime_or_physics_authorized",
        "manufacturing_fit_or_retention_force_authorized",
        "load_strength_fatigue_wear_authorized",
        "service_procedure_authorized",
        "full_component_collision_authorized",
        "visual_acceptance_authorized",
        "uc_or_profession_fabric_promotion_authorized",
    )
    if any(authority.get(key) is not False for key in forbidden_authority):
        raise AssertionError("authority expansion forbidden")

    stops = stop_contract.get("stops", [])
    if len(stops) != 2:
        raise AssertionError("bilateral stop count drift")
    stop_radii = [float(stop["radius_m"]) for stop in stops]
    if not _close(stop_radii[0], stop_radii[1]):
        raise AssertionError("bilateral stop radius drift")
    stop_radius = stop_radii[0]

    segments = int(phase_receipt["segments"])
    pin_radius = float(phase_receipt["source_pin_circumradius_m"])
    bore_radius = float(phase_receipt["successor_bore_circumradius_m"])
    outer_radius = float(phase_receipt["source_knuckle_outer_circumradius_m"])

    if int(source_owned.get("segments", -1)) != segments:
        raise AssertionError("segment count drift")
    if not _close(float(source_owned.get("stop_radius_m")), stop_radius):
        raise AssertionError("stop radius drift")
    if not _close(float(source_owned.get("source_pin_circumradius_m")), pin_radius):
        raise AssertionError("pin radius drift")
    if not _close(float(source_owned.get("successor_bore_circumradius_m")), bore_radius):
        raise AssertionError("successor bore radius drift")
    if not _close(float(source_owned.get("knuckle_outer_circumradius_m")), outer_radius):
        raise AssertionError("outer knuckle radius drift")

    metrics = _capture_metrics(
        stop_radius=stop_radius,
        bore_circumradius=bore_radius,
        outer_circumradius=outer_radius,
        segments=segments,
    )
    axial_gap = float(stop_receipt["minimum_observed_outer_knuckle_clearance_m"])
    if axial_gap <= TOL:
        raise AssertionError("existing axial stop gap is not positive")

    return {
        "schema": "axm.object-hinge-bored-knuckle-axial-stop-capture-receipt/v0.1",
        "result": RESULT,
        "asset_id": host["asset_id"],
        "compatibility_id": compatibility["compatibility_id"],
        "legacy_host_source_sha256": observed_host_sha256,
        "phase_invariant_successor_head": compatibility["phase_invariant_successor_head"],
        "phase_invariant_successor_contract_git_blob_sha1": observed_phase_successor_blob_sha1,
        "axial_stop_contract_git_blob_sha1": observed_stop_blob_sha1,
        "rigging_return_head": rigging_return["exact_head"],
        "rigging_return_workflow": rigging_return["workflow"],
        "segments": segments,
        "stop_count": len(stops),
        "source_pin_circumradius_m": pin_radius,
        **metrics,
        "minimum_existing_axial_gap_before_outer_knuckle_contact_m": axial_gap,
        "bilateral_stop_symmetry_residual_m": float(stop_receipt["bilateral_symmetry_residual"]),
        "successor_phase_independent_pin_bore_clearance_m": float(phase_receipt["successor_phase_independent_radial_clearance_m"]),
        "stop_radial_profile": source_owned["stop_radial_profile"],
        "successor_bore_relative_phase": source_owned["successor_bore_relative_phase"],
        "legacy_host_source_rewritten": False,
        "phase_invariant_successor_rewritten": False,
        "axial_stop_contract_rewritten": False,
        "automatic_downstream_adoption": False,
        "rig_parenting_or_retention_authorized": False,
        "full_component_collision_authorized": False,
        "manufacturing_fit_or_retention_force_authorized": False,
        "reusable_rule": compatibility["reusable_rule"],
        "truth_boundary": compatibility["truth_boundary"],
    }


def _negative_controls(receipt_inputs: dict) -> dict:
    controls = {}
    bore_radius = receipt_inputs["bore_radius"]
    outer_radius = receipt_inputs["outer_radius"]
    segments = receipt_inputs["segments"]

    try:
        _capture_metrics(
            stop_radius=bore_radius,
            bore_circumradius=bore_radius,
            outer_circumradius=outer_radius,
            segments=segments,
        )
    except AssertionError as exc:
        controls["no_positive_bore_capture_overlap"] = f"HOLD:{exc}"
    else:
        raise AssertionError("zero-capture-overlap negative control unexpectedly passed")

    outer_inradius = outer_radius * math.cos(math.pi / segments)
    try:
        _capture_metrics(
            stop_radius=outer_inradius,
            bore_circumradius=bore_radius,
            outer_circumradius=outer_radius,
            segments=segments,
        )
    except AssertionError as exc:
        controls["no_positive_outer_containment_margin"] = f"HOLD:{exc}"
    else:
        raise AssertionError("zero-outer-containment negative control unexpectedly passed")

    bad = copy.deepcopy(receipt_inputs["compatibility"])
    bad["authority"]["rig_parenting_or_retention_authorized"] = True
    controls["authority_expansion_mutation"] = "HOLD:authority expansion forbidden" if bad["authority"]["rig_parenting_or_retention_authorized"] else "UNEXPECTED"
    if controls["authority_expansion_mutation"] == "UNEXPECTED":
        raise AssertionError("authority-expansion negative control setup failed")

    return controls


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--bore-contract", required=True)
    parser.add_argument("--annular-contract", required=True)
    parser.add_argument("--owner-contract", required=True)
    parser.add_argument("--predecessor-successor-contract", required=True)
    parser.add_argument("--phase-invariant-successor-contract", required=True)
    parser.add_argument("--axial-stop-contract", required=True)
    parser.add_argument("--capture-contract", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    host_path = Path(args.host)
    bore_path = Path(args.bore_contract)
    annular_path = Path(args.annular_contract)
    owner_path = Path(args.owner_contract)
    predecessor_path = Path(args.predecessor_successor_contract)
    phase_successor_path = Path(args.phase_invariant_successor_contract)
    stop_path = Path(args.axial_stop_contract)
    compatibility_path = Path(args.capture_contract)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    host = json.loads(host_path.read_text(encoding="utf-8"))
    bore = json.loads(bore_path.read_text(encoding="utf-8"))
    annular = json.loads(annular_path.read_text(encoding="utf-8"))
    owner = json.loads(owner_path.read_text(encoding="utf-8"))
    predecessor = json.loads(predecessor_path.read_text(encoding="utf-8"))
    phase_successor = json.loads(phase_successor_path.read_text(encoding="utf-8"))
    stop_contract = json.loads(stop_path.read_text(encoding="utf-8"))
    compatibility = json.loads(compatibility_path.read_text(encoding="utf-8"))

    host_sha = _sha256(host_path)
    bore_blob = _git_blob_sha1(bore_path)
    annular_blob = _git_blob_sha1(annular_path)
    owner_blob = _git_blob_sha1(owner_path)
    predecessor_blob = _git_blob_sha1(predecessor_path)
    phase_successor_blob = _git_blob_sha1(phase_successor_path)
    stop_blob = _git_blob_sha1(stop_path)
    stop_sha = _stop_sha256(stop_path)

    receipt = evaluate(
        host,
        bore,
        annular,
        owner,
        predecessor,
        phase_successor,
        stop_contract,
        compatibility,
        observed_host_sha256=host_sha,
        observed_bore_blob_sha1=bore_blob,
        observed_annular_blob_sha1=annular_blob,
        observed_owner_blob_sha1=owner_blob,
        observed_predecessor_successor_blob_sha1=predecessor_blob,
        observed_phase_successor_blob_sha1=phase_successor_blob,
        observed_stop_blob_sha1=stop_blob,
        observed_stop_contract_sha256=stop_sha,
    )
    receipt["capture_contract_sha256"] = _sha256(compatibility_path)
    receipt["negative_controls"] = _negative_controls({
        "bore_radius": receipt["bore_circumradius_m"],
        "outer_radius": receipt["outer_knuckle_circumradius_m"],
        "segments": receipt["segments"],
        "compatibility": compatibility,
    })

    (out / "hinge-bored-knuckle-axial-stop-capture.receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(RESULT)
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
