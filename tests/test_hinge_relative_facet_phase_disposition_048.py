from __future__ import annotations

import copy
import hashlib
import json
import unittest
from pathlib import Path

from tools.verify_hinge_relative_facet_phase_disposition_048 import evaluate

ROOT = Path(__file__).resolve().parents[1]
ASSET = ROOT / "assets" / "modular-equipment-case-001"


def load(name: str) -> dict:
    return json.loads((ASSET / name).read_text(encoding="utf-8"))


def git_blob_sha1(name: str) -> str:
    data = (ASSET / name).read_bytes()
    h = hashlib.sha1()
    h.update(f"blob {len(data)}\0".encode("ascii"))
    h.update(data)
    return h.hexdigest()


class RelativeFacetPhaseDisposition048Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.successor = load("hinge-bored-knuckle-relative-facet-phase-source-successor-003.json")
        self.disposition = load("hinge-bored-knuckle-relative-facet-phase-disposition-048.json")

    def run_eval(self, *, successor=None, disposition=None):
        successor = self.successor if successor is None else successor
        disposition = self.disposition if disposition is None else disposition
        return evaluate(
            successor,
            disposition,
            observed_successor_blob_sha1=git_blob_sha1(
                "hinge-bored-knuckle-relative-facet-phase-source-successor-003.json"
            ),
        )

    def test_failed_visual_successor_disposition_passes(self) -> None:
        receipt = self.run_eval()
        self.assertEqual(receipt["result"], "PASS_SOURCE_SUCCESSOR_REVIEW_DISPOSITION_RETAINED")
        self.assertTrue(receipt["source_successor_structurally_valid"])
        self.assertEqual(receipt["visual_disposition"], "REJECTED_FOR_CURRENT_HINGE_HIGHLIGHT_REPAIR")
        self.assertEqual(
            receipt["current_review_reference_successor"],
            "modular-equipment-case-001/hinge-bored-knuckle-phase-invariant-source-successor-002",
        )
        self.assertFalse(receipt["phase_sweep_authorized"])
        self.assertFalse(receipt["second_phase_candidate_authorized"])
        self.assertEqual(receipt["next_owner_pr"], 16)

    def test_visual_rejection_cannot_be_relabelled_adopted(self) -> None:
        disposition = copy.deepcopy(self.disposition)
        disposition["disposition"]["adopted_for_current_visual_repair"] = True
        with self.assertRaises(AssertionError):
            self.run_eval(disposition=disposition)

    def test_phase_sweep_cannot_be_reopened(self) -> None:
        disposition = copy.deepcopy(self.disposition)
        disposition["disposition"]["phase_sweep_authorized"] = True
        with self.assertRaises(AssertionError):
            self.run_eval(disposition=disposition)

    def test_second_phase_candidate_cannot_be_reopened(self) -> None:
        disposition = copy.deepcopy(self.disposition)
        disposition["disposition"]["second_phase_candidate_authorized"] = True
        with self.assertRaises(AssertionError):
            self.run_eval(disposition=disposition)

    def test_current_review_reference_cannot_silently_become_failed_successor(self) -> None:
        disposition = copy.deepcopy(self.disposition)
        disposition["disposition"]["current_review_reference"]["source_successor"] = self.disposition["source_successor_id"]
        with self.assertRaises(AssertionError):
            self.run_eval(disposition=disposition)

    def test_materials_artifact_digest_drift_fails(self) -> None:
        disposition = copy.deepcopy(self.disposition)
        disposition["review_identity"]["materials_artifact_sha256"] = "0" * 64
        with self.assertRaises(AssertionError):
            self.run_eval(disposition=disposition)

    def test_next_owner_cannot_be_silently_returned_to_hard_surface(self) -> None:
        disposition = copy.deepcopy(self.disposition)
        disposition["disposition"]["next_owner"]["object_pr"] = 25
        with self.assertRaises(AssertionError):
            self.run_eval(disposition=disposition)

    def test_structural_successor_phase_identity_drift_fails(self) -> None:
        successor = copy.deepcopy(self.successor)
        successor["source_owned_successor"]["owner_group_phase_deg"]["lid"] = 10.0
        with self.assertRaises(AssertionError):
            self.run_eval(successor=successor)


if __name__ == "__main__":
    unittest.main()
