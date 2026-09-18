from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path
from typing import Any

SCHEMA = "axm.object-hinge-phase-invariant-bored-knuckle-rig-compatibility/v0.1"
RESULT = "PASS_PHASE_INVARIANT_BORED_KNUCKLE_SUCCESSOR_RIG_1MM_RADIAL_NONCONTACT_CONTINUOUS_0_TO_110"
SUCCESSOR_HEAD = "a6d18b9fe729304dc4d95d962ed27527adce211f"
SUCCESSOR_BLOB = "7e078189d5c80508b28932563326cd5629c4efa6"
PREDECESSOR_RIGGING_HEAD = "38f32efe4a1b053f77255c31bee021646156e4ad"
PREDECESSOR_SOURCE_SUCCESSOR_HEAD = "178d93e8976a741271d7f47ab4865519de925657"
HISTORICAL_LID_RIG_HEAD = "4b72c9918c5fc1e89bd18a0be24fb4afac6e7775"
SOURCE_SHA256 = "49b1f9ed9865893d6de6f1ec8f069576732df694853fde4e3fcff366de32644a"
LID_PLAN_DIGEST = "0ad6dc2ca22676cf301579932e599a441eb7c4bccce31991d1b727aeb22ac422"
REPRESENTATIVE_ANGLES = [0, 15, 30, 45, 60, 75, 90, 105, 110]
TOL = 1e-12


def _assert_exact(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"{label} drift: {actual!r} != {expected!r}")


def _assert_close(actual: float, expected: float, label: str, tol: float = TOL) -> None:
    if abs(float(actual) - float(expected)) > tol:
        raise AssertionError(f"{label} drift: {actual} != {expected}")


