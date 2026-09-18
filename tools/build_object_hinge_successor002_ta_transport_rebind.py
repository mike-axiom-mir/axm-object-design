from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from build_object_uc_rigid_scene_handoff import canonical_digest, make_component_surface_group

RESULT = "PASS_OBJECT_HINGE_SUCCESSOR002_TA_SCENE_REBIND_TO_CURRENT_UC__HOLD_DEFAULT_RUNTIME_VISUAL"
SCHEMA = "axm.object-technical-art-hinge-successor002-transport-rebind-receipt/v0.1"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_head(root: Path) -> str:
    return subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"expected JSON object: {path}")
    return value


def parse_grouped_obj(path: Path) -> dict[str, Any]:
    vertices: list[list[float]] = []
    faces: list[tuple[int, int, int]] = []
    groups: list[dict[str, Any]] = []
    active_name: str | None = None
    active_first = 0

    def close_group() -> None:
        nonlocal active_name, active_first
        if active_name is None:
            return
        count = len(faces) - active_first
        if count <= 0:
            raise AssertionError(f"OBJ group has no faces: {active_name}")
        selected = faces[active_first:]
        groups.append(
            {
                "name": active_name,
                "first_face": active_first,
                "face_count": count,
                "vertex_indices": sorted({index for face in selected for index in face}),
            }
        )

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if parts[0] == "v":
            if len(parts) < 4:
                raise AssertionError("malformed OBJ vertex")
            vertices.append([float(parts[1]), float(parts[2]), float(parts[3])])
        elif parts[0] == "g":
            close_group()
            if len(parts) != 2:
                raise AssertionError("bounded successor OBJ expects one name per group")
            active_name = parts[1]
            active_first = len(faces)
        elif parts[0] == "f":
            if active_name is None:
                raise AssertionError("OBJ face appears before first named group")
            if len(parts) != 4:
                raise AssertionError("bounded successor OBJ expects triangulated faces")
            face: list[int] = []
            for token in parts[1:]:
                index_text = token.split("/", 1)[0]
                index = int(index_text)
                if index <= 0:
                    raise AssertionError("bounded successor OBJ requires positive one-based indices")
                face.append(index - 1)
            faces.append(tuple(face))
    close_group()
    if any(index < 0 or index >= len(vertices) for face in faces for index in face):
        raise AssertionError("OBJ face index out of range")
    return {"vertices": vertices, "faces": faces, "groups": groups}


def primitive_triangles(primitive: dict[str, Any]) -> int:
    indices = primitive.get("indices")
    if not isinstance(indices, list) or len(indices) % 3:
        raise AssertionError(f"primitive index payload is not triangulated: {primitive.get('id')}")
    return len(indices) // 3


def require_authority_boundary(contract: dict[str, Any]) -> None:
    authority = contract.get("authority", {})
    if authority.get("technical_art_receiver_rebind_only") is not True:
        raise AssertionError("Technical Art receiver scope is not explicit")
    forbidden_true = (
        "source_successor_default_adopted",
        "automatic_downstream_adoption",
        "hard_surface_or_geometry_authority_transferred",
        "rigging_authority_transferred",
        "animation_authority_transferred",
        "runtime_or_physics_accepted",
        "visual_or_art_accepted",
        "uc_domain_policy_added",
        "canon_or_production_accepted",
    )
    for key in forbidden_true:
        if authority.get(key) is not False:
            raise AssertionError(f"authority expansion forbidden: {key}")


def verify_owner_receipts(
    contract: dict[str, Any],
    hard_surface: dict[str, Any],
    geometry: dict[str, Any],
    rigging: dict[str, Any],
) -> None:
    results = contract["owner_results"]
    if hard_surface.get("result") != results["hard_surface"]:
        raise AssertionError("Hard Surface successor receipt is not the pinned PASS")
    if hard_surface.get("successor_id") != contract["successor_id"]:
        raise AssertionError("Hard Surface successor identity drift")
    if hard_surface.get("automatic_downstream_adoption") is not False:
        raise AssertionError("Hard Surface successor unexpectedly authorizes downstream adoption")

    if geometry.get("result") != results["geometry"]:
        raise AssertionError("Geometry successor receipt is not the pinned PASS")
    if geometry.get("successor_id") != contract["successor_id"]:
        raise AssertionError("Geometry successor identity drift")
    if geometry.get("hard_surface_donor_head") != contract["hard_surface_head"]:
        raise AssertionError("Geometry donor head drift")
    if geometry.get("historical_pass_transferred") is not False:
        raise AssertionError("Geometry historical PASS transfer is forbidden")
    if geometry.get("automatic_downstream_adoption") is not False:
        raise AssertionError("Geometry unexpectedly authorizes downstream adoption")

    if rigging.get("result") != results["rigging"]:
        raise AssertionError("Rigging successor receipt is not the pinned PASS")
    source_successor = rigging.get("source_successor", {})
    if source_successor.get("head") != contract["hard_surface_head"]:
        raise AssertionError("Rigging source-successor head drift")
    decision = rigging.get("decision", {})
    if decision.get("source_successor_geometry_adopted") is not False:
        raise AssertionError("Rigging receipt unexpectedly adopts source geometry")
    if decision.get("automatic_downstream_adoption") is not False:
        raise AssertionError("Rigging receipt unexpectedly authorizes downstream adoption")


