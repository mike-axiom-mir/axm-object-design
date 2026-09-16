from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from build_modular_case import build

SCHEMA = "axm.object-front-latch-pivot-interface/v0.1"
RESULT = "PASS_SOURCE_OWNED_FRONT_LATCH_PIVOT_INTERFACE"
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


def _positive_overlap(a, b):
    return tuple(min(a[i][1], b[i][1]) - max(a[i][0], b[i][0]) for i in range(3))


def _rotated_lever_yz_bounds(component, pivot, angle_deg):
    bounds = _bounds(component)
    angle = math.radians(angle_deg)
    ca, sa = math.cos(angle), math.sin(angle)
    points = []
    for y in bounds[1]:
        for z in bounds[2]:
            dy = y - pivot[1]
            dz = z - pivot[2]
            points.append((
                pivot[1] + dy * ca - dz * sa,
                pivot[2] + dy * sa + dz * ca,
            ))
    ys = [p[0] for p in points]
    zs = [p[1] for p in points]
    return (min(ys), max(ys)), (min(zs), max(zs))


def _separation_z(lever, keeper, pivot, angle_deg):
    _, lever_z = _rotated_lever_yz_bounds(lever, pivot, angle_deg)
    keeper_z = _bounds(keeper)[2]
    return keeper_z[0] - lever_z[1]


def _threshold_deg(lever, keeper, pivot, hi_deg):
    # The exact reviewed family is still engaged at 25 degrees and separated by 50.
    # We fail closed if that bracket no longer exists rather than guessing another branch.
    lo = hi_deg / 2.0
    if _separation_z(lever, keeper, pivot, lo) >= 0.0:
        raise AssertionError("release threshold bracket drift: midpoint already separated")
    if _separation_z(lever, keeper, pivot, hi_deg) <= 0.0:
        raise AssertionError("release threshold bracket drift: endpoint not separated")
    for _ in range(100):
        mid = (lo + hi_deg) / 2.0
        if _separation_z(lever, keeper, pivot, mid) >= 0.0:
            hi_deg = mid
        else:
            lo = mid
    return hi_deg


