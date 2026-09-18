from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

from tools.verify_rigid_shell_orientation import build_evidence, write_obj

POLICY_SCHEMA = "axm.object-geometry-rigid-shell-uc-orientation-rebind/v0.1"
RECEIPT_SCHEMA = "axm.object-geometry-rigid-shell-uc-orientation-rebind-receipt/v0.1"
RESULT = "PASS_OBJECT_RIGID_SHELL_MERGED_UC_ORIENTATION_OBSERVER_REBIND"
EXPECTED_ASSET_ID = "modular-equipment-case-001"
EXPECTED_SOURCE_SHA256 = "49b1f9ed9865893d6de6f1ec8f069576732df694853fde4e3fcff366de32644a"
EXPECTED_HISTORICAL_GEOMETRY_HEAD = "606d8189a3bf4502141d8038f08d35d421829dde"
EXPECTED_UC_PR_HEAD = "316e9c2a59e92046af309667fe21b956676b7286"
EXPECTED_UC_MERGE = "13a823349a568db266099564d6f5d8d7bac48b2b"
EXPECTED_UC_TOPOLOGY_BLOB = "b82c812d9c98799d0ccefa416ba2bd8d813245ee"
EXPECTED_UC_ORIENTATION_BLOB = "c8edfccbd49aa0e8aacf62a51b18440ef7499ac0"
EXPECTED_GROUP_COUNT = 31
EXPECTED_SOURCE_CONFLICTS = 304
EXPECTED_LOCAL_CANDIDATE_FLIPS = 508
VOLUME_COMPARE_TOLERANCE_M3 = 1e-12


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode("utf-8") + data).hexdigest()


def validate_policy(policy: dict[str, Any]) -> None:
    if policy.get("schema") != POLICY_SCHEMA:
        raise AssertionError("unexpected Object UC orientation rebind schema")
    if policy.get("asset_id") != EXPECTED_ASSET_ID:
        raise AssertionError("unexpected Object UC orientation rebind asset")
    if policy.get("source_sha256") != EXPECTED_SOURCE_SHA256:
        raise AssertionError("Object UC orientation rebind source identity drift")

    historical = policy.get("historical_local_candidate", {})
    if historical.get("pull_request") != 33:
        raise AssertionError("historical Geometry PR identity drift")
    if historical.get("exact_head") != EXPECTED_HISTORICAL_GEOMETRY_HEAD:
        raise AssertionError("historical Geometry exact-head drift")
    if historical.get("candidate_preserved") is not True:
        raise AssertionError("historical Geometry candidate must remain preserved")
    if historical.get("local_helper_retired") is not False:
        raise AssertionError("shared observer rebind is not local-helper retirement authority")

    uc = policy.get("merged_uc_observer", {})
    exact = {
        "repository": "mike-axiom-mir/axm-universal-creation",
        "pull_request": 200,
        "pull_request_final_head": EXPECTED_UC_PR_HEAD,
        "merge_commit": EXPECTED_UC_MERGE,
        "mesh_topology_blob": EXPECTED_UC_TOPOLOGY_BLOB,
        "mesh_closed_orientation_blob": EXPECTED_UC_ORIENTATION_BLOB,
        "include_closed_component_orientation": True,
        "orientation_frame_label": "OBJECT_SOURCE_NUMERIC_XYZ_METRES",
        "orientation_handedness": "UNDECLARED",
    }
    for key, value in exact.items():
        if uc.get(key) != value:
            raise AssertionError(f"merged UC observer identity/contract drift: {key}")
    if not math.isclose(float(uc.get("weld_tolerance_m", 0.0)), 1e-9, rel_tol=0.0, abs_tol=0.0):
        raise AssertionError("unexpected Object->UC weld tolerance")
    if not math.isclose(float(uc.get("orientation_volume_epsilon_m3", -1.0)), 1e-15, rel_tol=0.0, abs_tol=0.0):
        raise AssertionError("unexpected Object->UC orientation volume epsilon")

    required_true = (
        "historical_positive_volume_label_is_not_current_exterior_authority",
        "shared_parity_is_diagnostic_only",
        "hard_surface_exterior_authority_preserved",
        "technical_art_transport_authority_preserved",
        "renderer_front_face_authority_preserved",
        "runtime_authority_preserved",
        "gameplay_collision_authority_preserved",
    )
    for key in required_true:
        if policy.get(key) is not True:
            raise AssertionError(f"authority/truth boundary weakened: {key}")
    for key in (
        "positive_signed_volume_defines_outward",
        "source_geometry_changed",
        "candidate_geometry_changed",
        "source_adopted",
        "candidate_adopted",
    ):
        if policy.get(key) is not False:
            raise AssertionError(f"forbidden authority promotion: {key}")