def build_rebind(
    *,
    contract_path: Path,
    baseline_surface_path: Path,
    baseline_manifest_path: Path,
    baseline_receipt_path: Path,
    successor_obj_path: Path,
    expected_successor_obj_sha256: str,
    hard_surface_receipt_path: Path,
    geometry_receipt_path: Path,
    rigging_receipt_path: Path,
    uc_root: Path,
    out_dir: Path,
) -> dict[str, Any]:
    contract = read_json(contract_path)
    if contract.get("schema") != "axm.object-technical-art-hinge-successor002-transport-rebind/v0.1":
        raise AssertionError("unsupported Technical Art successor rebind contract")
    require_authority_boundary(contract)

    observed_uc_head = git_head(uc_root)
    if observed_uc_head != contract["current_uc_head"]:
        raise AssertionError(f"current UC head drift: {observed_uc_head}")

    observed_obj_sha = sha256_file(successor_obj_path)
    if observed_obj_sha != expected_successor_obj_sha256:
        raise AssertionError("exact successor OBJ identity drift")

    hard_surface = read_json(hard_surface_receipt_path)
    geometry = read_json(geometry_receipt_path)
    rigging = read_json(rigging_receipt_path)
    verify_owner_receipts(contract, hard_surface, geometry, rigging)

    baseline_surface = read_json(baseline_surface_path)
    baseline_manifest = read_json(baseline_manifest_path)
    baseline_receipt = read_json(baseline_receipt_path)
    if baseline_receipt.get("result") != "PASS_OBJECT_SOURCE_OWNED_RIGID_PARTS_THROUGH_UC_SCENE_GRAPH":
        raise AssertionError("baseline Technical Art scene handoff is not green")
    if baseline_receipt.get("observed_uc_commit") != contract["current_uc_head"]:
        raise AssertionError("baseline scene is not rebuilt against current UC")
    if baseline_surface.get("schema") != "axm.surface-3d/v0.1":
        raise AssertionError("baseline surface schema drift")

    mapping: dict[str, str] = dict(contract["component_mapping"])
    expected_target_names = set(mapping.values())
    baseline_primitives = baseline_surface.get("primitives")
    if not isinstance(baseline_primitives, list):
        raise AssertionError("baseline surface primitives missing")
    by_id = {primitive.get("id"): primitive for primitive in baseline_primitives}
    if len(by_id) != len(baseline_primitives):
        raise AssertionError("baseline primitive IDs are not unique")
    if not expected_target_names.issubset(by_id):
        raise AssertionError("baseline scene lacks one or more hinge receiver components")

    successor_mesh = parse_grouped_obj(successor_obj_path)
    source_group_names = {group["name"] for group in successor_mesh["groups"]}
    if source_group_names != set(mapping):
        raise AssertionError(f"successor OBJ group identity drift: {sorted(source_group_names)}")
    if len(successor_mesh["groups"]) != int(contract["expected_successor_knuckle_count"]):
        raise AssertionError("successor knuckle count drift")

    pivot_source = baseline_receipt.get("hinge_pivot_source_m")
    if not (isinstance(pivot_source, list) and len(pivot_source) == 3):
        raise AssertionError("baseline hinge pivot missing")
    lid_owned = set(contract["lid_owned_hinge_components"])
    body_owned = set(contract["body_owned_hinge_components"])
    if lid_owned | body_owned != expected_target_names or lid_owned & body_owned:
        raise AssertionError("Technical Art owner partition drift")

    replacement_by_id: dict[str, dict[str, Any]] = {}
    replacement_stats: dict[str, Any] = {}
    max_closed_error = 0.0
    expected_triangles_per = int(contract["expected_triangles_per_knuckle"])
    for group in successor_mesh["groups"]:
        target = mapping[group["name"]]
        renamed = dict(group)
        renamed["name"] = target
        primitive, static_error = make_component_surface_group(
            successor_mesh,
            renamed,
            local_origin_source=pivot_source if target in lid_owned else None,
        )
        triangles = primitive_triangles(primitive)
        if triangles != expected_triangles_per:
            raise AssertionError(f"successor triangle count drift for {target}: {triangles}")
        replacement_by_id[target] = primitive
        replacement_stats[target] = {
            "source_group": group["name"],
            "triangles": triangles,
            "positions": len(primitive["positions"]),
            "closed_static_localization_max_error_m": static_error,
        }
        max_closed_error = max(max_closed_error, static_error)
    if max_closed_error > 1e-12:
        raise AssertionError(f"successor closed localization drift: {max_closed_error}")

    successor_surface = copy.deepcopy(baseline_surface)
    successor_surface["name"] = "modular-equipment-case-001-rigid-component-proof-hinge-successor002"
    successor_surface["primitives"] = [
        replacement_by_id.get(primitive["id"], primitive) for primitive in baseline_primitives
    ]

    unchanged_ids = sorted(set(by_id) - expected_target_names)
    successor_by_id = {primitive["id"]: primitive for primitive in successor_surface["primitives"]}
    for component_id in unchanged_ids:
        if canonical_digest(by_id[component_id]) != canonical_digest(successor_by_id[component_id]):
            raise AssertionError(f"unrelated receiver primitive drift: {component_id}")

    old_hinge_triangles = sum(primitive_triangles(by_id[name]) for name in expected_target_names)
    new_hinge_triangles = sum(primitive_triangles(replacement_by_id[name]) for name in expected_target_names)
    if new_hinge_triangles != int(contract["expected_successor_hinge_triangles"]):
        raise AssertionError("aggregate successor hinge triangle count drift")
    old_total = sum(primitive_triangles(p) for p in baseline_primitives)
    expected_new_total = old_total - old_hinge_triangles + new_hinge_triangles

    sys.path.insert(0, str(uc_root / "src"))
    from axm_uc.procedural_3d import build_glb, verify_glb  # noqa: E402
    from axm_uc.rigid_scene_graph import rebind_rigid_scene_graph, verify_rigid_scene_graph  # noqa: E402

    flat = build_glb(successor_surface)
    rebound = rebind_rigid_scene_graph(
        flat["body"], baseline_manifest, expected_spec_digest=flat["specification_sha256"]
    )
    flat_verification = verify_glb(flat["body"], expected_spec_digest=flat["specification_sha256"])
    rebound_verification = verify_glb(rebound["body"], expected_spec_digest=flat["specification_sha256"])
    graph_verification = verify_rigid_scene_graph(
        rebound["body"], expected_manifest_digest=rebound["manifest_sha256"]
    )
    if flat_verification["triangles"] != expected_new_total or rebound_verification["triangles"] != expected_new_total:
        raise AssertionError("current UC triangle count drift")
    if rebound_verification["nodes"] != len(successor_surface["primitives"]):
        raise AssertionError("current UC mesh-node count drift")
    if rebound["receipt"].get("binary_geometry_payload_identical") is not True:
        raise AssertionError("rigid-scene rebind changed successor binary geometry payload")

    for name in lid_owned:
        if graph_verification["parent_by_child"].get(name) != "lid_shell":
            raise AssertionError(f"lid hinge component lost lid parentage: {name}")
    for name in body_owned:
        if name in graph_verification["parent_by_child"]:
            raise AssertionError(f"body hinge component unexpectedly parented: {name}")
    for keeper in baseline_receipt.get("source_owned_keeper_children", []):
        if graph_verification["parent_by_child"].get(keeper) != "lid_shell":
            raise AssertionError(f"existing keeper parentage drift: {keeper}")
    for lever in baseline_receipt.get("source_owned_fixed_levers", []):
        if lever in graph_verification["parent_by_child"]:
            raise AssertionError(f"existing fixed lever parentage drift: {lever}")

    out_dir.mkdir(parents=True, exist_ok=True)
    surface_out = out_dir / "object-rigid-components-hinge-successor002.surface.json"
    manifest_out = out_dir / "object-rigid-scene-graph-hinge-successor002.json"
    flat_out = out_dir / "object-rigid-components-hinge-successor002-flat.glb"
    rebound_out = out_dir / "object-rigid-components-hinge-successor002-rebound.glb"
    surface_out.write_text(json.dumps(successor_surface, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest_out.write_text(json.dumps(rebound["manifest"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    flat_out.write_bytes(flat["body"])
    rebound_out.write_bytes(rebound["body"])

    receipt = {
        "schema": SCHEMA,
        "result": RESULT,
        "technical_art_head": git_head(Path.cwd()),
        "predecessor_technical_art_head": contract["predecessor_technical_art_head"],
        "hard_surface_head": contract["hard_surface_head"],
        "geometry_head": contract["geometry_head"],
        "rigging_head": contract["rigging_head"],
        "uc_head": observed_uc_head,
        "successor_id": contract["successor_id"],
        "successor_obj_sha256": observed_obj_sha,
        "owner_results": contract["owner_results"],
        "baseline_surface_sha256": sha256_file(baseline_surface_path),
        "baseline_manifest_sha256": sha256_file(baseline_manifest_path),
        "baseline_rebound_glb_sha256": baseline_receipt.get("rebound_glb_sha256"),
        "successor_surface_sha256": sha256_file(surface_out),
        "successor_flat_glb_sha256": hashlib.sha256(flat["body"]).hexdigest(),
        "successor_rebound_glb_sha256": hashlib.sha256(rebound["body"]).hexdigest(),
        "successor_rigid_manifest_sha256": rebound["manifest_sha256"],
        "successor_binary_chunk_sha256": rebound["receipt"]["binary_chunk_sha256"],
        "successor_binary_geometry_payload_identical_across_rebind": True,
        "mesh_nodes": rebound_verification["nodes"],
        "baseline_total_triangles": old_total,
        "baseline_hinge_triangles": old_hinge_triangles,
        "successor_hinge_triangles": new_hinge_triangles,
        "successor_total_triangles": expected_new_total,
        "unrelated_primitives_byte_semantics_preserved": True,
        "unrelated_primitive_count": len(unchanged_ids),
        "replacement_stats": replacement_stats,
        "closed_static_localization_max_error_m": max_closed_error,
        "graph_verification": graph_verification,
        "flat_uc_verification": flat_verification,
        "rebound_uc_verification": rebound_verification,
        "target_host_import_observed": False,
        "authority": contract["authority"],
        "truth_boundary": {
            "hard_surface_source_successor_consumed_exactly": True,
            "geometry_topology_receipt_consumed_exactly": True,
            "rigging_compatibility_receipt_consumed_exactly": True,
            "only_five_hinge_receiver_primitives_replaced": True,
            "source_successor_default_adopted": False,
            "automatic_downstream_adoption": False,
            "uc_domain_policy_added": False,
            "animation_acceptance_transferred": False,
            "runtime_or_physics_accepted": False,
            "final_visual_or_art_accepted": False,
            "canon_or_production_accepted": False,
        },
    }
    receipt_path = out_dir / "object-hinge-successor002-ta-transport-rebind-receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", required=True)
    parser.add_argument("--baseline-surface", required=True)
    parser.add_argument("--baseline-manifest", required=True)
    parser.add_argument("--baseline-receipt", required=True)
    parser.add_argument("--successor-obj", required=True)
    parser.add_argument("--expected-successor-obj-sha256", required=True)
    parser.add_argument("--hard-surface-receipt", required=True)
    parser.add_argument("--geometry-receipt", required=True)
    parser.add_argument("--rigging-receipt", required=True)
    parser.add_argument("--uc-root", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    receipt = build_rebind(
        contract_path=Path(args.contract),
        baseline_surface_path=Path(args.baseline_surface),
        baseline_manifest_path=Path(args.baseline_manifest),
        baseline_receipt_path=Path(args.baseline_receipt),
        successor_obj_path=Path(args.successor_obj),
        expected_successor_obj_sha256=args.expected_successor_obj_sha256,
        hard_surface_receipt_path=Path(args.hard_surface_receipt),
        geometry_receipt_path=Path(args.geometry_receipt),
        rigging_receipt_path=Path(args.rigging_receipt),
        uc_root=Path(args.uc_root),
        out_dir=Path(args.out),
    )
    print(RESULT)
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
