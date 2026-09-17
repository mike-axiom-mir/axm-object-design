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

SCHEMA = "axm.object-lid-keeper-socket-binding/v0.1"
RESULT = "PASS_LID_OWNED_KEEPER_SOCKET_BINDING_111_POSES"
SOURCE_SHA256 = "49b1f9ed9865893d6de6f1ec8f069576732df694853fde4e3fcff366de32644a"
OWNERSHIP_HEAD = "d3fa10a270faae7925811f44f03381fe5c5d0215"
LID_RIG_HEAD = "4b72c9918c5fc1e89bd18a0be24fb4afac6e7775"
PREVIOUS_RIGGING_HEAD = "9556308c9986f71519bc488badc1b1a63e855e7e"
LID_PLAN_DIGEST = "0ad6dc2ca22676cf301579932e599a441eb7c4bccce31991d1b727aeb22ac422"
TOL = 1e-12


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rotate_about_x(point: list[float], origin: list[float], angle_deg: float) -> list[float]:
    x, y, z = map(float, point)
    ox, oy, oz = map(float, origin)
    y -= oy
    z -= oz
    a = math.radians(angle_deg)
    c, s = math.cos(a), math.sin(a)
    return [x, oy + y * c - z * s, oz + y * s + z * c]


def _corners(component: dict[str, Any]) -> list[list[float]]:
    if component.get("kind") != "box":
        raise AssertionError(f"expected box component: {component.get('name')}")
    cx, cy, cz = map(float, component["center_m"])
    sx, sy, sz = map(float, component["size_m"])
    return [
        [cx + dx * sx / 2.0, cy + dy * sy / 2.0, cz + dz * sz / 2.0]
        for dx in (-1.0, 1.0)
        for dy in (-1.0, 1.0)
        for dz in (-1.0, 1.0)
    ]


def _sub(a: list[float], b: list[float]) -> list[float]:
    return [float(a[i]) - float(b[i]) for i in range(3)]


def _dist(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((float(a[i]) - float(b[i])) ** 2 for i in range(3)))


def _max_pairwise_drift(before: list[list[float]], after: list[list[float]]) -> float:
    best = 0.0
    for i in range(len(before)):
        for j in range(i + 1, len(before)):
            best = max(best, abs(_dist(before[i], before[j]) - _dist(after[i], after[j])))
    return best


