from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from verify_hinge_knuckle_rig_parent_binding import (
    LID_PLAN_DIGEST,
    LID_RIG_HEAD as PARENT_LID_RIG_HEAD,
    OWNER_STACK_BLOB as PARENT_OWNER_STACK_BLOB,
    OWNER_STACK_HEAD as PARENT_OWNER_STACK_HEAD,
    PREVIOUS_RIGGING_HEAD as PARENT_PREVIOUS_RIGGING_HEAD,
    SOURCE_SHA256,
    digest as canonical_digest,
    verify as verify_parent_binding,
)

SCHEMA = "axm.object-hinge-bored-knuckle-rig-compatibility/v0.1"
RESULT = "PASS_BORED_KNUCKLE_SUCCESSOR_RIG_RADIAL_NONCONTACT_CONTINUOUS_0_TO_110"
MOTION_CLEARANCE_GATE = "HOLD_SOURCE_STATIC_1MM_AS_CONTINUOUS_MOTION_CLEARANCE__PIN_PHASE_UNSPECIFIED"
SUCCESSOR_HEAD = "178d93e8976a741271d7f47ab4865519de925657"
SUCCESSOR_BLOB = "beaf16f588450a3b298e2e581b590c5dc0c07380"
ANNULAR_BLOB = "39a52ad5ba8497a8a524d764bbf6744bb11cf54a"
OWNER_STACK_BLOB = "e4e7c95769c0827a6a019afd672ff4b20cd13541"
LID_RIG_HEAD = "4b72c9918c5fc1e89bd18a0be24fb4afac6e7775"
PREDECESSOR_RIGGING_HEAD = "16b32c5ac6d52d768d64f0fac9fedfe4ee9f24fe"
TOL = 1e-12


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _assert_exact(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"{label} drift: {actual!r} != {expected!r}")


def _assert_close(actual: float, expected: float, label: str, tol: float = TOL) -> None:
    if abs(float(actual) - float(expected)) > tol:
        raise AssertionError(f"{label} drift: {actual} != {expected}")


def _validate_compatibility_contract(contract: dict[str, Any]) -> None:
    _assert_exact(contract.get("schema"), SCHEMA, "compatibility schema")
    _assert_exact(contract.get("asset_id"), "modular-equipment-case-001", "compatibility asset")
    _assert_exact(
        contract.get("compatibility_id"),
        "modular-equipment-case-001/hinge-bored-knuckle-rig-compatibility-001",
        "compatibility id",
    )

    successor = contract.get("source_successor", {})
    _assert_exact(successor.get("head"), SUCCESSOR_HEAD, "source successor head")
    _assert_exact(successor.get("contract_git_blob_sha1"), SUCCESSOR_BLOB, "source successor blob")
    _assert_exact(successor.get("annular_mesh_git_blob_sha1"), ANNULAR_BLOB, "annular mesh blob")
    _assert_exact(successor.get("owner_stack_git_blob_sha1"), OWNER_STACK_BLOB, "owner stack blob")
    _assert_exact(
        successor.get("schema"),
        "axm.object-hinge-bored-knuckle-source-successor/v0.1",
        "source successor schema",
    )
    _assert_exact(
        successor.get("successor_id"),
        "modular-equipment-case-001/hinge-bored-knuckle-source-successor-001",
        "source successor id",
    )

    rig = contract.get("historical_rig", {})
    _assert_exact(rig.get("head"), LID_RIG_HEAD, "historical rig head")
    _assert_exact(rig.get("plan_digest"), LID_PLAN_DIGEST, "historical rig plan digest")
    _assert_exact(rig.get("joint_id"), "rear-lid-hinge-001", "historical joint")
    _assert_exact(rig.get("axis"), [1, 0, 0], "historical rig axis")
    _assert_exact(rig.get("angle_limit_deg"), [0, 110], "historical rig angle limit")
    _assert_exact(rig.get("opening_rotation_sign"), -1, "historical opening sign")
    _assert_exact(rig.get("moving_lid_knuckles"), ["l0", "l1"], "moving lid knuckles")
    _assert_exact(rig.get("fixed_body_knuckles"), ["b0", "b1", "b2"], "fixed body knuckles")

    _assert_exact(contract.get("predecessor_rigging_head"), PREDECESSOR_RIGGING_HEAD, "predecessor Rigging head")
    _assert_exact(
        contract.get("representative_source_angles_deg"),
        [0, 15, 30, 45, 60, 75, 90, 105, 110],
        "representative source angles",
    )

    constraint = contract.get("rig_constraint", {})
    _assert_exact(
        constraint.get("pin_centerline"),
        "EXACT_SOURCE_HINGE_AXIS_COAXIAL_NO_TRANSLATION",
        "pin centerline constraint",
    )
    _assert_exact(constraint.get("pin_axial_phase"), "UNSPECIFIED", "pin axial phase")
    _assert_exact(constraint.get("pin_physical_owner"), "UNSPECIFIED", "pin physical owner")

    decision = contract.get("decision", {})
    if decision.get("source_successor_rig_compatibility_authorized") is not True:
        raise AssertionError("Rigging compatibility authorization missing")
    for key in (
        "source_successor_geometry_adopted",
        "automatic_downstream_adoption",
        "source_static_clearance_promoted_to_continuous_motion_clearance",
    ):
        if decision.get(key) is not False:
            raise AssertionError(f"compatibility authority drift: {key}")

    authority = contract.get("authority", {})
    if authority.get("rigging_constraint_evidence_authorized") is not True:
        raise AssertionError("Rigging evidence authority missing")
    for key in (
        "animation_accepted",
        "technical_art_target_host_accepted",
        "runtime_accepted",
        "physics_or_load_accepted",
        "manufacturing_fit_or_bearing_accepted",
        "visual_accepted",
        "canon_or_production_accepted",
    ):
        if authority.get(key) is not False:
            raise AssertionError(f"downstream authority drift: {key}")


