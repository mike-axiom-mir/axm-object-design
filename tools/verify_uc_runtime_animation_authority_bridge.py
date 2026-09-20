from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

SCHEMA = "axm.object-ta-current-target-uc-animation-authority-bridge/v0.2"
RESULT = "PASS_UC_RUNTIME_CLOCK_OVER_CURRENT_TARGET_RIGGED_ANIMATION"
PROTECTED_ANIMATION_PATHS = (
    "assets/modular-equipment-case-001/lid-latch-motion-sequence-001.json",
    "assets/modular-equipment-case-001/lid-motion-clip.json",
    "tools/build_lid_motion_evidence.py",
    "tools/build_lid_latch_motion_evidence.py",
    "animation-proof/observe_animationplayer.gd",
)

def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()

def is_ancestor(root: Path, ancestor: str, head: str) -> bool:
    return subprocess.call(
        ["git", "-C", str(root), "merge-base", "--is-ancestor", ancestor, head],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ) == 0

def blob(root: Path, ref: str, path: str) -> str:
    return git(root, "rev-parse", f"{ref}:{path}")

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", type=Path, default=Path("."))
    p.add_argument("--sequence-evidence", type=Path, required=True)
    p.add_argument("--runtime-bridge", type=Path, required=True)
    p.add_argument("--lid-target-binding", type=Path, required=True)
    p.add_argument("--latch-target-binding", type=Path, required=True)
    p.add_argument("--animation-authority-head", required=True)
    p.add_argument("--prior-technical-art-head", required=True)
    p.add_argument("--technical-art-head", required=True)
    p.add_argument("--historical-technical-art-head", required=True)
    p.add_argument("--lid-target-rig-head", required=True)
    p.add_argument("--latch-target-rig-head", required=True)
    p.add_argument("--current-latch-source-rig-head", required=True)
    p.add_argument("--exact-head", required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    root = a.repo_root.resolve()
    if git(root, "rev-parse", a.exact_head) != a.exact_head: raise AssertionError("exact receiving head drift")
    if not is_ancestor(root, a.animation_authority_head, a.exact_head): raise AssertionError("current Animation authority head is not in receiving ancestry")
    if not is_ancestor(root, a.prior_technical_art_head, a.exact_head): raise AssertionError("prior Technical Art bridge head is not in receiving ancestry")
    protected_blobs: dict[str, str] = {}
    for path in PROTECTED_ANIMATION_PATHS:
        authority_blob = blob(root, a.animation_authority_head, path)
        exact_blob = blob(root, a.exact_head, path)
        if authority_blob != exact_blob:
            raise AssertionError(f"Technical Art mutated protected Animation payload: {path}")
        protected_blobs[path] = exact_blob
    sequence = load_json(a.sequence_evidence.resolve())
    bridge = load_json(a.runtime_bridge.resolve())
    lid = load_json(a.lid_target_binding.resolve())
    latch = load_json(a.latch_target_binding.resolve())
    if sequence.get("result") != "PASS_ORDERED_LATCH_RELEASE_LID_CLIP_REENGAGE_SEQUENCE": raise AssertionError("Animation sequence evidence is not green")
    if sequence.get("exact_receiving_head") != a.exact_head: raise AssertionError("sequence evidence is not bound to exact receiving head")
    if int(sequence.get("endpoint_inclusive_sample_count", 0)) != 101: raise AssertionError("Animation sample-count drift")
    if int(sequence.get("sample_rate_hz", 0)) != 40 or abs(float(sequence.get("duration_s", -1.0)) - 2.5) > 1e-12: raise AssertionError("Animation timing grid drift")
    if bridge.get("result") != "PASS_UC_RUNTIME_OBJECT_TARGET_CLOCK_BINDING": raise AssertionError("UC runtime bridge evidence is not green")
    if bridge.get("exact_object_head") != a.exact_head: raise AssertionError("runtime bridge is not bound to exact receiving head")
    if bridge.get("object_sequence_id") != sequence.get("sequence_id") or bridge.get("object_sequence_digest") != sequence.get("sequence_digest"): raise AssertionError("UC runtime bridge sequence identity drift")
    if bridge.get("target_adapter_policy") != "SEEK_TARGET_ANIMATIONPLAYER_TO_UC_CLIP_TIME_NO_RETIME": raise AssertionError("Technical Art target adapter policy drift")
    if len(bridge.get("checkpoints", [])) != 5: raise AssertionError("UC runtime checkpoint count drift")
    if lid.get("result") != "PASS_EXACT_LID_RIG_TO_UC_TARGET_BINDING_READY": raise AssertionError("current lid target-Rigging binding not green")
    if latch.get("result") != "PASS_SOURCE_OWNED_FRONT_LATCH_CAPTURE_ENVELOPE_TO_UC_TARGET_BINDING_READY": raise AssertionError("current front-latch target-Rigging binding not green")
    if lid.get("technical_art_donor_head") != a.technical_art_head or latch.get("technical_art_donor_head") != a.technical_art_head: raise AssertionError("target-Rigging Technical Art donor drift")
    if lid.get("technical_art_historical_donor_head") != a.historical_technical_art_head or latch.get("technical_art_historical_donor_head") != a.historical_technical_art_head: raise AssertionError("historical Technical Art identity drift")
    if latch.get("source_rig_donor_head") != a.current_latch_source_rig_head: raise AssertionError("current front-latch source-Rigging donor drift")
    if lid.get("technical_art_provenance_rebind", {}).get("historical_receipts_reused_as_current_evidence") is not False: raise AssertionError("lid target binding reused historical receipt as current evidence")
    if latch.get("technical_art_provenance_rebind", {}).get("historical_receipts_reused_as_current_evidence") is not False: raise AssertionError("latch target binding reused historical receipt as current evidence")
    output = {
        "schema": SCHEMA, "result": RESULT, "exact_receiving_head": a.exact_head, "animation_authority_head": a.animation_authority_head,
        "prior_technical_art_head": a.prior_technical_art_head, "technical_art_head": a.technical_art_head, "historical_technical_art_head": a.historical_technical_art_head,
        "lid_target_rig_head": a.lid_target_rig_head, "latch_target_rig_head": a.latch_target_rig_head, "current_latch_source_rig_head": a.current_latch_source_rig_head,
        "protected_animation_git_blobs": protected_blobs, "sequence_id": sequence.get("sequence_id"), "sequence_digest": sequence.get("sequence_digest"),
        "sequence_evidence_sha256": sha256(a.sequence_evidence.resolve()), "runtime_bridge_sha256": sha256(a.runtime_bridge.resolve()),
        "lid_target_binding_sha256": sha256(a.lid_target_binding.resolve()), "latch_target_binding_sha256": sha256(a.latch_target_binding.resolve()),
        "uc_runtime_commit": bridge.get("uc_runtime_commit"), "uc_runtime_module_git_blob_sha": bridge.get("uc_runtime_module_git_blob_sha"), "uc_runtime_module_sha256": bridge.get("uc_runtime_module_sha256"),
        "duration_s": bridge.get("duration_s"), "sample_rate_hz": bridge.get("sample_rate_hz"), "checkpoint_count": len(bridge.get("checkpoints", [])), "target_adapter_policy": bridge.get("target_adapter_policy"),
        "motion_change": False, "retimed": False, "retargeted": False, "key_count_changed": False,
        "truth_boundary": {"current_animation_payload_is_byte_identical_to_animation_authority": True, "current_lid_target_rig_binding_consumed": True, "current_front_latch_target_rig_binding_consumed": True,
            "repaired_technical_art_identity_consumed": True, "historical_technical_art_identity_retained_separately": True, "historical_receipts_reused_as_current_evidence": False,
            "uc_runtime_identity_preserved": True, "target_host_observed_by_this_composite_tool": False, "wall_clock_pacing_observed": False, "controller_or_input_acceptance": False,
            "physics_or_collision_acceptance": False, "gameplay_acceptance": False, "final_motion_or_visual_acceptance": False},
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(output, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
