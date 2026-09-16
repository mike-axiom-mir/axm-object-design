from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import build_modular_case
import build_lid_motion_evidence as lid_motion

CONTRACT_SCHEMA = "axm.object-animation-source-authority-rebind/v0.1"
RESULT = "PASS_ANIMATION_SOURCE_AUTHORITY_REBIND_MOTION_EQUIVALENCE"
EXPECTED_PRIOR_ANIMATION_HEAD = "5cb073f9fcf825014556ed165ee081e1eca71cdc"
EXPECTED_PRIOR_SEQUENCE_ID = "lid-latch-open-hold-close-001"
EXPECTED_PRIOR_SEQUENCE_DIGEST = "0a3523cf792264f610881552fd2ebd438aabdfd05e30e92af9dbb33ded1fa2d3"
EXPECTED_SOURCE_INTERFACE_HEAD = "6086f39a3da344c57a68653f90d040e03e04cec2"
EXPECTED_SOURCE_INTERFACE_SHA256 = "bcbbe098371eb702bc9289a97370744093105925202eda6036bdced6e25e34d3"
EXPECTED_SOURCE_RIG_HEAD = "a1acd2bcb2074f41e536562f2673508e2cb0a4d5"
EXPECTED_SOURCE_RIG_BINDING_SHA256 = "615f8ff34cc0897fd399345301efce1ca9cb0aa58e86caca92b914049b89adce"
EXPECTED_HISTORICAL_RIG_HEAD = "3b667ff5d30c46ec2fe7da7679518970f8610018"
EXPECTED_SOURCE_RIG_RESULT = "PASS_SOURCE_OWNED_FRONT_LATCH_RIG_REBIND"
EPS = 1e-12


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def component_map(source: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["name"]: row for row in build_modular_case.build(source)["components"]}


def box_corners(component: dict[str, Any]) -> list[tuple[float, float, float]]:
    center = tuple(float(v) for v in component["center_m"])
    size = tuple(float(v) for v in component["size_m"])
    return lid_motion.box_corners(center, size)


def rotated_digest(
    component: dict[str, Any],
    pivot: tuple[float, float, float],
    angle_deg: float,
) -> str:
    moved = [lid_motion.rotate_x(point, pivot, angle_deg) for point in box_corners(component)]
    rounded = [[round(v, 12) for v in point] for point in moved]
    return canonical_digest(rounded)


def by_station(rows: list[dict[str, Any]], key: str = "station_id") -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        station_id = str(row[key])
        if station_id in out:
            raise AssertionError(f"duplicate station identity: {station_id}")
        out[station_id] = row
    return out


