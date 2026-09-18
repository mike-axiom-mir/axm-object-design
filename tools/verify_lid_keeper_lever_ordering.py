from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_modular_case
import verify_lid_keeper_socket_binding as keeper_socket

SCHEMA = "axm.object-keeper-lever-authored-pose-ordering/v0.1"
RESULT = "PASS_SOURCE_OWNED_KEEPER_LEVER_ORDERING_101_AUTHORED_POSES__HOLD_CONTINUOUS_COLLISION"
SOURCE_SHA256 = "49b1f9ed9865893d6de6f1ec8f069576732df694853fde4e3fcff366de32644a"
OWNERSHIP_HEAD = "d3fa10a270faae7925811f44f03381fe5c5d0215"
SOURCE_INTERFACE_HEAD = "6086f39a3da344c57a68653f90d040e03e04cec2"
SOURCE_RIG_HEAD = "a1acd2bcb2074f41e536562f2673508e2cb0a4d5"
LID_RIG_HEAD = "4b72c9918c5fc1e89bd18a0be24fb4afac6e7775"
PREVIOUS_RIGGING_HEAD = "9556308c9986f71519bc488badc1b1a63e855e7e"
ANIMATION_HEAD = "82b0c22e3a9eb346f2b06745b958a570d41beb15"
ANIMATION_SEQUENCE_ID = "lid-latch-open-hold-close-001"
ANIMATION_SEQUENCE_DIGEST = "0a3523cf792264f610881552fd2ebd438aabdfd05e30e92af9dbb33ded1fa2d3"
SOURCE_RIG_BINDING_SHA256 = "615f8ff34cc0897fd399345301efce1ca9cb0aa58e86caca92b914049b89adce"
CLEAR_EPS_M = 1e-9
IDENTITY_EPS = 1e-12


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rotate_yz(y: float, z: float, py: float, pz: float, angle_deg: float) -> tuple[float, float]:
    y -= py
    z -= pz
    angle = math.radians(angle_deg)
    c, s = math.cos(angle), math.sin(angle)
    return py + y * c - z * s, pz + y * s + z * c


def _rect_yz(component: dict[str, Any], pivot: list[float], angle_deg: float) -> list[tuple[float, float]]:
    if component.get("kind") != "box":
        raise AssertionError(f"expected box component: {component.get('name')}")
    _, cy, cz = map(float, component["center_m"])
    _, sy, sz = map(float, component["size_m"])
    py, pz = float(pivot[1]), float(pivot[2])
    center_y, center_z = _rotate_yz(cy, cz, py, pz, angle_deg)
    hy, hz = sy / 2.0, sz / 2.0
    angle = math.radians(angle_deg)
    c, s = math.cos(angle), math.sin(angle)
    points: list[tuple[float, float]] = []
    for dy, dz in ((-hy, -hz), (hy, -hz), (hy, hz), (-hy, hz)):
        points.append((center_y + dy * c - dz * s, center_z + dy * s + dz * c))
    return points


def _axis_gaps(poly_a: list[tuple[float, float]], poly_b: list[tuple[float, float]]) -> list[float]:
    axes: list[tuple[float, float]] = []
    for poly in (poly_a, poly_b):
        for i in range(len(poly)):
            y0, z0 = poly[i]
            y1, z1 = poly[(i + 1) % len(poly)]
            ey, ez = y1 - y0, z1 - z0
            ay, az = -ez, ey
            length = math.hypot(ay, az)
            if length <= 0.0:
                raise AssertionError("degenerate rectangle edge")
            axes.append((ay / length, az / length))
    gaps: list[float] = []
    for ay, az in axes:
        pa = [y * ay + z * az for y, z in poly_a]
        pb = [y * ay + z * az for y, z in poly_b]
        gaps.append(max(min(pb) - max(pa), min(pa) - max(pb)))
    return gaps


def _sat_separation_m(poly_a: list[tuple[float, float]], poly_b: list[tuple[float, float]]) -> float:
    """Positive means separated on at least one SAT axis; <=0 means overlap/touch."""
    return max(_axis_gaps(poly_a, poly_b))


