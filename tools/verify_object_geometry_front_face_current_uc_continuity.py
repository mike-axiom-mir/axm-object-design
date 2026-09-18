from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

RESULT = "PASS_OBJECT_GEOMETRY_MERGED_UC_ORIENTATION_TO_CURRENT_UC_TRANSPORT_CONTINUITY"
SCHEMA = "axm.object-technical-art-orientation-transport-continuity/v0.1"

HISTORICAL_GEOMETRY_HEAD = "606d8189a3bf4502141d8038f08d35d421829dde"
CURRENT_GEOMETRY_REBIND_HEAD = "444e6a10be53e883e8aee0a75b2b93b74cee3dbd"
HARD_SURFACE_HEAD = "77a4058b305fab7fd04dab94781b9460f089727e"
UC_ORIENTATION_MERGE = "13a823349a568db266099564d6f5d8d7bac48b2b"
UC_TOPOLOGY_BLOB = "b82c812d9c98799d0ccefa416ba2bd8d813245ee"
UC_ORIENTATION_BLOB = "c8edfccbd49aa0e8aacf62a51b18440ef7499ac0"
UC_PROCEDURAL_BLOB = "cdb654d4d0f68a4ca7539d98a985d7a70cf7ee36"
UC_RIGID_SCENE_GRAPH_BLOB = "fada5e5e06e110b48c7c9886e6a7f73c5c3a2d44"
EXPECTED_SOURCE_SHA256 = "49b1f9ed9865893d6de6f1ec8f069576732df694853fde4e3fcff366de32644a"
EXPECTED_CORRECTED_GLB_SHA256 = "c3326180d7626b224e16d372c2ff5f6fe47a6c9d13241d8225cea7629e58bd83"
EXPECTED_UNADAPTED_GLB_SHA256 = "708926421688fbc9cc727aadb21023b4e543b174ac1434fd5387d732c2d498a2"
EXPECTED_GROUPS = 31
EXPECTED_TRIANGLES = 812


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_head(root: Path) -> str:
    return subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()