def verify(
    predecessor_rig_receipt: dict[str, Any],
    successor: dict[str, Any],
    successor_receipt: dict[str, Any],
    compatibility: dict[str, Any],
    *,
    observed_successor_head: str,
    observed_successor_blob: str,
    observed_predecessor_rigging_head: str,
) -> dict[str, Any]:
    _assert_exact(observed_predecessor_rigging_head, PREDECESSOR_RIGGING_HEAD, "predecessor Rigging head")
    _assert_exact(
        predecessor_rig_receipt.get("result"),
        "PASS_BORED_KNUCKLE_SUCCESSOR_RIG_RADIAL_NONCONTACT_CONTINUOUS_0_TO_110",
        "predecessor Rigging result",
    )
    _assert_exact(predecessor_rig_receipt.get("source_sha256"), SOURCE_SHA256, "source identity")
    old_rig = predecessor_rig_receipt.get("rig_identity", {})
    _assert_exact(old_rig.get("historical_lid_rig_head"), HISTORICAL_LID_RIG_HEAD, "historical lid rig")
    _assert_exact(old_rig.get("lid_plan_digest"), LID_PLAN_DIGEST, "lid plan digest")
    _assert_exact(old_rig.get("axis"), [1, 0, 0], "hinge axis")
    _assert_exact(old_rig.get("angle_limit_deg"), [0, 110], "hinge angle range")
    _assert_exact(old_rig.get("opening_rotation_sign"), -1, "opening sign")
    _assert_exact(old_rig.get("moving_lid_knuckles"), ["l0", "l1"], "moving knuckles")
    _assert_exact(old_rig.get("fixed_body_knuckles"), ["b0", "b1", "b2"], "fixed knuckles")
    _assert_exact(
        predecessor_rig_receipt.get("source_successor", {}).get("head"),
        PREDECESSOR_SOURCE_SUCCESSOR_HEAD,
        "predecessor source-successor head",
    )
    _assert_exact(
        predecessor_rig_receipt.get("decision", {}).get("source_successor_geometry_adopted"),
        False,
        "predecessor adoption boundary",
    )

    _assert_exact(observed_successor_head, SUCCESSOR_HEAD, "phase-invariant source-successor head")
    _assert_exact(observed_successor_blob, SUCCESSOR_BLOB, "phase-invariant source-successor blob")
    _assert_exact(
        successor.get("schema"),
        "axm.object-hinge-bored-knuckle-phase-invariant-source-successor/v0.1",
        "source-successor schema",
    )
    _assert_exact(
        successor.get("successor_id"),
        "modular-equipment-case-001/hinge-bored-knuckle-phase-invariant-source-successor-002",
        "source-successor id",
    )
    _assert_exact(successor.get("legacy_host_source_sha256"), SOURCE_SHA256, "source-successor host source")
    _assert_exact(successor.get("predecessor_successor_head"), PREDECESSOR_SOURCE_SUCCESSOR_HEAD, "successor predecessor head")
    _assert_exact(
        successor.get("phase_invariant_claim_scope"),
        "CONCENTRIC_REGULAR_12_GON_RADIAL_CROSS_SECTION_ONLY",
        "phase-invariant scope",
    )
    _assert_exact(successor.get("replacement_scope"), "HINGE_KNUCKLE_BORE_GEOMETRY_ONLY", "replacement scope")

    source_owned = successor.get("source_owned_successor", {})
    _assert_exact(source_owned.get("segments"), 12, "segment count")
    _assert_close(source_owned.get("source_pin_circumradius_m"), 0.009, "pin circumradius")
    _assert_exact(source_owned.get("pin_relative_axial_phase"), "UNSPECIFIED", "pin phase")
    _assert_exact(source_owned.get("pin_physical_owner"), "UNSPECIFIED", "pin physical owner")
    for key in (
        "automatic_default_replacement",
        "automatic_downstream_adoption",
        "legacy_host_source_rewritten",
        "predecessor_source_successor_rewritten",
    ):
        _assert_exact(source_owned.get(key), False, f"source successor boundary {key}")
    _assert_exact(successor.get("authority", {}).get("rig_parenting_authorized"), False, "Hard-Surface Rigging authority boundary")

    _assert_exact(
        successor_receipt.get("result"),
        "PASS_SOURCE_OWNED_PHASE_INVARIANT_BORED_HINGE_KNUCKLE_SUCCESSOR",
        "source-owner successor result",
    )
    _assert_exact(successor_receipt.get("successor_id"), successor.get("successor_id"), "source-owner successor receipt id")
    _assert_exact(successor_receipt.get("rigging_return_head"), PREDECESSOR_RIGGING_HEAD, "source-owner Rigging return head")
    _assert_exact(successor_receipt.get("owner_sequence"), ["body", "lid", "body", "lid", "body"], "owner sequence")
    _assert_exact(successor_receipt.get("candidate_boundary_edges"), 0, "successor boundary edges")
    _assert_exact(successor_receipt.get("candidate_non_manifold_edges"), 0, "successor non-manifold edges")
    _assert_exact(successor_receipt.get("candidate_orientation_conflicts"), 0, "successor orientation conflicts")
    _assert_exact(successor_receipt.get("candidate_degenerate_triangles"), 0, "successor degenerate triangles")

    _assert_exact(compatibility.get("schema"), SCHEMA, "compatibility schema")
    _assert_exact(compatibility.get("asset_id"), "modular-equipment-case-001", "compatibility asset")
    _assert_exact(
        compatibility.get("compatibility_id"),
        "modular-equipment-case-001/hinge-phase-invariant-bored-knuckle-rig-compatibility-002",
        "compatibility id",
    )
    receiver_source = compatibility.get("source_successor", {})
    _assert_exact(receiver_source.get("head"), SUCCESSOR_HEAD, "compatibility source-successor head")
    _assert_exact(receiver_source.get("contract_git_blob_sha1"), SUCCESSOR_BLOB, "compatibility source-successor blob")
    _assert_exact(compatibility.get("predecessor_rigging_head"), PREDECESSOR_RIGGING_HEAD, "compatibility predecessor Rigging head")
    _assert_exact(compatibility.get("representative_source_angles_deg"), REPRESENTATIVE_ANGLES, "representative angles")
    constraint = compatibility.get("rig_constraint", {})
    _assert_exact(constraint.get("pin_centerline"), "EXACT_SOURCE_HINGE_AXIS_COAXIAL_NO_TRANSLATION", "coaxial constraint")
    _assert_exact(constraint.get("pin_axial_phase"), "UNSPECIFIED", "compatibility pin phase")
    _assert_exact(constraint.get("pin_physical_owner"), "UNSPECIFIED", "compatibility pin owner")
    decision = compatibility.get("decision", {})
    _assert_exact(decision.get("source_successor_rig_compatibility_authorized"), True, "Rigging compatibility decision")
    _assert_exact(decision.get("phase_independent_1mm_radial_lower_bound_accepted_as_source_geometric_constraint"), True, "1mm source-geometric constraint")
    for key in ("source_successor_geometry_adopted", "automatic_downstream_adoption", "pin_parent_or_axial_phase_claimed"):
        _assert_exact(decision.get(key), False, f"Rigging decision boundary {key}")
    authority = compatibility.get("authority", {})
    _assert_exact(authority.get("rigging_constraint_evidence_authorized"), True, "Rigging evidence authority")
    for key in (
        "animation_accepted",
        "technical_art_target_host_accepted",
        "runtime_accepted",
        "physics_or_load_accepted",
        "manufacturing_fit_or_bearing_accepted",
        "visual_accepted",
        "canon_or_production_accepted",
    ):
        _assert_exact(authority.get(key), False, f"downstream authority {key}")

    segments = int(source_owned["segments"])
    pin = float(source_owned["source_pin_circumradius_m"])
    bore = float(source_owned["bore_circumradius_m"])
    factor = math.cos(math.pi / segments)
    phase_independent = bore * factor - pin
    same_phase = (bore - pin) * factor
    minimum = float(source_owned["minimum_phase_independent_radial_clearance_m"])
    if phase_independent < minimum - TOL:
        raise AssertionError(f"phase-independent radial clearance below source contract: {phase_independent} < {minimum}")
    _assert_close(phase_independent, successor_receipt.get("successor_phase_independent_radial_clearance_m"), "source receipt phase-independent clearance")
    _assert_close(same_phase, source_owned.get("same_phase_radial_clearance_m"), "source same-phase clearance")
    _assert_close(same_phase, successor_receipt.get("successor_same_phase_radial_clearance_m"), "source receipt same-phase clearance")

    witnesses = []
    for angle in REPRESENTATIVE_ANGLES:
        witnesses.append({
            "source_angle_deg": float(angle),
            "applied_lid_angle_deg": -float(angle),
            "moving_lid_knuckles": ["l0", "l1"],
            "fixed_body_knuckles": ["b0", "b1", "b2"],
            "pin_centerline_constraint": "EXACT_SOURCE_HINGE_AXIS_COAXIAL_NO_TRANSLATION",
            "pin_axial_phase_assumed": False,
            "phase_independent_radial_clearance_lower_bound_m": phase_independent,
        })

    return {
        "schema": "axm.object-hinge-phase-invariant-bored-knuckle-rig-compatibility-receipt/v0.1",
        "result": RESULT,
        "asset_id": "modular-equipment-case-001",
        "compatibility_id": compatibility["compatibility_id"],
        "source_sha256": SOURCE_SHA256,
        "source_successor": {
            "head": SUCCESSOR_HEAD,
            "contract_git_blob_sha1": SUCCESSOR_BLOB,
            "successor_id": successor["successor_id"],
            "source_owner_result": successor_receipt["result"],
        },
        "predecessor_rigging": {
            "head": PREDECESSOR_RIGGING_HEAD,
            "result": predecessor_rig_receipt["result"],
            "historical_lid_rig_head": HISTORICAL_LID_RIG_HEAD,
            "lid_plan_digest": LID_PLAN_DIGEST,
        },
        "continuous_radial_certificate": {
            "kind": "REGULAR_POLYGON_CIRCUMDISK_INDISK_CONTAINMENT",
            "domain_deg": [0.0, 110.0],
            "segments": segments,
            "pin_circumradius_m": pin,
            "bore_circumradius_m": bore,
            "bore_inradius_m": bore * factor,
            "source_minimum_phase_independent_radial_clearance_m": minimum,
            "phase_independent_radial_clearance_lower_bound_m": phase_independent,
            "same_phase_radial_clearance_m": same_phase,
            "coaxial_centerline_required": True,
            "pin_axial_phase": "UNSPECIFIED",
            "pin_physical_owner": "UNSPECIFIED",
            "proof_scope": "radial 2D cross-section non-contact only; no pin phase/parent, axial stop/contact, bearing/load/tolerance or full-component collision claim",
        },
        "representative_pose_witnesses": witnesses,
        "decision": {
            "source_successor_rig_compatibility_authorized": True,
            "phase_independent_1mm_radial_lower_bound_proven": phase_independent >= minimum - TOL,
            "source_successor_geometry_adopted": False,
            "automatic_downstream_adoption": False,
            "pin_parent_or_axial_phase_claimed": False,
        },
        "truth_boundary": {
            "source_geometry_changed": False,
            "historical_rig_changed": False,
            "pin_parent_or_axial_phase_claimed": False,
            "animation_accepted": False,
            "technical_art_target_host_accepted": False,
            "runtime_accepted": False,
            "physics_or_load_accepted": False,
            "manufacturing_fit_or_bearing_accepted": False,
            "full_component_collision_accepted": False,
            "visual_accepted": False,
            "canon_or_production_accepted": False,
        },
    }