def _x_overlap_m(a: dict[str, Any], b: dict[str, Any]) -> float:
    ax, _, _ = map(float, a["center_m"])
    bx, _, _ = map(float, b["center_m"])
    asx, _, _ = map(float, a["size_m"])
    bsx, _, _ = map(float, b["size_m"])
    return min(ax + asx / 2.0, bx + bsx / 2.0) - max(ax - asx / 2.0, bx - bsx / 2.0)


def _validate_identity(
    *,
    source: dict[str, Any],
    source_sha256: str,
    ownership: dict[str, Any],
    source_interface: dict[str, Any],
    source_rig_binding: dict[str, Any],
    animation_authority: dict[str, Any],
    animation_evidence: dict[str, Any],
    observed_animation_head: str,
    observed_source_rig_head: str,
    observed_source_interface_head: str,
) -> None:
    if source_sha256 != SOURCE_SHA256:
        raise AssertionError("exact Object source byte identity drift")
    if ownership.get("host_source_sha256") != SOURCE_SHA256:
        raise AssertionError("ownership source identity drift")
    if source_interface.get("host_source_sha256") != SOURCE_SHA256:
        raise AssertionError("source latch interface host identity drift")
    if source_rig_binding.get("host_source_sha256") != SOURCE_SHA256:
        raise AssertionError("source Rigging binding host identity drift")

    if observed_animation_head != ANIMATION_HEAD:
        raise AssertionError("Animation donor head drift")
    if observed_source_rig_head != SOURCE_RIG_HEAD:
        raise AssertionError("source Rigging head drift")
    if observed_source_interface_head != SOURCE_INTERFACE_HEAD:
        raise AssertionError("source mechanical interface head drift")

    if source_interface.get("schema") != "axm.object-front-latch-pivot-interface/v0.1":
        raise AssertionError("unexpected source latch interface schema")
    if source_interface.get("interface_id") != "front-latch-pivot-interface-001":
        raise AssertionError("source latch interface identity drift")
    if source_interface.get("joint_axis") != [1.0, 0.0, 0.0] and source_interface.get("joint_axis") != [1, 0, 0]:
        raise AssertionError("source latch interface axis drift")
    if source_interface.get("ownership_contract", {}).get("donor_head") != OWNERSHIP_HEAD:
        raise AssertionError("source latch ownership donor drift")

    if source_rig_binding.get("schema") != "axm.object-front-latch-source-rig-binding/v0.1":
        raise AssertionError("unexpected source Rigging binding schema")
    if source_rig_binding.get("binding_id") != "front-latch-source-rig-binding-002":
        raise AssertionError("source Rigging binding identity drift")
    if source_rig_binding.get("source_interface", {}).get("head") != SOURCE_INTERFACE_HEAD:
        raise AssertionError("source Rigging binding no longer consumes exact source interface")
    if source_rig_binding.get("pose_samples_deg") != [0.0, 25.0, 50.0]:
        raise AssertionError("source Rigging representative latch boundary drift")

    if animation_authority.get("schema") != "axm.object-animation-source-authority-rebind/v0.1":
        raise AssertionError("unexpected Animation source-authority schema")
    prior = animation_authority.get("prior_animation_evidence", {})
    current_rig = animation_authority.get("source_rig_binding", {})
    preservation = animation_authority.get("preservation_contract", {})
    if prior.get("sequence_id") != ANIMATION_SEQUENCE_ID or prior.get("sequence_digest") != ANIMATION_SEQUENCE_DIGEST:
        raise AssertionError("Animation choreography identity drift")
    if current_rig.get("head") != SOURCE_RIG_HEAD:
        raise AssertionError("Animation authority does not bind current source Rigging head")
    if current_rig.get("binding_sha256") != SOURCE_RIG_BINDING_SHA256:
        raise AssertionError("Animation authority source Rigging identity drift")
    if preservation.get("timing") != "NO_RETIME" or preservation.get("target_geometry") != "NO_RETARGET":
        raise AssertionError("Animation authority retime/retarget boundary drift")
    if preservation.get("authored_samples") != "NO_KEY_CHANGE_101_ENDPOINT_INCLUSIVE":
        raise AssertionError("Animation authority authored sample boundary drift")

    if animation_evidence.get("result") != "PASS_ORDERED_LATCH_RELEASE_LID_CLIP_REENGAGE_SEQUENCE":
        raise AssertionError("exact Animation pose-set prerequisite is not green")
    if animation_evidence.get("exact_receiving_head") != ANIMATION_HEAD:
        raise AssertionError("Animation pose-set exact-head binding drift")
    if animation_evidence.get("host_source_sha256") != SOURCE_SHA256:
        raise AssertionError("Animation pose-set source identity drift")
    if animation_evidence.get("sequence_id") != ANIMATION_SEQUENCE_ID:
        raise AssertionError("Animation pose-set sequence id drift")
    if animation_evidence.get("sequence_digest") != ANIMATION_SEQUENCE_DIGEST:
        raise AssertionError("Animation pose-set sequence digest drift")
    if int(animation_evidence.get("sample_rate_hz", 0)) != 40:
        raise AssertionError("Animation pose-set sample-rate drift")
    if abs(float(animation_evidence.get("duration_s", -1.0)) - 2.5) > IDENTITY_EPS:
        raise AssertionError("Animation pose-set duration drift")
    if int(animation_evidence.get("endpoint_inclusive_sample_count", 0)) != 101:
        raise AssertionError("Animation pose-set count drift")
    if len(animation_evidence.get("samples", [])) != 101:
        raise AssertionError("Animation pose-set row count drift")


