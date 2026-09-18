from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from tools.verify_hinge_bored_knuckle_source_successor import (
    RESULT,
    _git_blob_sha1,
    _sha256,
    evaluate,
)

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "assets/modular-equipment-case-001"
HOST = BASE / "source.json"
BORE = BASE / "hinge-pin-bore-clearance-001.json"
ANNULAR = BASE / "hinge-pin-annular-mesh-001.json"
OWNER = BASE / "hinge-knuckle-owner-stack-001.json"
SUCCESSOR = BASE / "hinge-bored-knuckle-source-successor-001.json"


def _load():
    paths = [HOST, BORE, ANNULAR, OWNER, SUCCESSOR]
    values = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    return (*values, _sha256(HOST), _git_blob_sha1(BORE), _git_blob_sha1(ANNULAR), _git_blob_sha1(OWNER))


def _evaluate(successor_override=None):
    host, bore, annular, owner, successor, host_sha, bore_blob, annular_blob, owner_blob = _load()
    if successor_override is not None:
        successor = successor_override(successor)
    return evaluate(
        host, bore, annular, owner, successor,
        observed_host_sha256=host_sha,
        observed_bore_blob_sha1=bore_blob,
        observed_annular_blob_sha1=annular_blob,
        observed_owner_blob_sha1=owner_blob,
    )


class HingeBoredKnuckleSourceSuccessorTests(unittest.TestCase):
    def test_exact_successor_passes(self):
        receipt = _evaluate()
        self.assertEqual(receipt["result"], RESULT)
        self.assertEqual(receipt["knuckle_count"], 5)
        self.assertEqual(receipt["segments"], 12)
        self.assertEqual(receipt["candidate_vertices"], 240)
        self.assertEqual(receipt["candidate_triangles"], 480)
        self.assertAlmostEqual(receipt["minimum_pin_to_bore_surface_clearance_m"], 0.001, places=12)
        self.assertEqual(receipt["owner_sequence"], ["body", "lid", "body", "lid", "body"])
        self.assertTrue(receipt["legacy_source_default_preserved"])
        self.assertTrue(receipt["hard_surface_source_successor_authorized"])
        self.assertFalse(receipt["automatic_downstream_adoption"])
        self.assertFalse(receipt["manufacturing_fit_class_authorized"])

    def test_automatic_adoption_fails_closed(self):
        def mutate(successor):
            bad = copy.deepcopy(successor)
            bad["source_owned_successor"]["automatic_downstream_adoption"] = True
            return bad
        with self.assertRaisesRegex(AssertionError, "automatic downstream adoption forbidden"):
            _evaluate(mutate)

    def test_legacy_source_rewrite_fails_closed(self):
        def mutate(successor):
            bad = copy.deepcopy(successor)
            bad["source_owned_successor"]["legacy_host_source_rewritten"] = True
            return bad
        with self.assertRaisesRegex(AssertionError, "legacy source rewrite forbidden"):
            _evaluate(mutate)

    def test_manufacturing_fit_authority_fails_closed(self):
        def mutate(successor):
            bad = copy.deepcopy(successor)
            bad["authority"]["manufacturing_fit_class_authorized"] = True
            return bad
        with self.assertRaisesRegex(AssertionError, "authority expansion forbidden"):
            _evaluate(mutate)

    def test_annular_donor_identity_drift_fails_closed(self):
        host, bore, annular, owner, successor, host_sha, bore_blob, _annular_blob, owner_blob = _load()
        with self.assertRaisesRegex(AssertionError, "annular-mesh donor identity drift"):
            evaluate(
                host, bore, annular, owner, successor,
                observed_host_sha256=host_sha,
                observed_bore_blob_sha1=bore_blob,
                observed_annular_blob_sha1="0" * 40,
                observed_owner_blob_sha1=owner_blob,
            )


if __name__ == "__main__":
    unittest.main()
