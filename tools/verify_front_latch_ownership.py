from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import build_modular_case

SCHEMA = "axm.object-front-latch-ownership/v0.1"
RESULT = "PASS_EXPLICIT_FRONT_LATCH_COMPONENT_OWNERSHIP"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _aabb(component: dict) -> dict[str, tuple[float, float]]:
    if component.get("kind") != "box":
        raise AssertionError(f"component is not a box: {component.get('name')}")
    center = component["center_m"]
    size = component["size_m"]
    return {
        axis: (center[i] - size[i] / 2.0, center[i] + size[i] / 2.0)
        for i, axis in enumerate(("x", "y", "z"))
    }


def _overlap_1d(a: tuple[float, float], b: tuple[float, float]) -> float:
    return min(a[1], b[1]) - max(a[0], b[0])


def _overlap_xyz(a: dict, b: dict) -> dict[str, float]:
    return {axis: _overlap_1d(a[axis], b[axis]) for axis in ("x", "y", "z")}


def _component_map(result: dict) -> dict[str, dict]:
    return {c["name"]: c for c in result["components"]}


def verify(host: dict, contract: dict, *, host_sha: str, contract_sha: str) -> dict:
    if contract.get("schema") != SCHEMA:
        raise AssertionError(f"unsupported latch contract schema: {contract.get('schema')}")
    if contract.get("asset_id") != host.get("asset_id"):
        raise AssertionError("contract asset identity mismatch")
    if contract.get("host_source_sha256") != host_sha:
        raise AssertionError("host source identity mismatch")
    if contract.get("contract_id") != "front-latch-ownership-001":
        raise AssertionError("unexpected latch contract identity")

    built = build_modular_case.build(host)
    components = _component_map(built)
    source_xs = host.get("latches", {}).get("x_positions", [])
    stations = contract.get("stations", [])
    if len(source_xs) != 2 or len(stations) != 2:
        raise AssertionError("v0.1 requires exactly two source latch stations")

    required_owner_roles = {
        "lid_shell": "lid_shell",
        "front_service_panel": "service_panel",
    }
    for name, role in required_owner_roles.items():
        if name not in components or components[name].get("role") != role:
            raise AssertionError(f"required owner component missing or role drifted: {name}")

    closed = contract.get("closed_relation", {})
    max_face_gap = float(closed.get("keeper_lid_front_face_max_gap_m", -1.0))
    if max_face_gap < 0:
        raise AssertionError("invalid keeper/lid face-gap bound")
    if not closed.get("require_positive_keeper_lever_aabb_overlap"):
        raise AssertionError("keeper/lever positive-overlap requirement must remain enabled")
    if not closed.get("require_positive_lever_panel_aabb_overlap"):
        raise AssertionError("lever/panel positive-overlap requirement must remain enabled")

    station_results = []
    for expected_index, station in enumerate(stations):
        if station.get("source_index") != expected_index:
            raise AssertionError("latch station source-index drift")
        source_x = float(source_xs[expected_index])
        if abs(float(station.get("source_x_m")) - source_x) > 1e-12:
            raise AssertionError("latch station source_x mismatch")

        keeper_name = station.get("keeper_component")
        lever_name = station.get("lever_component")
        if keeper_name not in components or lever_name not in components:
            raise AssertionError("declared latch component is missing from exact source build")
        keeper = components[keeper_name]
        lever = components[lever_name]
        if keeper.get("role") != station.get("keeper_role") or keeper.get("role") != "latch_keeper":
            raise AssertionError("keeper role mismatch")
        if lever.get("role") != station.get("lever_role") or lever.get("role") != "latch_lever":
            raise AssertionError("lever role mismatch")
        if station.get("keeper_owner_component") != "lid_shell":
            raise AssertionError("keeper ownership drift: exact v0.1 keeper must remain lid-owned")
        if station.get("lever_owner_component") != "front_service_panel":
            raise AssertionError("lever ownership drift: exact v0.1 lever must remain service-panel-owned")
        if abs(float(keeper["center_m"][0]) - source_x) > 1e-12:
            raise AssertionError("keeper center no longer matches source latch station")
        if abs(float(lever["center_m"][0]) - source_x) > 1e-12:
            raise AssertionError("lever center no longer matches source latch station")

        keeper_box = _aabb(keeper)
        lever_box = _aabb(lever)
        lid_box = _aabb(components["lid_shell"])
        panel_box = _aabb(components["front_service_panel"])

        capture_overlap = _overlap_xyz(keeper_box, lever_box)
        if min(capture_overlap.values()) <= 0:
            raise AssertionError(f"closed keeper/lever proof volumes do not overlap: {station['id']}")

        lever_panel_overlap = _overlap_xyz(lever_box, panel_box)
        if min(lever_panel_overlap.values()) <= 0:
            raise AssertionError(f"lever no longer overlaps its service-panel owner: {station['id']}")

        keeper_lid_overlap = _overlap_xyz(keeper_box, lid_box)
        # The source keeper is mounted against the lid's negative-Y face: it has
        # positive X/Z overlap and exact face contact in Y rather than volume penetration.
        if keeper_lid_overlap["x"] <= 0 or keeper_lid_overlap["z"] <= 0:
            raise AssertionError(f"keeper no longer spans its lid-owner mounting region: {station['id']}")
        front_face_gap = abs(keeper_box["y"][1] - lid_box["y"][0])
        if front_face_gap > max_face_gap:
            raise AssertionError(f"keeper/lid front-face gap exceeds bound: {station['id']}")

        station_results.append(
            {
                "id": station["id"],
                "source_index": expected_index,
                "source_x_m": source_x,
                "keeper_component": keeper_name,
                "keeper_owner_component": "lid_shell",
                "lever_component": lever_name,
                "lever_owner_component": "front_service_panel",
                "closed_keeper_lever_overlap_m": capture_overlap,
                "lever_panel_overlap_m": lever_panel_overlap,
                "keeper_lid_overlap_m": keeper_lid_overlap,
                "keeper_lid_front_face_gap_m": front_face_gap,
                "state": "PASS_EXACT_STATIC_LATCH_OWNERSHIP_RELATION",
            }
        )

    bilateral_x_residual = abs(station_results[0]["source_x_m"] + station_results[1]["source_x_m"])
    if bilateral_x_residual > 1e-12:
        raise AssertionError("bilateral latch station symmetry drift")

    minimum_keeper_lever_overlap = min(
        value
        for row in station_results
        for value in row["closed_keeper_lever_overlap_m"].values()
    )
    minimum_lever_panel_overlap = min(
        value
        for row in station_results
        for value in row["lever_panel_overlap_m"].values()
    )
    maximum_keeper_lid_face_gap = max(row["keeper_lid_front_face_gap_m"] for row in station_results)

    return {
        "schema": "axm.object-front-latch-ownership-evidence/v0.1",
        "result": RESULT,
        "asset_id": host["asset_id"],
        "host_source_sha256": host_sha,
        "contract_source_sha256": contract_sha,
        "source_latch_x_positions_m": source_xs,
        "station_count": len(station_results),
        "bilateral_x_residual_m": bilateral_x_residual,
        "minimum_closed_keeper_lever_axis_overlap_m": minimum_keeper_lever_overlap,
        "minimum_lever_service_panel_axis_overlap_m": minimum_lever_panel_overlap,
        "maximum_keeper_lid_front_face_gap_m": maximum_keeper_lid_face_gap,
        "station_results": station_results,
        "scope": "exact source ownership + static closed proof-volume relationships only",
        "non_claims": [
            "latch pivot or articulated release path",
            "retention force or engineering load",
            "continuous/full-mesh collision clearance",
            "animation timing or controller behavior",
            "manufacturing tolerance or tool access",
            "gameplay or visual acceptance",
        ],
    }


