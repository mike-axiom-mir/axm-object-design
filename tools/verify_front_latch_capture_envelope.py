from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from build_modular_case import build

SCHEMA = "axm.object-front-latch-capture-envelope/v0.1"
RESULT = "PASS_SOURCE_OWNED_FRONT_LATCH_CAPTURE_TO_CLEARANCE_ENVELOPE"
TOL = 1e-12


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _bounds(component):
    if component.get("kind") != "box":
        raise AssertionError(f"expected box component: {component.get('name')}")
    center = component["center_m"]
    size = component["size_m"]
    return tuple((center[i] - size[i] / 2.0, center[i] + size[i] / 2.0) for i in range(3))


def _rect_yz(bounds):
    y0, y1 = bounds[1]
    z0, z1 = bounds[2]
    return [(y0, z0), (y1, z0), (y1, z1), (y0, z1)]


def _rotate_yz(point, pivot, angle_deg):
    y, z = point
    py, pz = pivot
    angle = math.radians(angle_deg)
    ca, sa = math.cos(angle), math.sin(angle)
    dy, dz = y - py, z - pz
    return (py + dy * ca - dz * sa, pz + dy * sa + dz * ca)


def _unit_axes(poly):
    axes = []
    for i in range(len(poly)):
        y0, z0 = poly[i]
        y1, z1 = poly[(i + 1) % len(poly)]
        ey, ez = y1 - y0, z1 - z0
        ay, az = -ez, ey
        length = math.hypot(ay, az)
        if length <= TOL:
            raise AssertionError("degenerate rectangle edge in SAT proof")
        ay, az = ay / length, az / length
        if ay < -TOL or (abs(ay) <= TOL and az < 0.0):
            ay, az = -ay, -az
        if not any(abs(ay - bx) <= TOL and abs(az - bz) <= TOL for bx, bz in axes):
            axes.append((ay, az))
    return axes


def _projection(poly, axis):
    values = [p[0] * axis[0] + p[1] * axis[1] for p in poly]
    return min(values), max(values)


def _sat_margin(poly_a, poly_b):
    best = float("inf")
    best_axis = None
    for axis in _unit_axes(poly_a) + _unit_axes(poly_b):
        a0, a1 = _projection(poly_a, axis)
        b0, b1 = _projection(poly_b, axis)
        overlap = min(a1, b1) - max(a0, b0)
        if overlap < best:
            best = overlap
            best_axis = axis
    if best_axis is None:
        raise AssertionError("SAT proof produced no axes")
    return best, best_axis


def _x_overlap(bounds_a, bounds_b):
    return min(bounds_a[0][1], bounds_b[0][1]) - max(bounds_a[0][0], bounds_b[0][0])


def _lever_poly_at(lever_bounds, pivot_yz, angle_deg):
    return [_rotate_yz(p, pivot_yz, angle_deg) for p in _rect_yz(lever_bounds)]


def _z_aabb_gap(lever_bounds, keeper_bounds, pivot_yz, angle_deg):
    rotated = _lever_poly_at(lever_bounds, pivot_yz, angle_deg)
    lever_z_max = max(p[1] for p in rotated)
    return keeper_bounds[2][0] - lever_z_max


