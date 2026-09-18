from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections import Counter
from pathlib import Path

SCHEMA = "axm.object-hinge-knuckle-owner-stack/v0.1"
RESULT = "PASS_SOURCE_OWNED_HINGE_KNUCKLE_OWNER_STACK"


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

    expected = contract["ordered_knuckles"]
    observed = sorted(hinge.get("knuckles", []), key=lambda row: float(row["center_x"]))
    if len(observed) != len(expected):
        raise AssertionError("hinge owner-stack count drift")

    observed_order = [{"id": row["id"], "owner": row["owner"]} for row in observed]
    if observed_order != expected:
        raise AssertionError(f"hinge owner-stack drift: {observed_order}")

    expected_length = float(contract["expected_knuckle_length_m"])
    expected_pitch = float(contract["expected_center_pitch_m"])
    expected_gap = float(contract["expected_inter_knuckle_gap_m"])
    source_min_clearance = float(hinge["min_axial_clearance"])
    declared_min_clearance = float(contract["minimum_source_axial_clearance_m"])
    if not _close(source_min_clearance, declared_min_clearance):
        raise AssertionError("source axial-clearance threshold drift")

    intervals = []
    for row in observed:
        center = float(row["center_x"])
        length = float(row["length"])
        if not _close(length, expected_length):
            raise AssertionError(f"knuckle length drift: {row['id']}")
        intervals.append({
            "id": row["id"],
            "owner": row["owner"],
            "center_x_m": center,
            "x_min_m": center - length / 2.0,
            "x_max_m": center + length / 2.0,
            "length_m": length,
        })

    pitches = []
    gaps = []
    for left, right in zip(intervals, intervals[1:]):
        pitch = right["center_x_m"] - left["center_x_m"]
        gap = right["x_min_m"] - left["x_max_m"]
        pitches.append(pitch)
        gaps.append(gap)
        if not _close(pitch, expected_pitch):
            raise AssertionError(f"knuckle center pitch drift: {left['id']}->{right['id']}: {pitch}")
        if not _close(gap, expected_gap):
            raise AssertionError(f"inter-knuckle gap drift: {left['id']}->{right['id']}: {gap}")
        if gap < source_min_clearance - 1e-12:
            raise AssertionError(f"source axial clearance violated: {left['id']}->{right['id']}: {gap}")
        if left["owner"] == right["owner"]:
            raise AssertionError(f"adjacent hinge owners do not alternate: {left['id']}->{right['id']}")

    owner_counts = Counter(row["owner"] for row in intervals)
    if dict(owner_counts) != contract["expected_owner_counts"]:
        raise AssertionError(f"hinge owner counts drift: {dict(owner_counts)}")

    terminal_owner = contract["terminal_owner"]
    if intervals[0]["owner"] != terminal_owner or intervals[-1]["owner"] != terminal_owner:
        raise AssertionError("hinge terminal-owner drift")

    required_bracket_owner = contract["required_lid_bracketing_owner"]
    bracket_rows = []
    for idx, row in enumerate(intervals):
        if row["owner"] != "lid":
            continue
        if idx == 0 or idx == len(intervals) - 1:
            raise AssertionError(f"lid knuckle is terminal instead of bracketed: {row['id']}")
        left = intervals[idx - 1]
        right = intervals[idx + 1]
        if left["owner"] != required_bracket_owner or right["owner"] != required_bracket_owner:
            raise AssertionError(f"lid knuckle owner bracketing drift: {row['id']}")
        bracket_rows.append({
            "lid_id": row["id"],
            "left_neighbor_id": left["id"],
            "right_neighbor_id": right["id"],
            "left_neighbor_owner": left["owner"],
            "right_neighbor_owner": right["owner"],
        })

    symmetry_residuals = [
        abs(intervals[0]["center_x_m"] + intervals[-1]["center_x_m"]),
        abs(intervals[1]["center_x_m"] + intervals[-2]["center_x_m"]),
        abs(intervals[2]["center_x_m"]),
        abs(intervals[0]["x_min_m"] + intervals[-1]["x_max_m"]),
        abs(intervals[0]["x_max_m"] + intervals[-1]["x_min_m"]),
        abs(intervals[1]["x_min_m"] + intervals[-2]["x_max_m"]),
        abs(intervals[1]["x_max_m"] + intervals[-2]["x_min_m"]),
    ]
    max_symmetry_residual = max(symmetry_residuals)
    if max_symmetry_residual > 1e-12:
        raise AssertionError(f"hinge owner-stack bilateral symmetry drift: {max_symmetry_residual}")

    authority = contract["authority"]
    required_false = (
        "source_geometry_changed",
        "rig_parenting_authorized",
        "animation_authorized",
        "physical_retention_claimed",
        "load_capacity_claimed",
        "manufacturing_fit_claimed",
    )
    promoted = [key for key in required_false if authority.get(key) is not False]
    if promoted:
        raise AssertionError(f"authority expansion forbidden: {promoted}")

    minimum_gap = min(gaps)
    minimum_pitch = min(pitches)
    axial_clearance_surplus = minimum_gap - source_min_clearance

    return {
        "schema": "axm.object-hinge-knuckle-owner-stack-receipt/v0.1",
        "result": RESULT,
        "asset_id": host["asset_id"],
        "host_source_sha256": contract["host_source_sha256"],
        "hinge_axis": list(hinge["axis"]),
        "ordered_knuckles": intervals,
        "owner_sequence": [row["owner"] for row in intervals],
        "owner_counts": dict(owner_counts),
        "adjacent_center_pitches_m": pitches,
        "adjacent_gaps_m": gaps,
        "minimum_center_pitch_m": minimum_pitch,
        "minimum_inter_knuckle_gap_m": minimum_gap,
        "source_minimum_axial_clearance_m": source_min_clearance,
        "axial_clearance_surplus_m": axial_clearance_surplus,
        "lid_bracketing": bracket_rows,
        "maximum_stack_symmetry_residual_m": max_symmetry_residual,
        "source_geometry_changed": False,
        "rig_parenting_authorized": False,
        "physical_retention_claimed": False,
        "load_capacity_claimed": False,
        "manufacturing_fit_claimed": False,
        "truth_boundary": contract["truth_boundary"],
    }


