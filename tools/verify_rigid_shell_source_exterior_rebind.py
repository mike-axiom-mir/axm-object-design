from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from tools.verify_rigid_shell_orientation import build_evidence as build_historical_orientation_evidence

POLICY_SCHEMA = "axm.object-geometry-rigid-shell-source-exterior-rebind/v0.1"
RECEIPT_SCHEMA = "axm.object-geometry-rigid-shell-source-exterior-rebind-receipt/v0.1"
EXPECTED_ASSET_ID = "modular-equipment-case-001"
EXPECTED_SOURCE_SHA256 = "49b1f9ed9865893d6de6f1ec8f069576732df694853fde4e3fcff366de32644a"
EXPECTED_HISTORICAL_GEOMETRY_HEAD = "606d8189a3bf4502141d8038f08d35d421829dde"
EXPECTED_HISTORICAL_RESULT = "PASS_DERIVED_RIGID_SHELL_OUTWARD_ORIENTATION_CANDIDATE"
EXPECTED_HARD_SURFACE_HEAD = "77a4058b305fab7fd04dab94781b9460f089727e"
EXPECTED_HARD_SURFACE_CONTRACT_BLOB = "a9f3c40868f7d77c524738155178af51c91b947e"
EXPECTED_CANONICAL_EXTERIOR_FACE_ORDER_DIGEST = "3a28b04f065cd58a21a310588ab4cecce54878c67b41793439d358c837647d63"
EXPECTED_FACE_COUNT = 812
EXPECTED_GROUP_COUNT = 31


def git_blob_sha1(path: Path) -> str:
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode("utf-8")
    return hashlib.sha1(header + data).hexdigest()


def candidate_face_order_digest(candidate_mesh: dict[str, Any]) -> str:
    faces = candidate_mesh["faces"]
    groups = candidate_mesh["groups"]
    if len(faces) != EXPECTED_FACE_COUNT:
        raise AssertionError("Geometry candidate triangle-count drift")
    if len(groups) != EXPECTED_GROUP_COUNT:
        raise AssertionError("Geometry candidate rigid-group-count drift")

    group_by_first = {group["first_face"]: group for group in groups}
    current_group = None
    lines: list[str] = []
    for face_index, face in enumerate(faces):
        if face_index in group_by_first:
            current_group = group_by_first[face_index]
        if current_group is None:
            raise AssertionError("Geometry candidate face precedes first rigid group")
        first = current_group["first_face"]
        end = first + current_group["face_count"]
        if not (first <= face_index < end):
            raise AssertionError("Geometry candidate rigid-group ranges are not contiguous")
        lines.append(
            f"{current_group['name']}|{face_index}|{face[0]},{face[1]},{face[2]}"
        )
    return hashlib.sha256(("\n".join(lines) + "\n").encode("utf-8")).hexdigest()


def validate_rebind_policy(policy: dict[str, Any]) -> None:
    if policy.get("schema") != POLICY_SCHEMA:
        raise AssertionError("unexpected Geometry source-exterior rebind schema")
    if policy.get("asset_id") != EXPECTED_ASSET_ID:
        raise AssertionError("unexpected Geometry source-exterior rebind asset")
    if policy.get("source_sha256") != EXPECTED_SOURCE_SHA256:
        raise AssertionError("Geometry source-exterior rebind source identity drift")

    historical = policy.get("historical_geometry_candidate", {})
    if historical.get("exact_head") != EXPECTED_HISTORICAL_GEOMETRY_HEAD:
        raise AssertionError("historical Geometry candidate identity drift")
    if historical.get("result") != EXPECTED_HISTORICAL_RESULT:
        raise AssertionError("historical Geometry result identity drift")

    hard_surface = policy.get("hard_surface_exterior_intent", {})
    if hard_surface.get("exact_head") != EXPECTED_HARD_SURFACE_HEAD:
        raise AssertionError("Hard-Surface exterior-intent donor identity drift")
    if hard_surface.get("contract_git_blob") != EXPECTED_HARD_SURFACE_CONTRACT_BLOB:
        raise AssertionError("Hard-Surface exterior-intent contract blob drift")
    if hard_surface.get("canonical_exterior_face_order_digest") != EXPECTED_CANONICAL_EXTERIOR_FACE_ORDER_DIGEST:
        raise AssertionError("Hard-Surface canonical exterior face-order digest drift")
    if hard_surface.get("expected_face_matches") != EXPECTED_FACE_COUNT:
        raise AssertionError("Hard-Surface exact face-match count drift")
    if hard_surface.get("expected_face_mismatches") != 0:
        raise AssertionError("Hard-Surface source-exterior donor must retain zero mismatches")
    if hard_surface.get("authority") != "source_exterior_semantics_only":
        raise AssertionError("Hard-Surface authority boundary drift")

    sign = policy.get("signed_volume_semantics", {})
    if sign.get("positive_signed_volume_defines_outward") is not False:
        raise AssertionError("positive algebraic signed volume may not define outward semantics")
    if not sign.get("source_frame"):
        raise AssertionError("signed-volume source frame must remain explicit")

    if policy.get("source_geometry_changed") is not False:
        raise AssertionError("Geometry rebind may not rewrite source geometry")
    if policy.get("candidate_geometry_changed") is not False:
        raise AssertionError("semantic rebind may not relabel the historical candidate as changed")
    if policy.get("source_adopted") is not False:
        raise AssertionError("Geometry rebind may not self-authorize source adoption")
    if policy.get("candidate_authority") != "geometry_topology_structural_review_only":
        raise AssertionError("Geometry rebind authority boundary drift")
    for key in (
        "hard_surface_authority_preserved",
        "technical_art_transport_authority_preserved",
        "materials_art_qa_authority_preserved",
        "runtime_authority_preserved",
        "gameplay_collision_authority_preserved",
    ):
        if policy.get(key) is not True:
            raise AssertionError(f"authority boundary weakened: {key}")


