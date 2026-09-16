from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from build_modular_case import build
import verify_front_latch_pivot_interface as source_interface

SCHEMA = "axm.object-front-latch-source-rig-binding/v0.1"
RESULT = "PASS_SOURCE_OWNED_FRONT_LATCH_RIG_REBIND"
EXPECTED_INTERFACE_HEAD = "6086f39a3da344c57a68653f90d040e03e04cec2"
EXPECTED_INTERFACE_SHA256 = "bcbbe098371eb702bc9289a97370744093105925202eda6036bdced6e25e34d3"
EXPECTED_HISTORICAL_RIG_HEAD = "3b667ff5d30c46ec2fe7da7679518970f8610018"
EXPECTED_HISTORICAL_PLAN_SHA256 = "81c27ab7b73ed9a43cb3f554b56c3f4294b893712075e33d13f5b02e008455db"
TOL = 1e-12


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _component_map(host: dict) -> dict[str, dict]:
    return {row["name"]: row for row in build(host)["components"]}


def _corners(component: dict) -> list[tuple[float, float, float]]:
    bounds = source_interface._bounds(component)
    return [
        (x, y, z)
        for x in bounds[0]
        for y in bounds[1]
        for z in bounds[2]
    ]


def _rotate_x(point: tuple[float, float, float], pivot: tuple[float, float, float], angle_deg: float) -> tuple[float, float, float]:
    angle = math.radians(angle_deg)
    ca, sa = math.cos(angle), math.sin(angle)
    x, y, z = point
    px, py, pz = pivot
    dy, dz = y - py, z - pz
    return (x, py + dy * ca - dz * sa, pz + dy * sa + dz * ca)


def _bounds_from_points(points: list[tuple[float, float, float]]):
    return tuple((min(p[i] for p in points), max(p[i] for p in points)) for i in range(3))


def _pairwise(points: list[tuple[float, float, float]]) -> list[float]:
    out = []
    for idx, a in enumerate(points):
        for b in points[idx + 1 :]:
            out.append(math.dist(a, b))
    return out


def _max_delta(a: list[float], b: list[float]) -> float:
    return max((abs(x - y) for x, y in zip(a, b)), default=0.0)


def _axis_overlap(a, b):
    return tuple(min(a[i][1], b[i][1]) - max(a[i][0], b[i][0]) for i in range(3))


