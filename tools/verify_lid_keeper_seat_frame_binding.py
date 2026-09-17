from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_modular_case

SCHEMA = "axm.object-lid-keeper-seat-rig-binding/v0.1"
RESULT = "PASS_SOURCE_OWNED_KEEPER_ATTACHMENT_SEAT_FRAME_BINDING_111_POSES"
SOURCE_SHA256 = "49b1f9ed9865893d6de6f1ec8f069576732df694853fde4e3fcff366de32644a"
KEEPER_SEAT_HEAD = "37217b244046055a40d9050b61eff2876566bad8"
KEEPER_SEAT_BLOB = "bc91018225d0141d278ffac8ade2176e47338e27"
LID_RIG_HEAD = "4b72c9918c5fc1e89bd18a0be24fb4afac6e7775"
PREVIOUS_RIGGING_HEAD = "29b3a4828b020fe608085df5eaaf9d33d5ea331f"
LID_PLAN_DIGEST = "0ad6dc2ca22676cf301579932e599a441eb7c4bccce31991d1b727aeb22ac422"
TOL = 1e-12


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _add(a: list[float], b: list[float]) -> list[float]:
    return [float(a[i]) + float(b[i]) for i in range(3)]


def _sub(a: list[float], b: list[float]) -> list[float]:
    return [float(a[i]) - float(b[i]) for i in range(3)]


def _scale(a: list[float], scalar: float) -> list[float]:
    return [float(v) * float(scalar) for v in a]


def _dot(a: list[float], b: list[float]) -> float:
    return sum(float(a[i]) * float(b[i]) for i in range(3))


def _cross(a: list[float], b: list[float]) -> list[float]:
    return [
        float(a[1]) * float(b[2]) - float(a[2]) * float(b[1]),
        float(a[2]) * float(b[0]) - float(a[0]) * float(b[2]),
        float(a[0]) * float(b[1]) - float(a[1]) * float(b[0]),
    ]


def _norm(a: list[float]) -> float:
    return math.sqrt(_dot(a, a))


def _dist(a: list[float], b: list[float]) -> float:
    return _norm(_sub(a, b))


def _rotate_about_x(point: list[float], origin: list[float], angle_deg: float) -> list[float]:
    x, y, z = map(float, point)
    ox, oy, oz = map(float, origin)
    y -= oy
    z -= oz
    a = math.radians(angle_deg)
    c, s = math.cos(a), math.sin(a)
    return [x, oy + y * c - z * s, oz + y * s + z * c]


def _rotate_vec_x(vector: list[float], angle_deg: float) -> list[float]:
    return _rotate_about_x(vector, [0.0, 0.0, 0.0], angle_deg)


def _aabb(component: dict[str, Any]) -> dict[str, tuple[float, float]]:
    if component.get("kind") != "box":
        raise AssertionError(f"component is not a box: {component.get('name')}")
    center = component["center_m"]
    size = component["size_m"]
    return {
        axis: (float(center[i]) - float(size[i]) / 2.0, float(center[i]) + float(size[i]) / 2.0)
        for i, axis in enumerate(("x", "y", "z"))
    }


def _assert_close(actual: float, expected: float, label: str) -> None:
    if abs(float(actual) - float(expected)) > TOL:
        raise AssertionError(f"{label} drift: {actual} != {expected}")


def _assert_vec(actual: list[float], expected: list[float], label: str) -> None:
    if len(actual) != len(expected):
        raise AssertionError(f"{label} length drift")
    for i, (a, e) in enumerate(zip(actual, expected)):
        _assert_close(float(a), float(e), f"{label}[{i}]")


def _frame_residual(primary: list[float], secondary: list[float], normal: list[float]) -> tuple[float, float]:
    orthogonality = max(
        abs(_norm(primary) - 1.0),
        abs(_norm(secondary) - 1.0),
        abs(_norm(normal) - 1.0),
        abs(_dot(primary, secondary)),
        abs(_dot(primary, normal)),
        abs(_dot(secondary, normal)),
    )
    parity = abs(_dot(_cross(primary, secondary), normal) - 1.0)
    return orthogonality, parity


def _seat_corners(center: list[float], primary: list[float], secondary: list[float], dimensions: list[float]) -> list[list[float]]:
    half_u = float(dimensions[0]) / 2.0
    half_v = float(dimensions[1]) / 2.0
    corners: list[list[float]] = []
    for su, sv in ((-1.0, -1.0), (-1.0, 1.0), (1.0, -1.0), (1.0, 1.0)):
        corners.append(_add(center, _add(_scale(primary, su * half_u), _scale(secondary, sv * half_v))))
    return corners


