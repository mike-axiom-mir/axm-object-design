from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import build_modular_case

SCHEMA = "axm.object-front-latch-keeper-seat/v0.1"
OWNERSHIP_SCHEMA = "axm.object-front-latch-ownership/v0.1"
RESULT = "PASS_SOURCE_OWNED_FRONT_LATCH_KEEPER_ATTACHMENT_SEATS"
TOL = 1e-12


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
        axis: (float(center[i]) - float(size[i]) / 2.0, float(center[i]) + float(size[i]) / 2.0)
        for i, axis in enumerate(("x", "y", "z"))
    }


def _assert_close(actual: float, expected: float, label: str) -> None:
    if abs(float(actual) - float(expected)) > TOL:
        raise AssertionError(f"{label} drift: {actual} != {expected}")


def _assert_vec(actual, expected, label: str) -> None:
    if len(actual) != len(expected):
        raise AssertionError(f"{label} length drift")
    for i, (a, e) in enumerate(zip(actual, expected)):
        _assert_close(float(a), float(e), f"{label}[{i}]")


def _component_map(result: dict) -> dict[str, dict]:
    return {c["name"]: c for c in result["components"]}


def verify(
    host: dict,
    ownership: dict,
    contract: dict,
    *,
    host_sha: str,
    ownership_sha: str,
    contract_sha: str,
) -> dict:
    if contract.get("schema") != SCHEMA:
        raise AssertionError(f"unsupported keeper-seat schema: {contract.get('schema')}")
    if ownership.get("schema") != OWNERSHIP_SCHEMA:
        raise AssertionError("unsupported ownership schema")
    if contract.get("asset_id") != host.get("asset_id") or ownership.get("asset_id") != host.get("asset_id"):
        raise AssertionError("asset identity mismatch")
    if contract.get("contract_id") != "front-latch-keeper-seat-001":
        raise AssertionError("unexpected keeper-seat contract identity")
    if contract.get("host_source_sha256") != host_sha:
        raise AssertionError("host source identity mismatch")
    if contract.get("ownership_contract_sha256") != ownership_sha:
        raise AssertionError("ownership contract identity mismatch")
    if ownership.get("host_source_sha256") != host_sha:
        raise AssertionError("ownership contract host identity mismatch")

    policy = contract.get("contact_policy", {})
    if not policy.get("require_exact_face_contact"):
        raise AssertionError("exact face-contact requirement must remain enabled")
    if not policy.get("require_zero_owner_volume_penetration"):
        raise AssertionError("zero owner-volume penetration requirement must remain enabled")
    if not policy.get("require_positive_planar_overlap"):
        raise AssertionError("positive planar-overlap requirement must remain enabled")

    authority = contract.get("authority", {})
    forbidden_true = [
        "physical_fastener_or_weld_defined",
        "retention_force_defined",
        "manufacturing_tolerance_defined",
        "rig_motion_defined",
        "animation_timing_defined",
        "runtime_parenting_adopted",
    ]
    for key in forbidden_true:
        if authority.get(key) is not False:
            raise AssertionError(f"authority expansion forbidden: {key}")

    built = build_modular_case.build(host)
    components = _component_map(built)
    lid = components.get("lid_shell")
    if not lid or lid.get("role") != "lid_shell":
        raise AssertionError("exact lid owner missing")
    lid_box = _aabb(lid)

    ownership_by_id = {s["id"]: s for s in ownership.get("stations", [])}
    stations = contract.get("stations", [])
    source_xs = host.get("latches", {}).get("x_positions", [])
    if len(stations) != 2 or len(source_xs) != 2:
        raise AssertionError("v0.1 requires exactly two bilateral keeper seats")

    rows = []
    for expected_index, station in enumerate(stations):
        sid = station.get("id")
        if station.get("source_index") != expected_index:
            raise AssertionError("seat source-index drift")
        if sid not in ownership_by_id:
            raise AssertionError(f"missing ownership station: {sid}")
        owner_row = ownership_by_id[sid]
        keeper_name = station.get("keeper_component")
        if keeper_name != owner_row.get("keeper_component"):
            raise AssertionError("keeper identity drift from ownership contract")
        if station.get("owner_component") != "lid_shell" or owner_row.get("keeper_owner_component") != "lid_shell":
            raise AssertionError("keeper owner drift")
        if station.get("owner_face") != "negative_y_face" or station.get("keeper_face") != "positive_y_face":
            raise AssertionError("keeper-seat face identity drift")
        if station.get("plane_axis") != "y":
            raise AssertionError("keeper-seat plane-axis drift")
        _assert_vec(station.get("owner_outward_normal", []), [0.0, -1.0, 0.0], "owner outward normal")
        _assert_vec(station.get("primary_axis", []), [1.0, 0.0, 0.0], "primary axis")
        _assert_vec(station.get("secondary_axis", []), [0.0, 0.0, 1.0], "secondary axis")

        keeper = components.get(keeper_name)
        if not keeper or keeper.get("role") != "latch_keeper":
            raise AssertionError(f"exact keeper component missing: {keeper_name}")
        source_x = float(source_xs[expected_index])
        _assert_close(float(keeper["center_m"][0]), source_x, "keeper source X")
        _assert_close(float(owner_row.get("source_x_m")), source_x, "ownership source X")

        keeper_box = _aabb(keeper)
        plane = lid_box["y"][0]
        _assert_close(keeper_box["y"][1], plane, "keeper +Y to lid -Y face contact")
        _assert_close(float(station.get("plane_coordinate_m")), plane, "declared seat plane")

        volume_overlap_y = min(keeper_box["y"][1], lid_box["y"][1]) - max(keeper_box["y"][0], lid_box["y"][0])
        _assert_close(volume_overlap_y, 0.0, "keeper/lid Y volume penetration")

        primary_bounds = [max(keeper_box["x"][0], lid_box["x"][0]), min(keeper_box["x"][1], lid_box["x"][1])]
        secondary_bounds = [max(keeper_box["z"][0], lid_box["z"][0]), min(keeper_box["z"][1], lid_box["z"][1])]
        width = primary_bounds[1] - primary_bounds[0]
        height = secondary_bounds[1] - secondary_bounds[0]
        if width <= 0.0 or height <= 0.0:
            raise AssertionError(f"keeper/lid planar seat overlap lost: {sid}")
        area = width * height
        center = [
            (primary_bounds[0] + primary_bounds[1]) / 2.0,
            plane,
            (secondary_bounds[0] + secondary_bounds[1]) / 2.0,
        ]

        _assert_vec(station.get("primary_bounds_m", []), primary_bounds, "primary bounds")
        _assert_vec(station.get("secondary_bounds_m", []), secondary_bounds, "secondary bounds")
        _assert_vec(station.get("dimensions_m", []), [width, height], "seat dimensions")
        _assert_close(float(station.get("area_m2")), area, "seat area")
        _assert_vec(station.get("center_m", []), center, "seat center")

        rows.append(
            {
                "id": sid,
                "source_index": expected_index,
                "source_x_m": source_x,
                "keeper_component": keeper_name,
                "owner_component": "lid_shell",
                "plane_coordinate_m": plane,
                "primary_bounds_m": primary_bounds,
                "secondary_bounds_m": secondary_bounds,
                "dimensions_m": [width, height],
                "area_m2": area,
                "center_m": center,
                "owner_volume_penetration_m": volume_overlap_y,
            }
        )

    left, right = rows
    bilateral_x_center_residual = abs(left["center_m"][0] + right["center_m"][0])
    bilateral_plane_residual = abs(left["plane_coordinate_m"] - right["plane_coordinate_m"])
    bilateral_z_center_residual = abs(left["center_m"][2] - right["center_m"][2])
    bilateral_area_residual = abs(left["area_m2"] - right["area_m2"])
    if max(bilateral_x_center_residual, bilateral_plane_residual, bilateral_z_center_residual, bilateral_area_residual) > TOL:
        raise AssertionError("bilateral keeper-seat symmetry drift")

    return {
        "schema": "axm.object-front-latch-keeper-seat-receipt/v0.1",
        "result": RESULT,
        "asset_id": host["asset_id"],
        "contract_id": contract["contract_id"],
        "host_source_sha256": host_sha,
        "ownership_contract_sha256": ownership_sha,
        "keeper_seat_contract_sha256": contract_sha,
        "station_count": len(rows),
        "station_results": rows,
        "minimum_seat_area_m2": min(r["area_m2"] for r in rows),
        "maximum_owner_volume_penetration_m": max(abs(r["owner_volume_penetration_m"]) for r in rows),
        "bilateral_x_center_residual_m": bilateral_x_center_residual,
        "bilateral_plane_residual_m": bilateral_plane_residual,
        "bilateral_z_center_residual_m": bilateral_z_center_residual,
        "bilateral_area_residual_m2": bilateral_area_residual,
        "physical_fastener_or_weld_proven": False,
        "retention_force_proven": False,
        "manufacturing_tolerance_proven": False,
        "rig_motion_proven": False,
        "animation_timing_proven": False,
        "runtime_parenting_adopted": False,
        "source_geometry_changed": False,
        "truth_boundary": contract.get("truth_boundary"),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", type=Path, required=True)
    ap.add_argument("--ownership", type=Path, required=True)
    ap.add_argument("--contract", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    host = json.loads(args.host.read_text(encoding="utf-8"))
    ownership = json.loads(args.ownership.read_text(encoding="utf-8"))
    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    receipt = verify(
        host,
        ownership,
        contract,
        host_sha=sha256(args.host),
        ownership_sha=sha256(args.ownership),
        contract_sha=sha256(args.contract),
    )
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(RESULT)


if __name__ == "__main__":
    main()
