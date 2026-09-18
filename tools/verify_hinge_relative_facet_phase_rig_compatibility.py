from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path
from typing import Any

SCHEMA = "axm.object-hinge-relative-facet-phase-rig-compatibility/v0.1"
RESULT = "PASS_HINGE_RELATIVE_FACET_PHASE_SUCCESSOR_RIG_PHASE_COMPOSITION_CONTINUOUS_0_TO_110"
SOURCE_SUCCESSOR_HEAD = "ef1dfc2f2c1adbe3c90ba089c66ac09d223df25c"
SOURCE_SUCCESSOR_BLOB = "e7a44523ea80e567a745cd61af7fd7005757cc12"
PREDECESSOR_RIGGING_HEAD = "cf377074f70ce7f7e386f1378c51705b3db4d305"
HISTORICAL_LID_RIG_HEAD = "4b72c9918c5fc1e89bd18a0be24fb4afac6e7775"
LID_PLAN_DIGEST = "0ad6dc2ca22676cf301579932e599a441eb7c4bccce31991d1b727aeb22ac422"
SOURCE_SHA256 = "49b1f9ed9865893d6de6f1ec8f069576732df694853fde4e3fcff366de32644a"
REPRESENTATIVE_ANGLES = [0, 15, 30, 45, 60, 75, 90, 105, 110]
TOL = 1e-12


def _assert_exact(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"{label} drift: {actual!r} != {expected!r}")


def _assert_close(actual: float, expected: float, label: str, tol: float = TOL) -> None:
    if abs(float(actual) - float(expected)) > tol:
        raise AssertionError(f"{label} drift: {actual} != {expected}")


def _rotate_yz(y: float, z: float, angle_deg: float) -> tuple[float, float]:
    a = math.radians(angle_deg)
    c, s = math.cos(a), math.sin(a)
    return (c * y - s * z, s * y + c * z)


def _composition_residual(radius: float, source_phase_deg: float, applied_deg: float) -> float:
    py, pz = _rotate_yz(radius, 0.0, source_phase_deg)
    ay, az = _rotate_yz(py, pz, applied_deg)
    cy, cz = _rotate_yz(radius, 0.0, source_phase_deg + applied_deg)
    return math.hypot(ay - cy, az - cz)


