from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import build_modular_case
import verify_lid_keeper_lever_ordering as authored

SCHEMA = "axm.object-latch-transition-contact-envelope/v0.1"
RESULT = "PASS_CONTINUOUS_NEUTRAL_LID_LATCH_PROOF_VOLUME_EXIT_REENTRY__INTENTIONAL_ENGAGEMENT_PRESERVED"
SOURCE_SHA256 = "49b1f9ed9865893d6de6f1ec8f069576732df694853fde4e3fcff366de32644a"
SOURCE_INTERFACE_HEAD = "6086f39a3da344c57a68653f90d040e03e04cec2"
SOURCE_RIG_HEAD = "a1acd2bcb2074f41e536562f2673508e2cb0a4d5"
SOURCE_RIG_BINDING_SHA256 = "615f8ff34cc0897fd399345301efce1ca9cb0aa58e86caca92b914049b89adce"
MECHANICAL_POLICY_HEAD = "8a23c32ebc6b4e1188d2961c878d9dc365bb6da7"
MECHANICAL_POLICY_BLOB = "c96437649bf5d5d7e7bf49a2206f6d6baeec5cd9"
PREVIOUS_MOVING_CLEARANCE_HEAD = "44e0a56872a823cf768c749672116fd026b1ef5e"
PREVIOUS_MOVING_CLEARANCE_ARTIFACT_ID = 10483747546
PREVIOUS_MOVING_CLEARANCE_ARTIFACT_SHA256 = "2785d67b29325a4041f5761033b56d07b93aa30ca9645db05434d432892b4a9e"
IDENTITY_EPS = 1e-12
CLASSIFICATION_EPS_M = 1e-12


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _value(coeff: tuple[float, float, float], angle_deg: float) -> float:
    constant, cos_coeff, sin_coeff = coeff
    angle = math.radians(angle_deg)
    return constant + cos_coeff * math.cos(angle) + sin_coeff * math.sin(angle)


def _stationary_angles(coeff: tuple[float, float, float], lo_deg: float, hi_deg: float) -> list[float]:
    _, cos_coeff, sin_coeff = coeff
    if abs(cos_coeff) <= IDENTITY_EPS and abs(sin_coeff) <= IDENTITY_EPS:
        return []
    base = math.degrees(math.atan2(sin_coeff, cos_coeff))
    result: list[float] = []
    for k in range(-4, 5):
        for offset in (0.0, 180.0):
            angle = base + offset + 360.0 * k
            if lo_deg < angle < hi_deg:
                result.append(angle)
    return result


def _continuous_extreme(
    coeff: tuple[float, float, float], lo_deg: float, hi_deg: float, *, want_max: bool
) -> tuple[float, float]:
    candidates = [float(lo_deg), float(hi_deg), *_stationary_angles(coeff, lo_deg, hi_deg)]
    rows = [(_value(coeff, angle), angle) for angle in candidates]
    return (max(rows) if want_max else min(rows))


def _axis_coefficients(keeper: dict[str, Any], lever: dict[str, Any], pivot: list[float]) -> dict[str, list[tuple[float, float, float]]]:
    if keeper.get("kind") != "box" or lever.get("kind") != "box":
        raise AssertionError("bounded latch transition proof requires exact box keeper and lever proof volumes")

    _, keeper_y, keeper_z = map(float, keeper["center_m"])
    _, keeper_size_y, keeper_size_z = map(float, keeper["size_m"])
    _, lever_y, lever_z = map(float, lever["center_m"])
    _, lever_size_y, lever_size_z = map(float, lever["size_m"])
    pivot_y, pivot_z = float(pivot[1]), float(pivot[2])

    keeper_half_y = keeper_size_y / 2.0
    keeper_half_z = keeper_size_z / 2.0
    lever_half_y = lever_size_y / 2.0
    lever_half_z = lever_size_z / 2.0
    rel_y = lever_y - pivot_y
    rel_z = lever_z - pivot_z

    # On the exact source-owned 0..50 degree +X rotation envelope, sin/cos are non-negative.
    # Each SAT signed interval gap is therefore exactly C + A*cos(theta) + B*sin(theta).
    return {
        "world_y": [
            (
                pivot_y - keeper_y - keeper_half_y,
                rel_y - lever_half_y,
                -rel_z - lever_half_z,
            ),
            (
                keeper_y - keeper_half_y - pivot_y,
                -rel_y - lever_half_y,
                rel_z - lever_half_z,
            ),
        ],
        "world_z": [
            (
                pivot_z - keeper_z - keeper_half_z,
                rel_z - lever_half_z,
                rel_y - lever_half_y,
            ),
            (
                keeper_z - keeper_half_z - pivot_z,
                -rel_z - lever_half_z,
                -rel_y - lever_half_y,
            ),
        ],
        "lever_local_y": [
            (
                rel_y - lever_half_y,
                pivot_y - keeper_y - keeper_half_y,
                pivot_z - keeper_z - keeper_half_z,
            ),
            (
                -rel_y - lever_half_y,
                keeper_y - keeper_half_y - pivot_y,
                keeper_z - keeper_half_z - pivot_z,
            ),
        ],
        "lever_local_z": [
            (
                rel_z - lever_half_z,
                pivot_z - keeper_z - keeper_half_z,
                -pivot_y + keeper_y - keeper_half_y,
            ),
            (
                -rel_z - lever_half_z,
                keeper_z - keeper_half_z - pivot_z,
                pivot_y - keeper_y - keeper_half_y,
            ),
        ],
    }


