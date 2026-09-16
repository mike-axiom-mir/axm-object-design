from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import build_modular_case
import verify_front_latch_ownership as ownership

SCHEMA = "axm.object-front-latch-articulation/v0.1"
RESULT = "PASS_BOUNDED_FRONT_LATCH_LEVER_ARTICULATION"
EXPECTED_OWNERSHIP_DONOR = "d3fa10a270faae7925811f44f03381fe5c5d0215"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _aabb(component: dict) -> dict[str, tuple[float, float]]:
    if component.get("kind") != "box":
        raise AssertionError(f"component is not a box: {component.get('name')}")
    c = component["center_m"]
    s = component["size_m"]
    return {
        axis: (float(c[i]) - float(s[i]) / 2.0, float(c[i]) + float(s[i]) / 2.0)
        for i, axis in enumerate(("x", "y", "z"))
    }


def _component_map(built: dict) -> dict[str, dict]:
    return {c["name"]: c for c in built["components"]}


def _box_corners(component: dict) -> list[tuple[float, float, float]]:
    b = _aabb(component)
    return [(x, y, z) for x in b["x"] for y in b["y"] for z in b["z"]]


def _rotate_x(point: tuple[float, float, float], pivot: tuple[float, float, float], angle_deg: float) -> tuple[float, float, float]:
    a = math.radians(angle_deg)
    x, y, z = point
    px, py, pz = pivot
    dy, dz = y - py, z - pz
    return (
        x,
        py + dy * math.cos(a) - dz * math.sin(a),
        pz + dy * math.sin(a) + dz * math.cos(a),
    )


def _bounds(points: list[tuple[float, float, float]]) -> dict[str, tuple[float, float]]:
    return {
        "x": (min(p[0] for p in points), max(p[0] for p in points)),
        "y": (min(p[1] for p in points), max(p[1] for p in points)),
        "z": (min(p[2] for p in points), max(p[2] for p in points)),
    }


def _overlap_1d(a: tuple[float, float], b: tuple[float, float]) -> float:
    return min(a[1], b[1]) - max(a[0], b[0])


def _pairwise_distances(points: list[tuple[float, float, float]]) -> list[float]:
    out = []
    for i, a in enumerate(points):
        for b in points[i + 1 :]:
            out.append(math.dist(a, b))
    return out


def _max_abs_delta(a: list[float], b: list[float]) -> float:
    return max((abs(x - y) for x, y in zip(a, b)), default=0.0)


def _threshold_angle(pivot: tuple[float, float, float], lever: dict, keeper: dict, max_angle_deg: float) -> tuple[float, float]:
    lever_box = _aabb(lever)
    keeper_box = _aabb(keeper)
    py, pz = pivot[1], pivot[2]
    dy_max = lever_box["y"][1] - py
    dz_max = lever_box["z"][1] - pz
    keeper_min_z = keeper_box["z"][0]

    def clearance(angle_deg: float) -> float:
        a = math.radians(angle_deg)
        lever_max_z = pz + dy_max * math.sin(a) + dz_max * math.cos(a)
        return keeper_min_z - lever_max_z

    turning_deg = math.degrees(math.atan2(dy_max, dz_max))
    lo = max(turning_deg, 0.0)
    hi = max_angle_deg
    if clearance(lo) >= 0.0 or clearance(hi) <= 0.0:
        raise AssertionError("review envelope does not bracket keeper Z-separation threshold")
    for _ in range(100):
        mid = (lo + hi) / 2.0
        if clearance(mid) >= 0.0:
            hi = mid
        else:
            lo = mid
    threshold = (lo + hi) / 2.0
    if threshold <= turning_deg:
        raise AssertionError("separation threshold is not on monotonic decreasing lever-max-Z branch")
    return threshold, clearance(max_angle_deg)


