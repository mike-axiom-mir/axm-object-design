from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from tools.verify_hinge_bored_knuckle_phase_invariant_successor import (
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
PREDECESSOR = BASE / "hinge-bored-knuckle-source-successor-001.json"
SUCCESSOR = BASE / "hinge-bored-knuckle-phase-invariant-source-successor-002.json"


def _load():
    paths = [HOST, BORE, ANNULAR, OWNER, PREDECESSOR, SUCCESSOR]
    values = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    return (
        *values,
        _sha256(HOST),
        _git_blob_sha1(BORE),
        _git_blob_sha1(ANNULAR),
        _git_blob_sha1(OWNER),
        _git_blob_sha1(PREDECESSOR),
    )


def _evaluate(successor_override=None, predecessor_blob_override=None):
    host, bore, annular, owner, predecessor, successor, host_sha, bore_blob, annular_blob, owner_blob, predecessor_blob = _load()
    if successor_override is not None:
        successor = successor_override(successor)
    if predecessor_blob_override is not None:
        predecessor_blob = predecessor_blob_override
    return evaluate(
        host, bore, annular, owner, predecessor, successor,
        observed_host_sha256=host_sha,
        observed_bore_blob_sha1=bore_blob,
        observed_annular_blob_sha1=annular_blob,
        observed_owner_blob_sha1=owner_blob,
        observed_predecessor_successor_blob_sha1=predecessor_blob,
    )


class HingeBoredKnucklePhaseInvariantSuccessorTests(unittest.TestCase):
    def test_exact_phase_invariant_successor_passes(self):
        receipt, _mesh = _evaluate()
        self.assertEqual(receipt["result"], RESULT)
        self.assertEqual(receipt["knuckle_count"], 5)
        self.assertEqual(receipt["segments"], 12)
        self.assertEqual(receipt["candidate_vertices"], 240)
        self.assertEqual(receipt["candidate_triangles"], 480)
        self.assertEqual(receipt["candidate_boundary_edges"], 0)
        self.assertEqual(receipt["candidate_non_manifold_edges"], 0)
        self.assertEqual(receipt["candidate_orientation_conflicts"], 0)
        self.assertEqual(receipt["candidate_degenerate_triangles"], 0)
        self.assertAlmostEqual(receipt["predecessor_phase_independent_radial_clearance_m"], 0.0006933324366016139, places=12)
        self.assertAlmostEqual(receipt["successor_phase_independent_radial_clearance_m"], 0.001, places=12)
        self.assertAlmostEqual(receipt["successor_same_phase_radial_clearance_m"], 0.0013066675633983836, places=12)
        self.assertGreaterEqual(receipt["successor_minimum_faceted_knuckle_wall_m"], 0.01)
        self.assertEqual(receipt["owner_sequence"], ["body", "lid", "body", "lid", "body"])
        self.assertEqual(receipt["pin_relative_axial_phase"], "UNSPECIFIED")
        self.assertFalse(receipt["automatic_downstream_adoption"])
        self.assertFalse(receipt["manufacturing_fit_class_authorized"])

    def test_predecessor_bore_fails_phase_invariant_requirement(self):
        def mutate(successor):
            bad = copy.deepcopy(successor)
            bad["source_owned_successor"]["bore_circumradius_m"] = 0.010035276180410082
            return bad
        with self.assertRaisesRegex(AssertionError, "phase-invariant bore radius drift"):
            _evaluate(mutate)

    def test_automatic_adoption_fails_closed(self):
        def mutate(successor):
            bad = copy.deepcopy(successor)
            bad["source_owned_successor"]["automatic_downstream_adoption"] = True
            return bad
        with self.assertRaisesRegex(AssertionError, "automatic downstream adoption forbidden"):
            _evaluate(mutate)

    def test_invented_pin_phase_fails_closed(self):
        def mutate(successor):
            bad = copy.deepcopy(successor)
            bad["source_owned_successor"]["pin_relative_axial_phase"] = "FIXED_TO_BODY"
            return bad
        with self.assertRaisesRegex(AssertionError, "pin relative axial phase must remain unspecified"):
            _evaluate(mutate)

    def test_manufacturing_fit_authority_fails_closed(self):
        def mutate(successor):
            bad = copy.deepcopy(successor)
            bad["authority"]["manufacturing_fit_class_authorized"] = True
            return bad
        with self.assertRaisesRegex(AssertionError, "authority expansion forbidden"):
            _evaluate(mutate)

    def test_predecessor_successor_identity_drift_fails_closed(self):
        with self.assertRaisesRegex(AssertionError, "predecessor successor identity drift"):
            _evaluate(predecessor_blob_override="0" * 40)


if __name__ == "__main__":
    unittest.main()