def _find_first_sat_transition(lever_bounds, keeper_bounds, pivot_yz, hi_deg, step_deg, iterations):
    keeper_poly = _rect_yz(keeper_bounds)
    neutral_margin, _ = _sat_margin(_lever_poly_at(lever_bounds, pivot_yz, 0.0), keeper_poly)
    if neutral_margin <= TOL:
        raise AssertionError("NEUTRAL_ENGAGEMENT_OVERLAP_LOST")

    steps = int(round(hi_deg / step_deg))
    if abs(steps * step_deg - hi_deg) > TOL:
        raise AssertionError("sample scan step must divide review envelope exactly")

    previous_angle = 0.0
    previous_margin = neutral_margin
    bracket = None
    separation_seen = False
    sampled_min_after_transition = float("inf")
    for i in range(1, steps + 1):
        angle = i * step_deg
        margin, _ = _sat_margin(_lever_poly_at(lever_bounds, pivot_yz, angle), keeper_poly)
        if not separation_seen and margin < 0.0:
            bracket = (previous_angle, angle)
            separation_seen = True
        elif separation_seen and margin >= 0.0:
            raise AssertionError("PROOF_VOLUME_CONTACT_REENTRY_ON_SAMPLED_RELEASE_PATH")
        if separation_seen:
            sampled_min_after_transition = min(sampled_min_after_transition, -margin)
        previous_angle, previous_margin = angle, margin

    if bracket is None:
        raise AssertionError("NO_PROOF_VOLUME_CONTACT_TO_SEPARATION_TRANSITION")

    lo, hi = bracket
    for _ in range(iterations):
        mid = (lo + hi) / 2.0
        margin, _ = _sat_margin(_lever_poly_at(lever_bounds, pivot_yz, mid), keeper_poly)
        if margin >= 0.0:
            lo = mid
        else:
            hi = mid
    threshold = (lo + hi) / 2.0
    threshold_margin, threshold_axis = _sat_margin(_lever_poly_at(lever_bounds, pivot_yz, threshold), keeper_poly)
    return {
        "sample_bracket_deg": [bracket[0], bracket[1]],
        "transition_deg": threshold,
        "transition_numeric_margin_m": threshold_margin,
        "transition_axis_yz": [threshold_axis[0], threshold_axis[1]],
        "minimum_sampled_separation_margin_after_transition_m": sampled_min_after_transition,
    }


def _find_z_aabb_transition(lever_bounds, keeper_bounds, pivot_yz, hi_deg, step_deg, iterations):
    if _z_aabb_gap(lever_bounds, keeper_bounds, pivot_yz, 0.0) >= 0.0:
        raise AssertionError("neutral Z AABB unexpectedly separated")
    steps = int(round(hi_deg / step_deg))
    previous_angle = 0.0
    previous_gap = _z_aabb_gap(lever_bounds, keeper_bounds, pivot_yz, 0.0)
    bracket = None
    for i in range(1, steps + 1):
        angle = i * step_deg
        gap = _z_aabb_gap(lever_bounds, keeper_bounds, pivot_yz, angle)
        if previous_gap < 0.0 and gap >= 0.0:
            bracket = (previous_angle, angle)
            break
        previous_angle, previous_gap = angle, gap
    if bracket is None:
        raise AssertionError("no Z AABB transition in review envelope")
    lo, hi = bracket
    for _ in range(iterations):
        mid = (lo + hi) / 2.0
        if _z_aabb_gap(lever_bounds, keeper_bounds, pivot_yz, mid) >= 0.0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2.0


def _in_range(value, bounds):
    return float(bounds[0]) - TOL <= value <= float(bounds[1]) + TOL


