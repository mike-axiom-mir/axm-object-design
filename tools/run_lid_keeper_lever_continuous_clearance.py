from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path

import build_modular_case
import verify_lid_keeper_lever_ordering as authored

SCHEMA = "axm.object-keeper-lever-continuous-lid-clearance/v0.1"
RESULT = "PASS_CONTINUOUS_KEEPER_LEVER_CLEARANCE_DURING_LID_MOTION__ENGAGEMENT_OVERLAP_HELD"
CLEAR_EPS_M = 1e-9
IDENTITY_EPS = 1e-12


def _normalized_ownership_for_observer(ownership: dict) -> dict:
    normalized = copy.deepcopy(ownership)
    for row in normalized.get("stations", []):
        source_index = int(row.get("source_index", -1))
        if source_index == 0:
            row["id"] = "left"
        elif source_index == 1:
            row["id"] = "right"
        else:
            raise AssertionError(f"unexpected ownership source_index: {source_index}")
    return normalized


def _z_min(component: dict, pivot: list[float], angle_deg: float) -> float:
    _, cy, cz = map(float, component["center_m"])
    _, sy, sz = map(float, component["size_m"])
    py, pz = float(pivot[1]), float(pivot[2])
    a = math.radians(angle_deg)
    s, c = math.sin(a), math.cos(a)
    return pz + (cy - py) * s + (cz - pz) * c - (sy / 2.0) * abs(s) - (sz / 2.0) * abs(c)


def _z_max(component: dict, pivot: list[float], angle_deg: float) -> float:
    _, cy, cz = map(float, component["center_m"])
    _, sy, sz = map(float, component["size_m"])
    py, pz = float(pivot[1]), float(pivot[2])
    a = math.radians(angle_deg)
    s, c = math.sin(a), math.cos(a)
    return pz + (cy - py) * s + (cz - pz) * c + (sy / 2.0) * abs(s) + (sz / 2.0) * abs(c)


def _continuous_min_z(component: dict, pivot: list[float], start_deg: float, end_deg: float) -> tuple[float, float]:
    """Exact trigonometric minimum for a rigid box's world-Z support over one angle interval."""
    lo, hi = sorted((float(start_deg), float(end_deg)))
    split = {lo, hi}
    first_k = math.floor(lo / 90.0) - 1
    last_k = math.ceil(hi / 90.0) + 1
    for k in range(first_k, last_k + 1):
        angle = 90.0 * k
        if lo < angle < hi:
            split.add(angle)
    bounds = sorted(split)
    candidates = set(bounds)

    _, cy, cz = map(float, component["center_m"])
    _, sy, sz = map(float, component["size_m"])
    py, pz = float(pivot[1]), float(pivot[2])
    ry, rz = cy - py, cz - pz
    hy, hz = sy / 2.0, sz / 2.0

    for a_deg, b_deg in zip(bounds, bounds[1:]):
        mid = math.radians((a_deg + b_deg) / 2.0)
        sin_sign = 1.0 if math.sin(mid) >= 0.0 else -1.0
        cos_sign = 1.0 if math.cos(mid) >= 0.0 else -1.0
        # On a sign-stable interval, z_min = pz + A*sin(theta) + B*cos(theta).
        A = ry - hy * sin_sign
        B = rz - hz * cos_sign
        critical = math.degrees(math.atan2(A, B))
        for k in range(-4, 5):
            angle = critical + 180.0 * k
            if a_deg < angle < b_deg:
                candidates.add(angle)

    values = [(angle, _z_min(component, pivot, angle)) for angle in sorted(candidates)]
    angle, value = min(values, key=lambda row: row[1])
    return value, angle


