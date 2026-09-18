from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

SCHEMA = "axm.object-source-successor-review-disposition/v0.1"
RESULT = "PASS_SOURCE_SUCCESSOR_REVIEW_DISPOSITION_RETAINED"
SUCCESSOR_ID = "modular-equipment-case-001/hinge-bored-knuckle-relative-facet-phase-source-successor-003"
SUCCESSOR_BLOB = "e7a44523ea80e567a745cd61af7fd7005757cc12"
MATERIALS_HEAD = "5509084acbaca2a7d45f072203b98174c621d5ef"
MATERIALS_ARTIFACT_SHA256 = "a0b33464768670b1f9d204ba1ac2e0a5a54327a6ddc5d681132fd68306469309"
ART_PACKET_BLOB = "910871c06902d9c5bb42a2246aa07bdfaa029045"


def git_blob_sha1(path: Path) -> str:
    data = path.read_bytes()
    h = hashlib.sha1()
    h.update(f"blob {len(data)}\0".encode("ascii"))
    h.update(data)
    return h.hexdigest()


def evaluate(successor003: dict, disposition: dict, *, observed_successor_blob_sha1: str | None = None) -> dict:
    if disposition.get("schema") != SCHEMA:
        raise AssertionError("disposition schema drift")
    if disposition.get("asset_id") != "modular-equipment-case-001":
        raise AssertionError("asset identity drift")
    if disposition.get("source_successor_id") != SUCCESSOR_ID:
        raise AssertionError("source successor identity drift")
    if disposition.get("source_successor_contract_git_blob_sha1") != SUCCESSOR_BLOB:
        raise AssertionError("pinned source successor blob drift")
    if observed_successor_blob_sha1 is not None and observed_successor_blob_sha1 != SUCCESSOR_BLOB:
        raise AssertionError("observed source successor blob drift")

    if successor003.get("successor_id") != SUCCESSOR_ID:
        raise AssertionError("source successor semantic identity drift")
    candidate = successor003.get("source_owned_successor", {})
    if candidate.get("owner_group_phase_deg") != {"body": 0.0, "lid": 15.0}:
        raise AssertionError("authored successor003 phase drift")
    if candidate.get("rotate_outer_and_bore_cross_sections_together") is not True:
        raise AssertionError("successor003 cross-section semantics drift")
    if candidate.get("automatic_default_replacement") is not False:
        raise AssertionError("successor003 default authority drift")
    if candidate.get("automatic_downstream_adoption") is not False:
        raise AssertionError("successor003 downstream authority drift")

    review = disposition.get("review_identity", {})
    if review.get("art_direction") != 48:
        raise AssertionError("Art Direction binding drift")
    if review.get("coordination_commit") != "f55363657ae63f88460559b3f0f210cd70a7cb57":
        raise AssertionError("Art coordination commit drift")
    if review.get("packet_git_blob_sha1") != ART_PACKET_BLOB:
        raise AssertionError("Art packet blob drift")
    if review.get("materials_pr") != 6 or review.get("materials_exact_head") != MATERIALS_HEAD:
        raise AssertionError("Materials review identity drift")
    if review.get("materials_workflow_run") != 35327655651:
        raise AssertionError("Materials workflow identity drift")
    if review.get("materials_artifact_id") != 10539926744:
        raise AssertionError("Materials artifact identity drift")
    if review.get("materials_artifact_sha256") != MATERIALS_ARTIFACT_SHA256:
        raise AssertionError("Materials artifact digest drift")

    outcome = disposition.get("review_outcome", {})
    if outcome.get("structural_status") != "PASS_SOURCE_OWNED_HINGE_RELATIVE_FACET_PHASE_SUCCESSOR":
        raise AssertionError("structural predecessor status drift")
    if outcome.get("visual_disposition") != "REJECTED_FOR_CURRENT_HINGE_HIGHLIGHT_REPAIR":
        raise AssertionError("visual disposition drift")
    primary = outcome.get("primary_rear_three_quarter", {})
    if primary.get("result") != "FAIL" or primary.get("near_white_l_ge_0_90_control") != 1625 or primary.get("near_white_l_ge_0_90_candidate") != 1633:
        raise AssertionError("primary review witness drift")
    if abs(float(primary.get("mask_iou", -1.0)) - 0.9902260232) > 1e-12:
        raise AssertionError("primary mask IoU drift")
    grazing = outcome.get("rear_grazing_non_regression", {})
    if grazing.get("result") != "FAIL" or grazing.get("near_white_l_ge_0_90_control") != 0 or grazing.get("near_white_l_ge_0_90_candidate") != 158:
        raise AssertionError("rear-grazing witness drift")
    side = outcome.get("side_three_quarter_reference", {})
    if side.get("result") != "PASS" or side.get("near_white_l_ge_0_90_control") != 0 or side.get("near_white_l_ge_0_90_candidate") != 0:
        raise AssertionError("side reference witness drift")

    state = disposition.get("disposition", {})
    required_false = (
        "adopted_for_current_visual_repair",
        "automatic_default_replacement",
        "automatic_downstream_adoption",
        "phase_sweep_authorized",
        "second_phase_candidate_authorized",
        "source_geometry_rewrite_authorized",
    )
    if state.get("source_successor_retained") is not True or state.get("source_successor_structurally_valid") is not True:
        raise AssertionError("failed successor was not retained as structurally valid evidence")
    for key in required_false:
        if state.get(key) is not False:
            raise AssertionError(f"disposition authority expanded: {key}")

    reference = state.get("current_review_reference", {})
    if reference.get("source_successor") != "modular-equipment-case-001/hinge-bored-knuckle-phase-invariant-source-successor-002":
        raise AssertionError("current review source reference drift")
    if reference.get("relative_owner_phase") != "SYNCHRONIZED_PREDECESSOR_PHASE":
        raise AssertionError("current review phase reference drift")
    if reference.get("hardware_steel_base_color") != "#7E868AFF" or float(reference.get("hardware_steel_metallic")) != 0.88 or float(reference.get("hardware_steel_roughness")) != 0.32:
        raise AssertionError("current review material reference drift")

    next_owner = state.get("next_owner", {})
    if next_owner.get("specialist") != "Technical Art / UC Integration" or next_owner.get("object_pr") != 16:
        raise AssertionError("next owner drift")
    if next_owner.get("requested_candidate") != "ONE_REVIEW_ONLY_HINGE_OUTER_CYLINDER_ANALYTIC_RADIAL_NORMAL_CANDIDATE":
        raise AssertionError("next bounded candidate drift")
    if next_owner.get("hard_surface_geometry_mutation_requested") is not False:
        raise AssertionError("Hard Surface geometry authority reopened")

    authority = disposition.get("authority", {})
    false_authorities = (
        "hard_surface_second_phase_candidate_authorized",
        "materials_retune_authorized",
        "source_default_adoption_authorized",
        "geometry_adoption_authorized",
        "rigging_adoption_authorized",
        "animation_adoption_authorized",
        "runtime_or_physics_adoption_authorized",
        "visual_acceptance_authorized",
        "uc_or_profession_fabric_promotion_authorized",
    )
    for key in false_authorities:
        if authority.get(key) is not False:
            raise AssertionError(f"authority expanded: {key}")
    if authority.get("technical_art_review_candidate_authorized") is not True:
        raise AssertionError("Technical Art review handoff missing")

    return {
        "schema": "axm.object-source-successor-review-disposition-receipt/v0.1",
        "result": RESULT,
        "asset_id": disposition["asset_id"],
        "source_successor_id": SUCCESSOR_ID,
        "source_successor_contract_git_blob_sha1": SUCCESSOR_BLOB,
        "source_successor_structurally_valid": True,
        "visual_disposition": outcome["visual_disposition"],
        "current_review_reference_successor": reference["source_successor"],
        "phase_sweep_authorized": False,
        "second_phase_candidate_authorized": False,
        "next_owner": next_owner["specialist"],
        "next_owner_pr": next_owner["object_pr"],
        "materials_exact_head": MATERIALS_HEAD,
        "materials_artifact_sha256": MATERIALS_ARTIFACT_SHA256,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--successor003", type=Path, required=True)
    parser.add_argument("--disposition", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    successor = json.loads(args.successor003.read_text(encoding="utf-8"))
    disposition = json.loads(args.disposition.read_text(encoding="utf-8"))
    receipt = evaluate(successor, disposition, observed_successor_blob_sha1=git_blob_sha1(args.successor003))
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "relative-facet-phase-disposition-048-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(RESULT)


if __name__ == "__main__":
    main()
