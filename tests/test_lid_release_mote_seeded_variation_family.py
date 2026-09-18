import copy
import json
import unittest
from pathlib import Path

from tools import build_lid_release_mote_seeded_variation_family as mod

ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "assets" / "modular-equipment-case-001" / "lid-release-mote-seeded-variation-family-001.json"


def profile():
    return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))


def synthetic_owner_effect():
    return {
        "schema": "axm.object-reactive-vfx/v0.1",
        "effect_id": "lid-open-release-motes-001",
        "asset_id": "modular-equipment-case-001",
        "animation_dependency": {
            "trigger_phase_id": "play_exact_lid_clip",
            "trigger_time_s": 0.25,
            "trigger_semantics": "EXACT_ANIMATION_PHASE_BOUNDARY_NOT_GAMEPLAY_EVENT",
        },
        "visual_source": {
            "particle_count": 18,
            "seed": 41027,
            "emission_span_s": 0.10,
            "lifetime_min_s": 0.30,
            "lifetime_max_s": 0.44,
            "size_min_m": 0.014,
            "size_max_m": 0.026,
            "vertical_speed_min_mps": 0.22,
            "vertical_speed_max_mps": 0.34,
            "camera_forward_speed_min_mps": 0.025,
            "camera_forward_speed_max_mps": 0.075,
            "lateral_speed_abs_max_mps": 0.055,
            "gravity_visual_mps2": -0.10,
            "color_srgb": [0.78, 0.72, 0.61],
            "alpha_peak": 0.56,
            "anchor": "CAMERA_FACING_LID_BODY_SEAM_DERIVED_FROM_IMPORTED_NEUTRAL_LID_AABB",
            "source_label": "STYLIZED_VISUAL_RELEASE_MOTES_NOT_DUST_OR_FLUID_SIMULATION",
        },
    }


class LidReleaseMoteSeededVariationFamilyTests(unittest.TestCase):
    def test_profile_is_exact_bounded_seed_family(self):
        mod.validate_profile(profile())

    def test_hash_contract_matches_retained_vfx_witnesses(self):
        self.assertAlmostEqual(mod.hash01(41027, 0, 1), 0.0962096209620962)
        self.assertAlmostEqual(mod.hash01(41027, 0, 2), 0.33073307330733076)
        self.assertAlmostEqual(mod.hash01(41027, 0, 8), 0.7377737773777377)
        self.assertAlmostEqual(mod.hash01(17489, 0, 1), 0.7424742474247424)

    def test_four_seeds_make_four_materially_different_tables(self):
        p = profile()
        effect = synthetic_owner_effect()
        outputs = [mod.build_variant(p, effect, row) for row in p["variants"]]
        self.assertEqual(len({row["mote_digest"] for row in outputs}), 4)
        self.assertTrue(all(len(row["motes"]) == 18 for row in outputs))
        for i, left in enumerate(outputs):
            for right in outputs[i + 1:]:
                changed = sum(a["unit_samples"] != b["unit_samples"] for a, b in zip(left["motes"], right["motes"]))
                self.assertEqual(changed, 18)

    def test_owner_seed_first_mote_exact_scalar_expansion(self):
        p = profile()
        row = mod.build_variant(p, synthetic_owner_effect(), p["variants"][0])["motes"][0]
        self.assertAlmostEqual(row["spawn_s"], 0.30652565256525655)
        self.assertAlmostEqual(row["lifetime_s"], 0.41196919691969197)
        self.assertAlmostEqual(row["size_m"], 0.01441044104410441)
        expected = [-0.025440044004400437, 0.2803900390039004, -0.06188868886888688]
        for observed, wanted in zip(row["velocity_mps"], expected):
            self.assertAlmostEqual(observed, wanted)

    def test_duplicate_seed_fails_closed(self):
        p = profile()
        p["variants"][1]["seed"] = p["variants"][0]["seed"]
        with self.assertRaisesRegex(AssertionError, "duplicate seed"):
            mod.validate_profile(p)

    def test_owner_parameter_override_policy_cannot_be_enabled(self):
        p = profile()
        p["parameter_contract"]["owner_effect_parameter_override"] = "ALLOWED"
        with self.assertRaisesRegex(AssertionError, "forbidden seed-family policy drift"):
            mod.validate_profile(p)

    def test_variant_order_does_not_change_canonical_identity_rows(self):
        p = profile()
        effect = synthetic_owner_effect()
        forward = [mod.build_variant(p, effect, row) for row in p["variants"]]
        reverse = [mod.build_variant(p, effect, row) for row in reversed(p["variants"])]
        forward_id = [(row["variant_id"], row["seed"], row["mote_digest"]) for row in sorted(forward, key=lambda row: row["variant_id"])]
        reverse_id = [(row["variant_id"], row["seed"], row["mote_digest"]) for row in sorted(reverse, key=lambda row: row["variant_id"])]
        self.assertEqual(forward_id, reverse_id)

    def test_review_variants_never_claim_adoption(self):
        p = profile()
        effect = synthetic_owner_effect()
        outputs = [mod.build_variant(p, effect, row) for row in p["variants"]]
        self.assertEqual(outputs[0]["adoption"], "OWNER_BASELINE_REPRODUCTION_ONLY")
        self.assertEqual({row["adoption"] for row in outputs[1:]}, {"REVIEW_VARIATION_ONLY"})


if __name__ == "__main__":
    unittest.main()