def _axis_gap(coefficients: dict[str, list[tuple[float, float, float]]], axis: str, angle_deg: float) -> float:
    return max(_value(coeff, angle_deg) for coeff in coefficients[axis])


def _sat_gap_from_coefficients(coefficients: dict[str, list[tuple[float, float, float]]], angle_deg: float) -> float:
    return max(_axis_gap(coefficients, axis, angle_deg) for axis in coefficients)


def _find_monotonic_root(coeff: tuple[float, float, float], lo_deg: float, hi_deg: float) -> float:
    lo_value = _value(coeff, lo_deg)
    hi_value = _value(coeff, hi_deg)
    if not lo_value < 0.0 or not hi_value > 0.0:
        raise AssertionError("expected release separator to bracket one overlap-to-separation transition")
    lo = float(lo_deg)
    hi = float(hi_deg)
    for _ in range(100):
        mid = (lo + hi) / 2.0
        if _value(coeff, mid) > 0.0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2.0


def _validate_exact_identity(
    *,
    source_path: Path,
    source_interface: dict[str, Any],
    source_rig_binding: dict[str, Any],
    mechanical_policy: dict[str, Any],
    observed_source_interface_head: str,
    observed_source_rig_head: str,
    observed_mechanical_policy_head: str,
    observed_mechanical_policy_blob: str,
    observed_previous_moving_clearance_head: str,
) -> None:
    if sha256_file(source_path) != SOURCE_SHA256:
        raise AssertionError("exact Object source byte identity drift")
    if observed_source_interface_head != SOURCE_INTERFACE_HEAD:
        raise AssertionError("source latch interface head drift")
    if observed_source_rig_head != SOURCE_RIG_HEAD:
        raise AssertionError("source Rigging binding head drift")
    if observed_mechanical_policy_head != MECHANICAL_POLICY_HEAD:
        raise AssertionError("mechanical state policy donor head drift")
    if observed_mechanical_policy_blob != MECHANICAL_POLICY_BLOB:
        raise AssertionError("mechanical state policy blob drift")
    if observed_previous_moving_clearance_head != PREVIOUS_MOVING_CLEARANCE_HEAD:
        raise AssertionError("previous moving-lid Rigging proof head drift")

    if source_interface.get("schema") != "axm.object-front-latch-pivot-interface/v0.1":
        raise AssertionError("unexpected source latch interface schema")
    if source_interface.get("interface_id") != "front-latch-pivot-interface-001":
        raise AssertionError("source latch interface identity drift")
    if source_interface.get("joint_axis") not in ([1, 0, 0], [1.0, 0.0, 0.0]):
        raise AssertionError("source latch +X joint axis drift")
    travel = source_interface.get("travel_envelope_deg", {})
    if float(travel.get("closed", math.nan)) != 0.0 or float(travel.get("review_release", math.nan)) != 50.0:
        raise AssertionError("source latch 0..50 degree review envelope drift")

    if source_rig_binding.get("schema") != "axm.object-front-latch-source-rig-binding/v0.1":
        raise AssertionError("unexpected source Rigging binding schema")
    if source_rig_binding.get("binding_id") != "front-latch-source-rig-binding-002":
        raise AssertionError("source Rigging binding identity drift")
    if source_rig_binding.get("host_source_sha256") != SOURCE_SHA256:
        raise AssertionError("source Rigging host identity drift")
    source_interface_dep = source_rig_binding.get("source_interface", {})
    if source_interface_dep.get("head") != SOURCE_INTERFACE_HEAD:
        raise AssertionError("source Rigging binding no longer pins exact source interface head")
    if source_rig_binding.get("pose_samples_deg") != [0.0, 25.0, 50.0]:
        raise AssertionError("source Rigging representative latch envelope drift")

    if mechanical_policy.get("schema") != "axm.object-front-latch-mechanical-state-policy/v0.1":
        raise AssertionError("unexpected mechanical state policy schema")
    if mechanical_policy.get("policy_id") != "front-latch-mechanical-state-guard-001":
        raise AssertionError("mechanical state policy identity drift")
    policy_interface = mechanical_policy.get("source_interface_dependency", {})
    if policy_interface.get("exact_head") != SOURCE_INTERFACE_HEAD:
        raise AssertionError("mechanical policy source-interface dependency drift")
    animation_dep = mechanical_policy.get("animation_observation_dependency", {})
    if animation_dep.get("required_rigging_head") != PREVIOUS_MOVING_CLEARANCE_HEAD:
        raise AssertionError("mechanical policy previous Rigging dependency drift")
    if int(animation_dep.get("required_rigging_artifact_id", -1)) != PREVIOUS_MOVING_CLEARANCE_ARTIFACT_ID:
        raise AssertionError("mechanical policy Rigging artifact id drift")
    if animation_dep.get("required_rigging_artifact_sha256") != PREVIOUS_MOVING_CLEARANCE_ARTIFACT_SHA256:
        raise AssertionError("mechanical policy Rigging artifact digest drift")

    rules = mechanical_policy.get("source_rules", {})
    if float(rules.get("lid_departure_requires_latch_angle_deg", math.nan)) != 50.0:
        raise AssertionError("mechanical policy release angle drift")
    if float(rules.get("latch_may_enter_below_release_angle_only_when_lid_open_angle_deg", math.nan)) != 0.0:
        raise AssertionError("mechanical policy neutral-lid transition guard drift")
    if rules.get("neutral_engagement_overlap_is_not_a_collision_defect") is not True:
        raise AssertionError("mechanical policy lost intentional engagement overlap semantic")
    if rules.get("continuous_release_clearance_claimed") is not False:
        raise AssertionError("mechanical policy silently promotes full release clearance")
    if rules.get("continuous_reengagement_clearance_claimed") is not False:
        raise AssertionError("mechanical policy silently promotes full reengagement clearance")
    if rules.get("animation_timing_owned") is not False or rules.get("runtime_controller_owned") is not False:
        raise AssertionError("mechanical policy authority inflation into Animation/Runtime")