def _git_head(repo: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
    ).strip()


def load_uc_inspector(uc_root: Path) -> Callable[..., dict[str, Any]]:
    uc_root = uc_root.resolve()
    if _git_head(uc_root) != EXPECTED_UC_MERGE:
        raise AssertionError("UC checkout is not the exact merged orientation observer commit")

    topology_path = uc_root / "src/axm_uc/mesh_topology.py"
    orientation_path = uc_root / "src/axm_uc/mesh_closed_orientation.py"
    if git_blob_sha(topology_path) != EXPECTED_UC_TOPOLOGY_BLOB:
        raise AssertionError("merged UC mesh_topology.py blob drift")
    if git_blob_sha(orientation_path) != EXPECTED_UC_ORIENTATION_BLOB:
        raise AssertionError("merged UC mesh_closed_orientation.py blob drift")

    src = str((uc_root / "src").resolve())
    sys.path.insert(0, src)
    try:
        from axm_uc.mesh_topology import inspect_mesh_topology
    finally:
        if sys.path and sys.path[0] == src:
            sys.path.pop(0)

    module_path = Path(inspect_mesh_topology.__code__.co_filename).resolve()
    if module_path != topology_path.resolve():
        raise AssertionError(f"UC inspector imported from unexpected path: {module_path}")
    return inspect_mesh_topology


def localize_group(
    vertices: list[list[float]] | list[tuple[float, float, float]],
    faces: list[list[int]] | list[tuple[int, int, int]],
) -> tuple[list[list[float]], list[int]]:
    referenced = sorted({index for face in faces for index in face})
    remap = {source: local for local, source in enumerate(referenced)}
    positions = [[float(value) for value in vertices[source]] for source in referenced]
    indices = [remap[index] for face in faces for index in face]
    return positions, indices


def _single_orientation_component(report: dict[str, Any], label: str) -> dict[str, Any]:
    orientation = report.get("closed_component_orientation")
    if not isinstance(orientation, dict):
        raise AssertionError(f"{label}: merged UC orientation sibling report missing")
    if orientation.get("schema") != "axm.mesh-closed-component-orientation/v0.1":
        raise AssertionError(f"{label}: unexpected shared orientation schema")
    if orientation.get("inspection_complete") is not True:
        raise AssertionError(f"{label}: merged UC orientation inspection incomplete")
    if orientation.get("component_count") != 1:
        raise AssertionError(f"{label}: rigid group must remain exactly one shared component")
    if orientation.get("orientable_component_count") != 1:
        raise AssertionError(f"{label}: rigid group not proven orientable by merged UC")
    if orientation.get("non_orientable_component_count") != 0:
        raise AssertionError(f"{label}: merged UC reported non-orientable component")
    if orientation.get("not_evaluated_component_count") != 0:
        raise AssertionError(f"{label}: merged UC left rigid group unevaluated")
    truth = orientation.get("truth_boundary", {})
    if truth.get("read_only_observer") is not True:
        raise AssertionError(f"{label}: shared observer read-only boundary drift")
    if truth.get("positive_signed_volume_called_outward") is not False:
        raise AssertionError(f"{label}: shared observer relabelled positive sign as outward")
    if truth.get("source_winding_repaired") is not False:
        raise AssertionError(f"{label}: shared observer may not repair source winding")
    if truth.get("product_adoption_authorized") is not False:
        raise AssertionError(f"{label}: shared observer may not authorize product adoption")
    component = orientation.get("components", [None])[0]
    if not isinstance(component, dict):
        raise AssertionError(f"{label}: merged UC component report missing")
    if component.get("closure_state") != "CLOSED":
        raise AssertionError(f"{label}: rigid group not closed in merged UC observer")
    if component.get("orientability_state") != "ORIENTABLE":
        raise AssertionError(f"{label}: rigid group not orientable in merged UC observer")
    if component.get("global_sign_normalized") is not False:
        raise AssertionError(f"{label}: shared observer unexpectedly normalized global sign")
    return component


