from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path

SCHEMA = "axm.object-hinge-pin-bore-clearance/v0.1"
RESULT = "PASS_HINGE_PIN_BORE_CLEARANCE_REVIEW_ENVELOPE"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _close(a: float, b: float, tol: float = 1e-12) -> bool:
    return abs(a - b) <= tol


def evaluate(host: dict, contract: dict, *, observed_host_sha256: str | None = None) -> dict:
    if contract.get("schema") != SCHEMA:
        raise AssertionError(f"unsupported contract schema: {contract.get('schema')}")
    if host.get("asset_id") != contract.get("asset_id"):
        raise AssertionError("asset identity drift")
    if observed_host_sha256 is not None and observed_host_sha256 != contract.get("host_source_sha256"):
        raise AssertionError("host source identity drift")

    hinge = host["hinge"]
    if hinge.get("axis") != contract.get("hinge_axis"):
        raise AssertionError("hinge axis drift")
    if len(hinge.get("knuckles", [])) != int(contract["expected_knuckle_count"]):
        raise AssertionError("knuckle count drift")
    if int(hinge.get("segments", -1)) != int(contract["expected_segments"]):
        raise AssertionError("hinge segmentation drift")

    pin_radius = float(hinge["pin_radius"])
    outer_radius = float(hinge["knuckle_radius"])
    bore_radius = float(contract["bore_radius_m"])
    min_clearance = float(contract["minimum_radial_clearance_m"])
    min_wall = float(contract["minimum_knuckle_wall_m"])

    if not _close(pin_radius, float(contract["pin_radius_m"])):
        raise AssertionError("pin radius drift")
    if pin_radius <= 0 or outer_radius <= 0 or bore_radius <= 0:
        raise AssertionError("non-positive radial dimension")

    radial_clearance = bore_radius - pin_radius
    wall_thickness = outer_radius - bore_radius
    if radial_clearance < min_clearance - 1e-12:
        raise AssertionError(f"insufficient bore-to-pin radial clearance: {radial_clearance}")
    if wall_thickness < min_wall - 1e-12:
        raise AssertionError(f"insufficient knuckle wall: {wall_thickness}")
    if bore_radius >= outer_radius:
        raise AssertionError("bore consumes knuckle outer shell")

    knuckles = sorted(hinge["knuckles"], key=lambda k: float(k["center_x"]))
    intervals = []
    for k in knuckles:
        c = float(k["center_x"])
        length = float(k["length"])
        if length <= 0:
            raise AssertionError("non-positive knuckle length")
        intervals.append({
            "id": k["id"],
            "owner": k["owner"],
            "x_min_m": c - length / 2.0,
            "x_max_m": c + length / 2.0,
            "length_m": length,
        })

    for a, b in zip(intervals, intervals[1:]):
        if b["x_min_m"] < a["x_max_m"] - 1e-12:
            raise AssertionError("knuckle axial overlap drift")

    pin_half = float(hinge["pin_length"]) / 2.0
    for row in intervals:
        if row["x_min_m"] < -pin_half - 1e-12 or row["x_max_m"] > pin_half + 1e-12:
            raise AssertionError("knuckle extends beyond source pin interval")

    total_knuckle_length = sum(row["length_m"] for row in intervals)
    source_solid_overlap_volume = math.pi * pin_radius * pin_radius * total_knuckle_length
    candidate_bore_void_volume = math.pi * bore_radius * bore_radius * total_knuckle_length
    candidate_pin_shell_overlap_volume = 0.0

    dimensions = host["dimensions_m"]
    hinge_center_y = float(dimensions["depth"]) / 2.0 + float(hinge["offset_y"])
    hinge_center_z = float(dimensions["body_height"]) + float(hinge["offset_z"])

    return {
        "schema": "axm.object-hinge-pin-bore-clearance-receipt/v0.1",
        "result": RESULT,
        "asset_id": host["asset_id"],
        "candidate_semantics": contract["candidate_semantics"],
        "host_source_sha256": contract["host_source_sha256"],
        "hinge_axis": list(hinge["axis"]),
        "hinge_line_origin_m": [0.0, hinge_center_y, hinge_center_z],
        "knuckle_count": len(intervals),
        "knuckle_intervals": intervals,
        "source_outer_radius_m": outer_radius,
        "source_pin_radius_m": pin_radius,
        "candidate_bore_radius_m": bore_radius,
        "radial_clearance_m": radial_clearance,
        "remaining_knuckle_wall_m": wall_thickness,
        "minimum_radial_clearance_m": min_clearance,
        "minimum_knuckle_wall_m": min_wall,
        "source_solid_pin_knuckle_overlap_volume_m3": source_solid_overlap_volume,
        "candidate_bore_void_volume_m3": candidate_bore_void_volume,
        "candidate_pin_shell_overlap_volume_m3": candidate_pin_shell_overlap_volume,
        "host_source_geometry_changed": False,
        "source_overlap_interpretation": "CURRENT_BUILDER_EMITS_SOLID_COAXIAL_KNUCKLE_AND_PIN_CYLINDERS; POSITIVE_VOLUME_OVERLAP IS A CONSTRUCTION OBSERVATION, NOT A RETROACTIVE FAILURE OF EARLIER NON_COLLISION STRUCTURAL CLAIMS",
        "truth_boundary": contract["truth_boundary"],
    }