def verify(
    source: dict[str, Any],
    owner_stack: dict[str, Any],
    successor: dict[str, Any],
    annular: dict[str, Any],
    successor_receipt: dict[str, Any],
    lid_plan: dict[str, Any],
    compatibility: dict[str, Any],
    *,
    source_sha256: str,
    observed_owner_stack_head: str,
    observed_owner_stack_blob: str,
    observed_successor_head: str,
    observed_successor_blob: str,
    observed_annular_blob: str,
    observed_lid_rig_head: str,
    observed_predecessor_rigging_head: str,
) -> dict[str, Any]:
    if source_sha256 != SOURCE_SHA256:
        raise AssertionError("exact Object source byte identity drift")
    _assert_exact(observed_owner_stack_head, PARENT_OWNER_STACK_HEAD, "owner-stack source head")
    _assert_exact(observed_owner_stack_blob, OWNER_STACK_BLOB, "owner-stack source blob")
    _assert_exact(observed_successor_head, SUCCESSOR_HEAD, "source-successor head")
    _assert_exact(observed_successor_blob, SUCCESSOR_BLOB, "source-successor contract blob")
    _assert_exact(observed_annular_blob, ANNULAR_BLOB, "annular-mesh contract blob")
    _assert_exact(observed_lid_rig_head, LID_RIG_HEAD, "historical lid-rig head")
    _assert_exact(observed_predecessor_rigging_head, PREDECESSOR_RIGGING_HEAD, "predecessor Rigging head")

    _validate_compatibility_contract(compatibility)

    parent_receipt = verify_parent_binding(
        source,
        owner_stack,
        lid_plan,
        source_sha256=source_sha256,
        observed_owner_stack_head=PARENT_OWNER_STACK_HEAD,
        observed_owner_stack_blob=PARENT_OWNER_STACK_BLOB,
        observed_lid_rig_head=PARENT_LID_RIG_HEAD,
        observed_previous_rigging_head=PARENT_PREVIOUS_RIGGING_HEAD,
    )
    if parent_receipt.get("result") != "PASS_SOURCE_OWNED_HINGE_KNUCKLE_PARENT_BINDING_CONTINUOUS_0_TO_110":
        raise AssertionError("predecessor parent partition did not re-prove")

    _assert_exact(successor.get("schema"), "axm.object-hinge-bored-knuckle-source-successor/v0.1", "successor schema")
    _assert_exact(successor.get("asset_id"), source.get("asset_id"), "successor asset")
    _assert_exact(
        successor.get("successor_id"),
        "modular-equipment-case-001/hinge-bored-knuckle-source-successor-001",
        "successor id",
    )
    _assert_exact(successor.get("legacy_host_source_sha256"), SOURCE_SHA256, "successor host source")
    _assert_exact(successor.get("annular_mesh_contract_git_blob_sha1"), ANNULAR_BLOB, "successor annular donor")
    _assert_exact(successor.get("owner_stack_contract_git_blob_sha1"), OWNER_STACK_BLOB, "successor owner donor")
    _assert_exact(
        successor.get("successor_semantics"),
        "SOURCE_OWNED_ALTERNATE_HINGE_KNUCKLE_GEOMETRY_EXPLICIT_RECEIVER_REBIND_REQUIRED",
        "successor semantics",
    )
    _assert_exact(successor.get("replacement_scope"), "HINGE_KNUCKLE_GEOMETRY_ONLY", "successor replacement scope")

    source_owned = successor.get("source_owned_successor", {})
    for key in ("automatic_default_replacement", "automatic_downstream_adoption", "legacy_host_source_rewritten"):
        if source_owned.get(key) is not False:
            raise AssertionError(f"source successor authority drift: {key}")
    if successor.get("authority", {}).get("rig_parenting_authorized") is not False:
        raise AssertionError("Hard-Surface source owner cannot pre-authorize Rigging parenting")

    _assert_exact(
        successor_receipt.get("schema"),
        "axm.object-hinge-bored-knuckle-source-successor-receipt/v0.1",
        "source-successor receipt schema",
    )
    _assert_exact(successor_receipt.get("result"), "PASS_SOURCE_OWNED_BORED_HINGE_KNUCKLE_SUCCESSOR", "source-successor result")
    _assert_exact(successor_receipt.get("asset_id"), source.get("asset_id"), "source-successor receipt asset")
    _assert_exact(successor_receipt.get("successor_id"), successor.get("successor_id"), "source-successor receipt id")
    _assert_exact(successor_receipt.get("annular_mesh_contract_git_blob_sha1"), ANNULAR_BLOB, "receipt annular blob")
    _assert_exact(successor_receipt.get("owner_stack_contract_git_blob_sha1"), OWNER_STACK_BLOB, "receipt owner blob")
    if successor_receipt.get("automatic_downstream_adoption") is not False:
        raise AssertionError("source-successor receipt automatic adoption drift")

    _assert_exact(annular.get("schema"), "axm.object-hinge-pin-annular-mesh/v0.1", "annular schema")
    _assert_exact(annular.get("asset_id"), source.get("asset_id"), "annular asset")
    _assert_exact(annular.get("host_source_sha256"), SOURCE_SHA256, "annular host source")
    segments = int(annular.get("expected_segments", 0))
    if segments != int(source["hinge"]["segments"]) or segments != 12:
        raise AssertionError("annular/source segment count drift")

    pin_radius = float(annular["source_pin_radius_m"])
    bore_circumradius = float(annular["mesh_bore_radius_m"])
    source_pin_radius = float(source["hinge"]["pin_radius"])
    _assert_close(pin_radius, source_pin_radius, "source pin radius")
    _assert_close(float(source_owned["minimum_pin_to_bore_surface_clearance_m"]), 0.001, "source-successor static clearance")
    _assert_close(float(annular["minimum_mesh_surface_clearance_m"]), 0.001, "annular static clearance")

    half_segment = math.pi / float(segments)
    bore_inradius = bore_circumradius * math.cos(half_segment)
    pin_circumradius = pin_radius

    same_phase_clearance = bore_inradius - pin_circumradius * math.cos(half_segment)
    _assert_close(same_phase_clearance, float(annular["minimum_mesh_surface_clearance_m"]), "same-phase clearance")

    phase_independent_clearance = bore_inradius - pin_circumradius
    if phase_independent_clearance <= TOL:
        raise AssertionError(
            f"phase-independent radial clearance is not positive: {phase_independent_clearance}"
        )

    if phase_independent_clearance >= same_phase_clearance - TOL:
        raise AssertionError("expected bounded phase uncertainty to reduce the guaranteed clearance below the same-phase metric")

    joint = lid_plan.get("joint", {})
    _assert_exact(joint.get("id"), "rear-lid-hinge-001", "lid joint id")
    _assert_exact(joint.get("axis_source"), "hinge.axis", "lid axis source")
    _assert_exact(joint.get("angle_limit_deg"), [0, 110], "lid angle domain")
    _assert_exact(joint.get("opening_rotation_sign"), -1, "lid opening sign")
    _assert_exact(joint.get("coaxial_moving_knuckles"), ["l0", "l1"], "lid moving knuckles")
    if canonical_digest(lid_plan) != LID_PLAN_DIGEST:
        raise AssertionError("lid articulation plan digest drift")
    _assert_exact(source["hinge"]["axis"], [1, 0, 0], "source hinge axis")

    angles = list(compatibility["representative_source_angles_deg"])
    witnesses = [
        {
            "source_angle_deg": float(angle),
            "applied_lid_angle_deg": float(joint["opening_rotation_sign"]) * float(angle),
            "moving_lid_knuckles": ["l0", "l1"],
            "fixed_body_knuckles": ["b0", "b1", "b2"],
            "pin_centerline_constraint": compatibility["rig_constraint"]["pin_centerline"],
            "pin_axial_phase_assumed": False,
            "phase_independent_radial_clearance_lower_bound_m": phase_independent_clearance,
        }
        for angle in angles
    ]

    static_to_continuous_guarantee_drop = same_phase_clearance - phase_independent_clearance
    return {
        "schema": "axm.object-hinge-bored-knuckle-rig-compatibility-receipt/v0.1",
        "result": RESULT,
        "motion_clearance_gate": MOTION_CLEARANCE_GATE,
        "asset_id": source["asset_id"],
        "source_sha256": SOURCE_SHA256,
        "compatibility_id": compatibility["compatibility_id"],
        "source_successor": {
            "head": SUCCESSOR_HEAD,
            "contract_git_blob_sha1": SUCCESSOR_BLOB,
            "annular_mesh_git_blob_sha1": ANNULAR_BLOB,
            "owner_stack_git_blob_sha1": OWNER_STACK_BLOB,
            "successor_id": successor["successor_id"],
            "source_owner_result": successor_receipt["result"],
        },
        "rig_identity": {
            "historical_lid_rig_head": LID_RIG_HEAD,
            "lid_plan_digest": LID_PLAN_DIGEST,
            "predecessor_rigging_head": PREDECESSOR_RIGGING_HEAD,
            "joint_id": joint["id"],
            "axis": [1, 0, 0],
            "angle_limit_deg": [0, 110],
            "opening_rotation_sign": -1,
            "moving_lid_knuckles": ["l0", "l1"],
            "fixed_body_knuckles": ["b0", "b1", "b2"],
        },
        "parent_partition_prerequisite": parent_receipt["result"],
        "representative_pose_witnesses": witnesses,
        "continuous_radial_certificate": {
            "kind": "REGULAR_POLYGON_CIRCUMDISK_INDISK_CONTAINMENT",
            "domain_deg": [0.0, 110.0],
            "segments": segments,
            "pin_circumradius_m": pin_circumradius,
            "bore_circumradius_m": bore_circumradius,
            "bore_inradius_m": bore_inradius,
            "pin_axial_phase": "UNSPECIFIED",
            "pin_physical_owner": "UNSPECIFIED",
            "coaxial_centerline_required": True,
            "phase_independent_radial_clearance_lower_bound_m": phase_independent_clearance,
            "neutral_same_phase_clearance_m": same_phase_clearance,
            "hard_surface_static_clearance_m": float(annular["minimum_mesh_surface_clearance_m"]),
            "static_to_phase_independent_guarantee_drop_m": static_to_continuous_guarantee_drop,
            "static_clearance_retained_fraction": phase_independent_clearance / same_phase_clearance,
            "proof_scope": (
                "radial 2D cross-section non-contact only; no pin phase/parent, axial stop/collar contact, "
                "retention, bearing/load/tolerance or full-component collision claim"
            ),
        },
        "decision": {
            "source_successor_rig_compatibility_authorized": True,
            "source_successor_geometry_adopted": False,
            "continuous_positive_radial_clearance_proven": True,
            "source_static_1mm_promoted_to_continuous_motion_clearance": False,
            "automatic_downstream_adoption": False,
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


def _negative_controls(
    source: dict[str, Any],
    owner_stack: dict[str, Any],
    successor: dict[str, Any],
    annular: dict[str, Any],
    successor_receipt: dict[str, Any],
    lid_plan: dict[str, Any],
    compatibility: dict[str, Any],
    kwargs: dict[str, Any],
) -> dict[str, str]:
    controls: dict[str, str] = {}

    bad = copy.deepcopy(annular)
    bad["mesh_bore_radius_m"] = 0.0092
    try:
        verify(source, owner_stack, successor, bad, successor_receipt, lid_plan, compatibility, **kwargs)
    except AssertionError as exc:
        controls["insufficient_phase_independent_bore"] = f"HOLD:{exc}"
    else:
        raise AssertionError("insufficient-bore negative control unexpectedly passed")

    bad = copy.deepcopy(successor)
    bad["source_owned_successor"]["automatic_downstream_adoption"] = True
    try:
        verify(source, owner_stack, bad, annular, successor_receipt, lid_plan, compatibility, **kwargs)
    except AssertionError as exc:
        controls["automatic_successor_adoption"] = f"HOLD:{exc}"
    else:
        raise AssertionError("automatic-adoption negative control unexpectedly passed")

    bad = copy.deepcopy(compatibility)
    bad["rig_constraint"]["pin_axial_phase"] = "FIXED_TO_BODY"
    try:
        verify(source, owner_stack, successor, annular, successor_receipt, lid_plan, bad, **kwargs)
    except AssertionError as exc:
        controls["silent_pin_phase_claim"] = f"HOLD:{exc}"
    else:
        raise AssertionError("pin-phase authority negative control unexpectedly passed")

    return controls


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--owner-stack", required=True)
    parser.add_argument("--successor-contract", required=True)
    parser.add_argument("--annular-contract", required=True)
    parser.add_argument("--successor-receipt", required=True)
    parser.add_argument("--lid-plan", required=True)
    parser.add_argument("--compatibility-contract", required=True)
    parser.add_argument("--observed-owner-stack-head", required=True)
    parser.add_argument("--observed-owner-stack-blob", required=True)
    parser.add_argument("--observed-successor-head", required=True)
    parser.add_argument("--observed-successor-blob", required=True)
    parser.add_argument("--observed-annular-blob", required=True)
    parser.add_argument("--observed-lid-rig-head", required=True)
    parser.add_argument("--observed-predecessor-rigging-head", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    source_path = Path(args.source)
    owner_path = Path(args.owner_stack)
    successor_path = Path(args.successor_contract)
    annular_path = Path(args.annular_contract)
    successor_receipt_path = Path(args.successor_receipt)
    lid_plan_path = Path(args.lid_plan)
    compatibility_path = Path(args.compatibility_contract)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    source = json.loads(source_path.read_text(encoding="utf-8"))
    owner = json.loads(owner_path.read_text(encoding="utf-8"))
    successor = json.loads(successor_path.read_text(encoding="utf-8"))
    annular = json.loads(annular_path.read_text(encoding="utf-8"))
    successor_receipt = json.loads(successor_receipt_path.read_text(encoding="utf-8"))
    lid_plan = json.loads(lid_plan_path.read_text(encoding="utf-8"))
    compatibility = json.loads(compatibility_path.read_text(encoding="utf-8"))

    kwargs = {
        "source_sha256": sha256_file(source_path),
        "observed_owner_stack_head": args.observed_owner_stack_head,
        "observed_owner_stack_blob": args.observed_owner_stack_blob,
        "observed_successor_head": args.observed_successor_head,
        "observed_successor_blob": args.observed_successor_blob,
        "observed_annular_blob": args.observed_annular_blob,
        "observed_lid_rig_head": args.observed_lid_rig_head,
        "observed_predecessor_rigging_head": args.observed_predecessor_rigging_head,
    }

    receipt = verify(source, owner, successor, annular, successor_receipt, lid_plan, compatibility, **kwargs)
    receipt["negative_controls"] = _negative_controls(
        source, owner, successor, annular, successor_receipt, lid_plan, compatibility, kwargs
    )
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(RESULT)
    print(MOTION_CLEARANCE_GATE)
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