def compare_group_reports(
    *,
    local_metrics: dict[str, Any],
    source_report: dict[str, Any],
    candidate_report: dict[str, Any],
) -> dict[str, Any]:
    name = str(local_metrics["name"])
    source_component = _single_orientation_component(source_report, f"{name}/source")
    candidate_component = _single_orientation_component(candidate_report, f"{name}/candidate")

    local_face_count = int(local_metrics["triangles"])
    if source_component.get("triangle_count") != local_face_count:
        raise AssertionError(f"{name}: source triangle count drift through UC")
    if candidate_component.get("triangle_count") != local_face_count:
        raise AssertionError(f"{name}: candidate triangle count drift through UC")

    local_source_conflicts = int(local_metrics["source_orientation_conflict_edges"])
    if source_component.get("current_orientation_conflict_edge_count") != local_source_conflicts:
        raise AssertionError(f"{name}: source shared-edge conflict count disagrees with local receipt")
    if candidate_component.get("current_orientation_conflict_edge_count") != 0:
        raise AssertionError(f"{name}: candidate regained shared-edge orientation conflicts")
    if candidate_component.get("current_shared_edge_orientation_state") != "CONSISTENT":
        raise AssertionError(f"{name}: candidate is not coherently wound in merged UC observer")
    if candidate_component.get("diagnostic_face_flip_count") != 0:
        raise AssertionError(f"{name}: merged UC requires fresh parity flips on historical candidate")

    shared_source_flips = int(source_component["diagnostic_face_flip_count"])
    local_final_flips = int(local_metrics["flipped_faces"])
    if local_final_flips not in {shared_source_flips, local_face_count - shared_source_flips}:
        raise AssertionError(f"{name}: local historical repair is not a shared parity solution/complement")

    local_candidate_volume = float(local_metrics["candidate_signed_volume_m3"])
    shared_source_candidate_volume = float(source_component["coherent_candidate_signed_volume"])
    shared_candidate_current_volume = float(candidate_component["current_signed_volume"])
    shared_candidate_coherent_volume = float(candidate_component["coherent_candidate_signed_volume"])

    if abs(abs(shared_source_candidate_volume) - abs(local_candidate_volume)) > VOLUME_COMPARE_TOLERANCE_M3:
        raise AssertionError(f"{name}: source shared parity volume magnitude disagrees with local candidate")
    if abs(shared_candidate_current_volume - local_candidate_volume) > VOLUME_COMPARE_TOLERANCE_M3:
        raise AssertionError(f"{name}: candidate current signed volume disagrees with local candidate")
    if abs(shared_candidate_coherent_volume - local_candidate_volume) > VOLUME_COMPARE_TOLERANCE_M3:
        raise AssertionError(f"{name}: candidate shared coherent volume disagrees with local candidate")

    return {
        "name": name,
        "triangles": local_face_count,
        "local_source_orientation_conflicts": local_source_conflicts,
        "shared_source_orientation_conflicts": source_component["current_orientation_conflict_edge_count"],
        "shared_source_diagnostic_flips": shared_source_flips,
        "local_historical_candidate_flips_from_source": local_final_flips,
        "parity_relation": (
            "EXACT_SHARED_PARITY"
            if local_final_flips == shared_source_flips
            else "GLOBAL_PARITY_COMPLEMENT"
        ),
        "candidate_shared_orientation_conflicts": 0,
        "candidate_shared_diagnostic_flips": 0,
        "local_candidate_signed_volume_m3": local_candidate_volume,
        "shared_source_coherent_candidate_signed_volume_m3": shared_source_candidate_volume,
        "shared_candidate_current_signed_volume_m3": shared_candidate_current_volume,
        "positive_sign_interpreted_as_outward": False,
    }


