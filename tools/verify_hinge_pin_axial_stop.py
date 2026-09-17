from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

SCHEMA = "axm.object-hinge-pin-axial-stop/v0.1"
RESULT = "PASS_SOURCE_OWNED_HINGE_PIN_AXIAL_STOP_PROOF"
TOL = 1e-12


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _interval(center: float, length: float):
    return (center - length / 2.0, center + length / 2.0)


def _write_svg(path: Path, receipt):
    width, height = 1180, 260
    x_min, x_max = -0.38, 0.38

    def sx(x):
        return 60.0 + (x - x_min) / (x_max - x_min) * 1060.0

    y_pin = 125
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="1180" height="260" fill="#ffffff"/>',
        '<text x="35" y="28" font-family="monospace" font-size="17">hinge-pin-axial-stop-001 — source-space structural proof (not engineering acceptance)</text>',
        f'<line x1="{sx(receipt["pin_interval_m"][0]):.2f}" y1="{y_pin}" x2="{sx(receipt["pin_interval_m"][1]):.2f}" y2="{y_pin}" stroke="#222" stroke-width="8"/>',
    ]
    for row in receipt["outer_knuckles"]:
        x0, x1 = row["interval_m"]
        lines.append(f'<rect x="{sx(x0):.2f}" y="92" width="{sx(x1)-sx(x0):.2f}" height="66" fill="none" stroke="#1f5f99" stroke-width="2"/>')
    for row in receipt["stop_results"]:
        x0, x1 = row["interval_m"]
        lines.append(f'<rect x="{sx(x0):.2f}" y="78" width="{sx(x1)-sx(x0):.2f}" height="94" fill="none" stroke="#b00020" stroke-width="4"/>')
        lines.append(f'<text x="{sx((x0+x1)/2)-55:.2f}" y="195" font-family="monospace" font-size="12">{row["id"]}</text>')
    lines.append('<text x="35" y="230" font-family="monospace" font-size="12">blue=outer source knuckles; black=existing source pin; red=additive source-owned proof collars</text>')
    lines.append('</svg>')
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def verify(host, contract, *, host_sha, contract_sha):
    if contract.get("schema") != SCHEMA:
        raise AssertionError("unsupported axial-stop schema")
    if contract.get("host_source_sha256") != host_sha:
        raise AssertionError("host source identity mismatch")
    hinge = host.get("hinge", {})
    if list(hinge.get("axis", [])) != [1, 0, 0] or contract.get("joint_axis") != [1.0, 0.0, 0.0]:
        raise AssertionError("hinge axis drift")

    pin_radius = float(hinge["pin_radius"])
    pin_length = float(hinge["pin_length"])
    pin_interval = _interval(0.0, pin_length)
    knuckles = hinge.get("knuckles", [])
    if len(knuckles) < 2:
        raise AssertionError("insufficient source knuckles")
    intervals = sorted(
        [(float(k["center_x"]) - float(k["length"]) / 2.0, float(k["center_x"]) + float(k["length"]) / 2.0, k["id"]) for k in knuckles],
        key=lambda row: row[0],
    )
    outer_left = intervals[0]
    outer_right = intervals[-1]

    stops = contract.get("stops", [])
    if len(stops) != 2 or {s.get("side") for s in stops} != {"left", "right"}:
        raise AssertionError("v0.1 requires one left and one right stop")
    rows = []
    min_clearance = float("inf")
    min_overhang = float("inf")
    for stop in stops:
        center = float(stop["center_x_m"])
        thickness = float(stop["thickness_m"])
        radius = float(stop["radius_m"])
        if thickness <= 0.0 or radius <= 0.0:
            raise AssertionError("non-positive stop dimensions")
        interval = _interval(center, thickness)
        if interval[0] < pin_interval[0] - TOL or interval[1] > pin_interval[1] + TOL:
            raise AssertionError("stop leaves exact source pin envelope")
        if stop["side"] == "left":
            if abs(interval[0] - pin_interval[0]) > TOL:
                raise AssertionError("left stop must terminate at exact source pin end")
            clearance = outer_left[0] - interval[1]
        else:
            if abs(interval[1] - pin_interval[1]) > TOL:
                raise AssertionError("right stop must terminate at exact source pin end")
            clearance = interval[0] - outer_right[1]
        overhang = radius - pin_radius
        if overhang + TOL < float(contract["minimum_radial_overhang_m"]):
            raise AssertionError("radial overhang below declared minimum")
        if clearance + TOL < float(contract["minimum_outer_knuckle_clearance_m"]):
            raise AssertionError("outer knuckle clearance below declared minimum")
        min_clearance = min(min_clearance, clearance)
        min_overhang = min(min_overhang, overhang)
        rows.append({
            "id": stop["id"],
            "side": stop["side"],
            "center_x_m": center,
            "interval_m": [interval[0], interval[1]],
            "thickness_m": thickness,
            "radius_m": radius,
            "radial_overhang_m": overhang,
            "outer_knuckle_clearance_m": clearance,
        })

    left = next(r for r in rows if r["side"] == "left")
    right = next(r for r in rows if r["side"] == "right")
    symmetry = max(
        abs(left["center_x_m"] + right["center_x_m"]),
        abs(left["thickness_m"] - right["thickness_m"]),
        abs(left["radius_m"] - right["radius_m"]),
        abs(left["outer_knuckle_clearance_m"] - right["outer_knuckle_clearance_m"]),
    )
    if symmetry > TOL:
        raise AssertionError("bilateral stop symmetry drift")

    return {
        "schema": "axm.object-hinge-pin-axial-stop-evidence/v0.1",
        "result": RESULT,
        "host_source_sha256": host_sha,
        "axial_stop_contract_sha256": contract_sha,
        "host_source_geometry_changed": False,
        "overlay_component_count": 2,
        "joint_axis": [1.0, 0.0, 0.0],
        "pin_radius_m": pin_radius,
        "pin_interval_m": [pin_interval[0], pin_interval[1]],
        "outer_knuckles": [
            {"id": outer_left[2], "interval_m": [outer_left[0], outer_left[1]]},
            {"id": outer_right[2], "interval_m": [outer_right[0], outer_right[1]]},
        ],
        "minimum_observed_radial_overhang_m": min_overhang,
        "minimum_observed_outer_knuckle_clearance_m": min_clearance,
        "bilateral_symmetry_residual": symmetry,
        "stop_results": rows,
        "truth_boundary": contract.get("truth_boundary"),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    host = json.loads(args.host.read_text(encoding="utf-8"))
    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    receipt = verify(host, contract, host_sha=sha256(args.host), contract_sha=sha256(args.contract))
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "hinge-pin-axial-stop-evidence.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_svg(args.out / "hinge-pin-axial-stop-proof.svg", receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
