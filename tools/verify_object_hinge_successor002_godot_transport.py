from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

RESULT = "PASS_OBJECT_HINGE_SUCCESSOR002_CURRENT_UC_GODOT_TRIANGLE_TRANSPORT"
COMPONENTS = ("hinge_body_b0", "hinge_lid_l0", "hinge_body_b1", "hinge_lid_l1", "hinge_body_b2")
POSITION_TOLERANCE_M = 1e-6


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"expected JSON object: {path}")
    return value


def verify(surface_path: Path, ta_receipt_path: Path, target_receipt_path: Path, target_arrays_path: Path) -> dict[str, Any]:
    surface = read_json(surface_path)
    ta = read_json(ta_receipt_path)
    target = read_json(target_receipt_path)
    arrays = read_json(target_arrays_path)

    if ta.get("result") != "PASS_OBJECT_HINGE_SUCCESSOR002_TA_SCENE_REBIND_TO_CURRENT_UC__HOLD_DEFAULT_RUNTIME_VISUAL":
        raise AssertionError("Technical Art successor-002 receipt is not green")
    if target.get("state") != "PASS_OBJECT_HINGE_SUCCESSOR002_CURRENT_UC_GODOT_IMPORT_PARENTAGE":
        raise AssertionError("Godot successor-002 target receipt is not green")
    if target.get("glb_sha256") != ta.get("successor_rebound_glb_sha256"):
        raise AssertionError("Godot target GLB identity drift")
    if arrays.get("glb_sha256") != target.get("glb_sha256"):
        raise AssertionError("Godot target array packet GLB identity drift")

    expected = {p.get("id"): p for p in surface.get("primitives", []) if p.get("id") in COMPONENTS}
    observed = arrays.get("components", {})
    if set(expected) != set(COMPONENTS) or set(observed) != set(COMPONENTS):
        raise AssertionError("successor hinge component set drift")

    max_position_delta = 0.0
    per_component: dict[str, Any] = {}
    for name in COMPONENTS:
        exp = expected[name]
        obs = observed[name]
        exp_positions = exp.get("positions", [])
        obs_positions = obs.get("vertices", [])
        exp_indices = [int(v) for v in exp.get("indices", [])]
        obs_indices = [int(v) for v in obs.get("indices", [])]
        if len(exp_positions) != len(obs_positions):
            raise AssertionError(f"vertex count drift for {name}")
        if exp_indices != obs_indices:
            raise AssertionError(f"imported triangle index/winding drift for {name}")
        if len(exp_indices) != 288 or int(obs.get("triangle_count", 0)) != 96:
            raise AssertionError(f"triangle count drift for {name}")
        component_max = 0.0
        for exp_pos, obs_pos in zip(exp_positions, obs_positions):
            if len(exp_pos) != 3 or len(obs_pos) != 3:
                raise AssertionError(f"malformed position tuple for {name}")
            delta = max(abs(float(exp_pos[i]) - float(obs_pos[i])) for i in range(3))
            component_max = max(component_max, delta)
        if component_max > POSITION_TOLERANCE_M:
            raise AssertionError(f"imported POSITION transport exceeds {POSITION_TOLERANCE_M} m for {name}: {component_max}")
        max_position_delta = max(max_position_delta, component_max)
        per_component[name] = {
            "vertices": len(exp_positions),
            "triangles": len(exp_indices) // 3,
            "indices_exact": True,
            "maximum_position_delta_m": component_max,
        }

    movement = target.get("maximum_world_vertex_movement_m", {})
    for name in ("hinge_lid_l0", "hinge_lid_l1"):
        if float(movement.get(name, 0.0)) < 0.005:
            raise AssertionError(f"lid-owned target movement evidence missing for {name}")
    for name in ("hinge_body_b0", "hinge_body_b1", "hinge_body_b2"):
        if float(movement.get(name, 1.0)) > 1e-6:
            raise AssertionError(f"body-owned target drift evidence exceeds bound for {name}")

    truth = ta.get("truth_boundary", {})
    if truth.get("source_successor_default_adopted") is not False or truth.get("uc_domain_policy_added") is not False:
        raise AssertionError("Technical Art authority boundary drift")

    return {
        "schema": "axm.object-technical-art-hinge-successor002-godot-transport-receipt/v0.1",
        "result": RESULT,
        "technical_art_head": ta["technical_art_head"],
        "hard_surface_head": ta["hard_surface_head"],
        "geometry_head": ta["geometry_head"],
        "rigging_head": ta["rigging_head"],
        "uc_head": ta["uc_head"],
        "successor_id": ta["successor_id"],
        "glb_sha256": target["glb_sha256"],
        "components": per_component,
        "aggregate_triangles": sum(item["triangles"] for item in per_component.values()),
        "maximum_position_delta_m": max_position_delta,
        "index_and_winding_exact_for_all_five_components": True,
        "godot_state": target["state"],
        "review_transform_degrees_x": target["review_transform_degrees_x"],
        "maximum_world_vertex_movement_m": movement,
        "truth_boundary": {
            "target_host_geometry_transport_observed": True,
            "target_host_owner_parentage_observed": True,
            "source_successor_default_adopted": False,
            "automatic_downstream_adoption": False,
            "generic_godot_or_uc_hinge_policy_claimed": False,
            "runtime_or_physics_accepted": False,
            "final_visual_or_art_accepted": False,
            "canon_or_production_accepted": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--surface", required=True)
    parser.add_argument("--ta-receipt", required=True)
    parser.add_argument("--target-receipt", required=True)
    parser.add_argument("--target-arrays", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    receipt = verify(Path(args.surface), Path(args.ta_receipt), Path(args.target_receipt), Path(args.target_arrays))
    Path(args.out).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(RESULT)
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