def verify(
    host: dict[str, Any],
    contract: dict[str, Any],
    prior: dict[str, Any],
    interface: dict[str, Any],
    source_rig: dict[str, Any],
    *,
    host_sha: str,
    interface_sha: str,
    exact_head: str,
) -> dict[str, Any]:
    if contract.get("schema") != CONTRACT_SCHEMA:
        raise AssertionError("unsupported animation source-authority rebind schema")
    if contract.get("asset_id") != host.get("asset_id"):
        raise AssertionError("rebind asset identity drift")
    if contract.get("host_source_sha256") != host_sha:
        raise AssertionError("rebind host source identity drift")

    prior_ref = contract.get("prior_animation_evidence", {})
    if prior_ref.get("head") != EXPECTED_PRIOR_ANIMATION_HEAD:
        raise AssertionError("prior Animation head drift")
    if prior_ref.get("sequence_id") != EXPECTED_PRIOR_SEQUENCE_ID:
        raise AssertionError("prior Animation sequence identity drift")
    if prior_ref.get("sequence_digest") != EXPECTED_PRIOR_SEQUENCE_DIGEST:
        raise AssertionError("prior Animation sequence digest drift")
    if prior_ref.get("role") != "EXACT_MOTION_CHOREOGRAPHY_DONOR_ONLY":
        raise AssertionError("prior Animation role drift")

    interface_ref = contract.get("source_interface", {})
    if interface_ref.get("head") != EXPECTED_SOURCE_INTERFACE_HEAD:
        raise AssertionError("source interface head drift")
    if interface_ref.get("sha256") != EXPECTED_SOURCE_INTERFACE_SHA256 or interface_sha != EXPECTED_SOURCE_INTERFACE_SHA256:
        raise AssertionError("source interface file identity drift")
    if interface_ref.get("role") != "CURRENT_SOURCE_MECHANICAL_AUTHORITY":
        raise AssertionError("source interface authority role drift")

    rig_ref = contract.get("source_rig_binding", {})
    if rig_ref.get("head") != EXPECTED_SOURCE_RIG_HEAD:
        raise AssertionError("source Rigging head drift")
    if rig_ref.get("binding_sha256") != EXPECTED_SOURCE_RIG_BINDING_SHA256:
        raise AssertionError("source Rigging binding file identity drift")
    if rig_ref.get("required_result") != EXPECTED_SOURCE_RIG_RESULT:
        raise AssertionError("source Rigging required result drift")
    if rig_ref.get("role") != "CURRENT_RIGGING_ACCEPTANCE_OF_SOURCE_AUTHORITY":
        raise AssertionError("source Rigging authority role drift")

    if prior.get("result") != "PASS_ORDERED_LATCH_RELEASE_LID_CLIP_REENGAGE_SEQUENCE":
        raise AssertionError("prior Animation choreography donor is not green")
    if prior.get("exact_receiving_head") != EXPECTED_PRIOR_ANIMATION_HEAD:
        raise AssertionError("prior Animation evidence head drift")
    if prior.get("asset_id") != host.get("asset_id") or prior.get("host_source_sha256") != host_sha:
        raise AssertionError("prior Animation host identity drift")
    if prior.get("sequence_id") != EXPECTED_PRIOR_SEQUENCE_ID or prior.get("sequence_digest") != EXPECTED_PRIOR_SEQUENCE_DIGEST:
        raise AssertionError("prior Animation sequence proof identity drift")
    if prior.get("latch_rig_dependency_head") != EXPECTED_HISTORICAL_RIG_HEAD:
        raise AssertionError("prior Animation historical Rigging donor drift")
    if int(prior.get("sample_rate_hz", 0)) != 40 or float(prior.get("duration_s", 0.0)) != 2.5:
        raise AssertionError("prior Animation time grid drift")
    samples = prior.get("samples", [])
    if len(samples) != 101 or int(prior.get("endpoint_inclusive_sample_count", 0)) != 101:
        raise AssertionError("prior Animation sample count drift")

    if interface.get("schema") != "axm.object-front-latch-pivot-interface/v0.1":
        raise AssertionError("unexpected source interface schema")
    if interface.get("asset_id") != host.get("asset_id") or interface.get("host_source_sha256") != host_sha:
        raise AssertionError("source interface host identity drift")
    if interface.get("joint_axis") != [1.0, 0.0, 0.0]:
        raise AssertionError("source interface joint axis drift")
    stations = interface.get("stations", [])
    if len(stations) != 2:
        raise AssertionError("source interface bilateral station count drift")

    if source_rig.get("result") != EXPECTED_SOURCE_RIG_RESULT:
        raise AssertionError("source Rigging rebind evidence is not green")
    if source_rig.get("host_source_sha256") != host_sha:
        raise AssertionError("source Rigging host identity drift")
    if source_rig.get("source_interface_head") != EXPECTED_SOURCE_INTERFACE_HEAD:
        raise AssertionError("source Rigging interface head drift")
    if source_rig.get("source_interface_sha256") != EXPECTED_SOURCE_INTERFACE_SHA256:
        raise AssertionError("source Rigging interface digest drift")
    if source_rig.get("binding_sha256") != EXPECTED_SOURCE_RIG_BINDING_SHA256:
        raise AssertionError("source Rigging binding digest drift")
    if source_rig.get("rig_authority") != "CURRENT_SOURCE_INTERFACE_AUTHORITY":
        raise AssertionError("source Rigging current authority drift")
    if source_rig.get("historical_rigging_observation_head") != EXPECTED_HISTORICAL_RIG_HEAD:
        raise AssertionError("source Rigging historical donor drift")
    if source_rig.get("historical_rigging_role") != "PROVENANCE_ONLY_NOT_CURRENT_INTERFACE_AUTHORITY":
        raise AssertionError("historical Rigging role was silently re-promoted")

    old_threshold = float(prior.get("rig_continuous_keeper_z_separation_threshold_deg"))
    new_threshold = float(source_rig.get("continuous_release_threshold_deg"))
    if abs(old_threshold - new_threshold) > EPS:
        raise AssertionError("source-authority rebind changed the retained release threshold")
    old_terminal = float(prior.get("rig_terminal_keeper_z_separation_m"))
    new_terminal = float(source_rig.get("minimum_endpoint_keeper_z_separation_m"))
    if abs(old_terminal - new_terminal) > EPS:
        raise AssertionError("source-authority rebind changed the retained terminal release separation")

    components = component_map(host)
    interface_by_station = {str(row["id"]): row for row in stations}
    source_rig_by_station = by_station(source_rig.get("station_results", []))
    if set(interface_by_station) != set(source_rig_by_station):
        raise AssertionError("source interface / source Rigging station identity mismatch")

    maximum_pivot_residual_m = 0.0
    for station_id, station in interface_by_station.items():
        pivot = tuple(float(v) for v in station.get("pivot_origin_m", []))
        rig_pivot = tuple(float(v) for v in source_rig_by_station[station_id].get("pivot_origin_m", []))
        if len(pivot) != 3 or len(rig_pivot) != 3:
            raise AssertionError("source-owned pivot missing")
        maximum_pivot_residual_m = max(maximum_pivot_residual_m, math.dist(pivot, rig_pivot))
    if maximum_pivot_residual_m > EPS:
        raise AssertionError("source interface / source Rigging pivot residual exceeded tolerance")

    geometry_comparisons = 0
    geometry_mismatches = 0
    max_angle_outside_interface_deg = 0.0
    for sample in samples:
        latch_angle = float(sample["latch_lever_angle_deg"])
        max_angle_outside_interface_deg = max(max_angle_outside_interface_deg, max(0.0, latch_angle - 50.0, -latch_angle))
        old_station_rows = by_station(sample.get("stations", []))
        if set(old_station_rows) != set(interface_by_station):
            raise AssertionError("Animation sample station identity drift")
        for station_id, station in interface_by_station.items():
            old_row = old_station_rows[station_id]
            lever_name = str(station["lever_component"])
            keeper_name = str(station["keeper_component"])
            if old_row.get("lever_component") != lever_name or old_row.get("keeper_component") != keeper_name:
                raise AssertionError("Animation sample component ownership drift")
            if lever_name not in components or keeper_name not in components:
                raise AssertionError("source-owned latch component missing from current host")
            pivot = tuple(float(v) for v in station["pivot_origin_m"])
            rebound_digest = rotated_digest(components[lever_name], pivot, latch_angle)
            geometry_comparisons += 1
            if rebound_digest != old_row.get("lever_digest"):
                geometry_mismatches += 1

    if max_angle_outside_interface_deg > EPS:
        raise AssertionError("Animation choreography left the source-owned 0..50 degree interface envelope")
    if geometry_comparisons != 202:
        raise AssertionError("expected exact 101 x 2 source-owned lever geometry comparisons")
    if geometry_mismatches:
        raise AssertionError(f"source-authority rebind changed {geometry_mismatches} retained lever geometry samples")

    preservation = contract.get("preservation_contract", {})
    if preservation.get("timing") != "NO_RETIME" or preservation.get("target_geometry") != "NO_RETARGET":
        raise AssertionError("Animation preservation contract drift")
    if preservation.get("authored_samples") != "NO_KEY_CHANGE_101_ENDPOINT_INCLUSIVE":
        raise AssertionError("Animation key preservation contract drift")

    return {
        "schema": "axm.object-animation-source-authority-rebind-evidence/v0.1",
        "result": RESULT,
        "exact_receiving_head": exact_head,
        "asset_id": host["asset_id"],
        "host_source_sha256": host_sha,
        "prior_animation_head": EXPECTED_PRIOR_ANIMATION_HEAD,
        "prior_sequence_id": EXPECTED_PRIOR_SEQUENCE_ID,
        "prior_sequence_digest": EXPECTED_PRIOR_SEQUENCE_DIGEST,
        "prior_historical_rig_head": EXPECTED_HISTORICAL_RIG_HEAD,
        "current_source_interface_head": EXPECTED_SOURCE_INTERFACE_HEAD,
        "current_source_interface_sha256": EXPECTED_SOURCE_INTERFACE_SHA256,
        "current_source_rig_head": EXPECTED_SOURCE_RIG_HEAD,
        "current_source_rig_binding_sha256": EXPECTED_SOURCE_RIG_BINDING_SHA256,
        "source_rig_result": EXPECTED_SOURCE_RIG_RESULT,
        "source_authority_role": "CURRENT_SOURCE_MECHANICAL_AUTHORITY",
        "rigging_authority_role": "CURRENT_RIGGING_ACCEPTANCE_OF_SOURCE_AUTHORITY",
        "historical_rigging_role": source_rig["historical_rigging_role"],
        "sample_rate_hz": 40,
        "duration_s": 2.5,
        "endpoint_inclusive_sample_count": 101,
        "station_count": 2,
        "source_owned_lever_geometry_comparison_count": geometry_comparisons,
        "source_owned_lever_geometry_mismatch_count": geometry_mismatches,
        "maximum_source_interface_vs_rig_pivot_residual_m": maximum_pivot_residual_m,
        "release_threshold_deg_before": old_threshold,
        "release_threshold_deg_after": new_threshold,
        "release_threshold_delta_deg": abs(old_threshold - new_threshold),
        "terminal_keeper_z_separation_m_before": old_terminal,
        "terminal_keeper_z_separation_m_after": new_terminal,
        "terminal_keeper_z_separation_delta_m": abs(old_terminal - new_terminal),
        "prior_sequence_geometry_digest": prior.get("sequence_geometry_digest"),
        "motion_change": False,
        "retimed": False,
        "retargeted": False,
        "key_count_changed": False,
        "truth_boundary": contract.get("truth_boundary"),
        "non_claims": [
            "no claim that the source-owned interface is merged or CANON",
            "no physical latch hook, catch, retention, force or collision acceptance",
            "no runtime controller, state-machine, input or wall-clock pacing acceptance",
            "no gameplay timing or gameplay acceptance",
            "no final motion style, weight, Art Direction or Visual QA acceptance",
            "no Technical Art or Runtime successor evidence is silently rebound by this Animation result",
            "no production-readiness, game-readiness or Animation mastery claim",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--prior-sequence-evidence", type=Path, required=True)
    parser.add_argument("--source-interface", type=Path, required=True)
    parser.add_argument("--source-rig-receipt", type=Path, required=True)
    parser.add_argument("--exact-head", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    host = json.loads(args.host.read_text(encoding="utf-8"))
    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    prior = json.loads(args.prior_sequence_evidence.read_text(encoding="utf-8"))
    interface = json.loads(args.source_interface.read_text(encoding="utf-8"))
    source_rig = json.loads(args.source_rig_receipt.read_text(encoding="utf-8"))
    evidence = verify(
        host,
        contract,
        prior,
        interface,
        source_rig,
        host_sha=file_sha256(args.host),
        interface_sha=file_sha256(args.source_interface),
        exact_head=args.exact_head,
    )
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "animation-source-authority-rebind-evidence.json").write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.out / "exact-head.txt").write_text(args.exact_head + "\n", encoding="utf-8")
    print(evidence["result"])


if __name__ == "__main__":
    main()
