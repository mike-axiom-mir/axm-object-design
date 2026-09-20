from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

CONTRACT_SCHEMA = "axm.object-exact-uc-glb-resource-reuse-contract/v0.2"
RECEIPT_SCHEMA = "axm.object-exact-uc-glb-resource-reuse-observation/v0.2"
RESULT = "PASS_EXACT_UC_GLB_MOVING_RESOURCE_IDENTITY_REUSE"

def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))

def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)

def verify(contract: dict[str, Any], receipt: dict[str, Any], runtime_head: str) -> dict[str, Any]:
    require(contract.get("schema") == CONTRACT_SCHEMA, "contract schema mismatch")
    require(receipt.get("schema") == RECEIPT_SCHEMA, "receipt schema mismatch")
    require(receipt.get("state") == RESULT, "exact UC GLB Runtime observation not green")
    require(receipt.get("animation_sequence_head") == runtime_head, "Runtime sequence receiving head drift")
    require(receipt.get("historical_runtime_head") == contract["historical_runtime_evidence"]["head"], "historical Runtime head drift")
    require(receipt.get("receiving_technical_art_bridge_head") == contract["receiving_technical_art_bridge_head"], "TA bridge receiving head drift")
    require(receipt.get("technical_art_object_head") == contract["technical_art"]["current_head"], "Technical Art head drift")
    require(receipt.get("technical_art_historical_head") == contract["technical_art"]["historical_head"], "historical Technical Art head drift")
    require(receipt.get("uc_commit") == contract["technical_art"]["uc_rigid_head"], "UC rigid donor drift")
    require(receipt.get("glb_sha256") == contract["technical_art"]["rebound_glb_sha256"], "exact repaired GLB drift")
    require(receipt.get("lid_target_binding_result") == "PASS_EXACT_LID_RIG_TO_UC_TARGET_BINDING_READY", "lid target-Rigging binding not green")
    require(receipt.get("front_latch_target_binding_result") == "PASS_SOURCE_OWNED_FRONT_LATCH_CAPTURE_ENVELOPE_TO_UC_TARGET_BINDING_READY", "front latch target-Rigging binding not green")
    require(receipt.get("current_latch_source_rig_head") == contract["target_rigging"]["current_latch_source_rig_head"], "current latch source-Rigging head drift")
    require(receipt.get("sequence_id") == contract["animation_sequence"]["id"], "sequence id drift")
    require(receipt.get("sequence_digest") == contract["animation_sequence"]["digest"], "sequence digest drift")
    require(int(receipt.get("sample_rate_hz", 0)) == contract["animation_sequence"]["sample_rate_hz"], "sample-rate drift")
    require(abs(float(receipt.get("duration_s", -1.0)) - contract["animation_sequence"]["duration_s"]) <= 1e-12, "duration drift")
    require(int(receipt.get("endpoint_inclusive_sample_count", 0)) == contract["animation_sequence"]["endpoint_inclusive_sample_count"], "sample count drift")
    require(int(receipt.get("moving_component_count", 0)) == len(contract["moving_components"]) == 7, "moving component count drift")
    require(receipt.get("moving_component_names") == contract["moving_components"], "moving component identity/order drift")
    require(receipt.get("resource_identity_stable") is True, "moving resource identity was not stable")
    require(int(receipt.get("observed_resource_replacements", -1)) == 0, "moving resource replacement observed")
    require(int(receipt.get("direct_transform_stress_updates", 0)) == contract["workload"]["total_transform_updates"] == 2000, "stress update count drift")
    require(int(receipt.get("direct_transform_stress_cycles", 0)) == contract["workload"]["stress_cycles"] == 20, "stress cycle count drift")
    require(int(receipt.get("repeated_visible_samples_per_cycle", 0)) == contract["workload"]["repeated_visible_samples_per_cycle"] == 100, "samples-per-cycle drift")
    require(float(receipt.get("neutral_pivot_wrapper_max_drift_m", 1.0)) <= 1e-6, "neutral pivot wrapper drift")
    require(float(receipt.get("max_lid_sample_seek_error_deg", 1.0)) <= 1e-4, "lid seek error too large")
    require(float(receipt.get("max_latch_sample_seek_error_deg", 1.0)) <= 1e-4, "latch seek error too large")
    require(float(receipt.get("endpoint_keeper_drift_m", 1.0)) <= 1e-6, "keeper endpoint drift")
    require(float(receipt.get("endpoint_lever_drift_m", 1.0)) <= 1e-6, "lever endpoint drift")
    require(len(receipt.get("captures", {})) == len(contract["workload"]["selected_capture_indices"]), "capture count drift")
    truth = receipt.get("truth_boundary", {})
    require(truth.get("exact_uc_glb_moving_resource_identity_stable_across_2000_updates") is True, "exact GLB reuse claim missing")
    require(truth.get("moving_node_mesh_material_replacement_observed") is False, "resource replacement truth boundary drift")
    require(truth.get("historical_99_95_percent_reduction_transferred_to_exact_uc_glb") is False, "historical comparison was silently transferred")
    require(contract["truth_boundary"]["historical_99_95_percent_reduction_is_not_transferred_to_exact_uc_glb"] is True, "contract historical-comparison boundary drift")
    require(contract["truth_boundary"]["synthetic_rebuild_control_on_exact_uc_glb"] is False, "contract unexpectedly claims exact-GLB synthetic control")
    result = {
        "schema": "axm.object-exact-uc-glb-resource-reuse-verification/v0.2",
        "result": RESULT,
        "exact_runtime_head": runtime_head,
        "historical_runtime_head": receipt["historical_runtime_head"],
        "receiving_technical_art_bridge_head": receipt["receiving_technical_art_bridge_head"],
        "technical_art_head": receipt["technical_art_object_head"],
        "glb_sha256": receipt["glb_sha256"],
        "sequence_id": receipt["sequence_id"],
        "sequence_digest": receipt["sequence_digest"],
        "moving_component_count": receipt["moving_component_count"],
        "direct_transform_stress_updates": receipt["direct_transform_stress_updates"],
        "resource_identity_stable": True,
        "observed_resource_replacements": 0,
        "historical_comparative_result_status": "PRESERVED_SEPARATELY_NOT_TRANSFERRED",
        "truth_boundary": {
            "exact_current_uc_glb_reuse_observed": True,
            "historical_99_95_percent_comparison_reused_as_current_measurement": False,
            "controller_state_machine_or_wall_clock_acceptance": False,
            "target_device_performance_acceptance": False,
            "physics_gameplay_or_final_visual_acceptance": False,
        },
    }
    return result

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--contract", type=Path, required=True)
    p.add_argument("--receipt", type=Path, required=True)
    p.add_argument("--runtime-head", required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    result = verify(load(a.contract), load(a.receipt), a.runtime_head)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
