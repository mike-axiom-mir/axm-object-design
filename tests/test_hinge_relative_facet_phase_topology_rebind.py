from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.verify_hinge_relative_facet_phase_topology_rebind import evaluate

ROOT = Path(__file__).resolve().parents[1]
ASSET = ROOT / "assets" / "modular-equipment-case-001"
HOST = ASSET / "source.json"
S2 = ASSET / "hinge-bored-knuckle-phase-invariant-source-successor-002.json"
S3 = ASSET / "hinge-bored-knuckle-relative-facet-phase-source-successor-003.json"
CONTRACT = ASSET / "hinge-relative-facet-phase-topology-rebind-003.json"
SOURCE_VERIFIER = ROOT / "tools" / "verify_hinge_bored_knuckle_relative_facet_phase_successor.py"


class RelativeFacetPhaseTopologyRebindTests(unittest.TestCase):
    def test_exact_successor003_rebind(self):
        receipt = evaluate(HOST, S2, S3, CONTRACT, SOURCE_VERIFIER)
        self.assertEqual(receipt["result"], "PASS_OBJECT_RELATIVE_FACET_PHASE_SUCCESSOR_GENUS1_TOPOLOGY_REBIND")
        self.assertEqual(receipt["changed_vertex_positions"], 96)
        self.assertEqual(receipt["unchanged_vertex_positions"], 144)
        self.assertEqual(receipt["successor003_aggregate"]["orientable_genus_sum"], 5)
        self.assertTrue(receipt["face_connectivity_identical_to_successor002"])
        self.assertFalse(receipt["technical_art_successor003_receiver_revalidated"])

    def _write_json(self, payload):
        handle = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(payload, handle, indent=2)
        handle.write("\n")
        handle.close()
        self.addCleanup(lambda: Path(handle.name).unlink(missing_ok=True))
        return Path(handle.name)

    def test_source_successor_blob_drift_fails_closed(self):
        payload = json.loads(S3.read_text())
        payload["source_owned_successor"]["owner_group_phase_deg"]["lid"] = 0.0
        mutated = self._write_json(payload)
        with self.assertRaisesRegex(AssertionError, "successor003 blob drift"):
            evaluate(HOST, S2, mutated, CONTRACT, SOURCE_VERIFIER)

    def test_genus_expectation_cannot_be_weakened(self):
        contract = json.loads(CONTRACT.read_text())
        contract["expected_per_knuckle"]["orientable_genus"] = 0
        mutated = self._write_json(contract)
        with self.assertRaisesRegex(AssertionError, "topology drift"):
            evaluate(HOST, S2, S3, mutated, SOURCE_VERIFIER)

    def test_historical_pass_transfer_cannot_be_enabled(self):
        contract = json.loads(CONTRACT.read_text())
        contract["geometry_authority"]["historical_pass_transferred"] = True
        mutated = self._write_json(contract)
        with self.assertRaisesRegex(AssertionError, "historical Geometry PASS transfer"):
            evaluate(HOST, S2, S3, mutated, SOURCE_VERIFIER)

    def test_receiver_adoption_cannot_be_promoted(self):
        contract = json.loads(CONTRACT.read_text())
        contract["geometry_authority"]["technical_art_receiver_adoption_authorized"] = True
        mutated = self._write_json(contract)
        with self.assertRaisesRegex(AssertionError, "Geometry authority expansion"):
            evaluate(HOST, S2, S3, mutated, SOURCE_VERIFIER)

    def test_source_builder_verifier_identity_is_pinned(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as handle:
            handle.write("# deliberate verifier drift\n")
            path = Path(handle.name)
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        with self.assertRaisesRegex(AssertionError, "builder/verifier blob drift"):
            evaluate(HOST, S2, S3, CONTRACT, path)


if __name__ == "__main__":
    unittest.main()