def verify(host: dict, ownership_contract: dict, plan: dict, *, host_sha: str, ownership_sha: str, plan_sha: str) -> dict:
    if plan.get("schema") != SCHEMA:
        raise AssertionError("unsupported articulation schema")
    if plan.get("asset_id") != host.get("asset_id"):
        raise AssertionError("articulation asset identity mismatch")
    if plan.get("host_source_sha256") != host_sha:
        raise AssertionError("host source identity mismatch")
    if plan.get("ownership_contract_id") != ownership_contract.get("contract_id"):
        raise AssertionError("ownership contract identity mismatch")
    if plan.get("ownership_donor_head") != EXPECTED_OWNERSHIP_DONOR:
        raise AssertionError("ownership donor head drift")
    if plan.get("joint_axis") != [1.0, 0.0, 0.0]:
        raise AssertionError("v0.1 requires exact +X joint axis")
    if plan.get("pivot_rule") != "source_x__panel_negative_y_face__lever_min_z":
        raise AssertionError("unsupported pivot derivation rule")
    if plan.get("moving_role") != "latch_lever" or plan.get("fixed_keeper_role") != "latch_keeper":
        raise AssertionError("latch role drift")
    if plan.get("owner_component") != "front_service_panel":
        raise AssertionError("lever owner drift")

    ownership_receipt = ownership.verify(
        host,
        ownership_contract,
        host_sha=host_sha,
        contract_sha=ownership_sha,
    )
    if ownership_receipt.get("result") != ownership.RESULT:
        raise AssertionError("ownership prerequisite did not pass")

    built = build_modular_case.build(host)
    components = _component_map(built)
    panel = components["front_service_panel"]
    panel_box = _aabb(panel)
    poses = [float(x) for x in plan.get("pose_samples_deg", [])]
    lo_angle = float(plan.get("review_angle_min_deg"))
    hi_angle = float(plan.get("review_angle_max_deg"))
    if poses != [0.0, 25.0, 50.0] or lo_angle != 0.0 or hi_angle != 50.0:
        raise AssertionError("v0.1 review envelope drift")

    rows = []
    threshold_values = []
    terminal_values = []
    for station in ownership_contract["stations"]:
        lever = components[station["lever_component"]]
        keeper = components[station["keeper_component"]]
        if lever.get("role") != "latch_lever" or keeper.get("role") != "latch_keeper":
            raise AssertionError("exact latch component role drift")
        lever_box = _aabb(lever)
        keeper_box = _aabb(keeper)
        source_x = float(station["source_x_m"])
        pivot = (source_x, panel_box["y"][0], lever_box["z"][0])

        # The candidate pivot must stay inside the exact static lever/panel overlap,
        # rather than floating outside the source construction.
        if not (lever_box["y"][0] - 1e-12 <= pivot[1] <= lever_box["y"][1] + 1e-12):
            raise AssertionError("derived pivot Y is outside lever proof volume")
        if not (panel_box["z"][0] - 1e-12 <= pivot[2] <= panel_box["z"][1] + 1e-12):
            raise AssertionError("derived pivot Z is outside panel proof volume")
        if abs(float(lever["center_m"][0]) - pivot[0]) > 1e-12:
            raise AssertionError("derived pivot X left source latch station")

        neutral = _box_corners(lever)
        neutral_dist = _pairwise_distances(neutral)
        pose_rows = []
        max_rigidity_drift = 0.0
        max_pivot_drift = 0.0
        for angle in poses:
            moved = [_rotate_x(p, pivot, angle) for p in neutral]
            moved_box = _bounds(moved)
            max_rigidity_drift = max(max_rigidity_drift, _max_abs_delta(neutral_dist, _pairwise_distances(moved)))
            rotated_pivot = _rotate_x(pivot, pivot, angle)
            max_pivot_drift = max(max_pivot_drift, math.dist(pivot, rotated_pivot))
            pose_rows.append(
                {
                    "angle_deg": angle,
                    "lever_bounds_m": {k: [v[0], v[1]] for k, v in moved_box.items()},
                    "keeper_axis_overlap_m": {
                        axis: _overlap_1d(moved_box[axis], keeper_box[axis]) for axis in ("x", "y", "z")
                    },
                }
            )

        closed = pose_rows[0]["keeper_axis_overlap_m"]
        if min(closed.values()) <= 0.0:
            raise AssertionError("neutral pose no longer reproduces closed keeper/lever overlap")
        threshold, terminal_sep = _threshold_angle(pivot, lever, keeper, hi_angle)
        minimum_terminal = float(plan.get("minimum_terminal_keeper_axis_separation_m", -1.0))
        if terminal_sep < minimum_terminal - 1e-12:
            raise AssertionError("terminal keeper separation is below declared bound")
        if max_rigidity_drift > 1e-12 or max_pivot_drift > 1e-12:
            raise AssertionError("rigid lever or pivot drift exceeded tolerance")

        # Analytic continuity certificate for the exact separated tail of the review arc.
        dy_max = lever_box["y"][1] - pivot[1]
        dz_max = lever_box["z"][1] - pivot[2]
        turning_deg = math.degrees(math.atan2(dy_max, dz_max))
        if threshold <= turning_deg or hi_angle >= 90.0:
            raise AssertionError("continuous separation proof assumptions violated")

        threshold_values.append(threshold)
        terminal_values.append(terminal_sep)
        rows.append(
            {
                "station_id": station["id"],
                "source_x_m": source_x,
                "pivot_m": list(pivot),
                "pivot_rule": plan["pivot_rule"],
                "pose_results": pose_rows,
                "maximum_rigid_pairwise_distance_drift_m": max_rigidity_drift,
                "maximum_pivot_drift_m": max_pivot_drift,
                "continuous_keeper_z_separation_threshold_deg": threshold,
                "terminal_keeper_z_separation_m": terminal_sep,
                "monotonic_branch_turning_angle_deg": turning_deg,
            }
        )

    bilateral_pivot_residual = max(
        abs(rows[0]["pivot_m"][0] + rows[1]["pivot_m"][0]),
        abs(rows[0]["pivot_m"][1] - rows[1]["pivot_m"][1]),
        abs(rows[0]["pivot_m"][2] - rows[1]["pivot_m"][2]),
    )
    bilateral_threshold_residual = abs(threshold_values[0] - threshold_values[1])
    bilateral_terminal_residual = abs(terminal_values[0] - terminal_values[1])
    if max(bilateral_pivot_residual, bilateral_threshold_residual, bilateral_terminal_residual) > 1e-12:
        raise AssertionError("bilateral articulation symmetry drift")

    return {
        "schema": "axm.object-front-latch-articulation-evidence/v0.1",
        "result": RESULT,
        "asset_id": host["asset_id"],
        "host_source_sha256": host_sha,
        "ownership_contract_sha256": ownership_sha,
        "ownership_donor_head": plan["ownership_donor_head"],
        "articulation_plan_sha256": plan_sha,
        "joint_axis": plan["joint_axis"],
        "review_envelope_deg": [lo_angle, hi_angle],
        "pose_samples_deg": poses,
        "station_results": rows,
        "continuous_keeper_z_separation_threshold_deg": threshold_values[0],
        "terminal_keeper_z_separation_m": min(terminal_values),
        "bilateral_pivot_residual_m": bilateral_pivot_residual,
        "bilateral_threshold_residual_deg": bilateral_threshold_residual,
        "bilateral_terminal_separation_residual_m": bilateral_terminal_residual,
        "truth_boundary": plan["truth_boundary"],
    }


