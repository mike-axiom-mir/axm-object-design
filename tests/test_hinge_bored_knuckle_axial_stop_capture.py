from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from tools.verify_hinge_bored_knuckle_axial_stop_capture import (
    RESULT,
    _capture_metrics,
    _git_blob_sha1,
    _sha256,
    _stop_sha256,
    evaluate,
)

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "assets/modular-equipment-case-001"
HOST = BASE / "source.json"
BORE = BASE / "hinge-pin-bore-clearance-001.json"
ANNULAR = BASE / "hinge-pin-annular-mesh-001.json"
OWNER = BASE / "hinge-knuckle-owner-stack-001.json"
PREDECESSOR = BASE / "hinge-bored-knuckle-source-successor-001.json"
PHASE_SUCCESSOR = BASE / "hinge-bored-knuckle-phase-invariant-source-successor-002.json"
STOP = BASE / "hinge-pin-axial-stop-001.json"
CAPTURE = BASE / "hinge-bored-knuckle-axial-stop-capture-001.json"


def _load():
    paths = [HOST, BORE, ANNULAR, OWNER, PREDECESSOR, PHASE_SUCCESSOR, STOP, CAPTURE]
    values = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    return (
        *values,
        _sha256(HOST),
        _git_blob_sha1(BORE),
        _git_blob_sha1(ANNULAR),
        _git_blob_sha1(OWNER),
        _git_blob_sha1(PREDECESSOR),
        _git_blob_sha1(PHASE_SUCCESSOR),
        _git_blob_sha1(STOP),
        _stop_sha256(STOP),
    )


def _evaluate(compatibility_override=None, observed_stop_blob_override=None):
    (
        host,
        bore,
        annular,
        owner,
        predecessor,
        phase_successor,
        stop,
        compatibility,
        host_sha,
        bore_blob,
        annular_blob,
        owner_blob,
        predecessor_blob,
        phase_successor_blob,
        stop_blob,
        stop_sha,
    ) = _load()
    if compatibility_override is not None:
        compatibility = compatibility_override(compatibility)
    if observed_stop_blob_override is not None:
        stop_blob = observed_stop_blob_override
    return evaluate(
        host,
        bore,
        annular,
        owner,
        predecessor,
        phase_successor,
        stop,
        compatibility,
        observed_host_sha256=host_sha,
        observed_bore_blob_sha1=bore_blob,
        observed_annular_blob_sha1=annular_blob,
        observed_owner_blob_sha1=owner_blob,
        observed_predecessor_successor_blob_sha1=predecessor_blob,
        observed_phase_successor_blob_sha1=phase_successor_blob,
        observed_stop_blob_sha1=stop_blob,
        observed_stop_contract_sha256=stop_sha,
    )


class HingeBoredKnuckleAxialStopCaptureTests(unittest.TestCase):
    def test_exact_compatibility_passes(self):
        receipt = _evaluate()
        self.assertEqual(receipt["result"], RESULT)
        self.assertEqual(receipt["segments"], 12)
        self.assertEqual(receipt["stop_count"], 2)
        self.assertAlmostEqual(receipt["stop_radius_m"], 0.013, places=12)
        self.assertAlmostEqual(receipt["bore_circumradius_m"], 0.010352761804100828, places=12)
        self.assertAlmostEqual(receipt["phase_independent_capture_overlap_m"], 0.0026472381958991716, places=12)
        self.assertAlmostEqual(receipt["outer_knuckle_inradius_m"], 0.020284442352070435, places=12)
        self.assertAlmostEqual(receipt["outer_knuckle_radial_containment_margin_m"], 0.007284442352070436, places=12)
        self.assertAlmostEqual(receipt["minimum_existing_axial_gap_before_outer_knuckle_contact_m"], 0.014, places=12)
        self.assertAlmostEqual(receipt["bilateral_stop_symmetry_residual_m"], 0.0, places=12)
        self.assertFalse(receipt["automatic_downstream_adoption"])
        self.assertFalse(receipt["rig_parenting_or_retention_authorized"])
        self.assertFalse(receipt["full_component_collision_authorized"])

    def test_zero_capture_overlap_fails_closed(self):
        with self.assertRaisesRegex(AssertionError, "does not positively overlap"):
            _capture_metrics(
                stop_radius=0.010352761804100828,
                bore_circumradius=0.010352761804100828,
                outer_circumradius=0.021,
                segments=12,
            )

    def test_outer_envelope_loss_fails_closed(self):
        with self.assertRaisesRegex(AssertionError, "not contained inside outer knuckle"):
            _capture_metrics(
                stop_radius=0.021,
                bore_circumradius=0.010352761804100828,
                outer_circumradius=0.021,
                segments=12,
            )

    def test_rigging_authority_expansion_fails_closed(self):
        def mutate(compatibility):
            bad = copy.deepcopy(compatibility)
            bad["authority"]["rig_parenting_or_retention_authorized"] = True
            return bad

        with self.assertRaisesRegex(AssertionError, "authority expansion forbidden"):
            _evaluate(mutate)

    def test_invented_bore_phase_fails_closed(self):
        def mutate(compatibility):
            bad = copy.deepcopy(compatibility)
            bad["source_owned_compatibility"]["successor_bore_relative_phase"] = "FIXED_TO_BODY"
            return bad

        with self.assertRaisesRegex(AssertionError, "bore phase must remain unspecified"):
            _evaluate(mutate)

    def test_axial_stop_identity_drift_fails_closed(self):
        with self.assertRaisesRegex(AssertionError, "observed axial-stop contract identity drift"):
            _evaluate(observed_stop_blob_override="0" * 40)


if __name__ == "__main__":
    unittest.main()
