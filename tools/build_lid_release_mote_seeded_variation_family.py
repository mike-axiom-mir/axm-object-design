from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

FAMILY_SCHEMA = "axm.object-lid-release-mote-seeded-variation-family/v0.1"
EFFECT_SCHEMA = "axm.object-reactive-vfx/v0.1"
OUTPUT_SCHEMA = "axm.object-derived-lid-release-mote-seed-variation/v0.1"
SUMMARY_SCHEMA = "axm.object-lid-release-mote-seeded-variation-family-evidence/v0.1"
RESULT = "PASS_BOUNDED_LID_RELEASE_MOTE_SEEDED_VARIATION_FAMILY"
HOLD = "HOLD_INVALID_LID_RELEASE_MOTE_SEEDED_VARIATION_FAMILY"
EXPECTED_OWNER_HEAD = "7994d6f28050053f07dd355d8c54a983b0e8268b"
EXPECTED_EFFECT_BLOB = "83c41db21e16847ac0a69215facd8697853eeb4f"
EXPECTED_VARIANTS = {
    "owner-seed-41027": 41027,
    "review-seed-17489": 17489,
    "review-seed-57203": 57203,
    "review-seed-91811": 91811,
}
SALT_FIELDS = (
    ("seam_x_t", 1),
    ("seam_z_t", 2),
    ("spawn_t", 3),
    ("lifetime_t", 4),
    ("size_t", 5),
    ("lateral_velocity_t", 6),
    ("vertical_velocity_t", 7),
    ("camera_forward_velocity_t", 8),
)


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def digest_json(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def git_blob_sha(path):
    payload = Path(path).read_bytes()
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload).hexdigest()


def hash01(seed, index, salt):
    value = (int(seed) + (int(index) + 1) * 1103515245 + (int(salt) + 1) * 12345) & 0x7FFFFFFF
    return float(value % 10000) / 9999.0


def lerp(a, b, t):
    return float(a) + (float(b) - float(a)) * float(t)


def _required_visual(effect):
    visual = effect.get("visual_source", {})
    required = (
        "particle_count", "seed", "emission_span_s", "lifetime_min_s", "lifetime_max_s",
        "size_min_m", "size_max_m", "vertical_speed_min_mps", "vertical_speed_max_mps",
        "camera_forward_speed_min_mps", "camera_forward_speed_max_mps",
        "lateral_speed_abs_max_mps", "gravity_visual_mps2", "color_srgb", "alpha_peak",
        "anchor", "source_label",
    )
    missing = [key for key in required if key not in visual]
    if missing:
        raise AssertionError(f"owner VFX visual contract incomplete: {missing}")
    return visual


def validate_profile(profile):
    if profile.get("schema") != FAMILY_SCHEMA:
        raise AssertionError("seeded mote family schema drift")
    if profile.get("family_id") != "object-lid-release-mote-seeded-variation-001":
        raise AssertionError("seeded mote family identity drift")
    owner = profile.get("owner_vfx", {})
    if owner.get("exact_head") != EXPECTED_OWNER_HEAD:
        raise AssertionError("VFX owner head drift")
    if owner.get("effect_git_blob_sha") != EXPECTED_EFFECT_BLOB:
        raise AssertionError("VFX owner effect blob pin drift")
    if owner.get("required_effect_schema") != EFFECT_SCHEMA:
        raise AssertionError("VFX owner schema pin drift")
    contract = profile.get("parameter_contract", {})
    if contract.get("seed_only_variation") is not True:
        raise AssertionError("seed-only variation boundary drift")
    if int(contract.get("maximum_variants", -1)) != 4:
        raise AssertionError("variation bound drift")
    if int(contract.get("maximum_particles_per_variant", -1)) != 64:
        raise AssertionError("particle bound drift")
    for key in (
        "duplicate_seeds", "owner_effect_parameter_override", "owner_timing_override",
        "owner_semantics_override", "automatic_vfx_adoption", "automatic_runtime_adoption",
    ):
        if contract.get(key) != "FORBIDDEN":
            raise AssertionError(f"forbidden seed-family policy drift: {key}")
    variants = profile.get("variants", [])
    if len(variants) != 4:
        raise AssertionError("exact four-variant review family required")
    observed = {}
    seeds = set()
    for row in variants:
        variant_id = str(row.get("variant_id", ""))
        seed = int(row.get("seed", -1))
        if variant_id in observed:
            raise AssertionError("duplicate variant identity")
        if seed in seeds:
            raise AssertionError("duplicate seed")
        if seed < int(contract.get("seed_min", 0)) or seed > int(contract.get("seed_max", 2147483647)):
            raise AssertionError("seed outside bounded domain")
        observed[variant_id] = seed
        seeds.add(seed)
    if observed != EXPECTED_VARIANTS:
        raise AssertionError("bounded review seed set drift")
    if profile.get("hash_contract", {}).get("salts") != {key: salt for key, salt in SALT_FIELDS}:
        raise AssertionError("hash salt contract drift")


