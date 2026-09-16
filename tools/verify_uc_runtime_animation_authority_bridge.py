#!/usr/bin/env python3
"""Compose exact Animation source-authority evidence with a UC runtime clock binding.

This is Object-local Technical Art receiving evidence. Animation keeps motion and
source-authority ownership; UC keeps only the adapter-neutral runtime clock.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

SCHEMA = "axm.uc-animation-runtime-source-authority-bridge/v0.1"
RESULT = "PASS_UC_RUNTIME_CLOCK_OVER_CURRENT_ANIMATION_SOURCE_AUTHORITY"


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise AssertionError(f"{path} must contain one JSON object")
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def is_ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(root), "merge-base", "--is-ancestor", ancestor, descendant],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--authority-contract", required=True, type=Path)
    parser.add_argument("--animation-rebind-evidence", required=True, type=Path)
    parser.add_argument("--runtime-bridge", required=True, type=Path)
    parser.add_argument("--animation-authority-head", required=True)
    parser.add_argument("--prior-technical-art-head", required=True)
    parser.add_argument("--exact-head", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    root = args.repo_root.resolve()
    observed_head = git(root, "rev-parse", "HEAD")
    if observed_head != args.exact_head:
        raise AssertionError("receiving head drift")
    if not is_ancestor(root, args.animation_authority_head, args.exact_head):
        raise AssertionError("current Animation authority head is not in receiving ancestry")
    if not is_ancestor(root, args.prior_technical_art_head, args.exact_head):
        raise AssertionError("prior Technical Art bridge head is not in receiving ancestry")

    authority_path = args.authority_contract.resolve()
    rebind_path = args.animation_rebind_evidence.resolve()
    bridge_path = args.runtime_bridge.resolve()
    authority = load_json(authority_path)
    rebind = load_json(rebind_path)
    bridge = load_json(bridge_path)

    if authority.get("schema") != "axm.object-animation-source-authority-rebind/v0.1":
        raise AssertionError("unexpected Animation authority contract schema")
    if rebind.get("result") != "PASS_ANIMATION_SOURCE_AUTHORITY_REBIND_MOTION_EQUIVALENCE":
        raise AssertionError("Animation source-authority evidence is not green")
    if bridge.get("result") != "PASS_UC_RUNTIME_OBJECT_TARGET_CLOCK_BINDING":
        raise AssertionError("UC runtime bridge evidence is not green")
    if rebind.get("exact_receiving_head") != args.exact_head or bridge.get("exact_object_head") != args.exact_head:
        raise AssertionError("cross-repo evidence is not bound to one exact receiving head")

    prior = authority.get("prior_animation_evidence", {})
    source_interface = authority.get("source_interface", {})
    source_rig = authority.get("source_rig_binding", {})
    preservation = authority.get("preservation_contract", {})
    sequence_id = str(prior.get("sequence_id", ""))
    sequence_digest = str(prior.get("sequence_digest", ""))
    if not sequence_id or len(sequence_digest) != 64:
        raise AssertionError("authority sequence identity missing")
    if rebind.get("prior_sequence_id") != sequence_id or rebind.get("prior_sequence_digest") != sequence_digest:
        raise AssertionError("Animation rebind sequence identity drift")
    if bridge.get("object_sequence_id") != sequence_id or bridge.get("object_sequence_digest") != sequence_digest:
        raise AssertionError("UC runtime bridge no longer addresses the authority-bound sequence")

    if rebind.get("current_source_interface_head") != source_interface.get("head"):
        raise AssertionError("source-interface authority head drift")
    if rebind.get("current_source_interface_sha256") != source_interface.get("sha256"):
        raise AssertionError("source-interface authority digest drift")
    if rebind.get("current_source_rig_head") != source_rig.get("head"):
        raise AssertionError("source-rig authority head drift")
    if rebind.get("current_source_rig_binding_sha256") != source_rig.get("binding_sha256"):
        raise AssertionError("source-rig authority digest drift")

    for key in ("motion_change", "retimed", "retargeted", "key_count_changed"):
        if rebind.get(key) is not False:
            raise AssertionError(f"protected motion field changed: {key}")
    if preservation.get("timing") != "NO_RETIME" or preservation.get("target_geometry") != "NO_RETARGET":
        raise AssertionError("Animation preservation policy drift")
    if bridge.get("target_adapter_policy") != "SEEK_TARGET_ANIMATIONPLAYER_TO_UC_CLIP_TIME_NO_RETIME":
        raise AssertionError("Technical Art target adapter policy drift")
    if int(bridge.get("sample_rate_hz", 0)) != int(rebind.get("sample_rate_hz", 0)):
        raise AssertionError("sample-rate identity drift")
    if abs(float(bridge.get("duration_s", -1.0)) - float(rebind.get("duration_s", -2.0))) > 1e-12:
        raise AssertionError("duration identity drift")

    output = {
        "schema": SCHEMA,
        "result": RESULT,
        "exact_receiving_head": args.exact_head,
        "animation_authority_head": args.animation_authority_head,
        "prior_technical_art_head": args.prior_technical_art_head,
        "animation_authority_is_ancestor": True,
        "prior_technical_art_is_ancestor": True,
        "authority_contract_sha256": sha256(authority_path),
        "authority_contract_canonical_sha256": canonical_sha256(authority),
        "animation_rebind_evidence_sha256": sha256(rebind_path),
        "runtime_bridge_sha256": sha256(bridge_path),
        "sequence_id": sequence_id,
        "sequence_digest": sequence_digest,
        "source_interface_head": source_interface.get("head"),
        "source_interface_sha256": source_interface.get("sha256"),
        "source_rig_head": source_rig.get("head"),
        "source_rig_binding_sha256": source_rig.get("binding_sha256"),
        "uc_runtime_commit": bridge.get("uc_runtime_commit"),
        "uc_runtime_module_git_blob_sha": bridge.get("uc_runtime_module_git_blob_sha"),
        "uc_runtime_module_sha256": bridge.get("uc_runtime_module_sha256"),
        "duration_s": bridge.get("duration_s"),
        "sample_rate_hz": bridge.get("sample_rate_hz"),
        "checkpoint_count": len(bridge.get("checkpoints", [])),
        "target_adapter_policy": bridge.get("target_adapter_policy"),
        "motion_change": False,
        "retimed": False,
        "retargeted": False,
        "key_count_changed": False,
        "truth_boundary": {
            "current_source_authority_identity_preserved": True,
            "animation_motion_identity_preserved": True,
            "uc_runtime_identity_preserved": True,
            "target_host_observed_by_this_composite_tool": False,
            "wall_clock_pacing_observed": False,
            "controller_or_input_acceptance": False,
            "physics_or_collision_acceptance": False,
            "gameplay_acceptance": False,
            "final_motion_or_visual_acceptance": False
        }
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
