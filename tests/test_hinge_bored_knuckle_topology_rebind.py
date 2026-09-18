from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from tools.verify_hinge_bored_knuckle_topology_rebind import (
    RESULT,
    _build_closed_solid_cylinder_control,
    _require_expected_topology,
    evaluate,
    inspect_topology,
)

ROOT = Path(__file__).resolve().parents[1]
ASSET = ROOT / "assets" / "modular-equipment-case-001"
HOST = ASSET / "source.json"
BORE = ASSET / "hinge-pin-bore-clearance-001.json"
ANNULAR = ASSET / "hinge-pin-annular-mesh-001.json"
SUCCESSOR = ASSET / "hinge-bored-knuckle-source-successor-001.json"
TOPOLOGY = ASSET / "hinge-bored-knuckle-topology-rebind-001.json"


class BoredKnuckleTopologyRebindTests(unittest.TestCase):
    def test_exact_successor_is_five_genus_one_vertex_manifolds(self) -> None:
        receipt = evaluate(HOST, BORE, ANNULAR, SUCCESSOR, TOPOLOGY)
        self.assertEqual(receipt["result"], RESULT)
        self.assertEqual(len(receipt["group_reports"]), 5)
        for group in receipt["group_reports"]:
            self.assertTrue(group["closed_orientable_vertex_manifold"])
            self.assertEqual(group["vertices"], 48)
            self.assertEqual(group["triangles"], 96)
            self.assertEqual(group["unique_edges"], 144)
            self.assertEqual(group["euler_characteristic"], 0)
            self.assertEqual(group["orientable_genus"], 1)
            self.assertEqual(group["max_vertex_fan_components"], 1)
        self.assertEqual(receipt["aggregate"]["vertices"], 240)
        self.assertEqual(receipt["aggregate"]["triangles"], 480)
        self.assertEqual(receipt["aggregate"]["unique_edges"], 720)
        self.assertEqual(receipt["aggregate"]["orientable_genus_sum"], 5)
        self.assertTrue(receipt["closed_solid_cylinder_negative_control"]["rejected_by_through_bore_gate"])

    def test_closed_solid_cylinder_is_closed_but_wrong_topology_class(self) -> None:
        vertices, faces = _build_closed_solid_cylinder_control(12)
        observed = inspect_topology(vertices, faces)
        self.assertTrue(observed["closed_orientable_vertex_manifold"])
        self.assertEqual(observed["boundary_edges"], 0)
        self.assertEqual(observed["non_manifold_edges"], 0)
        self.assertEqual(observed["orientation_conflicts"], 0)
        self.assertEqual(observed["euler_characteristic"], 2)
        self.assertEqual(observed["orientable_genus"], 0)
        expected = {
            "vertices": observed["vertices"],
            "triangles": observed["triangles"],
            "unique_edges": observed["unique_edges"],
            "triangle_components": 1,
            "boundary_edges": 0,
            "non_manifold_edges": 0,
            "orientation_conflicts": 0,
            "degenerate_triangles": 0,
            "isolated_vertices": 0,
            "max_vertex_fan_components": 1,
            "euler_characteristic": 0,
            "orientable_genus": 1,
        }
        with self.assertRaisesRegex(AssertionError, "topology drift"):
            _require_expected_topology(observed, expected, "solid-control")

    def test_successor_cannot_auto_adopt_downstream(self) -> None:
        payload = json.loads(SUCCESSOR.read_text(encoding="utf-8"))
        payload["source_owned_successor"]["automatic_downstream_adoption"] = True
        with tempfile.TemporaryDirectory() as tmp:
            mutated = Path(tmp) / SUCCESSOR.name
            mutated.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(AssertionError, "source-successor contract blob drift|automatic downstream adoption"):
                evaluate(HOST, BORE, ANNULAR, mutated, TOPOLOGY)

    def test_geometry_contract_cannot_take_runtime_authority(self) -> None:
        payload = json.loads(TOPOLOGY.read_text(encoding="utf-8"))
        payload["geometry_authority"]["runtime_or_physics_authorized"] = True
        with tempfile.TemporaryDirectory() as tmp:
            mutated = Path(tmp) / TOPOLOGY.name
            mutated.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(AssertionError, "Geometry authority expansion"):
                evaluate(HOST, BORE, ANNULAR, SUCCESSOR, mutated)

    def test_expected_genus_drift_fails_closed(self) -> None:
        payload = json.loads(TOPOLOGY.read_text(encoding="utf-8"))
        payload["expected_per_knuckle"]["orientable_genus"] = 0
        with tempfile.TemporaryDirectory() as tmp:
            mutated = Path(tmp) / TOPOLOGY.name
            mutated.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(AssertionError, "topology drift"):
                evaluate(HOST, BORE, ANNULAR, SUCCESSOR, mutated)


if __name__ == "__main__":
    unittest.main()
