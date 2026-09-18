from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from tools.verify_hinge_bored_knuckle_axial_stop_bracket import (
    RESULT,
    _axial_bracket_metrics,
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
BRACKET = BASE / "hinge-bored-knuckle-axial-stop-bracket-001.json"


def _load():
    paths = [HOST, BORE, ANNULAR, OWNER, PREDECESSOR, PHASE_SUCCESSOR, STOP, CAPTURE, BRACKET]
    values = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    return (*values, paths)


def _evaluate(bracket_mutator=None, capture_blob_override=None):
    host, bore, annular, owner, predecessor, phase, stop, capture, bracket, paths = _load()
    if bracket_mutator is not None:
        bracket = bracket_mutator(bracket)
    observed_capture_blob = _git_blob_sha1(CAPTURE) if capture_blob_override is None else capture_blob_override
    return evaluate(
        host,
        bore,
        annular,
        owner,
        predecessor,
        phase,
        stop,
        capture,
        bracket,
        observed_host_sha256=_sha256(HOST),
        observed_bore_blob_sha1=_git_blob_sha1(BORE),
        observed_annular_blob_sha1=_git_blob_sha1(ANNULAR),
        observed_owner_blob_sha1=_git_blob_sha1(OWNER),
        observed_predecessor_successor_blob_sha1=_git_blob_sha1(PREDECESSOR),
        observed_phase_successor_blob_sha1=_git_blob_sha1(PHASE_SUCCESSOR),
        observed_stop_blob_sha1=_git_blob_sha1(STOP),
        observed_stop_contract_sha256=_stop_sha256(STOP),
        observed_capture_blob_sha1=observed_capture_blob,
    )


class HingeBoredKnuckleAxialStopBracketTests(unittest.TestCase):
    def test_exact_static_bilateral_bracket_passes(self):
        receipt = _evaluate()
        self.assertEqual(receipt["result"], RESULT)
        self.assertAlmostEqual(receipt["left_stop_inward_face_x_m"], -0.344, places=12)
        self.assertAlmostEqual(receipt["right_stop_inward_face_x_m"], 0.344, places=12)
        self.assertAlmostEqual(receipt["left_stop_outward_face_x_m"], -0.35, places=12)
        self.assertAlmostEqual(receipt["right_stop_outward_face_x_m"], 0.35, places=12)
        self.assertAlmostEqual(receipt["knuckle_stack_min_x_m"], -0.33, places=12)
        self.assertAlmostEqual(receipt["knuckle_stack_max_x_m"], 0.33, places=12)
        self.assertAlmostEqual(receipt["left_static_axial_gap_m"], 0.014, places=12)
        self.assertAlmostEqual(receipt["right_static_axial_gap_m"], 0.014, places=12)
        self.assertAlmostEqual(receipt["complete_knuckle_stack_span_m"], 0.66, places=12)
        self.assertAlmostEqual(receipt["stop_inward_face_bracket_span_m"], 0.688, places=12)
        self.assertAlmostEqual(receipt["total_static_bracket_free_span_m"], 0.028, places=12)
        self.assertAlmostEqual(receipt["bilateral_gap_symmetry_residual_m"], 0.0, places=12)
        self.assertAlmostEqual(receipt["phase_independent_radial_capture_overlap_m"], 0.0026472381958991716, places=12)
        self.assertFalse(receipt["pin_stop_rigid_subassembly_authorized"])
        self.assertFalse(receipt["axial_translation_model_authorized"])
        self.assertFalse(receipt["retention_force_authorized"])

    def test_knuckle_stack_outgrows_left_bracket_fails_closed(self):
        host = json.loads(HOST.read_text(encoding="utf-8"))
        stop = json.loads(STOP.read_text(encoding="utf-8"))
        bad = copy.deepcopy(host)
        bad["hinge"]["knuckles"][0]["center_x"] = -0.30
        with self.assertRaisesRegex(AssertionError, "left stop inward face does not bracket"):
            _axial_bracket_metrics(bad, stop)

    def test_pin_endpoint_seating_drift_fails_closed(self):
        host = json.loads(HOST.read_text(encoding="utf-8"))
        stop = json.loads(STOP.read_text(encoding="utf-8"))
        bad = copy.deepcopy(stop)
        for item in bad["stops"]:
            if item["side"] == "right":
                item["center_x_m"] += 0.001
        with self.assertRaisesRegex(AssertionError, "stop outer faces no longer seat"):
            _axial_bracket_metrics(host, bad)

    def test_retention_authority_expansion_fails_closed(self):
        def mutate(bracket):
            bad = copy.deepcopy(bracket)
            bad["authority"]["retention_force_authorized"] = True
            return bad

        with self.assertRaisesRegex(AssertionError, "authority expansion forbidden"):
            _evaluate(mutate)

    def test_translation_model_authority_expansion_fails_closed(self):
        def mutate(bracket):
            bad = copy.deepcopy(bracket)
            bad["source_owned_geometry"]["axial_translation_model_authorized"] = True
            return bad

        with self.assertRaisesRegex(AssertionError, "axial_translation_model_authorized must remain false"):
            _evaluate(mutate)

    def test_radial_capture_identity_drift_fails_closed(self):
        with self.assertRaisesRegex(AssertionError, "observed radial-capture identity drift"):
            _evaluate(capture_blob_override="0" * 40)


if __name__ == "__main__":
    unittest.main()
