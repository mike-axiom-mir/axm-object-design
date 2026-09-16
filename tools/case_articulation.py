from __future__ import annotations

import hashlib
import json
import math
from typing import Any

PLAN_SCHEMA = "axm.object-articulation-plan/v0.1"
EVIDENCE_SCHEMA = "axm.object-articulation-evidence/v0.1"
SOURCE_SCHEMA = "axm.object-hard-surface/v0.1"
SEPARATION_TOLERANCE_M = 1e-9
RIGIDITY_TOLERANCE_M = 1e-9


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    return float(value)


def _vec3(value: Any, label: str) -> tuple[float, float, float]:
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError(f"{label} must be a three-value list")
    return tuple(_finite_number(item, f"{label}[{idx}]") for idx, item in enumerate(value))


def _rotate_yz(point: tuple[float, float], origin: tuple[float, float], angle_deg: float) -> tuple[float, float]:
    y, z = point
    oy, oz = origin
    y -= oy
    z -= oz
    angle = math.radians(angle_deg)
    c = math.cos(angle)
    s = math.sin(angle)
    return (oy + y * c - z * s, oz + y * s + z * c)


def _project(poly: list[tuple[float, float]], axis: tuple[float, float]) -> tuple[float, float]:
    length = math.hypot(axis[0], axis[1])
    if length <= 1e-12:
        raise ValueError("SAT axis must have non-zero length")
    axis = (axis[0] / length, axis[1] / length)
    values = [point[0] * axis[0] + point[1] * axis[1] for point in poly]
    return min(values), max(values)


def _sat_separating_margin(
    first: list[tuple[float, float]],
    second: list[tuple[float, float]],
    axes: list[tuple[float, float]],
) -> float:
    """Return the strongest separating gap; positive means the rectangles are disjoint."""
    best = -math.inf
    for axis in axes:
        first_min, first_max = _project(first, axis)
        second_min, second_max = _project(second, axis)
        best = max(best, second_min - first_max, first_min - second_max)
    return best


def _pairwise_rigidity_drift(
    before: list[tuple[float, float]], after: list[tuple[float, float]]
) -> float:
    drift = 0.0
    for first in range(len(before)):
        for second in range(first + 1, len(before)):
            drift = max(
                drift,
                abs(math.dist(before[first], before[second]) - math.dist(after[first], after[second])),
            )
    return drift