def negative_controls(predecessor, successor, successor_receipt, compatibility) -> dict[str, str]:
    controls: dict[str, str] = {}

    def expect_hold(name: str, pred: dict, succ: dict, rec: dict, comp: dict) -> None:
        try:
            verify(
                pred,
                succ,
                rec,
                comp,
                observed_successor_head=SUCCESSOR_HEAD,
                observed_successor_blob=SUCCESSOR_BLOB,
                observed_predecessor_rigging_head=PREDECESSOR_RIGGING_HEAD,
            )
        except AssertionError as exc:
            controls[name] = f"HOLD:{exc}"
        else:
            raise AssertionError(f"negative control unexpectedly passed: {name}")

    bad = copy.deepcopy(successor)
    bad["source_owned_successor"]["bore_circumradius_m"] = 0.010035276180410082
    expect_hold("predecessor_bore_insufficient_for_1mm_phase_invariant_clearance", predecessor, bad, successor_receipt, compatibility)

    bad = copy.deepcopy(successor)
    bad["source_owned_successor"]["automatic_downstream_adoption"] = True
    expect_hold("automatic_source_successor_adoption", predecessor, bad, successor_receipt, compatibility)

    bad = copy.deepcopy(successor)
    bad["source_owned_successor"]["pin_relative_axial_phase"] = "FIXED_TO_BODY"
    expect_hold("invented_pin_phase", predecessor, bad, successor_receipt, compatibility)

    bad_comp = copy.deepcopy(compatibility)
    bad_comp["decision"]["source_successor_geometry_adopted"] = True
    expect_hold("silent_geometry_adoption", predecessor, successor, successor_receipt, bad_comp)

    bad_comp = copy.deepcopy(compatibility)
    bad_comp["authority"]["animation_accepted"] = True
    expect_hold("animation_authority_expansion", predecessor, successor, successor_receipt, bad_comp)

    return controls


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--predecessor-rig-receipt", type=Path, required=True)
    parser.add_argument("--successor-contract", type=Path, required=True)
    parser.add_argument("--successor-receipt", type=Path, required=True)
    parser.add_argument("--compatibility-contract", type=Path, required=True)
    parser.add_argument("--observed-successor-head", required=True)
    parser.add_argument("--observed-successor-blob", required=True)
    parser.add_argument("--observed-predecessor-rigging-head", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    predecessor = json.loads(args.predecessor_rig_receipt.read_text())
    successor = json.loads(args.successor_contract.read_text())
    source_receipt = json.loads(args.successor_receipt.read_text())
    compatibility = json.loads(args.compatibility_contract.read_text())

    receipt = verify(
        predecessor,
        successor,
        source_receipt,
        compatibility,
        observed_successor_head=args.observed_successor_head,
        observed_successor_blob=args.observed_successor_blob,
        observed_predecessor_rigging_head=args.observed_predecessor_rigging_head,
    )
    receipt["negative_controls"] = negative_controls(predecessor, successor, source_receipt, compatibility)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(RESULT)


if __name__ == "__main__":
    main()
