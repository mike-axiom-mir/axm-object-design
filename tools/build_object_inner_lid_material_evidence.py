from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

REVIEW_SCHEMA = "axm.object-inner-lid-material-review/v0.2"
SOURCE_SURFACE_SCHEMA = "axm.object-hard-surface-surface-identity/v0.1"
PAYLOAD_SCHEMA = "axm.object-inner-lid-material-lookdev-payload/v0.1"
RECEIPT_SCHEMA = "axm.object-inner-lid-material-lookdev-receipt/v0.2"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_payload(
    base_path: Path,
    review_path: Path,
    source_surface_identity_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    base = load_json(base_path)
    review = load_json(review_path)
    source_identity = load_json(source_surface_identity_path)

    if review.get("schema") != REVIEW_SCHEMA:
        raise AssertionError("inner-lid review schema mismatch")
    if base.get("schema") != review.get("base_articulation_payload_schema"):
        raise AssertionError("base articulation payload schema drift")
    if base.get("asset_id") != review.get("asset_id"):
        raise AssertionError("asset identity drift")
    if base.get("material_profile_sha256") != review.get("base_material_profile_sha256"):
        raise AssertionError("material profile identity drift")
    if base.get("base_geometry_contract_sha256") != review.get("base_geometry_contract_sha256"):
        raise AssertionError("base geometry contract drift")

    source_ref = review.get("source_surface_identity")
    if not isinstance(source_ref, dict):
        raise AssertionError("source surface identity provenance missing")
    if source_ref.get("schema") != SOURCE_SURFACE_SCHEMA:
        raise AssertionError("source surface identity schema reference drift")
    if source_identity.get("schema") != SOURCE_SURFACE_SCHEMA:
        raise AssertionError("source surface identity schema mismatch")
    if source_identity.get("asset_id") != review.get("asset_id"):
        raise AssertionError("source surface asset identity drift")
    if source_identity.get("surface_id") != source_ref.get("surface_id"):
        raise AssertionError("source surface id drift")
    if source_identity.get("surface_id") != "lid_inner_service_surface":
        raise AssertionError("unexpected source inner-lid surface identity")
    if source_identity.get("component_name") != "lid_shell":
        raise AssertionError("source surface component drift")
    if source_identity.get("required_role") != "lid_shell":
        raise AssertionError("source surface role drift")
    if source_identity.get("required_kind") != "box":
        raise AssertionError("source surface kind drift")
    if source_identity.get("surface_semantics") != "interior_service_surface":
        raise AssertionError("source surface semantics drift")

    selector = source_identity.get("selector")
    if not isinstance(selector, dict):
        raise AssertionError("source surface selector missing")
    if selector.get("policy") != "source_local_min_z_face":
        raise AssertionError("source surface selector drift")
    if selector.get("expected_triangle_count") != 2:
        raise AssertionError("source surface triangle scope drift")
    if selector.get("expected_unique_vertex_count") != 4:
        raise AssertionError("source surface vertex scope drift")

    review_provenance = source_identity.get("review_provenance")
    if not isinstance(review_provenance, dict):
        raise AssertionError("source surface review provenance missing")
    if review_provenance.get("repository") != source_ref.get("repository"):
        raise AssertionError("source surface review repository drift")
    if review_provenance.get("pull_request") != 6:
        raise AssertionError("source surface review PR drift")
    if review_provenance.get("head") != source_ref.get("review_parent_head"):
        raise AssertionError("source surface review parent head drift")
    if review_provenance.get("git_blob_sha") != source_ref.get("review_parent_git_blob_sha"):
        raise AssertionError("source surface review parent blob drift")
    if review_provenance.get("review_schema") != "axm.object-inner-lid-material-review/v0.1":
        raise AssertionError("source surface review parent schema drift")
    if review_provenance.get("review_selector") != selector.get("policy"):
        raise AssertionError("source surface review selector drift")

    material_authority = source_identity.get("material_authority")
    if not isinstance(material_authority, dict):
        raise AssertionError("source surface material authority missing")
    if material_authority.get("hard_surface_assigns_material") is not False:
        raise AssertionError("source surface must not assign final material")
    if material_authority.get("source_material_assignment") != "UNASSIGNED":
        raise AssertionError("source surface material assignment must remain UNASSIGNED")
    if material_authority.get("review_material_candidate_adopted") is not False:
        raise AssertionError("Materials review candidate must remain unadopted by source owner")

    source_truth = source_identity.get("truth_boundary", {})
    required_source_truth = {
        "host_source_geometry_changed": False,
        "surface_identity_source_owned": True,
        "material_slot_identity_only": True,
        "material_assignment": False,
        "materials_candidate_adopted": False,
        "art_direction_acceptance": False,
        "visual_qa_acceptance": False,
        "runtime_performance_acceptance": False,
        "canon": False,
        "production_readiness": False,
    }
    for key, expected in required_source_truth.items():
        if source_truth.get(key) is not expected:
            raise AssertionError(f"source surface truth-boundary drift for {key}")

    surface = review.get("surface_review")
    if not isinstance(surface, dict):
        raise AssertionError("surface review missing")
    component_name = surface.get("component_name")
    components = [item for item in base.get("components", []) if item.get("name") == component_name]
    if len(components) != 1:
        raise AssertionError("inner-lid component identity must resolve exactly once")
    component = components[0]
    if component.get("role") != surface.get("required_role"):
        raise AssertionError("inner-lid component role drift")
    if component.get("kind") != surface.get("required_kind") or component.get("kind") != "box":
        raise AssertionError("inner-lid proof currently requires the exact box source representation")
    if surface.get("surface_selector") != "source_local_min_z_face":
        raise AssertionError("unsupported inner-lid face selector")
    if source_identity.get("component_name") != component_name:
        raise AssertionError("Materials component no longer matches source-owned surface")
    if source_identity.get("required_role") != surface.get("required_role"):
        raise AssertionError("Materials role no longer matches source-owned surface")
    if source_identity.get("required_kind") != surface.get("required_kind"):
        raise AssertionError("Materials kind no longer matches source-owned surface")
    if selector.get("policy") != surface.get("surface_selector"):
        raise AssertionError("Materials selector no longer matches source-owned surface")

    materials = base.get("materials", {}).get("candidate", {})
    control_material_id = surface.get("control_material_id")
    candidate_material_id = surface.get("candidate_material_id")
    if component.get("candidate_material") != control_material_id:
        raise AssertionError("control material no longer matches exact lid candidate assignment")
    if control_material_id not in materials or candidate_material_id not in materials:
        raise AssertionError("inner-lid review material identity missing from existing candidate family")
    if control_material_id == candidate_material_id:
        raise AssertionError("inner-lid candidate must differ from uniform-shell control")
    if surface.get("candidate_is_existing_family_member") is not True:
        raise AssertionError("v0.2 inner-lid proof forbids new material family members")
    if surface.get("new_material_scalars_authored") is not False:
        raise AssertionError("v0.2 inner-lid proof forbids new material scalars")
    if materials[control_material_id] == materials[candidate_material_id]:
        raise AssertionError("inner-lid control and candidate material specs are identical")

    poses_by_id = {str(item.get("id")): item for item in base.get("poses", [])}
    selected_poses = []
    for pose_id in review.get("pose_ids", []):
        if pose_id not in poses_by_id:
            raise AssertionError(f"inner-lid pose identity missing: {pose_id}")
        pose = poses_by_id[pose_id]
        if float(pose.get("open_angle_deg", 0.0)) <= 0.0:
            raise AssertionError("inner-lid review requires an open pose")
        selected_poses.append(pose)
    if [item["id"] for item in selected_poses] != ["mid_open", "peak_open"]:
        raise AssertionError("v0.2 inner-lid review requires exact mid_open + peak_open poses")

    base_contexts = set(base.get("camera_contexts", []))
    review_contexts = list(review.get("camera_contexts", []))
    if "three_quarter" not in base_contexts:
        raise AssertionError("base articulation proof lost the shared three_quarter camera")
    if set(review_contexts) != {"three_quarter", "front_interior"}:
        raise AssertionError("inner-lid camera context drift")

    truth = review.get("truth_boundary", {})
    required_truth = {
        "source_geometry_changed": False,
        "source_surface_identity_owned": True,
        "source_material_assignment_authored": False,
        "materials_candidate_adopted_as_source_material": False,
        "review_representation_face_split_only": True,
        "existing_material_scalars_only": True,
        "proof_camera_added_for_inner_face_observation": True,
        "uvs": False,
        "textures": False,
        "art_direction_acceptance": False,
        "visual_qa_acceptance": False,
        "runtime_performance_acceptance": False,
        "canon": False,
    }
    for key, expected in required_truth.items():
        if truth.get(key) is not expected:
            raise AssertionError(f"truth-boundary drift for {key}")

    source_surface_payload = {
        "surface_id": source_identity["surface_id"],
        "component_name": source_identity["component_name"],
        "required_role": source_identity["required_role"],
        "required_kind": source_identity["required_kind"],
        "surface_semantics": source_identity["surface_semantics"],
        "selector": source_identity["selector"],
        "source_head": source_ref["head"],
        "source_path": source_ref["path"],
        "source_git_blob_sha": source_ref["git_blob_sha"],
        "source_contract_sha256": sha256(source_surface_identity_path),
        "material_assignment": source_identity["material_authority"]["source_material_assignment"],
        "materials_candidate_adopted_by_source": source_identity["material_authority"]["review_material_candidate_adopted"],
    }

    payload = {
        "schema": PAYLOAD_SCHEMA,
        "asset_id": base["asset_id"],
        "components": base["components"],
        "materials": base["materials"],
        "hinge_origin_m": base["hinge_origin_m"],
        "direct_moving_component_roles": base["direct_moving_component_roles"],
        "rigid_owner_follow_component_names": base["rigid_owner_follow_component_names"],
        "poses": selected_poses,
        "camera_contexts": review_contexts,
        "surface_review": surface,
        "source_surface_identity": source_surface_payload,
        "base_material_profile_sha256": base["material_profile_sha256"],
        "base_geometry_contract_sha256": base["base_geometry_contract_sha256"],
        "base_articulation_payload_sha256": sha256(base_path),
        "truth_boundary": truth,
    }
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "result": "PASS_SOURCE_OWNED_INNER_LID_EXISTING_FAMILY_SLOT_REBIND",
        "asset_id": base["asset_id"],
        "base_articulation_payload_sha256": payload["base_articulation_payload_sha256"],
        "review_contract_sha256": sha256(review_path),
        "source_surface_identity_sha256": source_surface_payload["source_contract_sha256"],
        "source_surface_id": source_surface_payload["surface_id"],
        "source_surface_head": source_surface_payload["source_head"],
        "source_surface_git_blob_sha": source_surface_payload["source_git_blob_sha"],
        "base_material_profile_sha256": payload["base_material_profile_sha256"],
        "base_geometry_contract_sha256": payload["base_geometry_contract_sha256"],
        "component_name": component_name,
        "surface_selector": surface["surface_selector"],
        "control_material_id": control_material_id,
        "candidate_material_id": candidate_material_id,
        "control_material": materials[control_material_id],
        "candidate_material": materials[candidate_material_id],
        "pose_ids": [item["id"] for item in selected_poses],
        "pose_angles_deg": [float(item["open_angle_deg"]) for item in selected_poses],
        "camera_contexts": review_contexts,
        "new_material_scalars_authored": False,
        "source_geometry_changed": False,
        "source_surface_identity_owned": True,
        "source_material_assignment_authored": False,
        "materials_candidate_adopted_as_source_material": False,
        "truth_boundary": truth,
    }
    return payload, receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="lookdev-proof/generated/object_material_articulation_payload.json")
    parser.add_argument("--review", default="lookdev/inner_lid_surface_review_001.json")
    parser.add_argument(
        "--source-surface-identity",
        default="lookdev-proof/generated/lid-inner-surface-identity-001.json",
    )
    parser.add_argument("--out", default="lookdev-proof/generated")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    payload, receipt = build_payload(
        Path(args.base),
        Path(args.review),
        Path(args.source_surface_identity),
    )
    (out / "object_inner_lid_material_payload.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out / "inner_lid_build_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