def validate_owner_effect(profile, effect, *, effect_path, owner_head):
    owner = profile["owner_vfx"]
    if owner_head != owner["exact_head"]:
        raise AssertionError("VFX owner head mismatch")
    if git_blob_sha(effect_path) != owner["effect_git_blob_sha"]:
        raise AssertionError("VFX owner effect blob drift")
    if effect.get("schema") != owner["required_effect_schema"]:
        raise AssertionError("owner effect schema drift")
    if effect.get("effect_id") != owner["effect_id"] or effect.get("asset_id") != "modular-equipment-case-001":
        raise AssertionError("owner effect identity drift")
    dependency = effect.get("animation_dependency", {})
    if dependency.get("trigger_phase_id") != owner["required_animation_phase"]:
        raise AssertionError("owner Animation phase drift")
    if dependency.get("trigger_semantics") != owner["required_trigger_semantics"]:
        raise AssertionError("owner trigger semantics drift")
    visual = _required_visual(effect)
    if visual.get("source_label") != owner["required_source_label"]:
        raise AssertionError("owner visual semantics drift")
    if visual.get("anchor") != owner["required_anchor"]:
        raise AssertionError("owner anchor semantics drift")
    count = int(visual["particle_count"])
    if count < 1 or count > int(profile["parameter_contract"]["maximum_particles_per_variant"]):
        raise AssertionError("owner particle count outside bounded review envelope")
    if int(visual["seed"]) != EXPECTED_VARIANTS["owner-seed-41027"]:
        raise AssertionError("owner baseline seed drift")
    for lo, hi, label in (
        (visual["lifetime_min_s"], visual["lifetime_max_s"], "lifetime"),
        (visual["size_min_m"], visual["size_max_m"], "size"),
        (visual["vertical_speed_min_mps"], visual["vertical_speed_max_mps"], "vertical speed"),
        (visual["camera_forward_speed_min_mps"], visual["camera_forward_speed_max_mps"], "camera-forward speed"),
    ):
        if float(lo) > float(hi):
            raise AssertionError(f"owner {label} range inverted")
    return visual, dependency


def build_variant(profile, effect, variant):
    visual = _required_visual(effect)
    dep = effect["animation_dependency"]
    seed = int(variant["seed"])
    motes = []
    for index in range(int(visual["particle_count"])):
        unit = {key: hash01(seed, index, salt) for key, salt in SALT_FIELDS}
        mote = {
            "index": index,
            "unit_samples": unit,
            "seam_normalized": [unit["seam_x_t"], unit["seam_z_t"]],
            "spawn_s": float(dep["trigger_time_s"]) + float(visual["emission_span_s"]) * unit["spawn_t"],
            "lifetime_s": lerp(visual["lifetime_min_s"], visual["lifetime_max_s"], unit["lifetime_t"]),
            "size_m": lerp(visual["size_min_m"], visual["size_max_m"], unit["size_t"]),
            "velocity_mps": [
                lerp(-float(visual["lateral_speed_abs_max_mps"]), float(visual["lateral_speed_abs_max_mps"]), unit["lateral_velocity_t"]),
                lerp(visual["vertical_speed_min_mps"], visual["vertical_speed_max_mps"], unit["vertical_velocity_t"]),
                -lerp(visual["camera_forward_speed_min_mps"], visual["camera_forward_speed_max_mps"], unit["camera_forward_velocity_t"]),
            ],
        }
        motes.append(mote)
    mote_digest = digest_json(motes)
    return {
        "schema": OUTPUT_SCHEMA,
        "family_id": profile["family_id"],
        "variant_id": variant["variant_id"],
        "role": variant["role"],
        "seed": seed,
        "owner_effect_id": effect["effect_id"],
        "owner_particle_count": int(visual["particle_count"]),
        "owner_trigger_time_s": float(dep["trigger_time_s"]),
        "owner_hash_contract": profile["hash_contract"]["id"],
        "seam_coordinate_boundary": "NORMALIZED_0_TO_1_ONLY_WORLD_SEAM_BOUNDS_REMAIN_VFX_TARGET_HOST_OWNED",
        "motes": motes,
        "mote_digest": mote_digest,
        "adoption": "REVIEW_VARIATION_ONLY" if variant["role"] != "EXACT_OWNER_BASELINE_SEED" else "OWNER_BASELINE_REPRODUCTION_ONLY",
    }