def verify(
    source: dict[str, Any],
    ownership: dict[str, Any],
    lid_plan: dict[str, Any],
    source_interface: dict[str, Any],
    source_rig_binding: dict[str, Any],
    animation_authority: dict[str, Any],
    animation_evidence: dict[str, Any],
    *,
    source_sha256: str,
    observed_ownership_head: str,
    observed_lid_rig_head: str,
    observed_previous_rigging_head: str,
    observed_animation_head: str,
    observed_source_rig_head: str,
    observed_source_interface_head: str,
) -> dict[str, Any]:
    _validate_identity(
        source=source,
        source_sha256=source_sha256,
        ownership=ownership,
        source_interface=source_interface,
        source_rig_binding=source_rig_binding,
        animation_authority=animation_authority,
        animation_evidence=animation_evidence,
        observed_animation_head=observed_animation_head,
        observed_source_rig_head=observed_source_rig_head,
        observed_source_interface_head=observed_source_interface_head,
    )

    keeper_prerequisite = keeper_socket.verify(
        source,
        ownership,
        lid_plan,
        source_sha256=source_sha256,
        observed_ownership_head=observed_ownership_head,
        observed_lid_rig_head=observed_lid_rig_head,
        observed_previous_rigging_head=observed_previous_rigging_head,
    )
    if keeper_prerequisite.get("result") != keeper_socket.RESULT:
        raise AssertionError("keeper socket prerequisite did not pass")

    if observed_ownership_head != OWNERSHIP_HEAD:
        raise AssertionError("front-latch ownership head drift")
    if observed_lid_rig_head != LID_RIG_HEAD:
        raise AssertionError("lid Rigging donor head drift")
    if observed_previous_rigging_head != PREVIOUS_RIGGING_HEAD:
        raise AssertionError("previous target Rigging head drift")

    built = build_modular_case.build(source)
    components = {row["name"]: row for row in built["components"]}
    hinge_origin = [float(v) for v in built["hinge_axis"]["origin_m"]]
    if [float(v) for v in built["hinge_axis"]["axis"]] != [1.0, 0.0, 0.0]:
        raise AssertionError("source lid hinge axis drift")

    interface_stations = {row["id"]: row for row in source_interface.get("stations", [])}
    ownership_stations = {row["id"]: row for row in ownership.get("stations", [])}
    if set(interface_stations) != {"left", "right"} or set(ownership_stations) != {"left", "right"}:
        raise AssertionError("bounded proof requires exact bilateral latch stations")

    for station_id, interface in interface_stations.items():
        owner = ownership_stations[station_id]
        if interface.get("keeper_component") != owner.get("keeper_component"):
            raise AssertionError("keeper component identity mismatch across source contracts")
        if interface.get("lever_component") != owner.get("lever_component"):
            raise AssertionError("lever component identity mismatch across source contracts")
        if interface.get("keeper_owner_component") != "lid_shell" or interface.get("lever_owner_component") != "front_service_panel":
            raise AssertionError("source latch owner drift")
        if interface.get("keeper_component") not in components or interface.get("lever_component") not in components:
            raise AssertionError("source latch component missing")
        if _x_overlap_m(components[interface["keeper_component"]], components[interface["lever_component"]]) <= 0.0:
            raise AssertionError("keeper/lever source X intervals no longer overlap at station")

    rows = animation_evidence["samples"]
    observations: list[dict[str, Any]] = []
    minimum_moving_lid_separation = math.inf
    minimum_pre_lid_separation = math.inf
    maximum_bilateral_separation_residual = 0.0
    moving_lid_sample_count = 0
    overlap_sample_count = 0
    clear_sample_count = 0
    first_moving_index: int | None = None
    last_moving_index: int | None = None
    peak_lid_index = max(range(len(rows)), key=lambda i: float(rows[i]["lid_open_angle_deg"]))

    for index, row in enumerate(rows):
        if int(row.get("index", -1)) != index:
            raise AssertionError("Animation pose-set index drift")
        lid_open_angle = float(row["lid_open_angle_deg"])
        lid_math_angle = float(row["lid_mathematical_rotation_deg"])
        latch_angle = float(row["latch_lever_angle_deg"])
        moving_lid = abs(lid_open_angle) > IDENTITY_EPS
        if moving_lid:
            moving_lid_sample_count += 1
            if first_moving_index is None:
                first_moving_index = index
            last_moving_index = index

        station_values: list[dict[str, Any]] = []
        separations: list[float] = []
        for station_id in ("left", "right"):
            interface = interface_stations[station_id]
            keeper = components[interface["keeper_component"]]
            lever = components[interface["lever_component"]]
            keeper_poly = _rect_yz(keeper, hinge_origin, lid_math_angle)
            lever_poly = _rect_yz(lever, [float(v) for v in interface["pivot_origin_m"]], latch_angle)
            separation = _sat_separation_m(keeper_poly, lever_poly)
            separations.append(separation)
            station_values.append(
                {
                    "station_id": station_id,
                    "keeper_component": interface["keeper_component"],
                    "lever_component": interface["lever_component"],
                    "sat_separation_m": separation,
                    "released_clear": separation > CLEAR_EPS_M,
                }
            )
            if moving_lid and separation <= CLEAR_EPS_M:
                raise AssertionError(
                    f"moving lid entered keeper/lever overlap at authored sample {index} station {station_id}: {separation}"
                )

        bilateral_residual = abs(separations[0] - separations[1])
        maximum_bilateral_separation_residual = max(maximum_bilateral_separation_residual, bilateral_residual)
        all_clear = all(value > CLEAR_EPS_M for value in separations)
        any_overlap = any(value <= CLEAR_EPS_M for value in separations)
        if all_clear:
            clear_sample_count += 1
        if any_overlap:
            overlap_sample_count += 1
            if moving_lid:
                raise AssertionError(f"engagement overlap occurred while lid moved at authored sample {index}")
        if moving_lid:
            minimum_moving_lid_separation = min(minimum_moving_lid_separation, min(separations))

        observations.append(
            {
                "index": index,
                "time_s": float(row["time_s"]),
                "lid_open_angle_deg": lid_open_angle,
                "lid_mathematical_rotation_deg": lid_math_angle,
                "latch_lever_angle_deg": latch_angle,
                "moving_lid": moving_lid,
                "all_stations_released_clear": all_clear,
                "any_station_engagement_overlap": any_overlap,
                "bilateral_separation_residual_m": bilateral_residual,
                "stations": station_values,
            }
        )

    if first_moving_index is None or last_moving_index is None:
        raise AssertionError("Animation pose-set contains no lid movement")
    if first_moving_index <= 0 or last_moving_index >= len(observations) - 1:
        raise AssertionError("lid-motion boundary cannot be bracketed by neutral authored samples")

    previous_to_motion = observations[first_moving_index - 1]
    next_after_motion = observations[last_moving_index + 1]
    if not previous_to_motion["all_stations_released_clear"]:
        raise AssertionError("keeper/lever release clearance was not established before first lid movement")
    if abs(previous_to_motion["lid_open_angle_deg"]) > IDENTITY_EPS:
        raise AssertionError("pre-lid release witness is not lid-neutral")
    if not next_after_motion["all_stations_released_clear"]:
        raise AssertionError("keeper/lever release clearance was not retained through first neutral sample after lid movement")
    if abs(next_after_motion["lid_open_angle_deg"]) > IDENTITY_EPS:
        raise AssertionError("post-lid release witness is not lid-neutral")
    minimum_pre_lid_separation = min(v["sat_separation_m"] for v in previous_to_motion["stations"])

    if observations[0]["all_stations_released_clear"]:
        raise AssertionError("neutral authored start no longer represents engaged keeper/lever proof volumes")
    if observations[-1]["all_stations_released_clear"]:
        raise AssertionError("neutral authored endpoint no longer represents re-engaged keeper/lever proof volumes")
    if maximum_bilateral_separation_residual > IDENTITY_EPS:
        raise AssertionError(f"bilateral release/engagement residual exceeds tolerance: {maximum_bilateral_separation_residual}")
    if not math.isfinite(minimum_moving_lid_separation) or minimum_moving_lid_separation <= CLEAR_EPS_M:
        raise AssertionError("moving-lid minimum keeper/lever separation is not positive")

    first_clear_index = next((o["index"] for o in observations if o["all_stations_released_clear"]), None)
    last_clear_index = next((o["index"] for o in reversed(observations) if o["all_stations_released_clear"]), None)
    if first_clear_index is None or last_clear_index is None:
        raise AssertionError("no released-clear authored pose found")

    representative_indices = sorted(
        set(
            i
            for i in (
                0,
                max(first_clear_index - 1, 0),
                first_clear_index,
                first_moving_index,
                peak_lid_index,
                last_moving_index,
                last_moving_index + 1,
                last_clear_index,
                min(last_clear_index + 1, len(observations) - 1),
                len(observations) - 1,
            )
            if 0 <= i < len(observations)
        )
    )

    return {
        "schema": SCHEMA,
        "result": RESULT,
        "asset_id": source["asset_id"],
        "source_sha256": source_sha256,
        "identity": {
            "ownership_head": OWNERSHIP_HEAD,
            "source_interface_head": SOURCE_INTERFACE_HEAD,
            "source_rig_head": SOURCE_RIG_HEAD,
            "source_rig_binding_sha256": SOURCE_RIG_BINDING_SHA256,
            "lid_rig_head": LID_RIG_HEAD,
            "previous_rigging_target_binding_head": PREVIOUS_RIGGING_HEAD,
            "animation_pose_set_head": ANIMATION_HEAD,
            "animation_sequence_id": ANIMATION_SEQUENCE_ID,
            "animation_sequence_digest": ANIMATION_SEQUENCE_DIGEST,
            "hinge_origin_m": hinge_origin,
            "hinge_axis": [1.0, 0.0, 0.0],
        },
        "prerequisites": {
            "keeper_socket_result": keeper_prerequisite["result"],
            "animation_pose_set_result": animation_evidence["result"],
            "animation_source_authority_role": "POSE_SET_AND_ORDERING_DONOR_ONLY_NOT_ANIMATION_ACCEPTANCE",
        },
        "authored_pose_field": {
            "sample_count": len(observations),
            "sample_rate_hz": 40,
            "duration_s": 2.5,
            "moving_lid_sample_count": moving_lid_sample_count,
            "released_clear_sample_count": clear_sample_count,
            "engagement_overlap_sample_count": overlap_sample_count,
            "first_released_clear_index": first_clear_index,
            "first_moving_lid_index": first_moving_index,
            "peak_lid_index": peak_lid_index,
            "last_moving_lid_index": last_moving_index,
            "last_released_clear_index": last_clear_index,
            "minimum_pre_lid_release_separation_m": minimum_pre_lid_separation,
            "minimum_moving_lid_keeper_lever_separation_m": minimum_moving_lid_separation,
            "maximum_bilateral_separation_residual_m": maximum_bilateral_separation_residual,
            "representative_indices": representative_indices,
            "representative_poses": [observations[i] for i in representative_indices],
        },
        "truth_boundary": {
            "proves": "At the exact 101 authored source-space pose samples, both source-owned lid keepers are already separated from their paired source-owned service-panel levers before lid motion begins, remain separated through every non-neutral lid pose, and any engagement overlap occurs only at lid-neutral authored poses; exact keeper socket and source Rigging identities remain pinned.",
            "does_not_prove": "Continuous keeper/lever collision clearance between authored samples, physical latch capture/retention/load, interpolation or wall-clock motion quality, Animation acceptance, Runtime/controller/state-machine acceptance, physics/gameplay, target-device behavior, final visual acceptance, CANON or production readiness.",
            "continuous_between_authored_samples_proven": False,
            "physical_latch_mechanism_accepted": False,
            "animation_accepted": False,
            "runtime_accepted": False,
            "gameplay_accepted": False,
        },
        "observations": observations,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--ownership", type=Path, required=True)
    parser.add_argument("--lid-plan", type=Path, required=True)
    parser.add_argument("--source-interface", type=Path, required=True)
    parser.add_argument("--source-rig-binding", type=Path, required=True)
    parser.add_argument("--animation-authority", type=Path, required=True)
    parser.add_argument("--animation-evidence", type=Path, required=True)
    parser.add_argument("--observed-ownership-head", required=True)
    parser.add_argument("--observed-lid-rig-head", required=True)
    parser.add_argument("--observed-previous-rigging-head", required=True)
    parser.add_argument("--observed-animation-head", required=True)
    parser.add_argument("--observed-source-rig-head", required=True)
    parser.add_argument("--observed-source-interface-head", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    source = json.loads(args.source.read_text(encoding="utf-8"))
    ownership = json.loads(args.ownership.read_text(encoding="utf-8"))
    lid_plan = json.loads(args.lid_plan.read_text(encoding="utf-8"))
    source_interface = json.loads(args.source_interface.read_text(encoding="utf-8"))
    source_rig_binding = json.loads(args.source_rig_binding.read_text(encoding="utf-8"))
    animation_authority = json.loads(args.animation_authority.read_text(encoding="utf-8"))
    animation_evidence = json.loads(args.animation_evidence.read_text(encoding="utf-8"))

    receipt = verify(
        source,
        ownership,
        lid_plan,
        source_interface,
        source_rig_binding,
        animation_authority,
        animation_evidence,
        source_sha256=sha256_file(args.source),
        observed_ownership_head=args.observed_ownership_head,
        observed_lid_rig_head=args.observed_lid_rig_head,
        observed_previous_rigging_head=args.observed_previous_rigging_head,
        observed_animation_head=args.observed_animation_head,
        observed_source_rig_head=args.observed_source_rig_head,
        observed_source_interface_head=args.observed_source_interface_head,
    )

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    field = receipt["authored_pose_field"]
    (args.out / "summary.txt").write_text(
        f"{receipt['result']}\n"
        f"sample_count={field['sample_count']}\n"
        f"moving_lid_sample_count={field['moving_lid_sample_count']}\n"
        f"released_clear_sample_count={field['released_clear_sample_count']}\n"
        f"engagement_overlap_sample_count={field['engagement_overlap_sample_count']}\n"
        f"minimum_pre_lid_release_separation_m={field['minimum_pre_lid_release_separation_m']:.18g}\n"
        f"minimum_moving_lid_keeper_lever_separation_m={field['minimum_moving_lid_keeper_lever_separation_m']:.18g}\n"
        f"maximum_bilateral_separation_residual_m={field['maximum_bilateral_separation_residual_m']:.18g}\n",
        encoding="utf-8",
    )
    print(receipt["result"])


if __name__ == "__main__":
    main()
