from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from tools.verify_hinge_phase_invariant_bored_knuckle_topology_rebind import inspect as inspect_topology
except ModuleNotFoundError:
    from verify_hinge_phase_invariant_bored_knuckle_topology_rebind import inspect as inspect_topology

SCHEMA = "axm.object-hinge-successor002-godot-receiver-topology/v0.1"
RESULT = "PASS_OBJECT_HINGE_SUCCESSOR002_GODOT_RECEIVER_GENUS1_TOPOLOGY_CONTINUITY"
RULE = "TARGET_HOST_TRIANGLE_REORDER_OR_REVERSAL_REQUIRES_EXPLICIT_TOPOLOGY_CLASS_REVALIDATION_BEFORE_RECEIVER_PASS"
SOURCE_RESULT = "PASS_OBJECT_PHASE_INVARIANT_BORED_KNUCKLE_SUCCESSOR_GENUS1_TOPOLOGY_REBIND"
TA_RESULT = "PASS_OBJECT_HINGE_SUCCESSOR002_CURRENT_UC_GODOT_TRIANGLE_TRANSPORT"
INDEX_TRANSFORM = "GODOT_4_7_2_GLTFDOCUMENT_RECEIVER_LOCAL_[a,b,c]_TO_[a,c,b]"


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"expected JSON object: {path}")
    return value


def faces_from_indices(indices: list[int]) -> list[tuple[int, int, int]]:
    if len(indices) % 3:
        raise AssertionError("index payload is not triangulated")
    return [tuple(indices[offset : offset + 3]) for offset in range(0, len(indices), 3)]


def receiver_reversed_indices(source_indices: list[int]) -> list[int]:
    out: list[int] = []
    for a, b, c in faces_from_indices(source_indices):
        out.extend((a, c, b))
    return out


def require_report(report: dict[str, Any], expected: dict[str, Any], label: str) -> None:
    for key, value in expected.items():
        if report.get(key) != value:
            raise AssertionError(f"{label} topology drift: {key}: {report.get(key)!r} != {value!r}")
    if report.get("closed_orientable_vertex_manifold") is not True:
        raise AssertionError(f"{label} is not a closed orientable indexed vertex-manifold")


def verify_component(
    source_positions: list[list[float]],
    source_indices: list[int],
    target_positions: list[list[float]],
    target_indices: list[int],
    expected: dict[str, Any],
    label: str,
) -> dict[str, Any]:
    if len(source_positions) != len(target_positions):
        raise AssertionError(f"{label} vertex-count transport drift")
    if any(index < 0 or index >= len(source_positions) for index in source_indices):
        raise AssertionError(f"{label} source index out of range")
    if any(index < 0 or index >= len(target_positions) for index in target_indices):
        raise AssertionError(f"{label} target index out of range")

    expected_target = receiver_reversed_indices(source_indices)
    if target_indices == source_indices:
        raise AssertionError(f"{label} source index stream was incorrectly treated as target-identical")
    if target_indices != expected_target:
        raise AssertionError(f"{label} receiver-local triangle reversal drift")

    source_faces = faces_from_indices(source_indices)
    target_faces = faces_from_indices(target_indices)
    source_report = inspect_topology(source_positions, source_faces, range(len(source_positions)))
    target_report = inspect_topology(target_positions, target_faces, range(len(target_positions)))
    require_report(source_report, expected, f"{label} source")
    require_report(target_report, expected, f"{label} target")

    keys = (
        "vertices",
        "triangles",
        "unique_edges",
        "triangle_components",
        "boundary_edges",
        "non_manifold_edges",
        "orientation_conflicts",
        "degenerate_triangles",
        "isolated_vertices",
        "max_vertex_fan_components",
        "euler_characteristic",
        "orientable_genus",
    )
    for key in keys:
        if source_report[key] != target_report[key]:
            raise AssertionError(f"{label} source/target topology invariant drift: {key}")

    return {
        "name": label,
        "source": source_report,
        "target": target_report,
        "receiver_reversed_triangles": len(target_indices) // 3,
        "source_indices_equal_after_import": False,
        "target_host_triangle_index_transform": INDEX_TRANSFORM,
        "topology_class_equal_after_receiver_transform": True,
    }


def aggregate(reports: list[dict[str, Any]], side: str) -> dict[str, int]:
    return {
        "vertices": sum(int(item[side]["vertices"]) for item in reports),
        "triangles": sum(int(item[side]["triangles"]) for item in reports),
        "unique_edges": sum(int(item[side]["unique_edges"]) for item in reports),
        "triangle_components": sum(int(item[side]["triangle_components"]) for item in reports),
        "euler_characteristic_sum": sum(int(item[side]["euler_characteristic"]) for item in reports),
        "orientable_genus_sum": sum(int(item[side]["orientable_genus"]) for item in reports),
    }