def _proof_svg(receipt: dict) -> str:
    width = 980
    height = 300
    x0 = 90.0
    scale = 1050.0
    y = 125.0
    h = 70.0
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="35" y="34" font-family="monospace" font-size="17">equipment-case hinge axial owner-stack proof</text>',
        '<text x="35" y="58" font-family="monospace" font-size="12">+X left to right; ownership/order semantics only, not load or retention evidence</text>',
    ]
    for row in receipt["ordered_knuckles"]:
        rx = x0 + (row["x_min_m"] + 0.36) * scale
        rw = row["length_m"] * scale
        fill = "#d9dde2" if row["owner"] == "body" else "#e8edf7"
        lines.append(f'<rect x="{rx:.3f}" y="{y:.3f}" width="{rw:.3f}" height="{h:.3f}" fill="{fill}" stroke="#222" stroke-width="2"/>')
        lines.append(f'<text x="{rx + rw/2:.3f}" y="{y + 30:.3f}" text-anchor="middle" font-family="monospace" font-size="14">{row["id"]}</text>')
        lines.append(f'<text x="{rx + rw/2:.3f}" y="{y + 50:.3f}" text-anchor="middle" font-family="monospace" font-size="11">{row["owner"]}</text>')
    lines.extend([
        f'<text x="35" y="235" font-family="monospace" font-size="12">owner sequence: {" / ".join(receipt["owner_sequence"])}</text>',
        f'<text x="35" y="257" font-family="monospace" font-size="12">adjacent gaps: {", ".join(f"{v:.3f} m" for v in receipt["adjacent_gaps_m"])}</text>',
        f'<text x="35" y="279" font-family="monospace" font-size="12">source minimum gap {receipt["source_minimum_axial_clearance_m"]:.3f} m; observed surplus {receipt["axial_clearance_surplus_m"]:.3f} m</text>',
        '</svg>',
        '',
    ])
    return "\n".join(lines)


def _negative_controls(host: dict, contract: dict, observed_sha: str) -> dict:
    controls: dict[str, str] = {}

    bad_host = copy.deepcopy(host)
    bad_host["hinge"]["knuckles"][1]["owner"] = "body"
    try:
        evaluate(bad_host, contract, observed_host_sha256=observed_sha)
    except AssertionError as exc:
        controls["owner_label_drift_without_geometry_change"] = f"HOLD:{exc}"
    else:
        raise AssertionError("owner-label negative control unexpectedly passed")

    bad_host = copy.deepcopy(host)
    bad_host["hinge"]["knuckles"][1]["center_x"] = -0.139
    try:
        evaluate(bad_host, contract, observed_host_sha256=observed_sha)
    except AssertionError as exc:
        controls["axial_pitch_drift"] = f"HOLD:{exc}"
    else:
        raise AssertionError("axial-pitch negative control unexpectedly passed")

    bad_contract = copy.deepcopy(contract)
    bad_contract["authority"]["rig_parenting_authorized"] = True
    try:
        evaluate(host, bad_contract, observed_host_sha256=observed_sha)
    except AssertionError as exc:
        controls["authority_expansion"] = f"HOLD:{exc}"
    else:
        raise AssertionError("authority-expansion negative control unexpectedly passed")

    try:
        evaluate(host, contract, observed_host_sha256="0" * 64)
    except AssertionError as exc:
        controls["source_identity_drift"] = f"HOLD:{exc}"
    else:
        raise AssertionError("source-identity negative control unexpectedly passed")

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

    (out / "hinge-knuckle-owner-stack.receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out / "hinge-knuckle-owner-stack.proof.svg").write_text(_proof_svg(receipt), encoding="utf-8")
    print(RESULT)
    print(json.dumps({
        "owner_sequence": receipt["owner_sequence"],
        "minimum_inter_knuckle_gap_m": receipt["minimum_inter_knuckle_gap_m"],
        "axial_clearance_surplus_m": receipt["axial_clearance_surplus_m"],
        "maximum_stack_symmetry_residual_m": receipt["maximum_stack_symmetry_residual_m"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