def _inspect_group(
    inspect_mesh_topology: Callable[..., dict[str, Any]],
    positions: list[list[float]],
    indices: list[int],
    policy: dict[str, Any],
    *,
    triangle_budget: int = 131_072,
) -> dict[str, Any]:
    uc = policy["merged_uc_observer"]
    return inspect_mesh_topology(
        positions,
        indices,
        weld_tolerance=float(uc["weld_tolerance_m"]),
        include_closed_component_orientation=True,
        orientation_triangle_budget=triangle_budget,
        orientation_volume_epsilon=float(uc["orientation_volume_epsilon_m3"]),
        orientation_frame_label=str(uc["orientation_frame_label"]),
        orientation_handedness=str(uc["orientation_handedness"]),
    )


def build_uc_rebind_evidence(
    source_path: Path,
    historical_policy_path: Path,
    rebind_policy_path: Path,
    uc_root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    policy = json.loads(rebind_policy_path.read_text(encoding="utf-8"))
    validate_policy(policy)
    inspect_mesh_topology = load_uc_inspector(uc_root)

    local_receipt, candidate_mesh = build_evidence(source_path, historical_policy_path)
    if local_receipt.get("source_orientation_conflict_edges") != EXPECTED_SOURCE_CONFLICTS:
        raise AssertionError("historical local source-conflict identity drift")
    if local_receipt.get("candidate_orientation_conflict_edges") != 0:
        raise AssertionError("historical local candidate conflict identity drift")
    if local_receipt.get("candidate_flipped_faces") != EXPECTED_LOCAL_CANDIDATE_FLIPS:
        raise AssertionError("historical local candidate flip-count identity drift")
    groups = candidate_mesh["groups"]
    if len(groups) != EXPECTED_GROUP_COUNT:
        raise AssertionError("historical rigid-group count drift")

    source_mesh = __import__("tools.build_modular_case", fromlist=["build"]).build(
        json.loads(source_path.read_text(encoding="utf-8"))
    )["mesh"]
    local_metrics_by_name = {entry["name"]: entry for entry in local_receipt["groups"]}

    group_receipts: list[dict[str, Any]] = []
    for group in groups:
        name = group["name"]
        start = int(group["first_face"])
        end = start + int(group["face_count"])
        source_positions, source_indices = localize_group(source_mesh["vertices"], source_mesh["faces"][start:end])
        candidate_positions, candidate_indices = localize_group(candidate_mesh["vertices"], candidate_mesh["faces"][start:end])
        source_report = _inspect_group(inspect_mesh_topology, source_positions, source_indices, policy)
        candidate_report = _inspect_group(inspect_mesh_topology, candidate_positions, candidate_indices, policy)
        group_receipts.append(
            compare_group_reports(
                local_metrics=local_metrics_by_name[name],
                source_report=source_report,
                candidate_report=candidate_report,
            )
        )

    if sum(item["shared_source_orientation_conflicts"] for item in group_receipts) != EXPECTED_SOURCE_CONFLICTS:
        raise AssertionError("merged UC aggregate source orientation-conflict count drift")
    if sum(item["candidate_shared_orientation_conflicts"] for item in group_receipts) != 0:
        raise AssertionError("merged UC aggregate candidate conflicts remain")
    if sum(item["candidate_shared_diagnostic_flips"] for item in group_receipts) != 0:
        raise AssertionError("merged UC still requests candidate parity repair")

    largest_group = max(group_receipts, key=lambda item: (item["triangles"], item["name"]))
    source_group = next(group for group in groups if group["name"] == largest_group["name"])
    start = int(source_group["first_face"])
    end = start + int(source_group["face_count"])
    budget_positions, budget_indices = localize_group(candidate_mesh["vertices"], candidate_mesh["faces"][start:end])
    budget = int(source_group["face_count"]) - 1
    budget_report = _inspect_group(
        inspect_mesh_topology,
        budget_positions,
        budget_indices,
        policy,
        triangle_budget=budget,
    )
    budget_orientation = budget_report["closed_component_orientation"]
    budget_component = budget_orientation["components"][0]
    if budget_orientation.get("inspection_complete") is not False:
        raise AssertionError("orientation work-budget negative did not hold inspection")
    if budget_component.get("orientability_state") != "NOT_EVALUATED":
        raise AssertionError("orientation work-budget negative emitted an orientability verdict")
    if budget_component.get("not_evaluated_reason") != "TRIANGLE_WORK_BUDGET_EXCEEDED":
        raise AssertionError("orientation work-budget negative returned wrong HOLD reason")
    if budget_component.get("parity_solution_sha256") is not None:
        raise AssertionError("orientation work-budget negative emitted partial parity evidence")

    receipt = {
        "schema": RECEIPT_SCHEMA,
        "asset_id": EXPECTED_ASSET_ID,
        "result": RESULT,
        "pattern": policy["pattern"],
        "source_sha256": EXPECTED_SOURCE_SHA256,
        "historical_local_candidate_exact_head": EXPECTED_HISTORICAL_GEOMETRY_HEAD,
        "historical_local_candidate_preserved": True,
        "historical_local_helper_retired": False,
        "merged_uc_observer": {
            "pull_request": 200,
            "pull_request_final_head": EXPECTED_UC_PR_HEAD,
            "merge_commit": EXPECTED_UC_MERGE,
            "mesh_topology_blob": EXPECTED_UC_TOPOLOGY_BLOB,
            "mesh_closed_orientation_blob": EXPECTED_UC_ORIENTATION_BLOB,
        },
        "rigid_groups": EXPECTED_GROUP_COUNT,
        "source_shared_orientation_conflicts": EXPECTED_SOURCE_CONFLICTS,
        "candidate_shared_orientation_conflicts": 0,
        "candidate_groups_requiring_shared_diagnostic_flips": 0,
        "parity_compatible_groups": len(group_receipts),
        "candidate_volume_matching_groups": len(group_receipts),
        "positive_signed_volume_defines_outward": False,
        "shared_parity_is_diagnostic_only": True,
        "source_geometry_changed": False,
        "candidate_geometry_changed": False,
        "source_adopted": False,
        "candidate_adopted": False,
        "hard_surface_exterior_authority_preserved": True,
        "technical_art_transport_authority_preserved": True,
        "renderer_front_face_authority_preserved": True,
        "runtime_authority_preserved": True,
        "gameplay_collision_authority_preserved": True,
        "work_budget_negative_control": {
            "group": largest_group["name"],
            "group_triangle_count": largest_group["triangles"],
            "triangle_budget": budget,
            "inspection_complete": False,
            "orientability_state": "NOT_EVALUATED",
            "reason": "TRIANGLE_WORK_BUDGET_EXCEEDED",
            "partial_parity_emitted": False,
        },
        "groups": group_receipts,
        "limitations": [
            "shared observer parity is diagnostic only and does not rewrite or adopt the Object source/candidate",
            "positive algebraic signed volume is a declared-frame observation and is not semantic exterior/outward authority",
            "the historical Object-local orientation helper/receipt remains provenance and is not retired by this parity rebind",
            "Hard Surface retains source exterior/interior semantics; Technical Art retains handedness/front-face transport policy",
            "no final normals/tangents/UV/material/rendering acceptance, Runtime/device acceptance, physics/collision/gameplay suitability, CANON, production readiness, game readiness or Geometry mastery is established",
        ],
    }
    return receipt, candidate_mesh


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=root / "assets/modular-equipment-case-001/source.json")
    parser.add_argument(
        "--historical-policy",
        type=Path,
        default=root / "assets/modular-equipment-case-001/rigid-shell-orientation-review-001.json",
    )
    parser.add_argument(
        "--rebind-policy",
        type=Path,
        default=root / "assets/modular-equipment-case-001/rigid-shell-uc-orientation-rebind-001.json",
    )
    parser.add_argument("--uc-root", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--obj", type=Path)
    args = parser.parse_args()

    receipt, candidate_mesh = build_uc_rebind_evidence(
        args.source,
        args.historical_policy,
        args.rebind_policy,
        args.uc_root,
    )
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.obj is not None:
        write_obj(args.obj, candidate_mesh)
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