def git_blob(root: Path, relative_path: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", f"HEAD:{relative_path}"], text=True
    ).strip()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def validate(
    *,
    geometry_rebind_root: Path,
    geometry_rebind_receipt_path: Path,
    historical_candidate_path: Path,
    rebound_candidate_path: Path,
    front_face_transport_receipt_path: Path,
    current_uc_root: Path,
    expected_current_uc_head: str,
) -> dict[str, Any]:
    geometry_head = git_head(geometry_rebind_root)
    current_uc_head = git_head(current_uc_root)
    require(geometry_head == CURRENT_GEOMETRY_REBIND_HEAD, "Geometry merged-UC rebind head drift")
    require(current_uc_head == expected_current_uc_head, "current UC head drift")

    geometry = json.loads(geometry_rebind_receipt_path.read_text(encoding="utf-8"))
    require(
        geometry.get("result") == "PASS_OBJECT_RIGID_SHELL_MERGED_UC_ORIENTATION_OBSERVER_REBIND",
        "Geometry merged-UC orientation rebind is not green",
    )
    require(geometry.get("source_sha256") == EXPECTED_SOURCE_SHA256, "Geometry source identity drift")
    require(
        geometry.get("historical_local_candidate_exact_head") == HISTORICAL_GEOMETRY_HEAD,
        "Geometry historical candidate provenance drift",
    )
    require(int(geometry.get("rigid_groups", -1)) == EXPECTED_GROUPS, "Geometry rigid-group drift")
    require(int(geometry.get("source_shared_orientation_conflicts", -1)) == 304, "source conflict drift")
    require(int(geometry.get("candidate_shared_orientation_conflicts", -1)) == 0, "candidate conflict drift")
    require(
        int(geometry.get("candidate_groups_requiring_shared_diagnostic_flips", -1)) == 0,
        "merged UC requests fresh candidate flips",
    )
    require(int(geometry.get("parity_compatible_groups", -1)) == EXPECTED_GROUPS, "parity compatibility drift")
    require(int(geometry.get("candidate_volume_matching_groups", -1)) == EXPECTED_GROUPS, "volume continuity drift")
    require(geometry.get("positive_signed_volume_defines_outward") is False, "shared sign became exterior authority")
    require(geometry.get("source_adopted") is False, "Geometry source adoption authority inflation")
    require(geometry.get("candidate_adopted") is False, "Geometry candidate adoption authority inflation")
    budget = geometry.get("work_budget_negative_control", {})
    require(budget.get("inspection_complete") is False, "Geometry budget negative lost fail-closed state")
    require(budget.get("orientability_state") == "NOT_EVALUATED", "Geometry budget negative emitted verdict")
    require(budget.get("reason") == "TRIANGLE_WORK_BUDGET_EXCEEDED", "Geometry budget negative reason drift")
    require(budget.get("partial_parity_emitted") is False, "Geometry budget negative emitted partial parity")

    merged = geometry.get("merged_uc_observer", {})
    require(merged.get("merge_commit") == UC_ORIENTATION_MERGE, "Geometry UC merge identity drift")
    require(merged.get("mesh_topology_blob") == UC_TOPOLOGY_BLOB, "Geometry topology blob drift")
    require(merged.get("mesh_closed_orientation_blob") == UC_ORIENTATION_BLOB, "Geometry orientation blob drift")

    historical_candidate_sha = sha256_file(historical_candidate_path)
    rebound_candidate_sha = sha256_file(rebound_candidate_path)
    require(historical_candidate_sha == rebound_candidate_sha, "merged-UC Geometry rebind changed candidate OBJ bytes")

    current_uc_blobs = {
        "mesh_topology.py": git_blob(current_uc_root, "src/axm_uc/mesh_topology.py"),
        "mesh_closed_orientation.py": git_blob(current_uc_root, "src/axm_uc/mesh_closed_orientation.py"),
        "procedural_3d.py": git_blob(current_uc_root, "src/axm_uc/procedural_3d.py"),
        "rigid_scene_graph.py": git_blob(current_uc_root, "src/axm_uc/rigid_scene_graph.py"),
    }
    require(current_uc_blobs["mesh_topology.py"] == UC_TOPOLOGY_BLOB, "current UC topology observer drift")
    require(current_uc_blobs["mesh_closed_orientation.py"] == UC_ORIENTATION_BLOB, "current UC orientation observer drift")
    require(current_uc_blobs["procedural_3d.py"] == UC_PROCEDURAL_BLOB, "current UC GLB publisher drift")
    require(current_uc_blobs["rigid_scene_graph.py"] == UC_RIGID_SCENE_GRAPH_BLOB, "current UC scene-graph publisher drift")

    transport = json.loads(front_face_transport_receipt_path.read_text(encoding="utf-8"))
    require(
        transport.get("result") == "PASS_OBJECT_GEOMETRY33_SOURCE_EXTERIOR_TO_CURRENT_UC_GLTF_PARITY_BRIDGE_READY",
        "Technical Art transport receipt is not green",
    )
    require(transport.get("geometry_exact_head") == HISTORICAL_GEOMETRY_HEAD, "transport historical Geometry drift")
    require(transport.get("hard_surface_exact_head") == HARD_SURFACE_HEAD, "transport Hard Surface drift")
    require(transport.get("source_sha256") == EXPECTED_SOURCE_SHA256, "transport source identity drift")
    require(transport.get("uc_exact_head") == expected_current_uc_head, "transport current UC head drift")
    require(transport.get("uc_procedural_3d_git_blob") == UC_PROCEDURAL_BLOB, "transport publisher blob drift")
    require(transport.get("uc_rigid_scene_graph_git_blob") == UC_RIGID_SCENE_GRAPH_BLOB, "transport scene graph blob drift")
    require(int(transport.get("source_triangles", -1)) == EXPECTED_TRIANGLES, "transport triangle drift")
    require(int(transport.get("source_rigid_groups", -1)) == EXPECTED_GROUPS, "transport group drift")

    corrected = transport.get("corrected_transport", {})
    unadapted = transport.get("unadapted_negative_control", {})
    require(corrected.get("glb_sha256") == EXPECTED_CORRECTED_GLB_SHA256, "corrected GLB bytes drifted on current UC")
    require(unadapted.get("glb_sha256") == EXPECTED_UNADAPTED_GLB_SHA256, "unadapted GLB bytes drifted on current UC")
    require(int(corrected.get("winding_reversal_faces", -1)) == EXPECTED_TRIANGLES, "corrected reversal count drift")
    require(int(unadapted.get("winding_reversal_faces", -1)) == 0, "negative reversal count drift")
    require(corrected.get("source_to_uc_position_map_determinant") == -1, "transport determinant drift")
    require(float(corrected.get("closed_static_localization_max_error_m", 1.0)) <= 1e-12, "corrected localization drift")
    require(float(unadapted.get("closed_static_localization_max_error_m", 1.0)) <= 1e-12, "negative localization drift")

    truth = transport.get("truth_boundary", {})
    require(truth.get("hard_surface_owns_exterior_intent") is True, "Hard Surface authority lost")
    require(truth.get("geometry_owns_orientation_candidate") is True, "Geometry authority lost")
    require(truth.get("technical_art_owns_transport_parity_adaptation") is True, "Technical Art authority lost")
    require(truth.get("uc_inferred_object_winding_policy") is False, "Object winding policy leaked into UC")
    require(truth.get("uc_modified") is False, "transport receipt claims UC modification")
    require(truth.get("source_geometry_adopted") is False, "transport adopted source geometry")

    return {
        "schema": SCHEMA,
        "result": RESULT,
        "geometry_current_rebind_head": geometry_head,
        "geometry_historical_candidate_head": HISTORICAL_GEOMETRY_HEAD,
        "hard_surface_head": HARD_SURFACE_HEAD,
        "source_sha256": EXPECTED_SOURCE_SHA256,
        "historical_candidate_obj_sha256": historical_candidate_sha,
        "merged_uc_rebind_candidate_obj_sha256": rebound_candidate_sha,
        "merged_uc_orientation_observer_commit": UC_ORIENTATION_MERGE,
        "current_uc_head": current_uc_head,
        "current_uc_blobs": current_uc_blobs,
        "rigid_groups": EXPECTED_GROUPS,
        "triangles": EXPECTED_TRIANGLES,
        "source_shared_orientation_conflicts": geometry["source_shared_orientation_conflicts"],
        "candidate_shared_orientation_conflicts": geometry["candidate_shared_orientation_conflicts"],
        "parity_compatible_groups": geometry["parity_compatible_groups"],
        "candidate_volume_matching_groups": geometry["candidate_volume_matching_groups"],
        "corrected_glb_sha256": corrected["glb_sha256"],
        "unadapted_glb_sha256": unadapted["glb_sha256"],
        "corrected_winding_reversal_faces": corrected["winding_reversal_faces"],
        "source_to_uc_determinant": corrected["source_to_uc_position_map_determinant"],
        "uc_modified": False,
        "truth_boundary": {
            "shared_uc_observer_is_read_only_structural_evidence": True,
            "hard_surface_retains_exterior_semantics": True,
            "geometry_retains_orientation_candidate": True,
            "technical_art_retains_handedness_and_target_transport": True,
            "materials_and_visual_qa_retain_rendered_acceptance": True,
            "runtime_retains_target_device_acceptance": True,
            "positive_signed_volume_called_outward": False,
            "global_godot_front_face_rule_claimed": False,
            "source_or_candidate_adopted": False,
            "canon_or_production_readiness": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--geometry-rebind-root", required=True, type=Path)
    parser.add_argument("--geometry-rebind-receipt", required=True, type=Path)
    parser.add_argument("--historical-candidate-obj", required=True, type=Path)
    parser.add_argument("--rebound-candidate-obj", required=True, type=Path)
    parser.add_argument("--front-face-transport-receipt", required=True, type=Path)
    parser.add_argument("--current-uc-root", required=True, type=Path)
    parser.add_argument("--expected-current-uc-head", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    receipt = validate(
        geometry_rebind_root=args.geometry_rebind_root.resolve(),
        geometry_rebind_receipt_path=args.geometry_rebind_receipt.resolve(),
        historical_candidate_path=args.historical_candidate_obj.resolve(),
        rebound_candidate_path=args.rebound_candidate_obj.resolve(),
        front_face_transport_receipt_path=args.front_face_transport_receipt.resolve(),
        current_uc_root=args.current_uc_root.resolve(),
        expected_current_uc_head=args.expected_current_uc_head,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
