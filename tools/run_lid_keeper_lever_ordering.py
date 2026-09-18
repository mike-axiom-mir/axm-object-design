from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import verify_lid_keeper_lever_ordering as observer


def _normalized_ownership_for_observer(ownership: dict) -> dict:
    normalized = copy.deepcopy(ownership)
    for row in normalized.get("stations", []):
        source_index = int(row.get("source_index", -1))
        if source_index == 0:
            row["id"] = "left"
        elif source_index == 1:
            row["id"] = "right"
        else:
            raise AssertionError(f"unexpected ownership source_index: {source_index}")
    return normalized


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
    original_ownership = json.loads(args.ownership.read_text(encoding="utf-8"))
    normalized_ownership = _normalized_ownership_for_observer(original_ownership)
    lid_plan = json.loads(args.lid_plan.read_text(encoding="utf-8"))
    source_interface = json.loads(args.source_interface.read_text(encoding="utf-8"))
    source_rig_binding = json.loads(args.source_rig_binding.read_text(encoding="utf-8"))
    animation_authority = json.loads(args.animation_authority.read_text(encoding="utf-8"))
    animation_evidence = json.loads(args.animation_evidence.read_text(encoding="utf-8"))

    original_keeper_verify = observer.keeper_socket.verify

    def keeper_verify_with_source_ids(source_arg, ownership_arg, lid_plan_arg, **kwargs):
        return original_keeper_verify(source_arg, original_ownership, lid_plan_arg, **kwargs)

    observer.keeper_socket.verify = keeper_verify_with_source_ids
    try:
        receipt = observer.verify(
            source,
            normalized_ownership,
            lid_plan,
            source_interface,
            source_rig_binding,
            animation_authority,
            animation_evidence,
            source_sha256=observer.sha256_file(args.source),
            observed_ownership_head=args.observed_ownership_head,
            observed_lid_rig_head=args.observed_lid_rig_head,
            observed_previous_rigging_head=args.observed_previous_rigging_head,
            observed_animation_head=args.observed_animation_head,
            observed_source_rig_head=args.observed_source_rig_head,
            observed_source_interface_head=args.observed_source_interface_head,
        )
    finally:
        observer.keeper_socket.verify = original_keeper_verify

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
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
    print((args.out / "summary.txt").read_text(encoding="utf-8"), end="")


if __name__ == "__main__":
    main()