def build_family(profile, effect, *, effect_path, owner_head):
    validate_profile(profile)
    visual, dependency = validate_owner_effect(profile, effect, effect_path=effect_path, owner_head=owner_head)
    outputs = [build_variant(profile, effect, row) for row in profile["variants"]]
    outputs.sort(key=lambda row: row["variant_id"])
    digests = [row["mote_digest"] for row in outputs]
    if len(set(digests)) != len(outputs):
        raise AssertionError("seed variation did not produce distinct mote tables")
    difference_rows = []
    for left_index, left in enumerate(outputs):
        for right in outputs[left_index + 1:]:
            changed = sum(
                digest_json(a["unit_samples"]) != digest_json(b["unit_samples"])
                for a, b in zip(left["motes"], right["motes"])
            )
            if changed != int(visual["particle_count"]):
                raise AssertionError("seed variants are not materially distinct across every retained mote")
            difference_rows.append({
                "left": left["variant_id"], "right": right["variant_id"],
                "changed_mote_parameter_rows": changed,
            })
    identity = {
        "owner_head": owner_head,
        "owner_effect_blob": git_blob_sha(effect_path),
        "owner_effect_id": effect["effect_id"],
        "owner_particle_count": int(visual["particle_count"]),
        "owner_trigger_time_s": float(dependency["trigger_time_s"]),
        "variants": [{"variant_id": row["variant_id"], "seed": row["seed"], "mote_digest": row["mote_digest"]} for row in outputs],
    }
    family_digest = digest_json(identity)
    return outputs, {
        "schema": SUMMARY_SCHEMA,
        "result": RESULT,
        "family_id": profile["family_id"],
        "owner_vfx_head": owner_head,
        "owner_effect_git_blob_sha": git_blob_sha(effect_path),
        "owner_effect_id": effect["effect_id"],
        "owner_baseline_seed": int(visual["seed"]),
        "variant_count": len(outputs),
        "particle_count_per_variant": int(visual["particle_count"]),
        "distinct_mote_table_digests": len(set(digests)),
        "pairwise_material_difference": difference_rows,
        "family_digest": family_digest,
        "ordering": "CANONICAL_VARIANT_ID_FOR_DIGEST",
        "decision": "PASS_DERIVED_SEEDED_MOTE_PARAMETER_FAMILY_ONLY__NO_VFX_RUNTIME_OR_VISUAL_ADOPTION",
        "truth_boundary": copy.deepcopy(profile["truth_boundary"]),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--owner-effect", required=True)
    parser.add_argument("--owner-head", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    profile = load_json(args.profile)
    effect = load_json(args.owner_effect)
    outputs, summary = build_family(profile, effect, effect_path=args.owner_effect, owner_head=args.owner_head)
    out = Path(args.output_dir)
    for row in outputs:
        write_json(out / f"{row['variant_id']}.json", row)
    write_json(out / "summary.json", summary)
    print(summary["result"])
    print(summary["family_digest"])


if __name__ == "__main__":
    main()
