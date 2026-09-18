from __future__ import annotations

import copy
import hashlib
import json
import math
import unittest
from pathlib import Path

from tools.build_hinge_pin_annular_mesh import RESULT, TOPOLOGY_RESULT, evaluate_mesh

ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / "assets/modular-equipment-case-001/source.json"
BORE = ROOT / "assets/modular-equipment-case-001/hinge-pin-bore-clearance-001.json"
MESH = ROOT / "assets/modular-equipment-case-001/hinge-pin-annular-mesh-001.json"


def _load():
    host = json.loads(HOST.read_text(encoding="utf-8"))
    bore = json.loads(BORE.read_text(encoding="utf-8"))
    mesh = json.loads(MESH.read_text(encoding="utf-8"))
    return (
        host,
        bore,
        mesh,
        hashlib.sha256(HOST.read_bytes()).hexdigest(),
        hashlib.sha256(BORE.read_bytes()).hexdigest(),
    )


class HingePinAnnularMeshTests(unittest.TestCase):
    def test_exact_mesh_candidate_passes(self):
        host, bore, mesh_contract, host_sha, bore_sha = _load()
        receipt, candidate = evaluate_mesh(
            host,
            bore,
            mesh_contract,
            observed_host_sha256=host_sha,
            observed_bore_contract_sha256=bore_sha,
        )
        self.assertEqual(receipt["result"], RESULT)
        self.assertEqual(receipt["topology_result"], TOPOLOGY_RESULT)
        self.assertEqual(receipt["candidate_vertices"], 240)
        self.assertEqual(receipt["candidate_triangles"], 480)
        self.assertEqual(receipt["candidate_triangle_components"], 5)
        self.assertEqual(receipt["candidate_boundary_edges"], 0)
        self.assertEqual(receipt["candidate_non_manifold_edges"], 0)
        self.assertEqual(receipt["candidate_orientation_conflicts"], 0)
        self.assertEqual(receipt["candidate_degenerate_triangles"], 0)
        self.assertGreaterEqual(receipt["minimum_mesh_surface_clearance_m"] + 1e-12, 0.001)
        self.assertGreaterEqual(receipt["minimum_mesh_knuckle_wall_m"] + 1e-12, 0.010)
        self.assertFalse(receipt["host_source_geometry_changed"])
        self.assertFalse(receipt["source_adoption"])
        self.assertEqual(len(candidate["groups"]), 5)

    def test_uncompensated_analytic_radius_fails_faceted_clearance(self):
        host, bore, mesh_contract, host_sha, bore_sha = _load()
        bad = copy.deepcopy(mesh_contract)
        bad["mesh_bore_radius_m"] = bore["bore_radius_m"]
        with self.assertRaisesRegex(AssertionError, "mesh bore circumradius does not preserve declared faceted clearance"):
            evaluate_mesh(
                host,
                bore,
                bad,
                observed_host_sha256=host_sha,
                observed_bore_contract_sha256=bore_sha,
            )
        observed = (bore["bore_radius_m"] - host["hinge"]["pin_radius"]) * math.cos(
            math.pi / host["hinge"]["segments"]
        )
        self.assertLess(observed, mesh_contract["minimum_mesh_surface_clearance_m"])

    def test_bore_contract_identity_drift_fails_closed(self):
        host, bore, mesh_contract, host_sha, _ = _load()
        with self.assertRaisesRegex(AssertionError, "bore-clearance prerequisite identity drift"):
            evaluate_mesh(
                host,
                bore,
                mesh_contract,
                observed_host_sha256=host_sha,
                observed_bore_contract_sha256="0" * 64,
            )

    def test_segment_drift_fails_closed(self):
        host, bore, mesh_contract, host_sha, bore_sha = _load()
        bad_host = copy.deepcopy(host)
        bad_host["hinge"]["segments"] = 16
        with self.assertRaisesRegex(AssertionError, "hinge segmentation drift"):
            evaluate_mesh(
                bad_host,
                bore,
                mesh_contract,
                observed_host_sha256=host_sha,
                observed_bore_contract_sha256=bore_sha,
            )


if __name__ == "__main__":
    unittest.main()