def validate_hard_surface_receipt(receipt: dict[str, Any]) -> None:
    if receipt.get("schema") != "axm.object-rigid-shell-exterior-intent-receipt/v0.1":
        raise AssertionError("unexpected Hard-Surface exterior-intent receipt schema")
    if receipt.get("asset_id") != EXPECTED_ASSET_ID:
        raise AssertionError("unexpected Hard-Surface exterior-intent asset")
    if receipt.get("result") != "PASS_SOURCE_OWNED_RIGID_SHELL_EXTERIOR_INTENT":
        raise AssertionError("Hard-Surface source-exterior donor is not PASS")
    if receipt.get("source_sha256") != EXPECTED_SOURCE_SHA256:
        raise AssertionError("Hard-Surface source identity drift")
    if receipt.get("canonical_exterior_face_order_digest") != EXPECTED_CANONICAL_EXTERIOR_FACE_ORDER_DIGEST:
        raise AssertionError("Hard-Surface canonical exterior digest drift")
    if receipt.get("source_triangle_winding_rewritten") is not False:
        raise AssertionError("Hard-Surface donor may not rewrite source triangle winding")
    if receipt.get("geometry_candidate_adopted") is not False:
        raise AssertionError("Hard-Surface donor may not adopt the Geometry candidate")
    if receipt.get("renderer_front_face_selected") is not False:
        raise AssertionError("Hard-Surface donor may not choose renderer front-face policy")

    probe = receipt.get("geometry_compatibility_probe", {})
    if probe.get("geometry_candidate_exact_head") != EXPECTED_HISTORICAL_GEOMETRY_HEAD:
        raise AssertionError("Hard-Surface receipt Geometry donor identity drift")
    if probe.get("geometry_candidate_faces_matching_source_exterior_intent") != EXPECTED_FACE_COUNT:
        raise AssertionError("Hard-Surface receipt does not prove all candidate faces match source exterior intent")
    if probe.get("geometry_candidate_face_mismatches") != 0:
        raise AssertionError("Hard-Surface receipt retains Geometry/source-exterior mismatches")
    if probe.get("geometry_candidate_compatibility") != "PASS_EXACT_FACE_ORDER_COMPATIBILITY_EVIDENCE_ONLY":
        raise AssertionError("Hard-Surface Geometry compatibility state drift")
    if probe.get("geometry_candidate_adopted") is not False:
        raise AssertionError("Hard-Surface compatibility probe may not authorize adoption")


