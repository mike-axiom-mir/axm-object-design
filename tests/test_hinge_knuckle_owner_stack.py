from __future__ import annotations

import copy
import hashlib
import json
import unittest
from pathlib import Path

from tools.verify_hinge_knuckle_owner_stack import RESULT, evaluate

ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / "assets/modular-equipment-case-001/source.json"
CONTRACT = ROOT / "assets/modular-equipment-case-001/hinge-knuckle-owner-stack-001.json"


def _load():
    host = json.loads(HOST.read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    sha = hashlib.sha256(HOST.read_bytes()).hexdigest()
    return host, contract, sha


class HingeKnuckleOwnerStackTests(unittest.TestCase):
    def test_exact_owner_stack_passes(self):
        host, contract, sha = _load()
        receipt = evaluate(host, contract, observed_host_sha256=sha)
        self.assertEqual(receipt["result"], RESULT)
        self.assertEqual(receipt["owner_sequence"], ["body", "lid", "body", "lid", "body"])
        self.assertEqual(receipt["owner_counts"], {"body": 3, "lid": 2})
        self.assertEqual([row["lid_id"] for row in receipt["lid_bracketing"]], ["l0", "l1"])
        self.assertAlmostEqual(receipt["minimum_inter_knuckle_gap_m"], 0.04, places=12)
        self.assertAlmostEqual(receipt["axial_clearance_surplus_m"], 0.03, places=12)
        self.assertEqual(receipt["maximum_stack_symmetry_residual_m"], 0.0)
        self.assertFalse(receipt["source_geometry_changed"])
        self.assertFalse(receipt["rig_parenting_authorized"])

    def test_owner_label_drift_fails_even_when_geometry_is_unchanged(self):
        host, contract, sha = _load()
        bad = copy.deepcopy(host)
        bad["hinge"]["knuckles"][1]["owner"] = "body"
        with self.assertRaisesRegex(AssertionError, "hinge owner-stack drift"):
            evaluate(bad, contract, observed_host_sha256=sha)

    def test_axial_pitch_drift_fails_closed(self):
        host, contract, sha = _load()
        bad = copy.deepcopy(host)
        bad["hinge"]["knuckles"][1]["center_x"] = -0.139
        with self.assertRaisesRegex(AssertionError, "knuckle center pitch drift"):
            evaluate(bad, contract, observed_host_sha256=sha)

    def test_source_clearance_threshold_drift_fails_closed(self):
        host, contract, sha = _load()
        bad = copy.deepcopy(host)
        bad["hinge"]["min_axial_clearance"] = 0.009
        with self.assertRaisesRegex(AssertionError, "source axial-clearance threshold drift"):
            evaluate(bad, contract, observed_host_sha256=sha)

    def test_authority_expansion_fails_closed(self):
        host, contract, sha = _load()
        bad = copy.deepcopy(contract)
        bad["authority"]["rig_parenting_authorized"] = True
        with self.assertRaisesRegex(AssertionError, "authority expansion forbidden"):
            evaluate(host, bad, observed_host_sha256=sha)

    def test_source_identity_drift_fails_closed(self):
        host, contract, _ = _load()
        with self.assertRaisesRegex(AssertionError, "host source identity drift"):
            evaluate(host, contract, observed_host_sha256="0" * 64)


if __name__ == "__main__":
    unittest.main()
