from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

CONTRACT_SCHEMA = "axm.object-animation-capture-timeline-rebind/v0.1"
SEQUENCE_EVIDENCE_SCHEMA = "axm.object-lid-latch-motion-evidence/v0.1"
RIG_EVIDENCE_SCHEMA = "axm.object-front-latch-source-rig-binding-evidence/v0.2"
CAPTURE_POLICY_SCHEMA = "axm.object-front-latch-capture-envelope/v0.1"
RIG_BINDING_SCHEMA = "axm.object-front-latch-source-rig-binding/v0.2"
RESULT = "PASS_OBJECT_LATCH_PROOF_VOLUME_CAPTURE_TIMELINE_REBIND__NO_RETIME"
EPS = 1e-9


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


def _smoothstep(value: float) -> float:
    value = min(1.0, max(0.0, value))
    return value * value * (3.0 - 2.0 * value)


def _inverse_smoothstep(target: float) -> float:
    if not 0.0 <= target <= 1.0:
        raise AssertionError("normalized threshold outside smoothstep domain")
    lo, hi = 0.0, 1.0
    for _ in range(100):
        mid = (lo + hi) * 0.5
        if _smoothstep(mid) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) * 0.5


def _inside(value: float, bounds: list[float]) -> bool:
    return len(bounds) == 2 and float(bounds[0]) < value < float(bounds[1])


def _expected_latch_angle(index: int, terminal_angle: float = 50.0) -> float:
    if index <= 10:
        return terminal_angle * _smoothstep(index / 10.0)
    if index <= 90:
        return terminal_angle
    return terminal_angle * (1.0 - _smoothstep((index - 90) / 10.0))


def _release_bracket(samples: list[dict[str, Any]], threshold: float) -> dict[str, Any]:
    for left, right in zip(samples[:10], samples[1:11]):
        a = float(left["latch_lever_angle_deg"])
        b = float(right["latch_lever_angle_deg"])
        if a <= threshold < b:
            return {
                "lower_index": int(left["index"]),
                "lower_time_s": float(left["time_s"]),
                "lower_angle_deg": a,
                "upper_index": int(right["index"]),
                "upper_time_s": float(right["time_s"]),
                "upper_angle_deg": b,
            }
    raise AssertionError("release samples do not bracket threshold")


def _reengage_bracket(samples: list[dict[str, Any]], threshold: float) -> dict[str, Any]:
    for left, right in zip(samples[90:100], samples[91:101]):
        a = float(left["latch_lever_angle_deg"])
        b = float(right["latch_lever_angle_deg"])
        if a > threshold >= b:
            return {
                "upper_index": int(left["index"]),
                "upper_time_s": float(left["time_s"]),
                "upper_angle_deg": a,
                "lower_index": int(right["index"]),
                "lower_time_s": float(right["time_s"]),
                "lower_angle_deg": b,
            }
    raise AssertionError("reengagement samples do not bracket threshold")


def _validate_preservation(contract: dict[str, Any]) -> None:
    preserved = contract.get("preservation_contract", {})
    for key in (
        "retimed",
        "keys_changed",
        "easing_changed",
        "amplitude_changed",
        "source_geometry_changed",
        "rig_pivots_changed",
        "rig_motion_envelope_changed",
    ):
        if preserved.get(key) is not False:
            raise AssertionError(f"motion/source preservation boundary drift: {key}")

    truth = contract.get("truth_boundary", {})
    if truth.get("animation_timeline_characterization_owned") is not True:
        raise AssertionError("Animation timeline characterization authority missing")
    for key in (
        "proof_volume_capture_boundary_is_physical_retention",
        "z_aabb_boundary_is_capture_threshold",
        "continuous_release_forces_proven",
        "continuous_reengagement_forces_proven",
        "runtime_controller_accepted",
        "gameplay_accepted",
        "final_visual_motion_accepted",
        "canon_or_production_ready",
    ):
        if truth.get(key) is not False:
            raise AssertionError(f"authority inflation: {key}")


