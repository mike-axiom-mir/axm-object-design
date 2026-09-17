from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

CONTROL_MODE = "rebuild_moving_parts_control"
CANDIDATE_MODE = "reuse_moving_parts_transform"
OBS_SCHEMA = "axm.object-lid-latch-runtime-observation/v0.1"
CONTRACT_SCHEMA = "axm.object-lid-latch-runtime-contract/v0.1"
RESULT = "PASS_REUSE_HETEROGENEOUS_LID_LATCH_TARGET_HOST_RESOURCES"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def percent_change(before: float, after: float) -> float | None:
    if before == 0:
        return None
    return ((after - before) / before) * 100.0


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def compare_runtime(
    control: dict[str, Any],
    candidate: dict[str, Any],
    contract: dict[str, Any],
    runtime_head: str,
) -> dict[str, Any]:
    _require(contract.get("schema") == CONTRACT_SCHEMA, "runtime contract schema mismatch")
    for row, mode in ((control, CONTROL_MODE), (candidate, CANDIDATE_MODE)):
        _require(row.get("schema") == OBS_SCHEMA, f"{mode} observation schema mismatch")
        _require(
            row.get("state") == "PASS_TARGET_HOST_LID_LATCH_SAMPLED_RUNTIME_OBSERVATION",
            f"{mode} did not pass target-host observation",
        )
        _require(row.get("mode") == mode, f"{mode} receipt mode drift")
        _require(row.get("promotion_effect") == "NONE", f"{mode} promotion effect drift")
        _require(row.get("asset_id") == contract.get("asset_id"), f"{mode} asset identity drift")
        _require(
            row.get("animation_motion_evidence_head") == contract["animation_dependency"]["commit"],
            f"{mode} Animation donor head drift",
        )
        _require(
            row.get("lid_rig_plan_digest") == contract["lid_rig_dependency"]["plan_digest"],
            f"{mode} lid Rigging plan digest drift",
        )
        _require(
            row.get("latch_rig_dependency_head") == contract["latch_rig_dependency"]["commit"],
            f"{mode} latch Rigging donor head drift",
        )
        _require(
            row.get("latch_rig_plan_sha256") == contract["latch_rig_dependency"]["plan_sha256"],
            f"{mode} latch Rigging plan digest drift",
        )
        _require(
            row.get("ownership_dependency_head") == contract["latch_ownership_dependency"]["commit"],
            f"{mode} Hard-Surface ownership donor head drift",
        )
        _require(
            row.get("ownership_contract_sha256") == contract["latch_ownership_dependency"]["sha256"],
            f"{mode} ownership contract digest drift",
        )
        _require(
            row.get("materials_receiving_base", {}).get("commit") == contract["materials_receiving_base"]["commit"],
            f"{mode} Materials receiving base drift",
        )
        _require(
            row.get("display_sample_count") == contract["required_display_sample_count"],
            f"{mode} display sample count drift",
        )
        _require(
            row.get("endpoint_inclusive_sample_count") == contract["required_endpoint_inclusive_sample_count"],
            f"{mode} endpoint sample count drift",
        )
        _require(row.get("stress_cycles") == contract["stress_cycles"], f"{mode} stress cycle drift")
        _require(row.get("capture_sample_indices") == contract["capture_sample_indices"], f"{mode} capture index drift")
        _require(row.get("camera_contexts") == contract["camera_contexts"], f"{mode} camera context drift")
        _require(
            row.get("moving_component_count") == contract["required_moving_component_count"],
            f"{mode} moving component count drift",
        )

    identity_fields = (
        "source_sha256",
        "sequence_id",
        "sequence_digest",
        "sequence_geometry_digest",
        "base_clip_id",
        "base_clip_digest",
        "lid_rig_plan_digest",
        "latch_rig_dependency_head",
        "latch_rig_plan_sha256",
        "ownership_dependency_head",
        "ownership_contract_sha256",
        "static_component_count",
        "moving_component_count",
        "display_sample_count",
        "endpoint_inclusive_sample_count",
        "evidence_updates",
        "stress_updates",
        "total_updates",
    )
    for field in identity_fields:
        _require(control.get(field) == candidate.get(field), f"control/candidate identity drift for {field}")

    moving_count = int(control["moving_component_count"])
    total_updates = int(control["total_updates"])
    _require(moving_count == int(contract["required_moving_component_count"]), "unexpected moving workload")
    _require(total_updates > 0, "empty moving workload")
    _require(
        total_updates == int(contract["required_display_sample_count"]) * (1 + int(contract["stress_cycles"])),
        "total update count drift",
    )

    control_resources = control["resource_constructions"]
    candidate_resources = candidate["resource_constructions"]
    expected_control = moving_count * total_updates
    expected_candidate = moving_count
    for key in ("moving_nodes", "moving_meshes", "moving_materials"):
        _require(int(control_resources[key]) == expected_control, f"control {key} construction count mismatch")
        _require(int(candidate_resources[key]) == expected_candidate, f"candidate {key} construction count mismatch")
    _require(candidate.get("candidate_resource_identity_stable") is True, "candidate resource identity did not remain stable")

    capture_checks: list[dict[str, Any]] = []
    memory_observations: list[dict[str, Any]] = []
    for sample_index in contract["capture_sample_indices"]:
        key = str(sample_index)
        _require(key in control["captures"] and key in candidate["captures"], f"missing retained sample {key}")
        for context in contract["camera_contexts"]:
            c_shot = control["captures"][key][context]
            n_shot = candidate["captures"][key][context]
            _require(c_shot.get("state") == "PASS" and n_shot.get("state") == "PASS", f"capture failure at {key}/{context}")
            _require(c_shot.get("sha256") == n_shot.get("sha256"), f"visual byte drift at {key}/{context}")
            _require(
                c_shot.get("width") == n_shot.get("width") and c_shot.get("height") == n_shot.get("height"),
                f"capture dimensions drift at {key}/{context}",
            )
            c_runtime = control["selected_runtime_counters"][key][context]
            n_runtime = candidate["selected_runtime_counters"][key][context]
            for counter in ("draw_calls_in_frame", "objects_in_frame", "primitives_in_frame"):
                _require(
                    c_runtime.get(counter) == n_runtime.get(counter),
                    f"renderer submission counter drift at {key}/{context}/{counter}",
                )
            capture_checks.append(
                {
                    "sample_index": sample_index,
                    "context": context,
                    "sha256": c_shot["sha256"],
                    "draw_calls_in_frame": c_runtime["draw_calls_in_frame"],
                    "objects_in_frame": c_runtime["objects_in_frame"],
                    "primitives_in_frame": c_runtime["primitives_in_frame"],
                }
            )
            memory_observations.append(
                {
                    "sample_index": sample_index,
                    "context": context,
                    "control_buffer_mem_bytes": c_runtime["buffer_mem_bytes"],
                    "candidate_buffer_mem_bytes": n_runtime["buffer_mem_bytes"],
                    "buffer_delta_bytes": int(n_runtime["buffer_mem_bytes"]) - int(c_runtime["buffer_mem_bytes"]),
                    "control_texture_mem_bytes": c_runtime["texture_mem_bytes"],
                    "candidate_texture_mem_bytes": n_runtime["texture_mem_bytes"],
                    "texture_delta_bytes": int(n_runtime["texture_mem_bytes"]) - int(c_runtime["texture_mem_bytes"]),
                }
            )

    reduction = 100.0 * (1.0 - (expected_candidate / expected_control))
    c_combined = control["submission_timing_observation"]["combined"]
    n_combined = candidate["submission_timing_observation"]["combined"]
    c_stress = control["submission_timing_observation"]["stress_sequence"]
    n_stress = candidate["submission_timing_observation"]["stress_sequence"]

    checks = {
        "exact_source_sequence_rig_ownership_identity_preserved": True,
        "exact_100_visible_authored_sequence_samples_consumed": int(control["display_sample_count"]) == 100,
        "heterogeneous_moving_component_count_is_seven": moving_count == 7,
        "candidate_moving_resource_identity_stable": candidate["candidate_resource_identity_stable"] is True,
        "construction_counts_match_declared_lifecycle": True,
        "retained_control_candidate_pixels_byte_identical": True,
        "retained_submission_counters_identical": True,
        "synthetic_control_explicit": contract["truth_boundary"].get("synthetic_rebuild_control_not_product_path") is True,
        "review_only_latch_pivot_remains_explicit": contract["truth_boundary"].get("latch_pivot_is_review_only_rig_candidate") is True,
        "physical_latch_not_claimed": contract["truth_boundary"].get("physical_latch_mechanism") is False,
        "target_device_budget_not_claimed": contract["truth_boundary"].get("target_device_fps_or_gpu_budget") is False,
    }
    _require(all(checks.values()), "one or more truth-boundary checks failed")

    return {
        "schema": "axm.object-lid-latch-runtime-comparison/v0.1",
        "state": RESULT,
        "exact_runtime_head": runtime_head,
        "asset_id": control["asset_id"],
        "source_sha256": control["source_sha256"],
        "sequence_id": control["sequence_id"],
        "sequence_digest": control["sequence_digest"],
        "sequence_geometry_digest": control["sequence_geometry_digest"],
        "base_clip_id": control["base_clip_id"],
        "base_clip_digest": control["base_clip_digest"],
        "materials_receiving_base": contract["materials_receiving_base"],
        "animation_dependency": contract["animation_dependency"],
        "lid_rig_dependency": contract["lid_rig_dependency"],
        "latch_rig_dependency": contract["latch_rig_dependency"],
        "latch_ownership_dependency": contract["latch_ownership_dependency"],
        "workload": {
            "moving_component_count": moving_count,
            "display_sample_count_per_cycle": control["display_sample_count"],
            "endpoint_inclusive_sample_count": control["endpoint_inclusive_sample_count"],
            "evidence_updates": control["evidence_updates"],
            "stress_cycles": control["stress_cycles"],
            "stress_updates": control["stress_updates"],
            "total_updates_per_mode": total_updates,
            "retained_capture_pairs": len(capture_checks),
        },
        "measurements": {
            "moving_node_constructions": {
                "control": control_resources["moving_nodes"],
                "candidate": candidate_resources["moving_nodes"],
                "reduction_percent": reduction,
            },
            "moving_mesh_constructions": {
                "control": control_resources["moving_meshes"],
                "candidate": candidate_resources["moving_meshes"],
                "reduction_percent": reduction,
            },
            "moving_material_constructions": {
                "control": control_resources["moving_materials"],
                "candidate": candidate_resources["moving_materials"],
                "reduction_percent": reduction,
            },
            "cpu_side_submission_combined_usec": {
                "control": c_combined,
                "candidate": n_combined,
                "median_change_percent": percent_change(float(c_combined["median_usec"]), float(n_combined["median_usec"])),
                "p95_change_percent": percent_change(float(c_combined["p95_usec"]), float(n_combined["p95_usec"])),
                "total_change_percent": percent_change(float(c_combined["total_usec"]), float(n_combined["total_usec"])),
            },
            "cpu_side_submission_stress_usec": {
                "control": c_stress,
                "candidate": n_stress,
                "median_change_percent": percent_change(float(c_stress["median_usec"]), float(n_stress["median_usec"])),
                "p95_change_percent": percent_change(float(c_stress["p95_usec"]), float(n_stress["p95_usec"])),
                "total_change_percent": percent_change(float(c_stress["total_usec"]), float(n_stress["total_usec"])),
            },
            "retained_memory_counter_observations": memory_observations,
        },
        "retained_visual_and_submission_checks": capture_checks,
        "visual_tradeoff_for_art_director": "NONE_OBSERVED_IN_EXACT_RETAINED_PROOF_FRAMES",
        "checks": checks,
        "truth_boundary": contract["truth_boundary"],
        "non_claims": [
            "no physical latch hook, catch, retention or release mechanism acceptance",
            "no AnimationPlayer, controller or state-machine acceptance",
            "no wall-clock 40 Hz pacing or frame-time acceptance",
            "no target-device FPS, GPU timing, VRAM or allocator acceptance",
            "no exact UC GLB dynamic lid/latch segmentation or playback claim",
            "no collision, physics, interaction or gameplay acceptance",
            "no final Animation, Materials, Art Direction or Visual QA acceptance",
            "no CANON, production readiness or Runtime mastery",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--contract", default="runtime/object_lid_latch_runtime_contract_001.json")
    parser.add_argument("--runtime-head", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    result = compare_runtime(
        load_json(Path(args.control)),
        load_json(Path(args.candidate)),
        load_json(Path(args.contract)),
        args.runtime_head,
    )
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