def verify(
    host: dict,
    ownership: dict,
    interface: dict,
    historical_plan: dict,
    binding: dict,
    *,
    host_sha: str,
    ownership_sha: str,
    interface_sha: str,
    historical_plan_sha: str,
    binding_sha: str,
) -> dict:
    if binding.get("schema") != SCHEMA:
        raise AssertionError("unsupported source-rig binding schema")
    if binding.get("asset_id") != host.get("asset_id"):
        raise AssertionError("binding asset identity mismatch")
    if binding.get("host_source_sha256") != host_sha:
        raise AssertionError("binding host source identity mismatch")

    source_ref = binding.get("source_interface", {})
    if source_ref.get("head") != EXPECTED_INTERFACE_HEAD:
        raise AssertionError("source interface head drift")
    if source_ref.get("sha256") != EXPECTED_INTERFACE_SHA256 or interface_sha != EXPECTED_INTERFACE_SHA256:
        raise AssertionError("source interface file identity drift")
    if source_ref.get("role") != "CURRENT_SOURCE_INTERFACE_AUTHORITY":
        raise AssertionError("source interface authority role drift")

    historical_ref = binding.get("historical_rigging_observation", {})
    if historical_ref.get("head") != EXPECTED_HISTORICAL_RIG_HEAD:
        raise AssertionError("historical Rigging head drift")
    if historical_ref.get("plan_sha256") != EXPECTED_HISTORICAL_PLAN_SHA256 or historical_plan_sha != EXPECTED_HISTORICAL_PLAN_SHA256:
        raise AssertionError("historical Rigging plan identity drift")
    if historical_ref.get("role") != "PROVENANCE_ONLY_NOT_CURRENT_INTERFACE_AUTHORITY":
        raise AssertionError("historical Rigging role drift")

    interface_receipt = source_interface.verify(
        host,
        ownership,
        interface,
        historical_plan,
        host_sha=host_sha,
        ownership_sha=ownership_sha,
        interface_sha=interface_sha,
        rigging_plan_sha=historical_plan_sha,
    )
    if interface_receipt.get("result") != source_interface.RESULT:
        raise AssertionError("source-owned pivot interface prerequisite did not pass")

    if binding.get("joint_axis") != interface.get("joint_axis") or binding.get("joint_axis") != [1.0, 0.0, 0.0]:
        raise AssertionError("binding joint axis drift")
    poses = [float(value) for value in binding.get("pose_samples_deg", [])]
    if poses != [0.0, 25.0, 50.0]:
        raise AssertionError("representative pose schedule drift")

    components = _component_map(host)
    rows = []
    max_rigidity_drift = 0.0
    max_pivot_drift = 0.0
    midpoint_overlaps = []
    endpoint_separations = []

    for station in interface.get("stations", []):
        lever = components.get(station.get("lever_component"))
        keeper = components.get(station.get("keeper_component"))
        if lever is None or keeper is None:
            raise AssertionError("source-owned latch component missing")
        if station.get("lever_owner_component") != "front_service_panel" or station.get("keeper_owner_component") != "lid_shell":
            raise AssertionError("source-owned latch owner drift")

        pivot = tuple(float(v) for v in station.get("pivot_origin_m", []))
        if len(pivot) != 3:
            raise AssertionError("source-owned pivot missing")
        neutral = _corners(lever)
        neutral_pairwise = _pairwise(neutral)
        keeper_bounds = source_interface._bounds(keeper)
        pose_rows = []

        for angle in poses:
            moved = [_rotate_x(point, pivot, angle) for point in neutral]
            moved_bounds = _bounds_from_points(moved)
            overlap = _axis_overlap(moved_bounds, keeper_bounds)
            rigid_drift = _max_delta(neutral_pairwise, _pairwise(moved))
            rotated_pivot = _rotate_x(pivot, pivot, angle)
            pivot_drift = math.dist(pivot, rotated_pivot)
            max_rigidity_drift = max(max_rigidity_drift, rigid_drift)
            max_pivot_drift = max(max_pivot_drift, pivot_drift)
            pose_rows.append({
                "angle_deg": angle,
                "keeper_axis_overlap_m": {"x": overlap[0], "y": overlap[1], "z": overlap[2]},
                "maximum_rigid_pairwise_distance_drift_m": rigid_drift,
                "pivot_drift_m": pivot_drift,
            })

        closed = pose_rows[0]["keeper_axis_overlap_m"]
        midpoint = pose_rows[1]["keeper_axis_overlap_m"]
        endpoint = pose_rows[2]["keeper_axis_overlap_m"]
        if binding.get("required_closed_overlap") is not True or min(closed.values()) <= 0.0:
            raise AssertionError("closed keeper/lever overlap boundary failed")
        if binding.get("required_midpoint_keeper_z_overlap") is not True or midpoint["z"] <= 0.0:
            raise AssertionError("midpoint keeper Z overlap boundary failed")
        required_release = float(binding.get("required_release_endpoint_keeper_z_separation_m", -1.0))
        endpoint_separation = -float(endpoint["z"])
        if endpoint_separation + TOL < required_release:
            raise AssertionError("release endpoint keeper Z separation boundary failed")
        midpoint_overlaps.append(float(midpoint["z"]))
        endpoint_separations.append(endpoint_separation)

        threshold = source_interface._threshold_deg(lever, keeper, pivot, poses[-1])
        if abs(threshold - float(interface_receipt["release_threshold_deg"])) > TOL:
            raise AssertionError("source-owned continuous release threshold drift")
        if abs(endpoint_separation - float(interface_receipt["terminal_keeper_z_separation_m"])) > TOL:
            raise AssertionError("source-owned terminal release separation drift")

        rows.append({
            "station_id": station["id"],
            "pivot_origin_m": list(pivot),
            "lever_component": station["lever_component"],
            "keeper_component": station["keeper_component"],
            "pose_results": pose_rows,
            "continuous_release_threshold_deg": threshold,
            "midpoint_keeper_z_overlap_m": midpoint["z"],
            "endpoint_keeper_z_separation_m": endpoint_separation,
        })

    if len(rows) != 2:
        raise AssertionError("exact bilateral latch station count drift")
    if max_rigidity_drift > TOL or max_pivot_drift > TOL:
        raise AssertionError("rigid lever or fixed pivot drift exceeded tolerance")

    bilateral_midpoint_residual = abs(midpoint_overlaps[0] - midpoint_overlaps[1])
    bilateral_endpoint_residual = abs(endpoint_separations[0] - endpoint_separations[1])
    if bilateral_midpoint_residual > TOL or bilateral_endpoint_residual > TOL:
        raise AssertionError("bilateral representative boundary drift")

    return {
        "schema": "axm.object-front-latch-source-rig-binding-evidence/v0.1",
        "result": RESULT,
        "asset_id": host["asset_id"],
        "host_source_sha256": host_sha,
        "ownership_contract_sha256": ownership_sha,
        "source_interface_head": source_ref["head"],
        "source_interface_sha256": interface_sha,
        "historical_rigging_observation_head": historical_ref["head"],
        "historical_rigging_observation_plan_sha256": historical_plan_sha,
        "historical_rigging_role": historical_ref["role"],
        "binding_sha256": binding_sha,
        "rig_authority": source_ref["role"],
        "pose_samples_deg": poses,
        "station_results": rows,
        "maximum_rigid_pairwise_distance_drift_m": max_rigidity_drift,
        "maximum_pivot_drift_m": max_pivot_drift,
        "continuous_release_threshold_deg": interface_receipt["release_threshold_deg"],
        "minimum_midpoint_keeper_z_overlap_m": min(midpoint_overlaps),
        "minimum_endpoint_keeper_z_separation_m": min(endpoint_separations),
        "bilateral_midpoint_overlap_residual_m": bilateral_midpoint_residual,
        "bilateral_endpoint_separation_residual_m": bilateral_endpoint_residual,
        "host_geometry_changed": False,
        "truth_boundary": binding["truth_boundary"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=Path, required=True)
    parser.add_argument("--ownership", type=Path, required=True)
    parser.add_argument("--interface", type=Path, required=True)
    parser.add_argument("--historical-plan", type=Path, required=True)
    parser.add_argument("--binding", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    host = json.loads(args.host.read_text(encoding="utf-8"))
    ownership = json.loads(args.ownership.read_text(encoding="utf-8"))
    interface = json.loads(args.interface.read_text(encoding="utf-8"))
    historical_plan = json.loads(args.historical_plan.read_text(encoding="utf-8"))
    binding = json.loads(args.binding.read_text(encoding="utf-8"))

    receipt = verify(
        host,
        ownership,
        interface,
        historical_plan,
        binding,
        host_sha=sha256(args.host),
        ownership_sha=sha256(args.ownership),
        interface_sha=sha256(args.interface),
        historical_plan_sha=sha256(args.historical_plan),
        binding_sha=sha256(args.binding),
    )
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "front-latch-source-rig-binding-evidence.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