def _verify_station_transition(
    keeper: dict[str, Any], lever: dict[str, Any], pivot: list[float], *, station_id: str
) -> dict[str, Any]:
    coefficients = _axis_coefficients(keeper, lever, pivot)
    release_start = 0.0
    release_end = 50.0

    # The exact source geometry makes this branch the first separating SAT witness.
    separator = coefficients["lever_local_y"][1]
    separator_start = _value(separator, release_start)
    separator_end = _value(separator, release_end)
    root_deg = _find_monotonic_root(separator, release_start, release_end)

    # d/d(theta_rad) [C + A cos(theta) + B sin(theta)] = B cos(theta) - A sin(theta).
    _, cos_coeff, sin_coeff = separator
    derivative_coeff = (0.0, sin_coeff, -cos_coeff)
    derivative_min_m_per_rad, derivative_min_at = _continuous_extreme(
        derivative_coeff, release_start, release_end, want_max=False
    )
    if derivative_min_m_per_rad <= CLASSIFICATION_EPS_M:
        raise AssertionError("release separator is no longer strictly monotonic through 0..50 degrees")

    # Before the root, prove every signed SAT interval gap on all four unique rectangle axes is <= 0.
    pre_root_axis_maxima: dict[str, float] = {}
    for axis, branches in coefficients.items():
        maxima = [_continuous_extreme(coeff, release_start, root_deg, want_max=True)[0] for coeff in branches]
        axis_max = max(maxima)
        pre_root_axis_maxima[axis] = axis_max
        if axis_max > CLASSIFICATION_EPS_M:
            raise AssertionError(f"unexpected earlier proof-volume separation on {axis}: {axis_max}")

    # At the root all SAT axes are non-positive and the selected axis touches at zero.
    root_sat_gap = _sat_gap_from_coefficients(coefficients, root_deg)
    if abs(root_sat_gap) > 5e-12:
        raise AssertionError(f"transition root is not SAT touch within tolerance: {root_sat_gap}")

    # After the root, strict monotonicity of the selected branch gives continuous positive separation.
    if separator_end <= CLASSIFICATION_EPS_M:
        raise AssertionError("release endpoint is not positively separated")

    representative_angles = [0.0, 5.0, 10.0, 25.0, 50.0]
    representative: list[dict[str, Any]] = []
    for angle in representative_angles:
        keeper_poly = authored._rect_yz(keeper, pivot, 0.0)
        lever_poly = authored._rect_yz(lever, pivot, angle)
        helper_sat = authored._sat_separation_m(keeper_poly, lever_poly)
        analytic_sat = _sat_gap_from_coefficients(coefficients, angle)
        if abs(helper_sat - analytic_sat) > 1e-12:
            raise AssertionError(
                f"analytic/helper SAT disagreement station={station_id} angle={angle}: {analytic_sat} vs {helper_sat}"
            )
        representative.append(
            {
                "latch_angle_deg": angle,
                "sat_gap_m": analytic_sat,
                "classification": "SEPARATED" if analytic_sat > CLASSIFICATION_EPS_M else "OVERLAP_OR_TOUCH",
            }
        )

    if representative[0]["sat_gap_m"] >= 0.0:
        raise AssertionError("neutral source engagement no longer overlaps")
    if representative[-1]["sat_gap_m"] <= 0.0:
        raise AssertionError("50 degree source release endpoint no longer separates")

    other_axes = [axis for axis in coefficients if axis != "lever_local_y"]
    maximum_other_axis_gap_before_root = max(pre_root_axis_maxima[axis] for axis in other_axes)

    return {
        "station_id": station_id,
        "keeper_component": keeper["name"],
        "lever_component": lever["name"],
        "release_path_deg": [release_start, release_end],
        "reengagement_path_deg": [release_end, release_start],
        "proof_volume_overlap_interval_deg": {"lower_inclusive": release_start, "upper_exclusive": root_deg},
        "proof_volume_touch_angle_deg": root_deg,
        "proof_volume_separated_interval_deg": {"lower_exclusive": root_deg, "upper_inclusive": release_end},
        "separator_axis": "lever_local_y",
        "separator_gap_start_m": separator_start,
        "separator_gap_end_m": separator_end,
        "separator_min_derivative_m_per_rad": derivative_min_m_per_rad,
        "separator_min_derivative_witness_deg": derivative_min_at,
        "maximum_nonseparator_axis_gap_before_touch_m": maximum_other_axis_gap_before_root,
        "pre_touch_axis_maxima_m": pre_root_axis_maxima,
        "representative_sat": representative,
        "reverse_reengagement_classification": "EXACT_REVERSE_SINGLE_REENTRY_AT_SAME_TOUCH_ANGLE",
    }


