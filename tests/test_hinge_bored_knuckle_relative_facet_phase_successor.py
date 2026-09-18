from __future__ import annotations

import copy
import hashlib
import json
import unittest
from pathlib import Path

from tools.verify_hinge_bored_knuckle_relative_facet_phase_successor import evaluate

ROOT = Path(__file__).resolve().parents[1]
ASSET = ROOT / "assets" / "modular-equipment-case-001"


def load(name: str) -> dict:
    return json.loads((ASSET / name).read_text(encoding="utf-8"))


def sha256(name: str) -> str:
    return hashlib.sha256((ASSET / name).read_bytes()).hexdigest()


def git_blob_sha1(name: str) -> str:
    data = (ASSET / name).read_bytes()
    h = hashlib.sha1()
    h.update(f"blob {len(data)}\0".encode("ascii"))
    h.update(data)
    return h.hexdigest()


class RelativeFacetPhaseSuccessorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.host = load("source.json")
        self.successor = load("hinge-bored-knuckle-phase-invariant-source-successor-002.json")
        self.owner = load("hinge-knuckle-owner-stack-001.json")
        self.stop = load("hinge-pin-axial-stop-001.json")
        self.capture = load("hinge-bored-knuckle-axial-stop-capture-001.json")
        self.bracket = load("hinge-bored-knuckle-axial-stop-bracket-001.json")
        self.contract = load("hinge-bored-knuckle-relative-facet-phase-source-successor-003.json")
        self.identity = {
            "observed_host_sha256": sha256("source.json"),
            "observed_successor002_blob_sha1": git_blob_sha1("hinge-bored-knuckle-phase-invariant-source-successor-002.json"),
            "observed_owner_stack_blob_sha1": git_blob_sha1("hinge-knuckle-owner-stack-001.json"),
            "observed_axial_stop_blob_sha1": git_blob_sha1("hinge-pin-axial-stop-001.json"),
            "observed_capture_blob_sha1": git_blob_sha1("hinge-bored-knuckle-axial-stop-capture-001.json"),
            "observed_bracket_blob_sha1": git_blob_sha1("hinge-bored-knuckle-axial-stop-bracket-001.json"),
        }

    def run_eval(self, **replacements):
        args = {
            "host": self.host,
            "successor002": self.successor,
            "owner_stack": self.owner,
            "axial_stop": self.stop,
            "capture": self.capture,
            "bracket": self.bracket,
            "contract": self.contract,
        }
        args.update(replacements)
        return evaluate(**args, **self.identity)

    def test_single_half_sector_successor_passes(self) -> None:
        receipt, mesh = self.run_eval()
        self.assertEqual(receipt["result"], "PASS_SOURCE_OWNED_HINGE_RELATIVE_FACET_PHASE_SUCCESSOR")
        self.assertAlmostEqual(receipt["body_phase_deg"], 0.0)
        self.assertAlmostEqual(receipt["lid_phase_deg"], 15.0)
        self.assertAlmostEqual(receipt["relative_lid_minus_body_phase_deg"], 15.0)
        self.assertEqual(receipt["body_owned_knuckles"], 3)
        self.assertEqual(receipt["lid_owned_knuckles"], 2)
        self.assertEqual(receipt["candidate_vertices"], 240)
        self.assertEqual(receipt["candidate_triangles"], 480)
        self.assertEqual(receipt["candidate_triangle_components"], 5)
        self.assertGreaterEqual(receipt["phase_independent_pin_bore_clearance_m"] + 1e-12, 0.001)
        self.assertGreater(receipt["phase_independent_stop_bore_capture_overlap_m"], 0.0)
        self.assertGreater(receipt["stop_to_outer_knuckle_inradius_containment_m"], 0.0)
        self.assertAlmostEqual(receipt["left_static_axial_gap_m"], 0.014)
        self.assertAlmostEqual(receipt["right_static_axial_gap_m"], 0.014)
        self.assertFalse(receipt["automatic_downstream_adoption"])
        self.assertEqual(len(mesh["groups"]), 5)

    def test_collapsing_lid_phase_to_predecessor_fails(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["source_owned_successor"]["owner_group_phase_deg"]["lid"] = 0.0
        contract["source_owned_successor"]["relative_lid_minus_body_phase_deg"] = 0.0
        with self.assertRaises(AssertionError):
            self.run_eval(contract=contract)

    def test_full_sector_alias_is_not_the_authored_candidate(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["source_owned_successor"]["owner_group_phase_deg"]["lid"] = 30.0
        contract["source_owned_successor"]["relative_lid_minus_body_phase_deg"] = 30.0
        with self.assertRaises(AssertionError):
            self.run_eval(contract=contract)

    def test_owner_stack_drift_fails_without_geometry_motion(self) -> None:
        owner = copy.deepcopy(self.owner)
        owner["ordered_knuckles"][1]["owner"] = "body"
        with self.assertRaises(AssertionError):
            self.run_eval(owner_stack=owner)

    def test_bore_dimension_drift_fails(self) -> None:
        successor = copy.deepcopy(self.successor)
        successor["source_owned_successor"]["bore_circumradius_m"] += 0.0001
        with self.assertRaises(AssertionError):
            self.run_eval(successor002=successor)

    def test_complete_cross_section_rotation_cannot_be_weakened(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["source_owned_successor"]["rotate_outer_and_bore_cross_sections_together"] = False
        with self.assertRaises(AssertionError):
            self.run_eval(contract=contract)

    def test_clearance_requirement_cannot_be_silently_relaxed_or_inflated(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["required_reproof"]["minimum_pin_bore_phase_independent_clearance_m"] = 0.0011
        with self.assertRaises(AssertionError):
            self.run_eval(contract=contract)

    def test_downstream_authority_expansion_fails(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["authority"]["visual_acceptance_authorized"] = True
        with self.assertRaises(AssertionError):
            self.run_eval(contract=contract)

    def test_phase_sweep_authority_expansion_fails(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["art_direction_return"]["no_phase_sweep"] = False
        with self.assertRaises(AssertionError):
            self.run_eval(contract=contract)


if __name__ == "__main__":
    unittest.main()