def verify(
    contract: dict[str, Any],
    sequence: dict[str, Any],
    rig: dict[str, Any],
    rig_binding: dict[str, Any],
    capture_policy: dict[str, Any],
    *,
    current_rig_head: str,
    source_authority_head: str,
    rig_binding_blob_sha: str,
    capture_policy_blob_sha: str,
    exact_head: str,
) -> dict[str, Any]:
    if contract.get("schema") != CONTRACT_SCHEMA:
        raise AssertionError("unsupported Animation capture-timeline contract")
    if sequence.get("schema") != SEQUENCE_EVIDENCE_SCHEMA:
        raise AssertionError("unexpected Animation sequence evidence schema")
    if rig.get("schema") != RIG_EVIDENCE_SCHEMA:
        raise AssertionError("unexpected current Rigging receipt schema")
    if rig_binding.get("schema") != RIG_BINDING_SCHEMA:
        raise AssertionError("unexpected current Rigging binding schema")
    if capture_policy.get("schema") != CAPTURE_POLICY_SCHEMA:
        raise AssertionError("unexpected capture policy schema")

    _validate_preservation(contract)
    asset_id = contract.get("asset_id")
    host_sha = contract.get("host_source_sha256")
    for name, value in (
        ("sequence", sequence.get("asset_id")),
        ("rig", rig.get("asset_id")),
        ("binding", rig_binding.get("asset_id")),
        ("capture policy", capture_policy.get("asset_id")),
    ):
        if value != asset_id:
            raise AssertionError(f"{name} asset identity drift")
    for name, value in (
        ("sequence", sequence.get("host_source_sha256")),
        ("rig", rig.get("host_source_sha256")),
        ("binding", rig_binding.get("host_source_sha256")),
        ("capture policy", capture_policy.get("host_source_sha256")),
    ):
        if value != host_sha:
            raise AssertionError(f"{name} host source identity drift")

    seq_ref = contract.get("animation_sequence", {})
    if sequence.get("result") != "PASS_ORDERED_LATCH_RELEASE_LID_CLIP_REENGAGE_SEQUENCE":
        raise AssertionError("Animation sequence prerequisite did not pass")
    if sequence.get("sequence_id") != seq_ref.get("sequence_id"):
        raise AssertionError("Animation sequence ID drift")
    if sequence.get("sequence_digest") != seq_ref.get("sequence_digest"):
        raise AssertionError("Animation sequence digest drift")
    if int(sequence.get("sample_rate_hz", -1)) != int(seq_ref.get("sample_rate_hz", -2)) or int(seq_ref.get("sample_rate_hz", -1)) != 40:
        raise AssertionError("Animation sequence sample rate drift")
    if abs(float(sequence.get("duration_s", -1.0)) - float(seq_ref.get("duration_s", -2.0))) > EPS or float(seq_ref.get("duration_s")) != 2.5:
        raise AssertionError("Animation sequence duration drift")
    samples = sequence.get("samples", [])
    if len(samples) != int(seq_ref.get("endpoint_inclusive_sample_count", -1)) or len(samples) != 101:
        raise AssertionError("Animation sequence sample-count drift")
    terminal = float(seq_ref.get("terminal_latch_angle_deg", -1.0))
    if terminal != 50.0:
        raise AssertionError("terminal latch review pose drift")

    max_latch_formula_residual = 0.0
    release_lid_residual = 0.0
    reengage_lid_residual = 0.0
    moving_lid_without_terminal_latch = 0
    for index, row in enumerate(samples):
        if int(row.get("index", -1)) != index:
            raise AssertionError("Animation sample index drift")
        if abs(float(row.get("time_s")) - index / 40.0) > EPS:
            raise AssertionError("Animation sample-time grid drift")
        actual_latch = float(row.get("latch_lever_angle_deg"))
        expected_latch = _expected_latch_angle(index, terminal)
        max_latch_formula_residual = max(max_latch_formula_residual, abs(actual_latch - expected_latch))
        lid = abs(float(row.get("lid_open_angle_deg")))
        if index <= 10:
            release_lid_residual = max(release_lid_residual, lid)
        if index >= 90:
            reengage_lid_residual = max(reengage_lid_residual, lid)
        if lid > EPS and abs(actual_latch - terminal) > EPS:
            moving_lid_without_terminal_latch += 1
    if max_latch_formula_residual > EPS:
        raise AssertionError("authored latch curve changed from exact 40 Hz smoothstep sequence")
    if release_lid_residual > EPS or reengage_lid_residual > EPS:
        raise AssertionError("lid moved during latch release or reengagement phase")
    if moving_lid_without_terminal_latch:
        raise AssertionError("lid moved before exact 50 degree review release endpoint")

    rig_ref = contract.get("current_rigging_authority", {})
    if current_rig_head != rig_ref.get("exact_head"):
        raise AssertionError("current Rigging authority head drift")
    if rig_binding_blob_sha != rig_ref.get("binding_git_blob_sha"):
        raise AssertionError("current Rigging binding blob drift")
    if rig.get("result") != rig_ref.get("required_result"):
        raise AssertionError("current Rigging capture-envelope prerequisite did not pass")
    if rig.get("source_mechanical_authority_head") != source_authority_head:
        raise AssertionError("Rigging receipt source authority drift")
    if rig.get("source_capture_result") != contract.get("source_capture_authority", {}).get("required_result"):
        raise AssertionError("Rigging receipt capture prerequisite drift")
    if rig.get("historical_interface_threshold_reclassified_as") != "Z_AABB_BROAD_PHASE_ONLY_NOT_CAPTURE_THRESHOLD":
        raise AssertionError("historical Z-AABB threshold was relabelled as capture")
    if rig.get("motion_envelope_retuned") is not False or rig.get("animation_timing_or_playback_accepted") is not False:
        raise AssertionError("Rigging receipt improperly retuned motion or claimed Animation acceptance")

    source_ref = contract.get("source_capture_authority", {})
    if source_authority_head != source_ref.get("exact_head"):
        raise AssertionError("source capture authority head drift")
    if capture_policy_blob_sha != source_ref.get("policy_git_blob_sha"):
        raise AssertionError("source capture policy blob drift")
    if capture_policy.get("source_semantics", {}).get("z_aabb_transition") != source_ref.get("z_aabb_semantics"):
        raise AssertionError("source broad-phase semantics drift")
    authority = capture_policy.get("authority", {})
    if authority.get("animation_timing_owned") is not False or authority.get("runtime_controller_owned") is not False:
        raise AssertionError("source owner authority inflated into Animation/Runtime")

    capture = float(rig.get("source_capture_transition_deg"))
    broad = float(rig.get("z_aabb_only_transition_deg"))
    if not _inside(capture, [float(x) for x in source_ref.get("required_capture_transition_deg_range", [])]):
        raise AssertionError("true proof-volume capture transition drift")
    if not _inside(broad, [float(x) for x in source_ref.get("required_z_aabb_only_transition_deg_range", [])]):
        raise AssertionError("Z-AABB broad-phase transition drift")
    if not 0.0 < capture < broad < terminal:
        raise AssertionError("capture/broad-phase/review-endpoint ordering collapsed")

    release_capture = _release_bracket(samples, capture)
    release_broad = _release_bracket(samples, broad)
    reengage_capture = _reengage_bracket(samples, capture)
    reengage_broad = _reengage_bracket(samples, broad)

    release_capture_time = 0.25 * _inverse_smoothstep(capture / terminal)
    release_broad_time = 0.25 * _inverse_smoothstep(broad / terminal)
    reengage_capture_time = 2.25 + 0.25 * _inverse_smoothstep(1.0 - capture / terminal)
    reengage_broad_time = 2.25 + 0.25 * _inverse_smoothstep(1.0 - broad / terminal)

    for time_s, bracket, label in (
        (release_capture_time, release_capture, "release capture"),
        (release_broad_time, release_broad, "release broad-phase"),
        (reengage_broad_time, reengage_broad, "reengage broad-phase"),
        (reengage_capture_time, reengage_capture, "reengage capture"),
    ):
        lo = min(float(bracket["lower_time_s"]), float(bracket["upper_time_s"]))
        hi = max(float(bracket["lower_time_s"]), float(bracket["upper_time_s"]))
        if not lo < time_s < hi:
            raise AssertionError(f"analytic {label} crossing escaped authored-key bracket")

    if not (release_capture_time < release_broad_time < 0.25):
        raise AssertionError("release boundary timing order drift")
    if not (2.25 < reengage_broad_time < reengage_capture_time < 2.5):
        raise AssertionError("reengagement boundary timing order drift")

    return {
        "schema": "axm.object-animation-capture-timeline-rebind-evidence/v0.1",
        "result": RESULT,
        "exact_animation_head": exact_head,
        "asset_id": asset_id,
        "host_source_sha256": host_sha,
        "sequence_id": sequence["sequence_id"],
        "sequence_digest": sequence["sequence_digest"],
        "sample_rate_hz": 40,
        "duration_s": 2.5,
        "endpoint_inclusive_sample_count": 101,
        "current_rigging_head": current_rig_head,
        "current_rigging_binding_git_blob_sha": rig_binding_blob_sha,
        "source_capture_authority_head": source_authority_head,
        "source_capture_policy_git_blob_sha": capture_policy_blob_sha,
        "source_capture_transition_deg": capture,
        "z_aabb_only_transition_deg": broad,
        "z_aabb_minus_capture_transition_deg": broad - capture,
        "release_timeline": {
            "proof_volume_contact_to_separation_crossing_time_s": release_capture_time,
            "proof_volume_crossing_authored_key_bracket": release_capture,
            "z_aabb_broad_phase_crossing_time_s": release_broad_time,
            "z_aabb_crossing_authored_key_bracket": release_broad,
            "lid_motion_start_s": 0.25,
            "proof_volume_crossing_to_lid_motion_margin_s": 0.25 - release_capture_time,
            "z_aabb_crossing_to_lid_motion_margin_s": 0.25 - release_broad_time,
        },
        "reengagement_timeline": {
            "lid_neutral_reengagement_start_s": 2.25,
            "z_aabb_broad_phase_reentry_time_s": reengage_broad_time,
            "z_aabb_reentry_authored_key_bracket": reengage_broad,
            "proof_volume_contact_reentry_time_s": reengage_capture_time,
            "proof_volume_reentry_authored_key_bracket": reengage_capture,
            "closed_endpoint_s": 2.5,
        },
        "motion_preservation": {
            "maximum_latch_curve_formula_residual_deg": max_latch_formula_residual,
            "maximum_release_phase_lid_angle_deg": release_lid_residual,
            "maximum_reengagement_phase_lid_angle_deg": reengage_lid_residual,
            "moving_lid_samples_without_exact_50deg_latch": moving_lid_without_terminal_latch,
            "retimed": False,
            "keys_changed": False,
            "easing_changed": False,
            "amplitude_changed": False,
            "source_geometry_changed": False,
            "rig_pivots_changed": False,
            "rig_motion_envelope_changed": False,
        },
        "interpretation": {
            "true_capture_boundary": "SOURCE_OWNED_PROOF_VOLUME_CONTACT_BOUNDARY_NOT_PHYSICAL_RETENTION",
            "historical_48p66_boundary": "Z_AABB_BROAD_PHASE_ONLY_NOT_CAPTURE_THRESHOLD",
            "fifty_degree_endpoint": "SOURCE_REVIEW_RELEASE_POSE_NOT_CAPTURE_THRESHOLD_NOT_RUNTIME_EVENT",
        },
        "runtime_controller_accepted": False,
        "gameplay_accepted": False,
        "final_visual_motion_accepted": False,
        "canon_or_production_ready": False,
        "truth_boundary": "This PASS only rebinds the unchanged Object Animation timeline to the current source-owned proof-volume contact boundary and characterizes when that unchanged curve crosses the true proof-volume and later Z-AABB broad-phase boundaries. It does not turn either boundary into physical latch retention, force, controller, gameplay, device-performance, final visual, CANON or production acceptance.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--sequence-evidence", type=Path, required=True)
    parser.add_argument("--current-rig-receipt", type=Path, required=True)
    parser.add_argument("--current-rig-binding", type=Path, required=True)
    parser.add_argument("--capture-policy", type=Path, required=True)
    parser.add_argument("--current-rig-head", required=True)
    parser.add_argument("--source-authority-head", required=True)
    parser.add_argument("--exact-head", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    sequence = json.loads(args.sequence_evidence.read_text(encoding="utf-8"))
    rig = json.loads(args.current_rig_receipt.read_text(encoding="utf-8"))
    rig_binding = json.loads(args.current_rig_binding.read_text(encoding="utf-8"))
    capture_policy = json.loads(args.capture_policy.read_text(encoding="utf-8"))

    receipt = verify(
        contract,
        sequence,
        rig,
        rig_binding,
        capture_policy,
        current_rig_head=args.current_rig_head,
        source_authority_head=args.source_authority_head,
        rig_binding_blob_sha=git_blob_sha(args.current_rig_binding),
        capture_policy_blob_sha=git_blob_sha(args.capture_policy),
        exact_head=args.exact_head,
    )
    args.out.mkdir(parents=True, exist_ok=True)
    output = args.out / "animation-capture-timeline-rebind-evidence.json"
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