def verify_transition(
    source: dict[str, Any],
    source_interface: dict[str, Any],
    source_rig_binding: dict[str, Any],
    mechanical_policy: dict[str, Any],
) -> dict[str, Any]:
    built = build_modular_case.build(source)
    components = {row["name"]: row for row in built["components"]}
    stations = {row["id"]: row for row in source_interface.get("stations", [])}
    if set(stations) != {"left", "right"}:
        raise AssertionError("continuous transition proof requires exact bilateral latch stations")

    receipts: list[dict[str, Any]] = []
    for station_id in ("left", "right"):
        station = stations[station_id]
        keeper = components.get(station["keeper_component"])
        lever = components.get(station["lever_component"])
        if keeper is None or lever is None:
            raise AssertionError("source latch proof-volume component missing")
        if station.get("keeper_owner_component") != "lid_shell":
            raise AssertionError("keeper owner drift")
        if station.get("lever_owner_component") != "front_service_panel":
            raise AssertionError("lever owner drift")
        pivot = [float(v) for v in station["pivot_origin_m"]]
        receipts.append(_verify_station_transition(keeper, lever, pivot, station_id=station_id))

    threshold_residual = abs(
        receipts[0]["proof_volume_touch_angle_deg"] - receipts[1]["proof_volume_touch_angle_deg"]
    )
    endpoint_gap_residual = abs(receipts[0]["separator_gap_end_m"] - receipts[1]["separator_gap_end_m"])
    if threshold_residual > IDENTITY_EPS or endpoint_gap_residual > IDENTITY_EPS:
        raise AssertionError("bilateral latch transition classification drift")

    policy_states = [row.get("id") for row in mechanical_policy.get("mechanical_states", [])]
    if policy_states != ["engaged_neutral", "released_neutral", "released_lid_motion", "reengagement_neutral"]:
        raise AssertionError("mechanical state policy sequence identity drift")

    return {
        "stations": receipts,
        "maximum_bilateral_touch_angle_residual_deg": threshold_residual,
        "maximum_bilateral_release_endpoint_gap_residual_m": endpoint_gap_residual,
        "continuous_classification": {
            "neutral_lid_required": True,
            "release_0_to_50_single_exit_proven": True,
            "reengagement_50_to_0_single_reentry_proven": True,
            "full_release_interval_clearance": False,
            "full_reengagement_interval_clearance": False,
            "proof_volume_semantics_only": True,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-interface", type=Path, required=True)
    parser.add_argument("--source-rig-binding", type=Path, required=True)
    parser.add_argument("--mechanical-state-policy", type=Path, required=True)
    parser.add_argument("--observed-source-interface-head", required=True)
    parser.add_argument("--observed-source-rig-head", required=True)
    parser.add_argument("--observed-mechanical-policy-head", required=True)
    parser.add_argument("--observed-mechanical-policy-blob", required=True)
    parser.add_argument("--observed-previous-moving-clearance-head", required=True)
    parser.add_argument("--assert-full-interval-clearance", action="store_true")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    source = json.loads(args.source.read_text(encoding="utf-8"))
    source_interface = json.loads(args.source_interface.read_text(encoding="utf-8"))
    source_rig_binding = json.loads(args.source_rig_binding.read_text(encoding="utf-8"))
    mechanical_policy = json.loads(args.mechanical_state_policy.read_text(encoding="utf-8"))

    _validate_exact_identity(
        source_path=args.source,
        source_interface=source_interface,
        source_rig_binding=source_rig_binding,
        mechanical_policy=mechanical_policy,
        observed_source_interface_head=args.observed_source_interface_head,
        observed_source_rig_head=args.observed_source_rig_head,
        observed_mechanical_policy_head=args.observed_mechanical_policy_head,
        observed_mechanical_policy_blob=args.observed_mechanical_policy_blob,
        observed_previous_moving_clearance_head=args.observed_previous_moving_clearance_head,
    )
    transition = verify_transition(source, source_interface, source_rig_binding, mechanical_policy)

    if args.assert_full_interval_clearance:
        raise AssertionError(
            "FULL_INTERVAL_CLEARANCE_FALSE_INTENTIONAL_ENGAGEMENT_OVERLAP: "
            "the exact source-owned 0 degree state is intentionally overlapping; only the post-exit interval is continuously separated"
        )

    receipt = {
        "schema": SCHEMA,
        "result": RESULT,
        "exact_identity_chain": {
            "host_source_sha256": SOURCE_SHA256,
            "source_interface_head": SOURCE_INTERFACE_HEAD,
            "source_rig_head": SOURCE_RIG_HEAD,
            "source_rig_binding_sha256": SOURCE_RIG_BINDING_SHA256,
            "mechanical_state_policy_head": MECHANICAL_POLICY_HEAD,
            "mechanical_state_policy_blob": MECHANICAL_POLICY_BLOB,
            "previous_moving_lid_rigging_head": PREVIOUS_MOVING_CLEARANCE_HEAD,
            "previous_moving_lid_artifact_id": PREVIOUS_MOVING_CLEARANCE_ARTIFACT_ID,
            "previous_moving_lid_artifact_sha256": PREVIOUS_MOVING_CLEARANCE_ARTIFACT_SHA256,
        },
        "transition": transition,
        "truth_boundary": {
            "neutral_lid_release_reengagement_proof_volume_classification_proven": True,
            "continuous_full_release_clearance_proven": False,
            "continuous_full_reengagement_clearance_proven": False,
            "physical_hook_catch_retention_or_load_proven": False,
            "manufacturing_or_tolerance_proven": False,
            "animation_timing_or_playback_accepted": False,
            "runtime_controller_or_state_machine_accepted": False,
            "physics_or_gameplay_accepted": False,
            "final_visual_accepted": False,
            "canon_or_production_ready": False,
        },
    }

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    first = transition["stations"][0]
    (args.out / "summary.txt").write_text(
        f"{RESULT}\n"
        f"touch_angle_deg={first['proof_volume_touch_angle_deg']:.15g}\n"
        f"release_endpoint_separator_gap_m={first['separator_gap_end_m']:.18g}\n"
        f"separator_min_derivative_m_per_rad={first['separator_min_derivative_m_per_rad']:.18g}\n"
        f"maximum_bilateral_touch_angle_residual_deg={transition['maximum_bilateral_touch_angle_residual_deg']:.18g}\n"
        "full_release_interval_clearance=false\n"
        "full_reengagement_interval_clearance=false\n",
        encoding="utf-8",
    )
    print((args.out / "summary.txt").read_text(encoding="utf-8"), end="")


if __name__ == "__main__":
    main()
