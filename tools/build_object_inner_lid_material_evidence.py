from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

REVIEW_SCHEMA = "axm.object-inner-lid-material-review/v0.1"
PAYLOAD_SCHEMA = "axm.object-inner-lid-material-lookdev-payload/v0.1"
RECEIPT_SCHEMA = "axm.object-inner-lid-material-lookdev-receipt/v0.1"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_payload(base_path: Path, review_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    base = load_json(base_path)
    review = load_json(review_path)

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
        raise AssertionError("v0.1 inner-lid proof forbids new material family members")
    if surface.get("new_material_scalars_authored") is not False:
        raise AssertionError("v0.1 inner-lid proof forbids new material scalars")
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
        raise AssertionError("v0.1 inner-lid review requires exact mid_open + peak_open poses")

    base_contexts = set(base.get("camera_contexts", []))
    review_contexts = list(review.get("camera_contexts", []))
    if "three_quarter" not in base_contexts:
        raise AssertionError("base articulation proof lost the shared three_quarter camera")
    if set(review_contexts) != {"three_quarter", "front_interior"}:
        raise AssertionError("inner-lid camera context drift")

    truth = review.get("truth_boundary", {})
    required_truth = {
        "source_geometry_changed": False,
        "source_material_slot_authored": False,
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
        "base_material_profile_sha256": base["material_profile_sha256"],
        "base_geometry_contract_sha256": base["base_geometry_contract_sha256"],
        "base_articulation_payload_sha256": sha256(base_path),
        "truth_boundary": truth,
    }
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "result": "PASS_SOURCE_BOUND_INNER_LID_EXISTING_FAMILY_SLOT_PAYLOAD",
        "asset_id": base["asset_id"],
        "base_articulation_payload_sha256": payload["base_articulation_payload_sha256"],
        "review_contract_sha256": sha256(review_path),
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
        "truth_boundary": truth,
    }
    return payload, receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="lookdev-proof/generated/object_material_articulation_payload.json")
    parser.add_argument("--review", default="lookdev/inner_lid_surface_review_001.json")
    parser.add_argument("--out", default="lookdev-proof/generated")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    payload, receipt = build_payload(Path(args.base), Path(args.review))
    (out / "object_inner_lid_material_payload.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out / "inner_lid_build_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