def _max_pairwise_drift(before: list[list[float]], after: list[list[float]]) -> float:
    best = 0.0
    for i in range(len(before)):
        for j in range(i + 1, len(before)):
            best = max(best, abs(_dist(before[i], before[j]) - _dist(after[i], after[j])))
    return best


def verify(
    source: dict[str, Any],
    ownership: dict[str, Any],
    keeper_seat: dict[str, Any],
    lid_plan: dict[str, Any],
    *,
    source_sha256: str,
    ownership_sha256: str,
    observed_keeper_seat_head: str,
    observed_keeper_seat_blob: str,
    observed_lid_rig_head: str,
    observed_previous_rigging_head: str,
    seat_override: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if source_sha256 != SOURCE_SHA256:
        raise AssertionError("exact Object source byte identity drift")
    if observed_keeper_seat_head != KEEPER_SEAT_HEAD:
        raise AssertionError("keeper-seat source-owner head drift")
    if observed_keeper_seat_blob != KEEPER_SEAT_BLOB:
        raise AssertionError("keeper-seat source-owner blob drift")
    if observed_lid_rig_head != LID_RIG_HEAD:
        raise AssertionError("historical lid articulation donor head drift")
    if observed_previous_rigging_head != PREVIOUS_RIGGING_HEAD:
        raise AssertionError("previous Rigging head drift")

    if ownership.get("schema") != "axm.object-front-latch-ownership/v0.1":
        raise AssertionError("unexpected ownership schema")
    if ownership.get("host_source_sha256") != SOURCE_SHA256:
        raise AssertionError("ownership source identity drift")
    if keeper_seat.get("schema") != "axm.object-front-latch-keeper-seat/v0.1":
        raise AssertionError("unexpected keeper-seat schema")
    if keeper_seat.get("contract_id") != "front-latch-keeper-seat-001":
        raise AssertionError("keeper-seat contract identity drift")
    if keeper_seat.get("host_source_sha256") != SOURCE_SHA256:
        raise AssertionError("keeper-seat source identity drift")
    if keeper_seat.get("ownership_contract_sha256") != ownership_sha256:
        raise AssertionError("keeper-seat ownership-contract identity drift")

    contact_policy = keeper_seat.get("contact_policy", {})
    if contact_policy.get("require_exact_face_contact") is not True:
        raise AssertionError("keeper-seat exact-contact policy drift")
    if contact_policy.get("require_zero_owner_volume_penetration") is not True:
        raise AssertionError("keeper-seat zero-penetration policy drift")
    if contact_policy.get("require_positive_planar_overlap") is not True:
        raise AssertionError("keeper-seat overlap policy drift")
    authority = keeper_seat.get("authority", {})
    for key in (
        "physical_fastener_or_weld_defined",
        "retention_force_defined",
        "manufacturing_tolerance_defined",
        "rig_motion_defined",
        "animation_timing_defined",
        "runtime_parenting_adopted",
    ):
        if authority.get(key) is not False:
            raise AssertionError(f"keeper-seat authority expansion forbidden: {key}")

    if lid_plan.get("schema") != "axm.object-articulation-plan/v0.1":
        raise AssertionError("unexpected lid articulation plan schema")
    if lid_plan.get("source_sha256") != SOURCE_SHA256:
        raise AssertionError("lid articulation source identity drift")
    if digest(lid_plan) != LID_PLAN_DIGEST:
        raise AssertionError("lid articulation plan digest drift")
    joint = lid_plan.get("joint", {})
    if joint.get("id") != "rear-lid-hinge-001":
        raise AssertionError("lid joint identity drift")
    if joint.get("moving_component") != "lid_shell" or joint.get("fixed_component") != "body_shell":
        raise AssertionError("lid articulation ownership drift")
    if joint.get("opening_rotation_sign") != -1:
        raise AssertionError("lid articulation sign drift")
    if joint.get("angle_limit_deg") != [0, 110] or joint.get("sweep_step_deg") != 1:
        raise AssertionError("lid articulation envelope drift")

    built = build_modular_case.build(source)
    components = {row["name"]: row for row in built["components"]}
    lid = components.get("lid_shell")
    if lid is None or lid.get("role") != "lid_shell":
        raise AssertionError("exact lid owner missing")
    lid_box = _aabb(lid)
    hinge_origin = [float(v) for v in built["hinge_axis"]["origin_m"]]
    if [float(v) for v in built["hinge_axis"]["axis"]] != [1.0, 0.0, 0.0]:
        raise AssertionError("source hinge axis drift")

    ownership_by_id = {str(row.get("id")): row for row in ownership.get("stations", [])}
    stations = keeper_seat.get("stations", [])
    if len(stations) != 2 or len(ownership_by_id) != 2:
        raise AssertionError("bounded proof requires exactly two source-owned keeper seats")

    neutral_rows: list[dict[str, Any]] = []
    for station in stations:
        sid = str(station.get("id", ""))
        owner_row = ownership_by_id.get(sid)
        if owner_row is None:
            raise AssertionError(f"missing ownership station: {sid}")
        keeper_name = str(station.get("keeper_component", ""))
        if keeper_name != owner_row.get("keeper_component"):
            raise AssertionError("keeper identity drift from ownership contract")
        if station.get("owner_component") != "lid_shell" or owner_row.get("keeper_owner_component") != "lid_shell":
            raise AssertionError("keeper owner drift")
        if station.get("owner_face") != "negative_y_face" or station.get("keeper_face") != "positive_y_face":
            raise AssertionError("keeper-seat face identity drift")
        if station.get("plane_axis") != "y":
            raise AssertionError("keeper-seat plane-axis drift")

        keeper = components.get(keeper_name)
        if keeper is None or keeper.get("role") != "latch_keeper":
            raise AssertionError(f"exact keeper component missing: {keeper_name}")
        keeper_box = _aabb(keeper)

        candidate = dict(station)
        if seat_override and sid in seat_override:
            candidate.update(seat_override[sid])

        plane = lid_box["y"][0]
        _assert_close(keeper_box["y"][1], plane, f"{sid} keeper/lid source face contact")
        _assert_close(float(candidate.get("plane_coordinate_m")), plane, f"{sid} seat plane")
        primary_bounds = [max(keeper_box["x"][0], lid_box["x"][0]), min(keeper_box["x"][1], lid_box["x"][1])]
        secondary_bounds = [max(keeper_box["z"][0], lid_box["z"][0]), min(keeper_box["z"][1], lid_box["z"][1])]
        width = primary_bounds[1] - primary_bounds[0]
        height = secondary_bounds[1] - secondary_bounds[0]
        if width <= 0.0 or height <= 0.0:
            raise AssertionError(f"keeper/lid planar seat overlap lost: {sid}")
        center = [
            (primary_bounds[0] + primary_bounds[1]) / 2.0,
            plane,
            (secondary_bounds[0] + secondary_bounds[1]) / 2.0,
        ]
        _assert_vec([float(v) for v in candidate.get("primary_bounds_m", [])], primary_bounds, f"{sid} primary bounds")
        _assert_vec([float(v) for v in candidate.get("secondary_bounds_m", [])], secondary_bounds, f"{sid} secondary bounds")
        _assert_vec([float(v) for v in candidate.get("dimensions_m", [])], [width, height], f"{sid} seat dimensions")
        _assert_close(float(candidate.get("area_m2")), width * height, f"{sid} seat area")
        _assert_vec([float(v) for v in candidate.get("center_m", [])], center, f"{sid} seat center")

        primary = [float(v) for v in candidate.get("primary_axis", [])]
        secondary = [float(v) for v in candidate.get("secondary_axis", [])]
        normal = [float(v) for v in candidate.get("owner_outward_normal", [])]
        _assert_vec(primary, [1.0, 0.0, 0.0], f"{sid} primary axis")
        _assert_vec(secondary, [0.0, 0.0, 1.0], f"{sid} secondary axis")
        _assert_vec(normal, [0.0, -1.0, 0.0], f"{sid} owner normal")
        orthogonality, parity = _frame_residual(primary, secondary, normal)
        if orthogonality > TOL or parity > TOL:
            raise AssertionError(f"{sid} source seat frame basis drift")

        neutral_corners = _seat_corners(center, primary, secondary, [width, height])
        neutral_rows.append(
            {
                "id": sid,
                "keeper": keeper_name,
                "center_m": center,
                "primary_axis": primary,
                "secondary_axis": secondary,
                "normal": normal,
                "dimensions_m": [width, height],
                "area_m2": width * height,
                "corners": neutral_corners,
                "lid_center_offset_m": _sub(center, [float(v) for v in lid["center_m"]]),
                "keeper_center_offset_m": _sub(center, [float(v) for v in keeper["center_m"]]),
                "keeper_center_m": [float(v) for v in keeper["center_m"]],
            }
        )

    representative_angles = [0, 30, 50, 60, 90, 100, 110]
    sweep: list[dict[str, Any]] = []
    max_center_recovery = 0.0
    max_axis_recovery = 0.0
    max_corner_recovery = 0.0
    max_pairwise_drift = 0.0
    max_area_drift = 0.0
    max_lid_local_offset_residual = 0.0
    max_keeper_local_offset_residual = 0.0
    max_orthogonality_residual = 0.0
    max_parity_residual = 0.0
    max_bilateral_x_residual = 0.0

    lid_center_neutral = [float(v) for v in lid["center_m"]]
    for open_angle in range(0, 111):
        math_angle = -float(open_angle)
        lid_center = _rotate_about_x(lid_center_neutral, hinge_origin, math_angle)
        pose_rows: list[dict[str, Any]] = []
        posed_centers: list[list[float]] = []
        for row in neutral_rows:
            center = _rotate_about_x(row["center_m"], hinge_origin, math_angle)
            primary = _rotate_vec_x(row["primary_axis"], math_angle)
            secondary = _rotate_vec_x(row["secondary_axis"], math_angle)
            normal = _rotate_vec_x(row["normal"], math_angle)
            keeper_center = _rotate_about_x(row["keeper_center_m"], hinge_origin, math_angle)
            corners = [_rotate_about_x(c, hinge_origin, math_angle) for c in row["corners"]]

            recovered_center = _rotate_about_x(center, hinge_origin, -math_angle)
            center_recovery = _dist(recovered_center, row["center_m"])
            recovered_primary = _rotate_vec_x(primary, -math_angle)
            recovered_secondary = _rotate_vec_x(secondary, -math_angle)
            recovered_normal = _rotate_vec_x(normal, -math_angle)
            axis_recovery = max(
                _dist(recovered_primary, row["primary_axis"]),
                _dist(recovered_secondary, row["secondary_axis"]),
                _dist(recovered_normal, row["normal"]),
            )
            recovered_corners = [_rotate_about_x(c, hinge_origin, -math_angle) for c in corners]
            corner_recovery = max(_dist(a, b) for a, b in zip(recovered_corners, row["corners"]))
            pairwise_drift = _max_pairwise_drift(row["corners"], corners)
            posed_width = _dist(corners[0], corners[2])
            posed_height = _dist(corners[0], corners[1])
            area_drift = abs(posed_width * posed_height - row["area_m2"])
            lid_local_offset = _rotate_vec_x(_sub(center, lid_center), -math_angle)
            keeper_local_offset = _rotate_vec_x(_sub(center, keeper_center), -math_angle)
            lid_local_residual = _dist(lid_local_offset, row["lid_center_offset_m"])
            keeper_local_residual = _dist(keeper_local_offset, row["keeper_center_offset_m"])
            orthogonality, parity = _frame_residual(primary, secondary, normal)

            max_center_recovery = max(max_center_recovery, center_recovery)
            max_axis_recovery = max(max_axis_recovery, axis_recovery)
            max_corner_recovery = max(max_corner_recovery, corner_recovery)
            max_pairwise_drift = max(max_pairwise_drift, pairwise_drift)
            max_area_drift = max(max_area_drift, area_drift)
            max_lid_local_offset_residual = max(max_lid_local_offset_residual, lid_local_residual)
            max_keeper_local_offset_residual = max(max_keeper_local_offset_residual, keeper_local_residual)
            max_orthogonality_residual = max(max_orthogonality_residual, orthogonality)
            max_parity_residual = max(max_parity_residual, parity)
            posed_centers.append(center)
            pose_rows.append(
                {
                    "station_id": row["id"],
                    "seat_center_m": center,
                    "primary_axis": primary,
                    "secondary_axis": secondary,
                    "owner_outward_normal": normal,
                    "center_recovery_residual_m": center_recovery,
                    "axis_recovery_residual": axis_recovery,
                    "corner_recovery_residual_m": corner_recovery,
                    "pairwise_distance_drift_m": pairwise_drift,
                    "area_drift_m2": area_drift,
                    "lid_local_offset_residual_m": lid_local_residual,
                    "keeper_local_offset_residual_m": keeper_local_residual,
                }
            )

        bilateral = abs(posed_centers[0][0] + posed_centers[1][0])
        max_bilateral_x_residual = max(max_bilateral_x_residual, bilateral)
        sweep.append(
            {
                "open_angle_deg": open_angle,
                "mathematical_x_rotation_deg": math_angle,
                "bilateral_seat_x_residual_m": bilateral,
                "stations": pose_rows,
            }
        )

    maxima = {
        "max_seat_center_recovery_residual_m": max_center_recovery,
        "max_seat_axis_recovery_residual": max_axis_recovery,
        "max_seat_corner_recovery_residual_m": max_corner_recovery,
        "max_seat_pairwise_distance_drift_m": max_pairwise_drift,
        "max_seat_area_drift_m2": max_area_drift,
        "max_lid_local_seat_offset_residual_m": max_lid_local_offset_residual,
        "max_keeper_local_seat_offset_residual_m": max_keeper_local_offset_residual,
        "max_frame_orthogonality_residual": max_orthogonality_residual,
        "max_frame_parity_residual": max_parity_residual,
        "max_bilateral_seat_x_residual_m": max_bilateral_x_residual,
    }
    for label, value in maxima.items():
        if float(value) > TOL:
            raise AssertionError(f"{label} exceeds tolerance: {value}")

    return {
        "schema": SCHEMA,
        "result": RESULT,
        "asset_id": source["asset_id"],
        "source_sha256": source_sha256,
        "identity": {
            "keeper_seat_source_owner_head": KEEPER_SEAT_HEAD,
            "keeper_seat_source_owner_blob": KEEPER_SEAT_BLOB,
            "keeper_seat_contract_id": "front-latch-keeper-seat-001",
            "ownership_contract_sha256": ownership_sha256,
            "lid_rig_head": LID_RIG_HEAD,
            "lid_plan_digest": LID_PLAN_DIGEST,
            "previous_rigging_head": PREVIOUS_RIGGING_HEAD,
            "joint_id": "rear-lid-hinge-001",
            "hinge_axis": [1.0, 0.0, 0.0],
            "hinge_origin_m": hinge_origin,
        },
        "seat_frame_binding": {
            "station_count": len(neutral_rows),
            "sweep_sample_count": len(sweep),
            "open_angle_envelope_deg": [0, 110],
            "step_deg": 1,
            "representative_angles_deg": representative_angles,
            "representative_poses": [sweep[a] for a in representative_angles],
            **maxima,
        },
        "truth_boundary": {
            "proves": "The exact Hard-Surface source-owned keeper attachment-seat centers, axes, dimensions and rigid planar frames remain lid-local and keeper-local over the exact historical 0..110 degree one-degree Rigging pose field.",
            "does_not_prove": "Physical fastening or retention, manufacturing fit, keeper/lever collision clearance, latch release/capture, combined motion, continuous collision freedom, Animation timing/interpolation/playback, Runtime/controller/device behavior, physics/gameplay, visual acceptance, CANON or production readiness.",
            "source_geometry_changed": False,
            "source_seat_semantics_changed": False,
            "animation_accepted": False,
            "runtime_accepted": False,
            "physical_attachment_accepted": False,
        },
        "sweep": sweep,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--ownership", type=Path, required=True)
    parser.add_argument("--keeper-seat", type=Path, required=True)
    parser.add_argument("--lid-plan", type=Path, required=True)
    parser.add_argument("--observed-keeper-seat-head", required=True)
    parser.add_argument("--observed-keeper-seat-blob", required=True)
    parser.add_argument("--observed-lid-rig-head", required=True)
    parser.add_argument("--observed-previous-rigging-head", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    source = json.loads(args.source.read_text(encoding="utf-8"))
    ownership = json.loads(args.ownership.read_text(encoding="utf-8"))
    keeper_seat = json.loads(args.keeper_seat.read_text(encoding="utf-8"))
    lid_plan = json.loads(args.lid_plan.read_text(encoding="utf-8"))
    receipt = verify(
        source,
        ownership,
        keeper_seat,
        lid_plan,
        source_sha256=sha256_file(args.source),
        ownership_sha256=sha256_file(args.ownership),
        observed_keeper_seat_head=args.observed_keeper_seat_head,
        observed_keeper_seat_blob=args.observed_keeper_seat_blob,
        observed_lid_rig_head=args.observed_lid_rig_head,
        observed_previous_rigging_head=args.observed_previous_rigging_head,
    )
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = receipt["seat_frame_binding"]
    (args.out / "summary.txt").write_text(
        f"{receipt['result']}\n"
        f"sweep_sample_count={summary['sweep_sample_count']}\n"
        f"max_seat_center_recovery_residual_m={summary['max_seat_center_recovery_residual_m']:.18g}\n"
        f"max_seat_axis_recovery_residual={summary['max_seat_axis_recovery_residual']:.18g}\n"
        f"max_seat_corner_recovery_residual_m={summary['max_seat_corner_recovery_residual_m']:.18g}\n"
        f"max_seat_pairwise_distance_drift_m={summary['max_seat_pairwise_distance_drift_m']:.18g}\n"
        f"max_seat_area_drift_m2={summary['max_seat_area_drift_m2']:.18g}\n",
        encoding="utf-8",
    )
    print(receipt["result"])


if __name__ == "__main__":
    main()
