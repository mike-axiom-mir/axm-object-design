from __future__ import annotations

import copy, json, tempfile, unittest
from pathlib import Path

from tools.verify_hinge_phase_invariant_bored_knuckle_topology_rebind import RESULT, evaluate, inspect, require, solid_control

ROOT=Path(__file__).resolve().parents[1]
ASSET=ROOT/"assets"/"modular-equipment-case-001"
HOST=ASSET/"source.json"
ANNULAR=ASSET/"hinge-pin-annular-mesh-001.json"
SUCCESSOR=ASSET/"hinge-bored-knuckle-phase-invariant-source-successor-002.json"
TOPOLOGY=ASSET/"hinge-phase-invariant-bored-knuckle-topology-rebind-002.json"
BUILDER=ROOT/"tools"/"build_hinge_pin_annular_mesh.py"


class PhaseInvariantBoredKnuckleTopologyRebindTests(unittest.TestCase):
    def test_exact_successor_rebinds_five_genus_one_shells(self):
        r=evaluate(HOST,ANNULAR,SUCCESSOR,TOPOLOGY,BUILDER)
        self.assertEqual(r["result"],RESULT)
        self.assertFalse(r["historical_pass_transferred"])
        self.assertTrue(r["face_connectivity_identical_to_predecessor"])
        self.assertEqual(r["changed_vertex_positions"],120)
        self.assertGreater(r["bore_circumradius_delta_m"],0.0)
        self.assertAlmostEqual(r["maximum_vertex_position_delta_m"],r["bore_circumradius_delta_m"],places=12)
        self.assertEqual(len(r["successor_group_reports"]),5)
        for g in r["successor_group_reports"]:
            self.assertTrue(g["closed_orientable_vertex_manifold"])
            self.assertEqual((g["vertices"],g["triangles"],g["unique_edges"]),(48,96,144))
            self.assertEqual((g["euler_characteristic"],g["orientable_genus"]),(0,1))
        self.assertEqual(r["successor_aggregate"]["orientable_genus_sum"],5)
        self.assertTrue(r["closed_solid_cylinder_negative_control"]["rejected_by_through_bore_gate"])

    def test_closed_solid_is_manifold_but_not_through_bore(self):
        v,f=solid_control(12); observed=inspect(v,f)
        self.assertTrue(observed["closed_orientable_vertex_manifold"])
        self.assertEqual((observed["euler_characteristic"],observed["orientable_genus"]),(2,0))
        expected={"vertices":observed["vertices"],"triangles":observed["triangles"],"unique_edges":observed["unique_edges"],
                  "triangle_components":1,"boundary_edges":0,"non_manifold_edges":0,"orientation_conflicts":0,
                  "degenerate_triangles":0,"isolated_vertices":0,"max_vertex_fan_components":1,"euler_characteristic":0,"orientable_genus":1}
        with self.assertRaisesRegex(AssertionError,"topology drift"):
            require(observed,expected,"solid-control")

    def test_historical_pass_transfer_cannot_be_claimed(self):
        payload=json.loads(TOPOLOGY.read_text())
        payload["geometry_authority"]["historical_pass_transferred"]=True
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/TOPOLOGY.name; p.write_text(json.dumps(payload))
            with self.assertRaisesRegex(AssertionError,"truth boundary"):
                evaluate(HOST,ANNULAR,SUCCESSOR,p,BUILDER)

    def test_geometry_cannot_take_downstream_authority(self):
        payload=json.loads(TOPOLOGY.read_text())
        payload["geometry_authority"]["technical_art_authorized"]=True
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/TOPOLOGY.name; p.write_text(json.dumps(payload))
            with self.assertRaisesRegex(AssertionError,"authority expansion"):
                evaluate(HOST,ANNULAR,SUCCESSOR,p,BUILDER)

    def test_expected_genus_drift_fails_closed(self):
        payload=json.loads(TOPOLOGY.read_text())
        payload["expected_per_knuckle"]["orientable_genus"]=0
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/TOPOLOGY.name; p.write_text(json.dumps(payload))
            with self.assertRaisesRegex(AssertionError,"topology drift"):
                evaluate(HOST,ANNULAR,SUCCESSOR,p,BUILDER)

    def test_changed_vertex_count_drift_fails_closed(self):
        payload=json.loads(TOPOLOGY.read_text())
        payload["expected_changed_vertex_positions"]=0
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/TOPOLOGY.name; p.write_text(json.dumps(payload))
            with self.assertRaisesRegex(AssertionError,"geometric-delta evidence drift"):
                evaluate(HOST,ANNULAR,SUCCESSOR,p,BUILDER)


if __name__=="__main__": unittest.main()