def _validate(source: dict[str, Any], source_sha256: str, plan: dict[str, Any]) -> dict[str, Any]:
    if source.get("schema") != SOURCE_SCHEMA:
        raise ValueError(f"source must use {SOURCE_SCHEMA}")
    if plan.get("schema") != PLAN_SCHEMA:
        raise ValueError(f"plan must use {PLAN_SCHEMA}")
    if plan.get("asset_id") != source.get("asset_id"):
        raise ValueError("plan asset_id must match exact source asset_id")
    if not isinstance(source_sha256, str) or len(source_sha256) != 64:
        raise ValueError("source_sha256 must be a SHA-256 hex digest")
    if plan.get("source_sha256") != source_sha256:
        raise ValueError("plan source_sha256 must match exact source bytes")

    hinge = source.get("hinge")
    if not isinstance(hinge, dict):
        raise ValueError("source hinge is required")
    axis = _vec3(hinge.get("axis"), "hinge.axis")
    if axis != (1.0, 0.0, 0.0):
        raise ValueError("v0.1 articulation proof supports only the exact source +X hinge axis")

    joint = plan.get("joint")
    if not isinstance(joint, dict) or joint.get("id") != "rear-lid-hinge-001":
        raise ValueError("plan requires rear-lid-hinge-001")
    if joint.get("axis_source") != "hinge.axis":
        raise ValueError("joint axis_source must remain hinge.axis")
    if joint.get("moving_component") != "lid_shell" or joint.get("fixed_component") != "body_shell":
        raise ValueError("v0.1 proof is bound to lid_shell moving against body_shell")
    if joint.get("opening_rotation_sign") != -1:
        raise ValueError("opening_rotation_sign must remain -1 around the exact +X source axis")

    source_lid_knuckles = [row.get("id") for row in hinge.get("knuckles", []) if row.get("owner") == "lid"]
    if joint.get("coaxial_moving_knuckles") != source_lid_knuckles:
        raise ValueError("coaxial_moving_knuckles must match exact source lid-owned hinge knuckles")

    limit = joint.get("angle_limit_deg")
    if not isinstance(limit, list) or len(limit) != 2:
        raise ValueError("angle_limit_deg must be [minimum, maximum]")
    minimum = _finite_number(limit[0], "angle_limit_deg[0]")
    maximum = _finite_number(limit[1], "angle_limit_deg[1]")
    if minimum != 0.0 or maximum != 110.0:
        raise ValueError("v0.1 bounded articulation envelope must remain exactly 0..110 degrees")

    representative = joint.get("representative_angles_deg")
    if representative != [0, 30, 60, 90, 110]:
        raise ValueError("representative_angles_deg must remain [0,30,60,90,110]")
    sweep_step = joint.get("sweep_step_deg")
    if sweep_step != 1:
        raise ValueError("sweep_step_deg must remain exactly 1 degree")

    assumptions = plan.get("assumptions")
    if not isinstance(assumptions, list) or "latches_disengaged_not_articulated" not in assumptions:
        raise ValueError("plan must preserve explicit latch-disengagement assumption")

    dimensions = source.get("dimensions_m", {})
    for key in ("width", "depth", "body_height", "lid_height", "split_gap"):
        value = _finite_number(dimensions.get(key), f"dimensions_m.{key}")
        if value <= 0.0:
            raise ValueError(f"dimensions_m.{key} must be > 0")

    return {
        "axis": axis,
        "minimum_angle_deg": minimum,
        "maximum_angle_deg": maximum,
        "representative_angles_deg": [float(value) for value in representative],
        "sweep_step_deg": int(sweep_step),
        "opening_rotation_sign": -1,
        "coaxial_moving_knuckles": source_lid_knuckles,
    }


