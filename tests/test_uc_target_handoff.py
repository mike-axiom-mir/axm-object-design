from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_modular_case import build as build_case
from build_object_uc_target_handoff import (
    bind_source_frame_to_compiled_socket,
    make_uc_surface_group,
    transform_module_to_source_world,
)
from verify_service_module_fit import build_local_mesh


HOST = json.loads((ROOT / "assets/modular-equipment-case-001/source.json").read_text(encoding="utf-8"))
MODULE = json.loads((ROOT / "assets/modular-equipment-case-001/utility-module-001.json").read_text(encoding="utf-8"))


def compiled_atom_from_source(socket: dict) -> dict:
    descriptor = copy.deepcopy(socket["uc_descriptor"])
    descriptor["transform"] = {
        key: [float(v) for v in values]
        for key, values in descriptor["transform"].items()
    }
    return {
        "id": socket["id"],
        "kind": "socket",
        "purpose": "test fixture",
        "uses": ["case-part"],
        "payload": descriptor,
    }


class ObjectUCTargetHandoffTests(unittest.TestCase):
    def test_right_service_binding_uses_source_frame_without_euler_interpretation(self):
        socket = next(s for s in HOST["sockets"] if s["uc_descriptor"]["name"] == "right_service")
        atom = compiled_atom_from_source(socket)
        binding = bind_source_frame_to_compiled_socket(socket, atom)
        self.assertEqual(binding["socket_name"], "right_service")
        self.assertEqual(binding["compiled_position"], [0.39, 0.0, 0.16])
        self.assertEqual(binding["source_normal"], [1.0, 0.0, 0.0])
        self.assertEqual(binding["source_lateral"], [0.0, 1.0, 0.0])
        self.assertEqual(binding["source_up"], [0.0, 0.0, 1.0])
        self.assertEqual(binding["compiled_rotation_euler_retained_not_interpreted"], [0.0, 90.0, 0.0])

    def test_exact_module_places_with_existing_clearance(self):
        socket = next(s for s in HOST["sockets"] if s["uc_descriptor"]["name"] == "right_service")
        atom = compiled_atom_from_source(socket)
        mesh = build_local_mesh(MODULE)
        placed = transform_module_to_source_world(mesh, socket, atom)
        xs = [v[0] for v in placed["vertices"]]
        self.assertAlmostEqual(min(xs), 0.42, places=12)
        self.assertAlmostEqual(max(xs), 0.515, places=12)
        self.assertAlmostEqual(min(xs) - (0.39 + socket["plate_thickness"]), 0.018, places=12)

    def test_compiled_socket_position_drift_fails_closed(self):
        socket = next(s for s in HOST["sockets"] if s["uc_descriptor"]["name"] == "right_service")
        atom = compiled_atom_from_source(socket)
        atom["payload"]["transform"]["position"][0] += 0.001
        with self.assertRaisesRegex(AssertionError, "compiled socket position drift"):
            bind_source_frame_to_compiled_socket(socket, atom)

    def test_surface_projection_is_finite_nondegenerate_and_triangle_preserving(self):
        result = build_case(HOST)
        group = make_uc_surface_group(
            "host-test",
            result["mesh"]["vertices"],
            result["mesh"]["faces"],
            color="#666D72FF",
            metallic=0.18,
            roughness=0.72,
        )
        self.assertEqual(len(group["indices"]) // 3, len(result["mesh"]["faces"]))
        self.assertEqual(len(group["positions"]), len(result["mesh"]["faces"]) * 3)
        self.assertEqual(len(group["normals"]), len(group["positions"]))
        for normal in group["normals"]:
            self.assertAlmostEqual(sum(v * v for v in normal), 1.0, places=10)


if __name__ == "__main__":
    unittest.main()