def _proof_svg(receipt: dict) -> str:
    width = 720
    height = 460
    cx, cy = 245.0, 225.0
    scale = 7000.0
    outer = receipt["source_outer_radius_m"] * scale
    bore = receipt["candidate_bore_radius_m"] * scale
    pin = receipt["source_pin_radius_m"] * scale
    return "\n".join([
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="28" y="34" font-family="monospace" font-size="17">equipment-case hinge radial construction proof</text>',
        '<text x="28" y="58" font-family="monospace" font-size="12">cross-section normal to +X; review geometry only, not engineering tolerance</text>',
        f'<circle cx="{cx}" cy="{cy}" r="{outer:.3f}" fill="#d9dde2" stroke="#222" stroke-width="2"/>',
        f'<circle cx="{cx}" cy="{cy}" r="{bore:.3f}" fill="white" stroke="#2255aa" stroke-width="2"/>',
        f'<circle cx="{cx}" cy="{cy}" r="{pin:.3f}" fill="#666" stroke="#111" stroke-width="2"/>',
        f'<text x="390" y="150" font-family="monospace" font-size="13">outer knuckle radius = {receipt["source_outer_radius_m"]:.3f} m</text>',
        f'<text x="390" y="178" font-family="monospace" font-size="13">candidate bore radius = {receipt["candidate_bore_radius_m"]:.3f} m</text>',
        f'<text x="390" y="206" font-family="monospace" font-size="13">source pin radius = {receipt["source_pin_radius_m"]:.3f} m</text>',
        f'<text x="390" y="250" font-family="monospace" font-size="13">radial clearance = {receipt["radial_clearance_m"]:.3f} m</text>',
        f'<text x="390" y="278" font-family="monospace" font-size="13">remaining wall = {receipt["remaining_knuckle_wall_m"]:.3f} m</text>',
        '<text x="28" y="424" font-family="monospace" font-size="11">gray ring = derived annular knuckle candidate; dark center = unchanged source pin; blue = candidate bore boundary</text>',
        '</svg>',
        '',
    ])


def _negative_controls(host: dict, contract: dict, observed_sha: str) -> dict:
    controls: dict[str, str] = {}

    bad = copy.deepcopy(contract)
    bad["bore_radius_m"] = float(contract["pin_radius_m"])
    try:
        evaluate(host, bad, observed_host_sha256=observed_sha)
    except AssertionError as exc:
        controls["zero_radial_clearance"] = f"HOLD:{exc}"
    else:
        raise AssertionError("zero-clearance negative control unexpectedly passed")

    bad = copy.deepcopy(contract)
    bad["bore_radius_m"] = float(host["hinge"]["knuckle_radius"]) - float(contract["minimum_knuckle_wall_m"]) + 0.001
    try:
        evaluate(host, bad, observed_host_sha256=observed_sha)
    except AssertionError as exc:
        controls["consumed_knuckle_wall"] = f"HOLD:{exc}"
    else:
        raise AssertionError("wall-consumption negative control unexpectedly passed")

    bad = copy.deepcopy(contract)
    bad["hinge_axis"] = [0, 1, 0]
    try:
        evaluate(host, bad, observed_host_sha256=observed_sha)
    except AssertionError as exc:
        controls["axis_drift"] = f"HOLD:{exc}"
    else:
        raise AssertionError("axis-drift negative control unexpectedly passed")

    try:
        evaluate(host, contract, observed_host_sha256="0" * 64)
    except AssertionError as exc:
        controls["source_identity_drift"] = f"HOLD:{exc}"
    else:
        raise AssertionError("source-drift negative control unexpectedly passed")

    return controls


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--contract", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    host_path = Path(args.host)
    contract_path = Path(args.contract)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    host = json.loads(host_path.read_text(encoding="utf-8"))
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    observed_sha = _sha256(host_path)
    receipt = evaluate(host, contract, observed_host_sha256=observed_sha)
    receipt["negative_controls"] = _negative_controls(host, contract, observed_sha)
    receipt["contract_sha256"] = _sha256(contract_path)

    (out / "hinge-pin-bore-clearance.receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out / "hinge-pin-bore-clearance.proof.svg").write_text(_proof_svg(receipt), encoding="utf-8")
    print(RESULT)
    print(json.dumps({
        "radial_clearance_m": receipt["radial_clearance_m"],
        "remaining_knuckle_wall_m": receipt["remaining_knuckle_wall_m"],
        "source_solid_pin_knuckle_overlap_volume_m3": receipt["source_solid_pin_knuckle_overlap_volume_m3"],
        "candidate_pin_shell_overlap_volume_m3": receipt["candidate_pin_shell_overlap_volume_m3"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