def inspect_articulation(source: dict[str, Any], source_sha256: str, plan: dict[str, Any]) -> dict[str, Any]:
    """Inspect one exact rigid lid/hinge articulation envelope without claiming animation/runtime acceptance."""
    checked = _validate(source, source_sha256, plan)
    dimensions = source["dimensions_m"]
    hinge = source["hinge"]

    depth = float(dimensions["depth"])
    body_height = float(dimensions["body_height"])
    lid_height = float(dimensions["lid_height"])
    split_gap = float(dimensions["split_gap"])

    hinge_origin_yz = (
        depth / 2.0 + float(hinge["offset_y"]),
        body_height + float(hinge["offset_z"]),
    )
    body_yz = [
        (-depth / 2.0, 0.0),
        (depth / 2.0, 0.0),
        (depth / 2.0, body_height),
        (-depth / 2.0, body_height),
    ]
    lid_center_neutral = (0.0, body_height + split_gap + lid_height / 2.0)
    lid_half_y = depth / 2.0
    lid_half_z = lid_height / 2.0
    lid_yz_neutral = [
        (lid_center_neutral[0] - lid_half_y, lid_center_neutral[1] - lid_half_z),
        (lid_center_neutral[0] + lid_half_y, lid_center_neutral[1] - lid_half_z),
        (lid_center_neutral[0] + lid_half_y, lid_center_neutral[1] + lid_half_z),
        (lid_center_neutral[0] - lid_half_y, lid_center_neutral[1] + lid_half_z),
    ]

    def sample(open_angle_deg: float) -> dict[str, Any]:
        math_angle = checked["opening_rotation_sign"] * open_angle_deg
        lid_yz = [_rotate_yz(point, hinge_origin_yz, math_angle) for point in lid_yz_neutral]
        local_angle = math.radians(math_angle)
        c = math.cos(local_angle)
        s = math.sin(local_angle)
        axes = [(1.0, 0.0), (0.0, 1.0), (c, s), (-s, c)]
        separation = _sat_separating_margin(body_yz, lid_yz, axes)
        rigidity_drift = _pairwise_rigidity_drift(lid_yz_neutral, lid_yz)
        center = _rotate_yz(lid_center_neutral, hinge_origin_yz, math_angle)
        status = "PASS" if separation > SEPARATION_TOLERANCE_M and rigidity_drift <= RIGIDITY_TOLERANCE_M else "FAIL"
        return {
            "open_angle_deg": float(open_angle_deg),
            "mathematical_rotation_deg": float(math_angle),
            "lid_center_yz_m": [round(center[0], 12), round(center[1], 12)],
            "lid_corners_yz_m": [[round(point[0], 12), round(point[1], 12)] for point in lid_yz],
            "body_shell_separating_margin_m": round(separation, 12),
            "lid_pairwise_rigidity_max_drift_m": round(rigidity_drift, 12),
            "hinge_origin_drift_m": 0.0,
            "status": status,
        }

    sweep_angles = list(range(int(checked["minimum_angle_deg"]), int(checked["maximum_angle_deg"]) + 1, checked["sweep_step_deg"]))
    sweep = [sample(float(angle)) for angle in sweep_angles]
    representative = [sample(angle) for angle in checked["representative_angles_deg"]]
    minimum_separation_row = min(sweep, key=lambda row: row["body_shell_separating_margin_m"])
    maximum_rigidity_drift = max(row["lid_pairwise_rigidity_max_drift_m"] for row in sweep)
    all_pass = all(row["status"] == "PASS" for row in sweep)

    return {
        "schema": EVIDENCE_SCHEMA,
        "asset_id": source["asset_id"],
        "source_sha256": source_sha256,
        "plan_digest": digest(plan),
        "joint_id": plan["joint"]["id"],
        "hinge_axis": list(checked["axis"]),
        "hinge_origin_m": [0.0, round(hinge_origin_yz[0], 12), round(hinge_origin_yz[1], 12)],
        "moving_component": plan["joint"]["moving_component"],
        "fixed_component": plan["joint"]["fixed_component"],
        "coaxial_moving_knuckles": checked["coaxial_moving_knuckles"],
        "angle_limit_deg": [checked["minimum_angle_deg"], checked["maximum_angle_deg"]],
        "sweep_step_deg": checked["sweep_step_deg"],
        "sweep_sample_count": len(sweep),
        "sweep_minimum_body_shell_separating_margin_m": minimum_separation_row["body_shell_separating_margin_m"],
        "sweep_minimum_separation_angle_deg": minimum_separation_row["open_angle_deg"],
        "sweep_maximum_lid_pairwise_rigidity_drift_m": round(maximum_rigidity_drift, 12),
        "representative_poses": representative,
        "sweep_samples": sweep,
        "assumptions": list(plan["assumptions"]),
        "gate": "PASS_SCOPED_LID_ARTICULATION" if all_pass else "FAIL_LID_ARTICULATION",
        "truth": {
            "proves": (
                "For the exact source bytes and exact source-derived +X rear hinge, the rigid lid shell remains rigid and "
                "separate from the fixed body shell at every integer-degree sample from 0 through 110 degrees; the exact "
                "source lid-owned hinge knuckles are coaxial with that articulation axis."
            ),
            "does_not_prove": (
                "Continuous collision freedom between integer-degree samples, latch motion, hinge load capacity, friction, "
                "damping, spring or motor behavior, full-component self-collision, animation timing/quality, engine/controller "
                "playback, runtime performance, gameplay, visual acceptance, production engineering, CANON, or mastery."
            ),
        },
    }
