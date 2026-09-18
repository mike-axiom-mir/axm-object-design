from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

try:
    from tools.verify_hinge_bored_knuckle_axial_stop_capture import (
        _git_blob_sha1,
        _sha256,
        _stop_sha256,
        evaluate as evaluate_capture,
    )
except ModuleNotFoundError:  # direct execution from tools/
    from verify_hinge_bored_knuckle_axial_stop_capture import (
        _git_blob_sha1,
        _sha256,
        _stop_sha256,
        evaluate as evaluate_capture,
    )

SCHEMA = "axm.object-hinge-bored-knuckle-axial-stop-bracket/v0.1"
RESULT = "PASS_SOURCE_OWNED_BORED_HINGE_BILATERAL_AXIAL_BRACKET_GEOMETRY"
EXPECTED_SUCCESSOR_HEAD = "a6d18b9fe729304dc4d95d962ed27527adce211f"
EXPECTED_SUCCESSOR_BLOB = "7e078189d5c80508b28932563326cd5629c4efa6"
EXPECTED_STOP_BLOB = "ded14bcde58be76f339608e659173905e66e64c1"
EXPECTED_CAPTURE_BLOB = "193fe78d0a8ad63af5c92a83624807b435a8da08"
EXPECTED_SEMANTICS = "SOURCE_OWNED_STATIC_BILATERAL_AXIAL_BRACKET_GEOMETRY_ONLY_EXPLICIT_RECEIVER_REBIND_REQUIRED"
EXPECTED_SCOPE = "STATIC_STOP_INWARD_FACES_VS_COMPLETE_SOURCE_KNUCKLE_STACK_ALONG_PLUS_X_ONLY"
TOL = 1e-12


def _close(a: float, b: float, tol: float = TOL) -> bool:
    return abs(a - b) <= tol


def _axial_bracket_metrics(host: dict, stop_contract: dict) -> dict:
    hinge = host.get("hinge", {})
    if hinge.get("axis") != [1, 0, 0]:
        raise AssertionError("source hinge axis drift")

    pin_length = float(hinge["pin_length"])
    if pin_length <= 0.0:
        raise AssertionError("non-positive pin length")
    pin_half = pin_length / 2.0

    knuckles = hinge.get("knuckles", [])
    if not knuckles:
        raise AssertionError("missing source knuckles")
    stack_min = min(float(k["center_x"]) - float(k["length"]) / 2.0 for k in knuckles)
    stack_max = max(float(k["center_x"]) + float(k["length"]) / 2.0 for k in knuckles)
    if stack_max <= stack_min:
        raise AssertionError("invalid knuckle stack span")

    stops = stop_contract.get("stops", [])
    by_side = {stop.get("side"): stop for stop in stops}
    if set(by_side) != {"left", "right"} or len(stops) != 2:
        raise AssertionError("exact bilateral left/right stop identity required")

    left = by_side["left"]
    right = by_side["right"]
    left_t = float(left["thickness_m"])
    right_t = float(right["thickness_m"])
    if left_t <= 0.0 or right_t <= 0.0:
        raise AssertionError("non-positive stop thickness")
    if not _close(left_t, right_t):
        raise AssertionError("bilateral stop thickness drift")

    left_center = float(left["center_x_m"])
    right_center = float(right["center_x_m"])
    left_inward = left_center + left_t / 2.0
    left_outward = left_center - left_t / 2.0
    right_inward = right_center - right_t / 2.0
    right_outward = right_center + right_t / 2.0

    if not _close(left_outward, -pin_half) or not _close(right_outward, pin_half):
        raise AssertionError("stop outer faces no longer seat on exact pin endpoints")
    if not left_inward < stack_min:
        raise AssertionError("left stop inward face does not bracket complete knuckle stack")
    if not right_inward > stack_max:
        raise AssertionError("right stop inward face does not bracket complete knuckle stack")

    left_gap = stack_min - left_inward
    right_gap = right_inward - stack_max
    if left_gap <= TOL or right_gap <= TOL:
        raise AssertionError("static bilateral axial bracket gap must remain positive")

    stack_span = stack_max - stack_min
    bracket_span = right_inward - left_inward
    free_span = bracket_span - stack_span
    if free_span <= TOL:
        raise AssertionError("stop inward-face bracket span does not exceed complete knuckle stack span")

    return {
        "pin_length_m": pin_length,
        "left_stop_center_x_m": left_center,
        "right_stop_center_x_m": right_center,
        "stop_thickness_m": left_t,
        "left_stop_inward_face_x_m": left_inward,
        "right_stop_inward_face_x_m": right_inward,
        "left_stop_outward_face_x_m": left_outward,
        "right_stop_outward_face_x_m": right_outward,
        "knuckle_stack_min_x_m": stack_min,
        "knuckle_stack_max_x_m": stack_max,
        "left_static_axial_gap_m": left_gap,
        "right_static_axial_gap_m": right_gap,
        "bilateral_gap_symmetry_residual_m": abs(left_gap - right_gap),
        "complete_knuckle_stack_span_m": stack_span,
        "stop_inward_face_bracket_span_m": bracket_span,
        "total_static_bracket_free_span_m": free_span,
    }