def _write_svg(path: Path, host: dict, receipt: dict) -> None:
    # Small source-space evidence aid. It intentionally shows proof boxes, not a
    # production latch design or aesthetic acceptance surface.
    w = float(host["dimensions_m"]["width"])
    depth = float(host["dimensions_m"]["depth"])
    body_h = float(host["dimensions_m"]["body_height"])
    lid_h = float(host["dimensions_m"]["lid_height"])
    gap = float(host["dimensions_m"]["split_gap"])
    panel_d = float(host["front_panel"]["depth"])
    W, H = 1000, 440

    def fx(x: float) -> float:
        return 55 + (x + 0.5) * 700

    def fz(z: float) -> float:
        return 375 - z * 760

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        '<rect width="1000" height="440" fill="#ffffff"/>',
        '<text x="55" y="28" font-family="monospace" font-size="16">front-latch-ownership-001 — static source proof (not motion/retention acceptance)</text>',
    ]
    # Main body/lid in XZ front view.
    lines.append(f'<rect x="{fx(-w/2):.2f}" y="{fz(body_h):.2f}" width="{fx(w/2)-fx(-w/2):.2f}" height="{fz(0)-fz(body_h):.2f}" fill="none" stroke="#555"/>')
    lid_z0 = body_h + gap
    lines.append(f'<rect x="{fx(-w/2):.2f}" y="{fz(lid_z0+lid_h):.2f}" width="{fx(w/2)-fx(-w/2):.2f}" height="{fz(lid_z0)-fz(lid_z0+lid_h):.2f}" fill="none" stroke="#555"/>')
    # Front service panel height from the exact builder formula.
    panel_h = body_h * 0.52
    panel_z0 = body_h * 0.52 - panel_h / 2
    panel_z1 = body_h * 0.52 + panel_h / 2
    lines.append(f'<rect x="{fx(-w*0.30):.2f}" y="{fz(panel_z1):.2f}" width="{fx(w*0.30)-fx(-w*0.30):.2f}" height="{fz(panel_z0)-fz(panel_z1):.2f}" fill="none" stroke="#777" stroke-dasharray="5 4"/>')
    for row in receipt["station_results"]:
        x = float(row["source_x_m"])
        # Exact builder dimensions: keeper 0.08 x 0.055 front projection, lever 0.055 x 0.095.
        kx0, kx1 = x - 0.04, x + 0.04
        kz0, kz1 = body_h + gap*0.5 - 0.0275, body_h + gap*0.5 + 0.0275
        lx0, lx1 = x - 0.0275, x + 0.0275
        lz0, lz1 = body_h*0.86 - 0.0475, body_h*0.86 + 0.0475
        lines.append(f'<rect x="{fx(kx0):.2f}" y="{fz(kz1):.2f}" width="{fx(kx1)-fx(kx0):.2f}" height="{fz(kz0)-fz(kz1):.2f}" fill="none" stroke="#111" stroke-width="2"/>')
        lines.append(f'<rect x="{fx(lx0):.2f}" y="{fz(lz1):.2f}" width="{fx(lx1)-fx(lx0):.2f}" height="{fz(lz0)-fz(lz1):.2f}" fill="none" stroke="#777" stroke-width="2"/>')
        lines.append(f'<text x="{fx(x)-46:.2f}" y="410" font-family="monospace" font-size="12">{row["id"]}</text>')
    lines.append('<text x="55" y="428" font-family="monospace" font-size="11">dark = lid-owned keeper; grey = service-panel-owned lever; boxes overlap in exact closed source proof only</text>')
    lines.append('</svg>')
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    host = json.loads(args.host.read_text(encoding="utf-8"))
    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    receipt = verify(
        host,
        contract,
        host_sha=sha256(args.host),
        contract_sha=sha256(args.contract),
    )
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "front-latch-ownership.receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_svg(args.out / "front-latch-ownership-proof.svg", host, receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
