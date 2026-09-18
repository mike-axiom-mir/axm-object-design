from __future__ import annotations

import json
import unittest
from pathlib import Path


CONTRACT = Path("lookdev/object_hinge_successor003_relative_facet_phase_material_review_001.json")
EXPECTED_RIG = {
    "repository": "mike-axiom-mir/axm-object-design",
    "pull_request": 27,
    "exact_head": "0974a97af10fedf62a5803a88921faf96f3448d5",
    "artifact_id": 10539181299,
    "artifact_sha256": "85afbaa5fd948ed5135826fbe0d8c842b6917545c2d897e2756dc098dbc1731b",
    "expected_result": "PASS_HINGE_RELATIVE_FACET_PHASE_SUCCESSOR_RIG_PHASE_COMPOSITION_CONTINUOUS_0_TO_110",
    "successor003_head": "ef1dfc2f2c1adbe3c90ba089c66ac09d223df25c",
    "successor003_contract_blob": "e7a44523ea80e567a745cd61af7fd7005757cc12",
    "joint": "rear-lid-hinge-001",
    "axis_source": [1, 0, 0],
    "opening_sign": -1,
    "source_angle_domain_deg": [0.0, 110.0],
    "body_phase_deg": 0.0,
    "lid_phase_deg": 15.0,
    "visual_authority": False,
}


class Successor003MaterialsRigBindingTest(unittest.TestCase):
    def test_exact_rigging_provenance_is_bound_without_adoption(self) -> None:
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(contract.get("rigging_owner"), EXPECTED_RIG)
        truth = contract.get("truth_boundary", {})
        self.assertIs(truth.get("rigging_or_animation_accepted"), False)
        self.assertIs(truth.get("source_successor_default_adopted"), False)
        self.assertIs(truth.get("art_direction_acceptance"), False)
        self.assertIs(truth.get("visual_qa_acceptance"), False)


if __name__ == "__main__":
    unittest.main()