def build_rebind_evidence(
    source_path: Path,
    historical_policy_path: Path,
    rebind_policy_path: Path,
    hard_surface_receipt_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    policy = json.loads(rebind_policy_path.read_text(encoding="utf-8"))
    validate_rebind_policy(policy)
    hard_surface_receipt = json.loads(hard_surface_receipt_path.read_text(encoding="utf-8"))
    validate_hard_surface_receipt(hard_surface_receipt)

    historical_receipt, candidate_mesh = build_historical_orientation_evidence(
        source_path, historical_policy_path
    )
    if historical_receipt.get("result") != EXPECTED_HISTORICAL_RESULT:
        raise AssertionError("historical Geometry orientation result drift")
    if historical_receipt.get("source_sha256") != EXPECTED_SOURCE_SHA256:
        raise AssertionError("historical Geometry source identity drift")
    if historical_receipt.get("candidate_orientation_conflict_edges") != 0:
        raise AssertionError("historical Geometry candidate orientation conflicts returned")
    if historical_receipt.get("candidate_flipped_faces") != 508:
        raise AssertionError("historical Geometry candidate winding identity drift")

    digest = candidate_face_order_digest(candidate_mesh)
    if digest != EXPECTED_CANONICAL_EXTERIOR_FACE_ORDER_DIGEST:
        raise AssertionError(
            "unchanged Geometry candidate no longer matches the exact Hard-Surface source-exterior face order"
        )

    receipt = {
        "schema": RECEIPT_SCHEMA,
        "asset_id": EXPECTED_ASSET_ID,
        "result": "PASS_DERIVED_RIGID_SHELL_SOURCE_EXTERIOR_COHERENT_ORIENTATION_CANDIDATE",
        "pattern": "COHERENT_WINDING_REQUIRES_EXACT_SOURCE_EXTERIOR_BIND__SIGNED_VOLUME_IS_FRAME_BOUND_DIAGNOSTIC",
        "source_sha256": EXPECTED_SOURCE_SHA256,
        "historical_geometry_candidate_exact_head": EXPECTED_HISTORICAL_GEOMETRY_HEAD,
        "historical_geometry_result_preserved": EXPECTED_HISTORICAL_RESULT,
        "historical_candidate_flipped_faces": historical_receipt["candidate_flipped_faces"],
        "historical_candidate_orientation_conflict_edges": historical_receipt["candidate_orientation_conflict_edges"],
        "hard_surface_exterior_intent_exact_head": EXPECTED_HARD_SURFACE_HEAD,
        "hard_surface_contract_git_blob": EXPECTED_HARD_SURFACE_CONTRACT_BLOB,
        "hard_surface_canonical_exterior_face_order_digest": EXPECTED_CANONICAL_EXTERIOR_FACE_ORDER_DIGEST,
        "candidate_face_order_digest": digest,
        "candidate_faces_matching_source_exterior_intent": EXPECTED_FACE_COUNT,
        "candidate_face_mismatches": 0,
        "candidate_source_exterior_coherent": True,
        "candidate_positive_signed_volume_groups_in_source_frame": historical_receipt["candidate_positive_signed_volume_groups"],
        "positive_signed_volume_defines_outward": False,
        "signed_volume_semantics": "algebraic orientation diagnostic in the declared Object source frame only; handedness-changing transport may reverse sign",
        "source_geometry_changed": False,
        "candidate_geometry_changed": False,
        "source_adopted": False,
        "technical_art_transport_adopted": False,
        "renderer_front_face_selected": False,
        "materials_art_qa_accepted": False,
        "runtime_adopted": False,
        "gameplay_collision_adopted": False,
        "hard_surface_receipt_result": hard_surface_receipt["result"],
        "truth_boundary": policy["truth_boundary"],
        "limitations": [
            "the historical Geometry candidate bytes are preserved; this pass repairs semantic grounding rather than mesh geometry",
            "source-exterior meaning comes from the exact Hard-Surface owner receipt, not from algebraic signed-volume sign",
            "positive signed volume remains only a descriptive source-frame observation and is not a universal outward rule",
            "Technical Art retains coordinate/parity transport and target-host front-face adaptation authority",
            "Materials, Art Direction and independent Visual QA retain rendered/culling acceptance",
            "no source adoption, Runtime/device, physics/gameplay, CANON, production-readiness, game-readiness or Geometry-mastery claim",
        ],
    }
    return receipt, candidate_mesh


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        default="assets/modular-equipment-case-001/source.json",
        type=Path,
    )
    parser.add_argument(
        "--historical-policy",
        default="assets/modular-equipment-case-001/rigid-shell-orientation-review-001.json",
        type=Path,
    )
    parser.add_argument(
        "--rebind-policy",
        default="assets/modular-equipment-case-001/rigid-shell-source-exterior-rebind-001.json",
        type=Path,
    )
    parser.add_argument("--hard-surface-receipt", required=True, type=Path)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()

    receipt, _ = build_rebind_evidence(
        args.source,
        args.historical_policy,
        args.rebind_policy,
        args.hard_surface_receipt,
    )
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
