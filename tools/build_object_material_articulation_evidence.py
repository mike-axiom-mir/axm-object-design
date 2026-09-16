from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from build_object_material_lookdev_evidence import build_payload, canonical_digest, sha256

REVIEW_SCHEMA = "axm.object-articulated-material-review/v0.1"
CLIP_SCHEMA = "axm.object-motion-clip/v0.1"
RIG_SCHEMA = "axm.object-articulation-plan/v0.1"
PAYLOAD_SCHEMA = "axm.object-articulated-material-lookdev-payload/v0.1"
RECEIPT_SCHEMA = "axm.object-articulated-material-lookdev-receipt/v0.1"
EPS = 1e-9


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def smoothstep(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return t * t * (3.0 - 2.0 * t)


def angle_at(clip: dict[str, Any], time_s: float) -> float:
    for index, phase in enumerate(clip["phases"]):
        start = float(phase["start_s"])
        end = float(phase["end_s"])
        if time_s + EPS < start:
            continue
        if time_s <= end + EPS or index == len(clip["phases"]) - 1:
            a0 = float(phase["start_angle_deg"])
            a1 = float(phase["end_angle_deg"])
            easing = phase["easing"]
            if easing == "constant":
                return a0
            if easing != "smoothstep":
                raise AssertionError(f"unsupported easing {easing!r}")
            u = 0.0 if abs(end - start) <= EPS else (time_s - start) / (end - start)
            return a0 + (a1 - a0) * smoothstep(u)
    raise AssertionError(f"time {time_s} outside animation phases")


def validate_dependencies(
    host_path: Path,
    review: dict[str, Any],
    clip: dict[str, Any],
    rig: dict[str, Any],
) -> dict[str, Any]:
    if review.get("schema") != REVIEW_SCHEMA:
        raise AssertionError("articulated material review schema mismatch")
    if clip.get("schema") != CLIP_SCHEMA:
        raise AssertionError("animation clip schema mismatch")
    if rig.get("schema") != RIG_SCHEMA:
        raise AssertionError("rig schema mismatch")
    host = load_json(host_path)
    host_sha = sha256(host_path)
    asset_id = review.get("asset_id")
    if clip.get("asset_id") != asset_id or rig.get("asset_id") != asset_id or host.get("asset_id") != asset_id:
        raise AssertionError("asset identity drift")
    if clip.get("source_sha256") != host_sha or rig.get("source_sha256") != host_sha:
        raise AssertionError("source digest drift")
    animation_dependency = review.get("animation_dependency", {})
    rig_dependency = review.get("rig_dependency", {})
    if animation_dependency.get("clip_id") != clip.get("clip_id"):
        raise AssertionError("animation clip identity drift")
    if rig_dependency.get("joint_id") != clip.get("joint_id"):
        raise AssertionError("review joint identity drift")
    if clip.get("rig_dependency", {}).get("commit") != rig_dependency.get("commit"):
        raise AssertionError("clip rig commit drift")
    observed_rig_digest = canonical_digest(rig)
    if rig_dependency.get("plan_digest") != observed_rig_digest:
        raise AssertionError("review rig plan digest drift")
    if clip.get("rig_dependency", {}).get("plan_digest") != observed_rig_digest:
        raise AssertionError("clip rig plan digest drift")
    joint = rig.get("joint", {})
    if joint.get("id") != rig_dependency.get("joint_id"):
        raise AssertionError("rig joint identity drift")
    if joint.get("moving_component") != "lid_shell" or joint.get("fixed_component") != "body_shell":
        raise AssertionError("unexpected rig component identity")
    if joint.get("opening_rotation_sign") != -1:
        raise AssertionError("unexpected opening rotation sign")
    if joint.get("axis_source") != "hinge.axis" or host.get("hinge", {}).get("axis") != [1, 0, 0]:
        raise AssertionError("unexpected hinge axis identity")
    dimensions = host["dimensions_m"]
    hinge = host["hinge"]
    hinge_origin = [
        0.0,
        float(dimensions["depth"]) / 2.0 + float(hinge["offset_y"]),
        float(dimensions["body_height"]) + float(hinge["offset_z"]),
    ]
    return {
        "host_source_sha256": host_sha,
        "clip_digest": canonical_digest(clip),
        "rig_plan_digest": observed_rig_digest,
        "hinge_origin_m": hinge_origin,
    }


def build_articulation_payload(
    host_path: Path,
    module_path: Path,
    profile_path: Path,
    review_path: Path,
    clip_path: Path,
    rig_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    base_payload, base_receipt = build_payload(host_path, module_path, profile_path)
    review = load_json(review_path)
    clip = load_json(clip_path)
    rig = load_json(rig_path)
    dependency_receipt = validate_dependencies(host_path, review, clip, rig)

    sign = int(rig["joint"]["opening_rotation_sign"])
    poses = []
    for spec in review.get("pose_samples", []):
        time_s = float(spec["time_s"])
        angle = angle_at(clip, time_s)
        expected = float(spec["expected_open_angle_deg"])
        if abs(angle - expected) > EPS:
            raise AssertionError(f"pose {spec['id']} expected {expected} deg but clip evaluates to {angle}")
        poses.append(
            {
                "id": spec["id"],
                "time_s": time_s,
                "open_angle_deg": angle,
                "mathematical_rotation_deg": sign * angle,
            }
        )
    if len(poses) < 3 or len({round(float(p["open_angle_deg"]), 9) for p in poses}) < 3:
        raise AssertionError("articulated material review requires at least three distinct poses")

    moving_roles = list(review.get("moving_component_roles", []))
    component_roles = {component["role"] for component in base_payload["components"]}
    missing_roles = sorted(set(moving_roles) - component_roles)
    if missing_roles:
        raise AssertionError(f"moving material roles missing from proof geometry: {missing_roles}")

    payload = {
        "schema": PAYLOAD_SCHEMA,
        "asset_id": review["asset_id"],
        "components": base_payload["components"],
        "materials": base_payload["materials"],
        "material_profile_sha256": sha256(profile_path),
        "base_geometry_contract_sha256": base_receipt["geometry_contract_sha256"],
        "animation_dependency": review["animation_dependency"],
        "rig_dependency": review["rig_dependency"],
        "animation_clip_digest": dependency_receipt["clip_digest"],
        "observed_rig_plan_digest": dependency_receipt["rig_plan_digest"],
        "hinge_origin_m": dependency_receipt["hinge_origin_m"],
        "moving_component_roles": moving_roles,
        "poses": poses,
        "camera_contexts": list(review.get("camera_contexts", [])),
        "truth_boundary": review["truth_boundary"],
    }
    if set(payload["camera_contexts"]) != {"three_quarter", "rear_hinge"}:
        raise AssertionError("v0.1 articulation lookdev requires exact three_quarter + rear_hinge cameras")

    receipt = {
        "schema": RECEIPT_SCHEMA,
        "result": "PASS_SOURCE_BOUND_ARTICULATED_MATERIAL_REVIEW_PAYLOAD",
        "host_source_sha256": dependency_receipt["host_source_sha256"],
        "module_source_sha256": sha256(module_path),
        "material_profile_sha256": sha256(profile_path),
        "review_contract_sha256": sha256(review_path),
        "animation_clip_sha256": sha256(clip_path),
        "animation_clip_digest": dependency_receipt["clip_digest"],
        "rig_file_sha256": sha256(rig_path),
        "rig_plan_digest": dependency_receipt["rig_plan_digest"],
        "hinge_origin_m": dependency_receipt["hinge_origin_m"],
        "base_material_payload_result": base_receipt["result"],
        "base_geometry_contract_sha256": base_receipt["geometry_contract_sha256"],
        "pose_count": len(poses),
        "pose_angles_deg": [p["open_angle_deg"] for p in poses],
        "camera_contexts": payload["camera_contexts"],
        "moving_component_roles": moving_roles,
        "truth_boundary": payload["truth_boundary"],
    }
    return payload, receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="assets/modular-equipment-case-001/source.json")
    parser.add_argument("--module", default="assets/modular-equipment-case-001/utility-module-001.json")
    parser.add_argument("--profile", default="lookdev/object_material_profile_001.json")
    parser.add_argument("--review", default="lookdev/articulated_material_review_001.json")
    parser.add_argument("--clip", default="lookdev-proof/generated/lid-motion-clip.json")
    parser.add_argument("--rig", default="lookdev-proof/generated/articulation.json")
    parser.add_argument("--out", default="lookdev-proof/generated")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    payload, receipt = build_articulation_payload(
        Path(args.host),
        Path(args.module),
        Path(args.profile),
        Path(args.review),
        Path(args.clip),
        Path(args.rig),
    )
    (out / "object_material_articulation_payload.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out / "articulation_build_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