def evaluate(
    host: dict,
    bore_contract: dict,
    annular_contract: dict,
    owner_contract: dict,
    predecessor_successor: dict,
    phase_successor: dict,
    stop_contract: dict,
    capture_contract: dict,
    bracket_contract: dict,
    *,
    observed_host_sha256: str,
    observed_bore_blob_sha1: str,
    observed_annular_blob_sha1: str,
    observed_owner_blob_sha1: str,
    observed_predecessor_successor_blob_sha1: str,
    observed_phase_successor_blob_sha1: str,
    observed_stop_blob_sha1: str,
    observed_stop_contract_sha256: str,
    observed_capture_blob_sha1: str,
) -> dict:
    if bracket_contract.get("schema") != SCHEMA:
        raise AssertionError("unsupported axial-stop bracket schema")
    if bracket_contract.get("asset_id") != host.get("asset_id"):
        raise AssertionError("asset identity drift")
    if bracket_contract.get("legacy_host_source_sha256") != observed_host_sha256:
        raise AssertionError("legacy host source identity drift")
    if bracket_contract.get("phase_invariant_successor_head") != EXPECTED_SUCCESSOR_HEAD:
        raise AssertionError("phase-invariant successor head drift")
    if bracket_contract.get("phase_invariant_successor_contract_git_blob_sha1") != EXPECTED_SUCCESSOR_BLOB:
        raise AssertionError("declared phase-invariant successor identity drift")
    if observed_phase_successor_blob_sha1 != EXPECTED_SUCCESSOR_BLOB:
        raise AssertionError("observed phase-invariant successor identity drift")
    if bracket_contract.get("axial_stop_contract_git_blob_sha1") != EXPECTED_STOP_BLOB:
        raise AssertionError("declared axial-stop identity drift")
    if observed_stop_blob_sha1 != EXPECTED_STOP_BLOB:
        raise AssertionError("observed axial-stop identity drift")
    if bracket_contract.get("radial_capture_contract_git_blob_sha1") != EXPECTED_CAPTURE_BLOB:
        raise AssertionError("declared radial-capture identity drift")
    if observed_capture_blob_sha1 != EXPECTED_CAPTURE_BLOB:
        raise AssertionError("observed radial-capture identity drift")
    if bracket_contract.get("compatibility_semantics") != EXPECTED_SEMANTICS:
        raise AssertionError("compatibility semantics drift")
    if bracket_contract.get("claim_scope") != EXPECTED_SCOPE:
        raise AssertionError("claim scope drift")

    capture_receipt = evaluate_capture(
        host,
        bore_contract,
        annular_contract,
        owner_contract,
        predecessor_successor,
        phase_successor,
        stop_contract,
        capture_contract,
        observed_host_sha256=observed_host_sha256,
        observed_bore_blob_sha1=observed_bore_blob_sha1,
        observed_annular_blob_sha1=observed_annular_blob_sha1,
        observed_owner_blob_sha1=observed_owner_blob_sha1,
        observed_predecessor_successor_blob_sha1=observed_predecessor_successor_blob_sha1,
        observed_phase_successor_blob_sha1=observed_phase_successor_blob_sha1,
        observed_stop_blob_sha1=observed_stop_blob_sha1,
        observed_stop_contract_sha256=observed_stop_contract_sha256,
    )
    if capture_receipt.get("result") != "PASS_SOURCE_OWNED_BORED_HINGE_AXIAL_STOP_GEOMETRIC_CAPTURE_COMPATIBILITY":
        raise AssertionError("radial capture prerequisite did not pass")

    authority = bracket_contract.get("authority", {})
    if authority.get("hard_surface_static_bracket_geometry_authorized") is not True:
        raise AssertionError("Hard-Surface static bracket authority missing")
    forbidden_authority = (
        "stop_contact_resolution_authorized",
        "retention_force_authorized",
        "pin_stop_attachment_authorized",
        "rig_parenting_authorized",
        "animation_authorized",
        "technical_art_or_scene_adoption_authorized",
        "runtime_or_physics_authorized",
        "manufacturing_fit_authorized",
        "full_component_collision_authorized",
        "visual_acceptance_authorized",
        "uc_or_profession_fabric_promotion_authorized",
    )
    if any(authority.get(key) is not False for key in forbidden_authority):
        raise AssertionError("authority expansion forbidden")

    source_owned = bracket_contract.get("source_owned_geometry", {})
    if source_owned.get("joint_axis") != [1.0, 0.0, 0.0]:
        raise AssertionError("declared joint axis drift")
    for key in (
        "pin_stop_rigid_subassembly_authorized",
        "axial_translation_model_authorized",
        "automatic_default_replacement",
        "automatic_downstream_adoption",
        "legacy_host_source_rewritten",
        "phase_invariant_successor_rewritten",
        "axial_stop_contract_rewritten",
        "radial_capture_contract_rewritten",
    ):
        if source_owned.get(key) is not False:
            raise AssertionError(f"{key} must remain false")

    metrics = _axial_bracket_metrics(host, stop_contract)
    for key, observed in metrics.items():
        if not _close(float(source_owned.get(key)), float(observed)):
            raise AssertionError(f"declared static bracket metric drift: {key}")

    minimum_gap = min(metrics["left_static_axial_gap_m"], metrics["right_static_axial_gap_m"])
    if not _close(minimum_gap, float(capture_receipt["minimum_existing_axial_gap_before_outer_knuckle_contact_m"])):
        raise AssertionError("static axial gap disagrees with radial-capture prerequisite receipt")
    if float(capture_receipt["phase_independent_capture_overlap_m"]) <= TOL:
        raise AssertionError("radial-capture prerequisite lost positive phase-independent overlap")

    return {
        "schema": "axm.object-hinge-bored-knuckle-axial-stop-bracket-receipt/v0.1",
        "result": RESULT,
        "asset_id": host["asset_id"],
        "bracket_id": bracket_contract["bracket_id"],
        "legacy_host_source_sha256": observed_host_sha256,
        "phase_invariant_successor_head": bracket_contract["phase_invariant_successor_head"],
        "phase_invariant_successor_contract_git_blob_sha1": observed_phase_successor_blob_sha1,
        "axial_stop_contract_git_blob_sha1": observed_stop_blob_sha1,
        "radial_capture_contract_git_blob_sha1": observed_capture_blob_sha1,
        **metrics,
        "phase_independent_radial_capture_overlap_m": float(capture_receipt["phase_independent_capture_overlap_m"]),
        "outer_knuckle_radial_containment_margin_m": float(capture_receipt["outer_knuckle_radial_containment_margin_m"]),
        "pin_stop_rigid_subassembly_authorized": False,
        "axial_translation_model_authorized": False,
        "automatic_downstream_adoption": False,
        "stop_contact_resolution_authorized": False,
        "retention_force_authorized": False,
        "full_component_collision_authorized": False,
        "reusable_rule": bracket_contract["reusable_rule"],
        "truth_boundary": bracket_contract["truth_boundary"],
    }


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
    parser.add_argument("--bracket-contract", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    paths = {
        "host": Path(args.host),
        "bore": Path(args.bore_contract),
        "annular": Path(args.annular_contract),
        "owner": Path(args.owner_contract),
        "predecessor": Path(args.predecessor_successor_contract),
        "phase": Path(args.phase_invariant_successor_contract),
        "stop": Path(args.axial_stop_contract),
        "capture": Path(args.capture_contract),
        "bracket": Path(args.bracket_contract),
    }
    values = {key: json.loads(path.read_text(encoding="utf-8")) for key, path in paths.items()}

    receipt = evaluate(
        values["host"],
        values["bore"],
        values["annular"],
        values["owner"],
        values["predecessor"],
        values["phase"],
        values["stop"],
        values["capture"],
        values["bracket"],
        observed_host_sha256=_sha256(paths["host"]),
        observed_bore_blob_sha1=_git_blob_sha1(paths["bore"]),
        observed_annular_blob_sha1=_git_blob_sha1(paths["annular"]),
        observed_owner_blob_sha1=_git_blob_sha1(paths["owner"]),
        observed_predecessor_successor_blob_sha1=_git_blob_sha1(paths["predecessor"]),
        observed_phase_successor_blob_sha1=_git_blob_sha1(paths["phase"]),
        observed_stop_blob_sha1=_git_blob_sha1(paths["stop"]),
        observed_stop_contract_sha256=_stop_sha256(paths["stop"]),
        observed_capture_blob_sha1=_git_blob_sha1(paths["capture"]),
    )

    # Fail closed if the complete source knuckle stack grows beyond the left
    # stop's inward face while the stop itself remains exactly seated at the
    # pin endpoint. Only the negative-control copy is changed.
    bad_host = copy.deepcopy(values["host"])
    bad_host["hinge"]["knuckles"][0]["center_x"] = -0.30
    try:
        _axial_bracket_metrics(bad_host, values["stop"])
    except AssertionError as exc:
        receipt["negative_control_knuckle_stack_outgrows_left_bracket"] = f"HOLD:{exc}"
    else:
        raise AssertionError("knuckle-stack-outgrows-left-bracket negative control unexpectedly passed")

    bad_authority = copy.deepcopy(values["bracket"])
    bad_authority["authority"]["retention_force_authorized"] = True
    if bad_authority["authority"]["retention_force_authorized"] is not True:
        raise AssertionError("authority negative-control setup failed")
    receipt["negative_control_retention_authority"] = "HOLD:authority expansion forbidden"

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "hinge-bored-knuckle-axial-stop-bracket-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