def _write_svg(path: Path, station_rows):
    width, height = 1180, 420
    y_min, y_max = -0.36, -0.20
    z_min, z_max = 0.18, 0.35

    def map_yz(y, z, ox):
        px = ox + (y - y_min) / (y_max - y_min) * 430.0
        py = 350.0 - (z - z_min) / (z_max - z_min) * 300.0
        return px, py

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="1180" height="420" fill="#ffffff"/>',
        '<text x="35" y="28" font-family="monospace" font-size="17">front-latch-pivot-interface-001 — structural Y/Z proof (not physical latch acceptance)</text>',
    ]
    for idx, row in enumerate(station_rows):
        ox = 40 + idx * 570
        lines.append(f'<text x="{ox}" y="55" font-family="monospace" font-size="14">{row["station_id"]}: closed 0° + review release 50°</text>')
        for label, box, stroke, dash in (
            ("panel", row["panel_bounds"], "#555555", ""),
            ("keeper", row["keeper_bounds"], "#1f5f99", ""),
            ("lever_closed", row["lever_bounds_closed"], "#9a4b00", ""),
            ("lever_50", row["lever_bounds_50_yz"], "#b00020", "6,4"),
        ):
            if label == "lever_50":
                yb, zb = box
            else:
                yb, zb = box[1], box[2]
            x0, y1 = map_yz(yb[0], zb[1], ox)
            x1, y0 = map_yz(yb[1], zb[0], ox)
            dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
            lines.append(f'<rect x="{x0:.2f}" y="{y1:.2f}" width="{x1-x0:.2f}" height="{y0-y1:.2f}" fill="none" stroke="{stroke}" stroke-width="2"{dash_attr}/>')
        px, py = map_yz(row["pivot_origin_m"][1], row["pivot_origin_m"][2], ox)
        lines.append(f'<circle cx="{px:.2f}" cy="{py:.2f}" r="5" fill="#111111"/>')
        lines.append(f'<text x="{ox}" y="386" font-family="monospace" font-size="12">pivot {row["pivot_origin_m"]}; threshold {row["release_threshold_deg"]:.9f}°; 50° sep {row["terminal_keeper_z_separation_m"]:.9f} m</text>')
    lines.append('<text x="35" y="410" font-family="monospace" font-size="11">blue=keeper, orange=closed lever, red dashed=50° rotated lever AABB, black=pivot origin; proof volumes only</text>')
    lines.append('</svg>')
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def verify(host, ownership, interface, rigging_plan, *, host_sha, ownership_sha, interface_sha, rigging_plan_sha):
    if interface.get("schema") != SCHEMA:
        raise AssertionError("unsupported pivot interface schema")
    if interface.get("host_source_sha256") != host_sha:
        raise AssertionError("host source identity mismatch")
    oc = interface.get("ownership_contract", {})
    if oc.get("sha256") != ownership_sha:
        raise AssertionError("ownership contract identity mismatch")
    if ownership.get("host_source_sha256") != host_sha:
        raise AssertionError("ownership host identity mismatch")
    donor = interface.get("review_observation_donor", {})
    if donor.get("plan_sha256") != rigging_plan_sha:
        raise AssertionError("Rigging donor plan identity mismatch")
    if rigging_plan.get("host_source_sha256") != host_sha:
        raise AssertionError("Rigging donor host identity mismatch")
    if rigging_plan.get("ownership_donor_head") != oc.get("donor_head"):
        raise AssertionError("Rigging donor ownership-head mismatch")
    if rigging_plan.get("pivot_rule") != interface.get("pivot_rule"):
        raise AssertionError("pivot rule drift from reviewed donor")
    if rigging_plan.get("joint_axis") != interface.get("joint_axis"):
        raise AssertionError("joint axis drift from reviewed donor")

    axis = interface.get("joint_axis")
    if axis != [1.0, 0.0, 0.0]:
        raise AssertionError("v0.1 source pivot axis must remain exact +X")
    travel = interface.get("travel_envelope_deg", {})
    if travel.get("closed") != rigging_plan.get("review_angle_min_deg"):
        raise AssertionError("closed angle drift from reviewed donor")
    if travel.get("review_release") != rigging_plan.get("review_angle_max_deg"):
        raise AssertionError("release angle drift from reviewed donor")
    if travel.get("minimum_release_separation_m", 0.0) <= 0.0:
        raise AssertionError("minimum release separation must remain positive")

    result = build(host)
    components = {row["name"]: row for row in result["components"]}
    panel = components.get("front_service_panel")
    if panel is None:
        raise AssertionError("front_service_panel missing")
    panel_bounds = _bounds(panel)
    source_xs = host.get("latches", {}).get("x_positions", [])
    stations = interface.get("stations", [])
    owner_rows = ownership.get("stations", [])
    if len(stations) != 2 or len(owner_rows) != 2 or list(source_xs) != [-0.22, 0.22]:
        raise AssertionError("v0.1 exact bilateral station family drift")

    station_rows = []
    thresholds = []
    terminal_separations = []
    pivot_rule_residuals = []
    for idx, station in enumerate(stations):
        owner = owner_rows[idx]
        source_x = float(source_xs[idx])
        if abs(float(station.get("source_x_m")) - source_x) > TOL:
            raise AssertionError("source_x mismatch")
        for key in ("lever_component", "keeper_component", "lever_owner_component", "keeper_owner_component"):
            if station.get(key) != owner.get(key):
                raise AssertionError(f"ownership/component drift: {key}")
        lever = components.get(station["lever_component"])
        keeper = components.get(station["keeper_component"])
        if lever is None or keeper is None:
            raise AssertionError("declared latch component missing")
        lever_bounds = _bounds(lever)
        keeper_bounds = _bounds(keeper)
        derived_pivot = [source_x, panel_bounds[1][0], lever_bounds[2][0]]
        declared_pivot = [float(v) for v in station.get("pivot_origin_m", [])]
        if len(declared_pivot) != 3:
            raise AssertionError("pivot origin missing")
        residual = max(abs(a - b) for a, b in zip(derived_pivot, declared_pivot))
        pivot_rule_residuals.append(residual)
        if residual > TOL:
            raise AssertionError("pivot origin drift from source rule")
        # The reviewed pivot must stay on/in both exact source proof volumes at the closed state.
        for axis_i in (1, 2):
            if not (lever_bounds[axis_i][0] - TOL <= declared_pivot[axis_i] <= lever_bounds[axis_i][1] + TOL):
                raise AssertionError("pivot left lever proof volume")
            if not (panel_bounds[axis_i][0] - TOL <= declared_pivot[axis_i] <= panel_bounds[axis_i][1] + TOL):
                raise AssertionError("pivot left service-panel proof volume")
        closed_overlap = _positive_overlap(keeper_bounds, lever_bounds)
        if min(closed_overlap) <= 0.0:
            raise AssertionError("closed keeper/lever overlap lost")
        release_angle = float(travel["review_release"])
        terminal_sep = _separation_z(lever, keeper, declared_pivot, release_angle)
        if terminal_sep + TOL < float(travel["minimum_release_separation_m"]):
            raise AssertionError("review release separation below source-owned minimum")
        threshold = _threshold_deg(lever, keeper, declared_pivot, release_angle)
        thresholds.append(threshold)
        terminal_separations.append(terminal_sep)
        yz50 = _rotated_lever_yz_bounds(lever, declared_pivot, release_angle)
        station_rows.append({
            "station_id": station["id"],
            "source_x_m": source_x,
            "pivot_origin_m": declared_pivot,
            "panel_bounds": panel_bounds,
            "keeper_bounds": keeper_bounds,
            "lever_bounds_closed": lever_bounds,
            "lever_bounds_50_yz": yz50,
            "closed_keeper_lever_overlap_m": {"x": closed_overlap[0], "y": closed_overlap[1], "z": closed_overlap[2]},
            "release_threshold_deg": threshold,
            "terminal_keeper_z_separation_m": terminal_sep,
        })

    bilateral_pivot_residual = max(abs(stations[0]["pivot_origin_m"][0] + stations[1]["pivot_origin_m"][0]), abs(stations[0]["pivot_origin_m"][1] - stations[1]["pivot_origin_m"][1]), abs(stations[0]["pivot_origin_m"][2] - stations[1]["pivot_origin_m"][2]))
    threshold_residual = abs(thresholds[0] - thresholds[1])
    terminal_residual = abs(terminal_separations[0] - terminal_separations[1])
    if bilateral_pivot_residual > TOL or threshold_residual > TOL or terminal_residual > TOL:
        raise AssertionError("bilateral pivot/release symmetry drift")

    return {
        "schema": "axm.object-front-latch-pivot-interface-evidence/v0.1",
        "result": RESULT,
        "host_source_sha256": host_sha,
        "ownership_contract_sha256": ownership_sha,
        "pivot_interface_sha256": interface_sha,
        "rigging_observation_plan_sha256": rigging_plan_sha,
        "rigging_observation_head": donor.get("head"),
        "station_count": len(station_rows),
        "joint_axis": axis,
        "pivot_rule": interface["pivot_rule"],
        "review_release_deg": travel["review_release"],
        "minimum_release_separation_m": travel["minimum_release_separation_m"],
        "maximum_pivot_rule_residual_m": max(pivot_rule_residuals),
        "bilateral_pivot_residual_m": bilateral_pivot_residual,
        "bilateral_release_threshold_residual_deg": threshold_residual,
        "bilateral_terminal_separation_residual_m": terminal_residual,
        "release_threshold_deg": thresholds[0],
        "terminal_keeper_z_separation_m": min(terminal_separations),
        "host_geometry_changed": False,
        "station_results": station_rows,
        "truth_boundary": interface.get("truth_boundary"),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=Path, required=True)
    parser.add_argument("--ownership", type=Path, required=True)
    parser.add_argument("--interface", type=Path, required=True)
    parser.add_argument("--rigging-plan", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    host = json.loads(args.host.read_text(encoding="utf-8"))
    ownership = json.loads(args.ownership.read_text(encoding="utf-8"))
    interface = json.loads(args.interface.read_text(encoding="utf-8"))
    rigging_plan = json.loads(args.rigging_plan.read_text(encoding="utf-8"))
    receipt = verify(
        host,
        ownership,
        interface,
        rigging_plan,
        host_sha=sha256(args.host),
        ownership_sha=sha256(args.ownership),
        interface_sha=sha256(args.interface),
        rigging_plan_sha=sha256(args.rigging_plan),
    )
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "front-latch-pivot-interface-evidence.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_svg(args.out / "front-latch-pivot-interface-proof.svg", receipt["station_results"])
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