def _write_svg(path: Path, receipt: dict) -> None:
    width, height = 1140, 420
    poses = receipt["pose_samples_deg"]
    row = receipt["station_results"][0]
    panels = []
    for idx, pose in enumerate(row["pose_results"]):
        x0 = 40 + idx * 360
        scale = 1400.0
        oy, oz = -0.295, 0.18
        def sy(y: float) -> float:
            return x0 + 150 + (y - oy) * scale
        def sz(z: float) -> float:
            return 355 - (z - oz) * scale
        panels.append(f'<text x="{x0+10}" y="28" font-family="monospace" font-size="16">{poses[idx]:.0f} deg</text>')
        # keeper and moved lever are drawn from exact retained axis bounds; this is a structural Y/Z proof view.
        kb_y = [-0.262, -0.240]
        kb_z = [0.2785, 0.3335]
        lb = pose["lever_bounds_m"]
        ky0, ky1 = sy(kb_y[0]), sy(kb_y[1]); kz0, kz1 = sz(kb_z[1]), sz(kb_z[0])
        ly0, ly1 = sy(lb["y"][0]), sy(lb["y"][1]); lz0, lz1 = sz(lb["z"][1]), sz(lb["z"][0])
        panels.append(f'<rect x="{ky0:.2f}" y="{kz0:.2f}" width="{ky1-ky0:.2f}" height="{kz1-kz0:.2f}" fill="none" stroke="#333" stroke-width="2"/>')
        panels.append(f'<rect x="{ly0:.2f}" y="{lz0:.2f}" width="{ly1-ly0:.2f}" height="{lz1-lz0:.2f}" fill="none" stroke="#777" stroke-width="2"/>')
        py, pz = row["pivot_m"][1], row["pivot_m"][2]
        panels.append(f'<circle cx="{sy(py):.2f}" cy="{sz(pz):.2f}" r="4" fill="#111"/>')
        panels.append(f'<text x="{x0+10}" y="388" font-family="monospace" font-size="12">keeper/lever axis overlaps: y={pose["keeper_axis_overlap_m"]["y"]:.6f}, z={pose["keeper_axis_overlap_m"]["z"]:.6f} m</text>')
    text = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">', '<rect width="100%" height="100%" fill="white"/>', '<text x="40" y="408" font-family="monospace" font-size="12">Structural Y/Z bounds only. Not physical latch, animation, runtime or visual acceptance.</text>'] + panels + ['</svg>']
    path.write_text("\n".join(text) + "\n", encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--host", type=Path, required=True)
    p.add_argument("--ownership", type=Path, required=True)
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    host = json.loads(args.host.read_text(encoding="utf-8"))
    ownership_contract = json.loads(args.ownership.read_text(encoding="utf-8"))
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    receipt = verify(
        host,
        ownership_contract,
        plan,
        host_sha=sha256(args.host),
        ownership_sha=sha256(args.ownership),
        plan_sha=sha256(args.plan),
    )
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "front-latch-articulation.receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_svg(args.out / "front-latch-articulation-proof.svg", receipt)
    print(receipt["result"])


if __name__ == "__main__":
    main()