def evaluate(
    contract_path: Path,
    source_surface_path: Path,
    target_arrays_path: Path,
    ta_receipt_path: Path,
    source_geometry_receipt_path: Path,
) -> dict[str, Any]:
    contract = read_json(contract_path)
    surface = read_json(source_surface_path)
    arrays = read_json(target_arrays_path)
    ta = read_json(ta_receipt_path)
    source_geometry = read_json(source_geometry_receipt_path)

    if contract.get("schema") != SCHEMA or contract.get("reusable_rule") != RULE:
        raise AssertionError("receiver topology contract identity drift")
    if source_geometry.get("result") != SOURCE_RESULT or contract.get("source_geometry_result") != SOURCE_RESULT:
        raise AssertionError("source Geometry result drift")
    if ta.get("result") != TA_RESULT or contract.get("technical_art_transport_result") != TA_RESULT:
        raise AssertionError("Technical Art target transport result drift")
    if ta.get("technical_art_head") != contract.get("technical_art_head"):
        raise AssertionError("Technical Art head drift")
    if ta.get("geometry_head") != contract.get("source_geometry_head"):
        raise AssertionError("source Geometry head drift in Technical Art receipt")
    if ta.get("glb_sha256") != contract.get("technical_art_glb_sha256"):
        raise AssertionError("target GLB identity drift")
    if arrays.get("glb_sha256") != ta.get("glb_sha256"):
        raise AssertionError("target array packet GLB identity drift")
    if ta.get("target_host_triangle_index_transform") != contract.get("target_host_triangle_index_transform"):
        raise AssertionError("target-host triangle transform identity drift")
    if ta.get("source_indices_equal_after_import_for_any_component") is not False:
        raise AssertionError("source/target index identity truth boundary drift")
    if float(ta.get("maximum_position_delta_m", 1.0)) > float(contract.get("target_position_tolerance_m", 0.0)):
        raise AssertionError("target POSITION transport exceeds bound")

    authority = contract.get("geometry_authority", {})
    if authority.get("receiver_topology_revalidation_is_observation_only") is not True:
        raise AssertionError("Geometry observation-only boundary drift")
    if authority.get("source_topology_pass_transferred_without_retest") is not False:
        raise AssertionError("source Geometry PASS transfer boundary drift")
    for key, value in authority.items():
        if key not in {"receiver_topology_revalidation_is_observation_only", "source_topology_pass_transferred_without_retest"} and value is not False:
            raise AssertionError(f"Geometry authority expansion: {key}")

    expected_components = tuple(contract.get("components", []))
    source_primitives = {item.get("id"): item for item in surface.get("primitives", []) if item.get("id") in expected_components}
    target_components = arrays.get("components", {})
    if set(source_primitives) != set(expected_components) or set(target_components) != set(expected_components):
        raise AssertionError("receiver component identity drift")

    expected_per_component = contract.get("expected_per_component", {})
    reports: list[dict[str, Any]] = []
    for name in expected_components:
        source = source_primitives[name]
        target = target_components[name]
        reports.append(
            verify_component(
                source.get("positions", []),
                [int(value) for value in source.get("indices", [])],
                target.get("vertices", []),
                [int(value) for value in target.get("indices", [])],
                expected_per_component,
                name,
            )
        )

    source_aggregate = aggregate(reports, "source")
    target_aggregate = aggregate(reports, "target")
    receiver_reversed_triangles = sum(int(item["receiver_reversed_triangles"]) for item in reports)
    expected_aggregate = contract.get("expected_aggregate", {})
    for label, observed in (("source", source_aggregate), ("target", target_aggregate)):
        for key, value in expected_aggregate.items():
            if key == "receiver_reversed_triangles":
                continue
            if observed.get(key) != value:
                raise AssertionError(f"{label} aggregate topology drift: {key}")
    if receiver_reversed_triangles != expected_aggregate.get("receiver_reversed_triangles"):
        raise AssertionError("receiver reversed-triangle count drift")
    if source_aggregate != target_aggregate:
        raise AssertionError("source/target aggregate topology class drift")

    source_receipt_aggregate = source_geometry.get("successor_aggregate", {})
    for key in ("vertices", "triangles", "unique_edges", "triangle_components", "euler_characteristic_sum", "orientable_genus_sum"):
        if source_receipt_aggregate.get(key) != source_aggregate.get(key):
            raise AssertionError(f"source Geometry receipt aggregate drift: {key}")

    return {
        "schema": "axm.object-hinge-successor002-godot-receiver-topology-receipt/v0.1",
        "result": RESULT,
        "asset_id": contract["asset_id"],
        "successor_id": contract["successor_id"],
        "source_geometry_head": contract["source_geometry_head"],
        "technical_art_head": contract["technical_art_head"],
        "technical_art_artifact_id": contract["technical_art_artifact_id"],
        "technical_art_artifact_sha256": contract["technical_art_artifact_sha256"],
        "glb_sha256": ta["glb_sha256"],
        "target_host": contract["target_host"],
        "target_host_triangle_index_transform": INDEX_TRANSFORM,
        "maximum_position_delta_m_from_technical_art": ta["maximum_position_delta_m"],
        "components": reports,
        "source_aggregate": source_aggregate,
        "target_aggregate": target_aggregate,
        "receiver_reversed_triangles": receiver_reversed_triangles,
        "source_topology_pass_transferred_without_retest": False,
        "receiver_topology_revalidated": True,
        "automatic_downstream_adoption": False,
        "reusable_rule": RULE,
        "truth_boundary": contract["truth_boundary"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", required=True)
    parser.add_argument("--source-surface", required=True)
    parser.add_argument("--target-arrays", required=True)
    parser.add_argument("--ta-receipt", required=True)
    parser.add_argument("--source-geometry-receipt", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    receipt = evaluate(
        Path(args.contract),
        Path(args.source_surface),
        Path(args.target_arrays),
        Path(args.ta_receipt),
        Path(args.source_geometry_receipt),
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(RESULT)
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