def verify(host, interface, policy, *, host_sha256, interface_sha256):
    if policy.get("schema") != SCHEMA:
        raise AssertionError("unsupported capture-envelope schema")
    if policy.get("asset_id") != interface.get("asset_id"):
        raise AssertionError("asset identity mismatch")
    if policy.get("host_source_sha256") != host_sha256:
        raise AssertionError("HOST_SOURCE_IDENTITY_DRIFT")
    if interface.get("host_source_sha256") != host_sha256:
        raise AssertionError("pivot interface host identity mismatch")
    declared_interface = policy.get("pivot_interface", {})
    if declared_interface.get("sha256") != interface_sha256:
        raise AssertionError("PIVOT_INTERFACE_IDENTITY_DRIFT")
    if interface.get("schema") != "axm.object-front-latch-pivot-interface/v0.1":
        raise AssertionError("pivot interface schema drift")
    if interface.get("joint_axis") != [1.0, 0.0, 0.0]:
        raise AssertionError("source latch axis must remain exact +X")

    contact = policy.get("contact_model", {})
    if contact.get("source_geometry") != "EXACT_SOURCE_BOX_PROOF_VOLUMES":
        raise AssertionError("CONTACT_MODEL_DRIFT")
    if contact.get("lever_motion") != "RIGID_ROTATION_ABOUT_SOURCE_OWNED_PLUS_X_PIVOT":
        raise AssertionError("CONTACT_MODEL_DRIFT")
    if contact.get("intersection_method") != "POSITIVE_X_INTERVAL_OVERLAP_PLUS_EXACT_YZ_ORIENTED_RECTANGLE_SAT":
        raise AssertionError("CONTACT_MODEL_DRIFT")
    step_deg = float(contact.get("sample_scan_step_deg", 0.0))
    iterations = int(contact.get("bisection_iterations", 0))
    if step_deg <= 0.0 or step_deg > 0.25 or iterations < 32:
        raise AssertionError("capture observer precision contract drift")

    authority = policy.get("authority", {})
    required_false = (
        "animation_timing_owned",
        "rigging_motion_authorship_owned",
        "runtime_controller_owned",
        "physics_owned",
        "physical_latch_retention_owned",
        "manufacturing_fit_owned",
    )
    if not authority.get("hard_surface_owns_source_contact_intent", False):
        raise AssertionError("source contact authority missing")
    if not authority.get("hard_surface_owns_proof_volume_capture_envelope", False):
        raise AssertionError("source capture-envelope authority missing")
    if any(authority.get(key, False) for key in required_false):
        raise AssertionError("AUTHORITY_INFLATION")

    result = build(host)
    components = {row["name"]: row for row in result["components"]}
    stations = interface.get("stations", [])
    if len(stations) != 2:
        raise AssertionError("v0.1 capture proof requires exact bilateral station pair")

    review_release = float(interface.get("travel_envelope_deg", {}).get("review_release"))
    if abs(review_release - 50.0) > TOL:
        raise AssertionError("review release envelope drift")
    minimum_endpoint_sep = float(contact.get("minimum_review_release_z_axis_separation_m", 0.0))
    if minimum_endpoint_sep <= 0.0:
        raise AssertionError("release endpoint minimum must remain positive")

    rows = []
    for station in stations:
        lever = components.get(station.get("lever_component"))
        keeper = components.get(station.get("keeper_component"))
        if lever is None or keeper is None:
            raise AssertionError("declared latch proof component missing")
        lever_bounds = _bounds(lever)
        keeper_bounds = _bounds(keeper)
        pivot = station.get("pivot_origin_m", [])
        if len(pivot) != 3:
            raise AssertionError("pivot origin missing")
        pivot_yz = (float(pivot[1]), float(pivot[2]))

        x_overlap = _x_overlap(lever_bounds, keeper_bounds)
        if x_overlap <= TOL:
            raise AssertionError("positive X overlap prerequisite lost")

        keeper_poly = _rect_yz(keeper_bounds)
        neutral_margin, neutral_axis = _sat_margin(_lever_poly_at(lever_bounds, pivot_yz, 0.0), keeper_poly)
        transition = _find_first_sat_transition(
            lever_bounds, keeper_bounds, pivot_yz, review_release, step_deg, iterations
        )
        z_transition = _find_z_aabb_transition(
            lever_bounds, keeper_bounds, pivot_yz, review_release, step_deg, iterations
        )
        endpoint_z_gap = _z_aabb_gap(lever_bounds, keeper_bounds, pivot_yz, review_release)
        endpoint_sat_margin, endpoint_sat_axis = _sat_margin(
            _lever_poly_at(lever_bounds, pivot_yz, review_release), keeper_poly
        )

        if endpoint_z_gap + TOL < minimum_endpoint_sep:
            raise AssertionError("RELEASE_ENDPOINT_Z_SEPARATION_BELOW_MINIMUM")
        if endpoint_sat_margin >= 0.0:
            raise AssertionError("release endpoint proof volumes still intersect")
        if not _in_range(transition["transition_deg"], contact.get("expected_contact_transition_deg_range", [])):
            raise AssertionError("CONTACT_TRANSITION_RANGE_MISMATCH")
        if not _in_range(z_transition, contact.get("expected_z_aabb_only_transition_deg_range", [])):
            raise AssertionError("Z_AABB_TRANSITION_RANGE_MISMATCH")
        if z_transition <= transition["transition_deg"] + 1.0:
            raise AssertionError("FALSE_Z_AABB_CAPTURE_EQUIVALENCE")

        rows.append({
            "station_id": station.get("id"),
            "x_interval_overlap_m": x_overlap,
            "neutral_yz_sat_overlap_margin_m": neutral_margin,
            "neutral_yz_sat_limiting_axis": [neutral_axis[0], neutral_axis[1]],
            "capture_transition_sample_bracket_deg": transition["sample_bracket_deg"],
            "capture_transition_deg": transition["transition_deg"],
            "capture_transition_numeric_margin_m": transition["transition_numeric_margin_m"],
            "capture_transition_axis_yz": transition["transition_axis_yz"],
            "z_aabb_only_transition_deg": z_transition,
            "z_aabb_minus_capture_transition_deg": z_transition - transition["transition_deg"],
            "review_release_deg": review_release,
            "review_release_z_axis_separation_m": endpoint_z_gap,
            "review_release_yz_sat_margin_m": endpoint_sat_margin,
            "review_release_yz_sat_limiting_axis": [endpoint_sat_axis[0], endpoint_sat_axis[1]],
            "sampled_release_path_reentry_observed": False,
        })

    capture_residual = abs(rows[0]["capture_transition_deg"] - rows[1]["capture_transition_deg"])
    z_residual = abs(rows[0]["z_aabb_only_transition_deg"] - rows[1]["z_aabb_only_transition_deg"])
    endpoint_residual = abs(rows[0]["review_release_z_axis_separation_m"] - rows[1]["review_release_z_axis_separation_m"])
    if max(capture_residual, z_residual, endpoint_residual) > TOL:
        raise AssertionError("BILATERAL_CAPTURE_ENVELOPE_DRIFT")

    return {
        "schema": "axm.object-front-latch-capture-envelope-evidence/v0.1",
        "result": RESULT,
        "asset_id": policy["asset_id"],
        "host_source_sha256": host_sha256,
        "pivot_interface_sha256": interface_sha256,
        "contact_model": contact["intersection_method"],
        "station_count": len(rows),
        "bilateral_capture_transition_residual_deg": capture_residual,
        "bilateral_z_aabb_transition_residual_deg": z_residual,
        "bilateral_release_endpoint_separation_residual_m": endpoint_residual,
        "capture_transition_deg": rows[0]["capture_transition_deg"],
        "z_aabb_only_transition_deg": rows[0]["z_aabb_only_transition_deg"],
        "z_aabb_minus_capture_transition_deg": rows[0]["z_aabb_minus_capture_transition_deg"],
        "review_release_z_axis_separation_m": min(row["review_release_z_axis_separation_m"] for row in rows),
        "host_source_geometry_changed": False,
        "pivot_interface_changed": False,
        "station_results": rows,
        "truth_boundary": {
            "intentional_neutral_engagement_overlap_preserved": True,
            "proof_volume_capture_transition_observed": True,
            "z_aabb_only_is_not_capture_threshold": True,
            "sampled_release_path_reentry_observed": False,
            "physical_latch_capture_or_retention_proven": False,
            "manufacturing_fit_or_tolerance_proven": False,
            "dynamic_release_or_reengagement_forces_proven": False,
            "continuous_full_assembly_collision_freedom_proven": False,
            "animation_timing_owned": False,
            "runtime_controller_owned": False,
            "physics_owned": False,
        },
        "source_truth_boundary": policy.get("truth_boundary"),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=Path, required=True)
    parser.add_argument("--interface", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    host = json.loads(args.host.read_text(encoding="utf-8"))
    interface = json.loads(args.interface.read_text(encoding="utf-8"))
    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    receipt = verify(
        host,
        interface,
        policy,
        host_sha256=sha256(args.host),
        interface_sha256=sha256(args.interface),
    )
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