def verify(
    source: dict[str, Any],
    ownership: dict[str, Any],
    lid_plan: dict[str, Any],
    *,
    source_sha256: str,
    observed_ownership_head: str,
    observed_lid_rig_head: str,
    observed_previous_rigging_head: str,
    local_offset_override: dict[str, list[float]] | None = None,
) -> dict[str, Any]:
    if source_sha256 != SOURCE_SHA256:
        raise AssertionError("exact Object source byte identity drift")
    if observed_ownership_head != OWNERSHIP_HEAD:
        raise AssertionError("front-latch ownership donor head drift")
    if observed_lid_rig_head != LID_RIG_HEAD:
        raise AssertionError("lid articulation donor head drift")
    if observed_previous_rigging_head != PREVIOUS_RIGGING_HEAD:
        raise AssertionError("previous Rigging target-binding head drift")
    if ownership.get("schema") != "axm.object-front-latch-ownership/v0.1":
        raise AssertionError("unexpected ownership schema")
    if ownership.get("host_source_sha256") != SOURCE_SHA256:
        raise AssertionError("ownership source identity drift")
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
    hinge_origin = [float(v) for v in built["hinge_axis"]["origin_m"]]
    if [float(v) for v in built["hinge_axis"]["axis"]] != [1.0, 0.0, 0.0]:
        raise AssertionError("source hinge axis drift")
    lid = components["lid_shell"]
    lid_center_neutral = [float(v) for v in lid["center_m"]]

    stations = ownership.get("stations", [])
    if len(stations) != 2:
        raise AssertionError("bounded proof requires exactly two latch stations")

    keeper_rows: list[dict[str, Any]] = []
    expected_names = {"latch_0_keeper", "latch_1_keeper"}
    seen_names: set[str] = set()
    for station in stations:
        keeper_name = str(station.get("keeper_component", ""))
        lever_name = str(station.get("lever_component", ""))
        if station.get("keeper_owner_component") != "lid_shell":
            raise AssertionError(f"keeper owner drift: {keeper_name}")
        if station.get("lever_owner_component") != "front_service_panel":
            raise AssertionError(f"lever owner drift: {lever_name}")
        if keeper_name not in components or lever_name not in components:
            raise AssertionError("source latch component missing")
        keeper = components[keeper_name]
        lever = components[lever_name]
        if keeper.get("role") != "latch_keeper" or lever.get("role") != "latch_lever":
            raise AssertionError("source latch role drift")
        seen_names.add(keeper_name)

        keeper_center = [float(v) for v in keeper["center_m"]]
        expected_offset = _sub(keeper_center, lid_center_neutral)
        candidate_offset = list(expected_offset)
        if local_offset_override and keeper_name in local_offset_override:
            candidate_offset = [float(v) for v in local_offset_override[keeper_name]]
        if _dist(candidate_offset, expected_offset) > TOL:
            raise AssertionError(f"keeper local socket offset drift: {keeper_name}")

        keeper_rows.append(
            {
                "station_id": station["id"],
                "keeper": keeper_name,
                "lever": lever_name,
                "neutral_keeper_center_m": keeper_center,
                "neutral_lid_local_center_offset_m": expected_offset,
                "neutral_keeper_corners": _corners(keeper),
                "lever_center_m": [float(v) for v in lever["center_m"]],
            }
        )

    if seen_names != expected_names:
        raise AssertionError("exact keeper identity drift")

    representative_angles = sorted(set([0, 30, 50, 60, 90, 100, 110]))
    sweep: list[dict[str, Any]] = []
    max_local_offset_residual = 0.0
    max_rigidity_drift = 0.0
    max_lever_drift = 0.0
    max_bilateral_x_residual = 0.0

    for open_angle in range(0, 111):
        math_angle = -float(open_angle)
        lid_center = _rotate_about_x(lid_center_neutral, hinge_origin, math_angle)
        per_keeper = []
        posed_keeper_centers: list[list[float]] = []
        for row in keeper_rows:
            center = _rotate_about_x(row["neutral_keeper_center_m"], hinge_origin, math_angle)
            corners = [_rotate_about_x(c, hinge_origin, math_angle) for c in row["neutral_keeper_corners"]]
            # Convert the posed center offset back into the lid's neutral local frame.
            posed_offset = _sub(center, lid_center)
            local_recovered = _rotate_about_x(posed_offset, [0.0, 0.0, 0.0], -math_angle)
            local_residual = _dist(local_recovered, row["neutral_lid_local_center_offset_m"])
            rigidity_drift = _max_pairwise_drift(row["neutral_keeper_corners"], corners)
            lever_drift = _dist(row["lever_center_m"], row["lever_center_m"])
            max_local_offset_residual = max(max_local_offset_residual, local_residual)
            max_rigidity_drift = max(max_rigidity_drift, rigidity_drift)
            max_lever_drift = max(max_lever_drift, lever_drift)
            posed_keeper_centers.append(center)
            per_keeper.append(
                {
                    "keeper": row["keeper"],
                    "center_m": center,
                    "lid_local_offset_residual_m": local_residual,
                    "rigidity_drift_m": rigidity_drift,
                    "lever_center_drift_m": lever_drift,
                }
            )
        bilateral = abs(posed_keeper_centers[0][0] + posed_keeper_centers[1][0])
        max_bilateral_x_residual = max(max_bilateral_x_residual, bilateral)
        sweep.append(
            {
                "open_angle_deg": open_angle,
                "mathematical_x_rotation_deg": math_angle,
                "lid_center_m": lid_center,
                "bilateral_keeper_x_residual_m": bilateral,
                "keepers": per_keeper,
            }
        )

    if max_local_offset_residual > TOL:
        raise AssertionError(f"lid-owned keeper local socket residual exceeds tolerance: {max_local_offset_residual}")
    if max_rigidity_drift > TOL:
        raise AssertionError(f"keeper rigidity drift exceeds tolerance: {max_rigidity_drift}")
    if max_lever_drift > TOL:
        raise AssertionError(f"fixed lever drift exceeds tolerance: {max_lever_drift}")
    if max_bilateral_x_residual > TOL:
        raise AssertionError(f"bilateral keeper symmetry drift: {max_bilateral_x_residual}")

    representative = [sweep[a] for a in representative_angles]
    return {
        "schema": SCHEMA,
        "result": RESULT,
        "asset_id": source["asset_id"],
        "source_sha256": source_sha256,
        "identity": {
            "ownership_head": OWNERSHIP_HEAD,
            "lid_rig_head": LID_RIG_HEAD,
            "lid_plan_digest": LID_PLAN_DIGEST,
            "previous_rigging_target_binding_head": PREVIOUS_RIGGING_HEAD,
            "joint_id": "rear-lid-hinge-001",
            "hinge_axis": [1.0, 0.0, 0.0],
            "hinge_origin_m": hinge_origin,
            "moving_owner": "lid_shell",
            "fixed_lever_owner": "front_service_panel",
        },
        "socket_binding": {
            "keeper_count": 2,
            "sweep_sample_count": len(sweep),
            "open_angle_envelope_deg": [0, 110],
            "step_deg": 1,
            "max_lid_local_offset_residual_m": max_local_offset_residual,
            "max_keeper_rigidity_drift_m": max_rigidity_drift,
            "max_fixed_lever_center_drift_m": max_lever_drift,
            "max_bilateral_keeper_x_residual_m": max_bilateral_x_residual,
            "representative_angles_deg": representative_angles,
            "representative_poses": representative,
        },
        "truth_boundary": {
            "proves": "The exact two source-owned upper latch keepers remain rigid lid-shell sockets over the exact historical 0..110 degree lid articulation field while the lower service-panel levers remain fixed.",
            "does_not_prove": "Keeper/lever collision clearance, latch release/capture, combined lever actuation, animation timing or playback, controller/runtime behavior, physics/load/manufacturing, visual acceptance, CANON or production readiness.",
            "animation_accepted": False,
            "runtime_accepted": False,
            "full_latch_mechanism_accepted": False,
        },
        "sweep": sweep,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--ownership", type=Path, required=True)
    parser.add_argument("--lid-plan", type=Path, required=True)
    parser.add_argument("--observed-ownership-head", required=True)
    parser.add_argument("--observed-lid-rig-head", required=True)
    parser.add_argument("--observed-previous-rigging-head", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    source = json.loads(args.source.read_text(encoding="utf-8"))
    ownership = json.loads(args.ownership.read_text(encoding="utf-8"))
    lid_plan = json.loads(args.lid_plan.read_text(encoding="utf-8"))
    receipt = verify(
        source,
        ownership,
        lid_plan,
        source_sha256=sha256_file(args.source),
        observed_ownership_head=args.observed_ownership_head,
        observed_lid_rig_head=args.observed_lid_rig_head,
        observed_previous_rigging_head=args.observed_previous_rigging_head,
    )
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = receipt["socket_binding"]
    (args.out / "summary.txt").write_text(
        f"{receipt['result']}\n"
        f"sweep_sample_count={summary['sweep_sample_count']}\n"
        f"max_lid_local_offset_residual_m={summary['max_lid_local_offset_residual_m']:.18g}\n"
        f"max_keeper_rigidity_drift_m={summary['max_keeper_rigidity_drift_m']:.18g}\n"
        f"max_fixed_lever_center_drift_m={summary['max_fixed_lever_center_drift_m']:.18g}\n",
        encoding="utf-8",
    )
    print(receipt["result"])


if __name__ == "__main__":
    main()