def _verify_continuous_clearance(
    source: dict,
    source_interface: dict,
    animation_evidence: dict,
    *,
    forced_latch_deg: float | None = None,
) -> dict:
    built = build_modular_case.build(source)
    components = {row["name"]: row for row in built["components"]}
    hinge_origin = [float(v) for v in built["hinge_axis"]["origin_m"]]
    stations = {row["id"]: row for row in source_interface.get("stations", [])}
    if set(stations) != {"left", "right"}:
        raise AssertionError("continuous proof requires exact bilateral source stations")

    rows = animation_evidence.get("samples", [])
    moving = [row for row in rows if abs(float(row["lid_open_angle_deg"])) > IDENTITY_EPS]
    if not moving:
        raise AssertionError("Animation donor has no non-neutral lid interval")

    authored_latch_angles = [float(row["latch_lever_angle_deg"]) for row in moving]
    if max(abs(value - 50.0) for value in authored_latch_angles) > IDENTITY_EPS:
        raise AssertionError("moving-lid interval no longer holds exact 50 degree latch release")
    latch_angle = 50.0 if forced_latch_deg is None else float(forced_latch_deg)

    max_open = max(float(row["lid_open_angle_deg"]) for row in moving)
    if abs(max_open - 100.0) > 1e-9:
        raise AssertionError("Animation donor moving-lid envelope drift")

    signs = []
    for row in moving:
        opened = float(row["lid_open_angle_deg"])
        mathematical = float(row["lid_mathematical_rotation_deg"])
        if abs(abs(mathematical) - opened) > 1e-9:
            raise AssertionError("Animation lid mathematical/open-angle relation drift")
        signs.append(1.0 if mathematical > 0.0 else -1.0)
    if any(sign != signs[0] for sign in signs):
        raise AssertionError("Animation lid rotation sign changes inside moving interval")
    math_end = signs[0] * max_open

    station_receipts = []
    minimum_axis_certificate = math.inf
    maximum_bilateral_residual = 0.0
    for station_id in ("left", "right"):
        interface = stations[station_id]
        keeper = components[interface["keeper_component"]]
        lever = components[interface["lever_component"]]
        lever_pivot = [float(v) for v in interface["pivot_origin_m"]]
        if authored._x_overlap_m(keeper, lever) <= 0.0:
            raise AssertionError("source keeper/lever X intervals no longer overlap")

        keeper_min_z, witness_angle = _continuous_min_z(keeper, hinge_origin, 0.0, math_end)
        lever_max_z = _z_max(lever, lever_pivot, latch_angle)
        z_axis_separation = keeper_min_z - lever_max_z
        if z_axis_separation <= CLEAR_EPS_M:
            raise AssertionError(
                "CONTINUOUS_CLEARANCE_VIOLATION: fixed world-Z separating-axis certificate is not positive "
                f"for station={station_id} latch_deg={latch_angle:.12g} separation_m={z_axis_separation:.18g}"
            )
        minimum_axis_certificate = min(minimum_axis_certificate, z_axis_separation)

        representative = []
        for lid_open in (0.0, float(moving[0]["lid_open_angle_deg"]), 50.0, 90.0, 100.0):
            lid_math = signs[0] * lid_open
            keeper_poly = authored._rect_yz(keeper, hinge_origin, lid_math)
            lever_poly = authored._rect_yz(lever, lever_pivot, latch_angle)
            sat = authored._sat_separation_m(keeper_poly, lever_poly)
            if sat <= CLEAR_EPS_M:
                raise AssertionError(
                    "CONTINUOUS_CLEARANCE_VIOLATION: representative SAT witness is not clear "
                    f"for station={station_id} lid_deg={lid_open:.12g} latch_deg={latch_angle:.12g}"
                )
            representative.append(
                {
                    "lid_open_angle_deg": lid_open,
                    "lid_mathematical_rotation_deg": lid_math,
                    "latch_lever_angle_deg": latch_angle,
                    "sat_separation_m": sat,
                }
            )

        station_receipts.append(
            {
                "station_id": station_id,
                "keeper_component": interface["keeper_component"],
                "lever_component": interface["lever_component"],
                "continuous_world_z_separation_lower_bound_m": z_axis_separation,
                "keeper_min_world_z_m": keeper_min_z,
                "keeper_min_world_z_witness_math_angle_deg": witness_angle,
                "lever_max_world_z_m": lever_max_z,
                "representative_poses": representative,
            }
        )

    if len(station_receipts) == 2:
        maximum_bilateral_residual = abs(
            station_receipts[0]["continuous_world_z_separation_lower_bound_m"]
            - station_receipts[1]["continuous_world_z_separation_lower_bound_m"]
        )
        if maximum_bilateral_residual > IDENTITY_EPS:
            raise AssertionError("bilateral continuous-clearance certificate drift")

    return {
        "continuous_lid_motion_interval": {
            "lid_open_angle_deg": [0.0, max_open],
            "lid_mathematical_rotation_deg": [0.0, math_end],
            "latch_lever_angle_deg": latch_angle,
            "certificate": "fixed world-Z separating axis with exact rigid-box trigonometric support minimum",
            "minimum_continuous_separation_lower_bound_m": minimum_axis_certificate,
            "maximum_bilateral_certificate_residual_m": maximum_bilateral_residual,
        },
        "stations": station_receipts,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--ownership", type=Path, required=True)
    parser.add_argument("--lid-plan", type=Path, required=True)
    parser.add_argument("--source-interface", type=Path, required=True)
    parser.add_argument("--source-rig-binding", type=Path, required=True)
    parser.add_argument("--animation-authority", type=Path, required=True)
    parser.add_argument("--animation-evidence", type=Path, required=True)
    parser.add_argument("--observed-ownership-head", required=True)
    parser.add_argument("--observed-lid-rig-head", required=True)
    parser.add_argument("--observed-previous-rigging-head", required=True)
    parser.add_argument("--observed-animation-head", required=True)
    parser.add_argument("--observed-source-rig-head", required=True)
    parser.add_argument("--observed-source-interface-head", required=True)
    parser.add_argument("--force-latch-deg", type=float)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    source = json.loads(args.source.read_text(encoding="utf-8"))
    original_ownership = json.loads(args.ownership.read_text(encoding="utf-8"))
    normalized_ownership = _normalized_ownership_for_observer(original_ownership)
    lid_plan = json.loads(args.lid_plan.read_text(encoding="utf-8"))
    source_interface = json.loads(args.source_interface.read_text(encoding="utf-8"))
    source_rig_binding = json.loads(args.source_rig_binding.read_text(encoding="utf-8"))
    animation_authority = json.loads(args.animation_authority.read_text(encoding="utf-8"))
    animation_evidence = json.loads(args.animation_evidence.read_text(encoding="utf-8"))

    original_keeper_verify = authored.keeper_socket.verify

    def keeper_verify_with_source_ids(source_arg, ownership_arg, lid_plan_arg, **kwargs):
        return original_keeper_verify(source_arg, original_ownership, lid_plan_arg, **kwargs)

    authored.keeper_socket.verify = keeper_verify_with_source_ids
    try:
        prerequisite = authored.verify(
            source,
            normalized_ownership,
            lid_plan,
            source_interface,
            source_rig_binding,
            animation_authority,
            animation_evidence,
            source_sha256=authored.sha256_file(args.source),
            observed_ownership_head=args.observed_ownership_head,
            observed_lid_rig_head=args.observed_lid_rig_head,
            observed_previous_rigging_head=args.observed_previous_rigging_head,
            observed_animation_head=args.observed_animation_head,
            observed_source_rig_head=args.observed_source_rig_head,
            observed_source_interface_head=args.observed_source_interface_head,
        )
    finally:
        authored.keeper_socket.verify = original_keeper_verify

    if prerequisite.get("result") != authored.RESULT:
        raise AssertionError("exact 101-authored-pose prerequisite is not green")

    continuous = _verify_continuous_clearance(
        source,
        source_interface,
        animation_evidence,
        forced_latch_deg=args.force_latch_deg,
    )
    receipt = {
        "schema": SCHEMA,
        "result": RESULT,
        "exact_identity_chain": {
            "host_source_sha256": authored.SOURCE_SHA256,
            "ownership_head": authored.OWNERSHIP_HEAD,
            "source_interface_head": authored.SOURCE_INTERFACE_HEAD,
            "source_rig_head": authored.SOURCE_RIG_HEAD,
            "historical_lid_rig_head": authored.LID_RIG_HEAD,
            "previous_target_rigging_head": authored.PREVIOUS_RIGGING_HEAD,
            "animation_pose_set_head": authored.ANIMATION_HEAD,
            "animation_sequence_id": authored.ANIMATION_SEQUENCE_ID,
            "animation_sequence_digest": authored.ANIMATION_SEQUENCE_DIGEST,
        },
        "prerequisite_result": prerequisite["result"],
        "continuous_clearance": continuous,
        "truth_boundary": {
            "continuous_lid_motion_keeper_lever_clearance_proven": True,
            "continuous_latch_release_clearance_proven": False,
            "continuous_latch_reengagement_clearance_proven": False,
            "engagement_overlap_preserved_as_intentional_source_state": True,
            "physical_latch_capture_or_retention_proven": False,
            "whole_object_collision_free": False,
            "animation_accepted": False,
            "runtime_accepted": False,
            "final_visual_accepted": False,
            "canon_or_production_ready": False,
        },
    }

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    field = continuous["continuous_lid_motion_interval"]
    (args.out / "summary.txt").write_text(
        f"{RESULT}\n"
        f"lid_open_interval_deg={field['lid_open_angle_deg']}\n"
        f"lid_math_interval_deg={field['lid_mathematical_rotation_deg']}\n"
        f"latch_lever_angle_deg={field['latch_lever_angle_deg']:.18g}\n"
        f"minimum_continuous_separation_lower_bound_m={field['minimum_continuous_separation_lower_bound_m']:.18g}\n"
        f"maximum_bilateral_certificate_residual_m={field['maximum_bilateral_certificate_residual_m']:.18g}\n",
        encoding="utf-8",
    )
    print((args.out / "summary.txt").read_text(encoding="utf-8"), end="")


if __name__ == "__main__":
    main()