def verify(
    predecessor_rig_receipt: dict[str, Any],
    successor003: dict[str, Any],
    successor003_receipt: dict[str, Any],
    compatibility: dict[str, Any],
    *,
    observed_successor_head: str,
    observed_successor_blob: str,
    observed_predecessor_rigging_head: str,
) -> dict[str, Any]:
    _assert_exact(observed_predecessor_rigging_head, PREDECESSOR_RIGGING_HEAD, "predecessor Rigging head")
    _assert_exact(
        predecessor_rig_receipt.get("result"),
        "PASS_PHASE_INVARIANT_BORED_KNUCKLE_SUCCESSOR_RIG_1MM_RADIAL_NONCONTACT_CONTINUOUS_0_TO_110",
        "predecessor Rigging result",
    )
    _assert_exact(predecessor_rig_receipt.get("source_sha256"), SOURCE_SHA256, "source identity")
    pred_rig = predecessor_rig_receipt.get("predecessor_rigging", {})
    _assert_exact(pred_rig.get("historical_lid_rig_head"), HISTORICAL_LID_RIG_HEAD, "historical lid rig")
    _assert_exact(pred_rig.get("lid_plan_digest"), LID_PLAN_DIGEST, "lid plan digest")
    pred_cert = predecessor_rig_receipt.get("continuous_radial_certificate", {})
    _assert_exact(pred_cert.get("domain_deg"), [0.0, 110.0], "predecessor motion domain")
    _assert_exact(pred_cert.get("segments"), 12, "predecessor segment count")
    _assert_close(
        pred_cert.get("phase_independent_radial_clearance_lower_bound_m"),
        0.0009999999999999992,
        "predecessor phase-independent radial lower bound",
    )

    _assert_exact(observed_successor_head, SOURCE_SUCCESSOR_HEAD, "source successor003 head")
    _assert_exact(observed_successor_blob, SOURCE_SUCCESSOR_BLOB, "source successor003 blob")
    _assert_exact(
        successor003.get("schema"),
        "axm.object-hinge-bored-knuckle-relative-facet-phase-source-successor/v0.1",
        "source successor003 schema",
    )
    _assert_exact(
        successor003.get("successor_id"),
        "modular-equipment-case-001/hinge-bored-knuckle-relative-facet-phase-source-successor-003",
        "source successor003 id",
    )
    source_phase = successor003.get("source_owned_successor", {})
    _assert_exact(source_phase.get("segments"), 12, "source segment count")
    _assert_exact(source_phase.get("hinge_axis"), [1, 0, 0], "source hinge axis")
    _assert_close(source_phase.get("owner_group_phase_deg", {}).get("body"), 0.0, "body source phase")
    _assert_close(source_phase.get("owner_group_phase_deg", {}).get("lid"), 15.0, "lid source phase")
    _assert_close(source_phase.get("relative_lid_minus_body_phase_deg"), 15.0, "relative source phase")
    _assert_exact(source_phase.get("rotate_outer_and_bore_cross_sections_together"), True, "complete cross-section phase rotation")
    for key in (
        "automatic_default_replacement",
        "automatic_downstream_adoption",
        "legacy_host_source_rewritten",
        "successor002_rewritten",
    ):
        _assert_exact(source_phase.get(key), False, f"source authority {key}")
    _assert_exact(successor003.get("authority", {}).get("rig_parenting_authorized"), False, "Hard-Surface Rigging authority boundary")

    _assert_exact(
        successor003_receipt.get("result"),
        "PASS_SOURCE_OWNED_HINGE_RELATIVE_FACET_PHASE_SUCCESSOR",
        "source successor003 result",
    )
    _assert_exact(successor003_receipt.get("successor_id"), successor003.get("successor_id"), "source receipt id")
    _assert_exact(successor003_receipt.get("segments"), 12, "source receipt segment count")
    _assert_close(successor003_receipt.get("body_phase_deg"), 0.0, "source receipt body phase")
    _assert_close(successor003_receipt.get("lid_phase_deg"), 15.0, "source receipt lid phase")
    _assert_close(successor003_receipt.get("relative_lid_minus_body_phase_deg"), 15.0, "source receipt relative phase")
    _assert_exact(successor003_receipt.get("knuckle_count"), 5, "source receipt knuckle count")
    _assert_exact(successor003_receipt.get("body_owned_knuckles"), 3, "source receipt body count")
    _assert_exact(successor003_receipt.get("lid_owned_knuckles"), 2, "source receipt lid count")
    _assert_close(
        successor003_receipt.get("phase_independent_pin_bore_clearance_m"),
        0.0009999999999999992,
        "source receipt 1mm lower bound",
    )
    _assert_exact(successor003_receipt.get("automatic_downstream_adoption"), False, "source receipt adoption boundary")

    _assert_exact(compatibility.get("schema"), SCHEMA, "compatibility schema")
    _assert_exact(compatibility.get("asset_id"), "modular-equipment-case-001", "compatibility asset")
    _assert_exact(
        compatibility.get("compatibility_id"),
        "modular-equipment-case-001/hinge-relative-facet-phase-rig-compatibility-003",
        "compatibility id",
    )
    receiver_source = compatibility.get("source_successor", {})
    _assert_exact(receiver_source.get("head"), SOURCE_SUCCESSOR_HEAD, "compatibility source head")
    _assert_exact(receiver_source.get("contract_git_blob_sha1"), SOURCE_SUCCESSOR_BLOB, "compatibility source blob")
    _assert_exact(compatibility.get("predecessor_rigging_head"), PREDECESSOR_RIGGING_HEAD, "compatibility predecessor Rigging head")
    _assert_exact(compatibility.get("representative_source_angles_deg"), REPRESENTATIVE_ANGLES, "representative angles")

    rig = compatibility.get("historical_rig", {})
    _assert_exact(rig.get("head"), HISTORICAL_LID_RIG_HEAD, "historical lid rig contract")
    _assert_exact(rig.get("plan_digest"), LID_PLAN_DIGEST, "historical rig digest")
    _assert_exact(rig.get("joint_id"), "rear-lid-hinge-001", "joint id")
    _assert_exact(rig.get("axis"), [1, 0, 0], "rig axis")
    _assert_exact(rig.get("angle_limit_deg"), [0, 110], "rig angle domain")
    _assert_exact(rig.get("opening_rotation_sign"), -1, "rig opening sign")
    _assert_exact(rig.get("moving_lid_knuckles"), ["l0", "l1"], "moving lid knuckles")
    _assert_exact(rig.get("fixed_body_knuckles"), ["b0", "b1", "b2"], "fixed body knuckles")

    phase = compatibility.get("source_phase_contract", {})
    _assert_exact(phase.get("segments"), 12, "compatibility phase segments")
    _assert_close(phase.get("period_deg"), 30.0, "phase period")
    _assert_close(phase.get("body_phase_deg"), 0.0, "compatibility body phase")
    _assert_close(phase.get("lid_phase_deg"), 15.0, "compatibility lid phase")
    _assert_close(phase.get("relative_lid_minus_body_phase_deg"), 15.0, "compatibility relative phase")
    _assert_exact(phase.get("outer_and_bore_rotate_together"), True, "compatibility cross-section phase")

    constraint = compatibility.get("rig_constraint", {})
    _assert_exact(constraint.get("hinge_centerline"), "EXACT_SOURCE_PLUS_X_CENTERLINE_NO_TRANSLATION", "hinge centerline")
    _assert_exact(
        constraint.get("source_phase_application"),
        "APPLY_SOURCE_OWNER_PHASE_ONCE_THEN_EXISTING_LID_RIG_ROTATION_ABOUT_SAME_PLUS_X_AXIS",
        "source phase application",
    )
    _assert_exact(constraint.get("body_parent"), "body_shell", "body parent")
    _assert_exact(constraint.get("lid_parent"), "lid_shell", "lid parent")
    _assert_exact(constraint.get("pin_axial_phase"), "UNSPECIFIED", "pin phase")
    _assert_exact(constraint.get("pin_physical_owner"), "UNSPECIFIED", "pin owner")

    decision = compatibility.get("decision", {})
    for key in (
        "source_successor_rig_compatibility_authorized",
        "source_owner_relative_facet_phase_preserved_through_rig",
        "phase_independent_1mm_radial_lower_bound_retained",
    ):
        _assert_exact(decision.get(key), True, f"Rigging decision {key}")
    for key in ("source_successor_geometry_adopted", "automatic_downstream_adoption", "pin_parent_or_axial_phase_claimed"):
        _assert_exact(decision.get(key), False, f"Rigging decision boundary {key}")

    authority = compatibility.get("authority", {})
    _assert_exact(authority.get("rigging_constraint_evidence_authorized"), True, "Rigging authority")
    for key in (
        "animation_accepted",
        "technical_art_target_host_accepted",
        "runtime_accepted",
        "physics_or_load_accepted",
        "manufacturing_fit_or_bearing_accepted",
        "full_component_collision_accepted",
        "visual_accepted",
        "canon_or_production_accepted",
    ):
        _assert_exact(authority.get(key), False, f"downstream authority {key}")

    frozen = successor003.get("frozen_geometry", {})
    outer_radius = float(frozen["knuckle_outer_circumradius_m"])
    bore_radius = float(frozen["bore_circumradius_m"])
    pin_radius = float(frozen["source_pin_circumradius_m"])
    factor = math.cos(math.pi / 12.0)
    radial_lower_bound = bore_radius * factor - pin_radius
    if radial_lower_bound < 0.001 - TOL:
        raise AssertionError("phase-independent 1mm radial lower bound lost")
    _assert_close(radial_lower_bound, successor003_receipt.get("phase_independent_pin_bore_clearance_m"), "source/Rigging radial lower-bound continuity")

    witnesses = []
    max_outer_residual = 0.0
    max_bore_residual = 0.0
    max_body_drift = 0.0
    for source_angle in REPRESENTATIVE_ANGLES:
        applied = -float(source_angle)
        outer_residual = _composition_residual(outer_radius, 15.0, applied)
        bore_residual = _composition_residual(bore_radius, 15.0, applied)
        max_outer_residual = max(max_outer_residual, outer_residual)
        max_bore_residual = max(max_bore_residual, bore_residual)
        body_drift = _composition_residual(outer_radius, 0.0, 0.0)
        max_body_drift = max(max_body_drift, body_drift)
        witnesses.append(
            {
                "source_angle_deg": float(source_angle),
                "applied_lid_angle_deg": applied,
                "body_source_phase_deg": 0.0,
                "lid_source_phase_deg": 15.0,
                "lid_unwrapped_cross_section_phase_deg": 15.0 + applied,
                "lid_phase_class_period_deg": 30.0,
                "moving_lid_knuckles": ["l0", "l1"],
                "fixed_body_knuckles": ["b0", "b1", "b2"],
                "outer_same_axis_composition_residual_m": outer_residual,
                "bore_same_axis_composition_residual_m": bore_residual,
                "phase_independent_radial_clearance_lower_bound_m": radial_lower_bound,
            }
        )

    if max_outer_residual > TOL or max_bore_residual > TOL or max_body_drift > TOL:
        raise AssertionError("representative same-axis phase composition residual exceeds tolerance")

    return {
        "schema": "axm.object-hinge-relative-facet-phase-rig-compatibility-receipt/v0.1",
        "result": RESULT,
        "asset_id": "modular-equipment-case-001",
        "compatibility_id": compatibility["compatibility_id"],
        "source_sha256": SOURCE_SHA256,
        "source_successor": {
            "head": SOURCE_SUCCESSOR_HEAD,
            "contract_git_blob_sha1": SOURCE_SUCCESSOR_BLOB,
            "successor_id": successor003["successor_id"],
            "source_owner_result": successor003_receipt["result"],
        },
        "predecessor_rigging": {
            "head": PREDECESSOR_RIGGING_HEAD,
            "result": predecessor_rig_receipt["result"],
            "historical_lid_rig_head": HISTORICAL_LID_RIG_HEAD,
            "lid_plan_digest": LID_PLAN_DIGEST,
        },
        "continuous_phase_composition_certificate": {
            "kind": "SAME_AXIS_SO2_ROTATION_COMPOSITION",
            "domain_deg": [0.0, 110.0],
            "hinge_axis": [1, 0, 0],
            "opening_rotation_sign": -1,
            "segments": 12,
            "phase_period_deg": 30.0,
            "body_source_phase_deg": 0.0,
            "lid_source_phase_deg": 15.0,
            "relative_source_phase_deg": 15.0,
            "identity": "R_x(-theta) * R_x(+15deg) = R_x(+15deg-theta) for every real theta in [0,110]",
            "phase_applied_exactly_once": True,
            "outer_and_bore_phase_locked": True,
            "phase_independent_radial_clearance_lower_bound_m": radial_lower_bound,
            "proof_scope": "source facet-phase offset plus existing rigid lid articulation only; no Animation timing/playback, pin phase/ownership, full collision, target-host or visual claim",
        },
        "representative_pose_witnesses": witnesses,
        "max_outer_same_axis_composition_residual_m": max_outer_residual,
        "max_bore_same_axis_composition_residual_m": max_bore_residual,
        "max_fixed_body_phase_drift_m": max_body_drift,
        "decision": {
            "source_successor_rig_compatibility_authorized": True,
            "source_owner_relative_facet_phase_preserved_through_rig": True,
            "phase_independent_1mm_radial_lower_bound_retained": radial_lower_bound >= 0.001 - TOL,
            "source_successor_geometry_adopted": False,
            "automatic_downstream_adoption": False,
            "pin_parent_or_axial_phase_claimed": False,
        },
        "truth_boundary": {
            "source_geometry_changed": False,
            "historical_rig_changed": False,
            "phase_successor_visual_improvement_claimed": False,
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


def negative_controls(predecessor: dict, successor: dict, source_receipt: dict, compatibility: dict) -> dict[str, str]:
    controls: dict[str, str] = {}

    def expect_hold(name: str, pred: dict, succ: dict, rec: dict, comp: dict) -> None:
        try:
            verify(
                pred,
                succ,
                rec,
                comp,
                observed_successor_head=SOURCE_SUCCESSOR_HEAD,
                observed_successor_blob=SOURCE_SUCCESSOR_BLOB,
                observed_predecessor_rigging_head=PREDECESSOR_RIGGING_HEAD,
            )
        except AssertionError as exc:
            controls[name] = f"HOLD:{exc}"
        else:
            raise AssertionError(f"negative control unexpectedly passed: {name}")

    bad = copy.deepcopy(successor)
    bad["source_owned_successor"]["owner_group_phase_deg"]["lid"] = 0.0
    expect_hold("collapsed_lid_source_phase", predecessor, bad, source_receipt, compatibility)

    bad = copy.deepcopy(successor)
    bad["source_owned_successor"]["owner_group_phase_deg"]["lid"] = 30.0
    expect_hold("double_applied_lid_source_phase", predecessor, bad, source_receipt, compatibility)

    bad_comp = copy.deepcopy(compatibility)
    bad_comp["historical_rig"]["moving_lid_knuckles"] = ["l0"]
    expect_hold("parent_partition_drift", predecessor, successor, source_receipt, bad_comp)

    bad_comp = copy.deepcopy(compatibility)
    bad_comp["historical_rig"]["angle_limit_deg"] = [0, 115]
    expect_hold("motion_domain_widening", predecessor, successor, source_receipt, bad_comp)

    bad_comp = copy.deepcopy(compatibility)
    bad_comp["decision"]["source_successor_geometry_adopted"] = True
    expect_hold("silent_geometry_adoption", predecessor, successor, source_receipt, bad_comp)

    bad_comp = copy.deepcopy(compatibility)
    bad_comp["authority"]["animation_accepted"] = True
    expect_hold("animation_authority_expansion", predecessor, successor, source_receipt, bad_comp)

    bad_comp = copy.deepcopy(compatibility)
    bad_comp["authority"]["runtime_accepted"] = True
    expect_hold("runtime_authority_expansion", predecessor, successor, source_receipt, bad_comp)

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

    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    predecessor = load(args.predecessor_rig_receipt)
    successor = load(args.successor_contract)
    source_receipt = load(args.successor_receipt)
    compatibility = load(args.compatibility_contract)

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
    (args.out / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
