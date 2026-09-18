#!/usr/bin/env python3
"""Bind UC's adapter-neutral animation clock to one exact Object target clip.

This is receiving Technical Art plumbing. It does not move Object motion semantics
into Universal Creation and it does not claim wall-clock playback or controller
acceptance. The output is a deterministic handoff consumed by a target-host proof.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


SCHEMA = "axm.uc-animation-runtime-target-clock-binding/v0.1"
RESULT = "PASS_UC_RUNTIME_OBJECT_TARGET_CLOCK_BINDING"
CHECKPOINTS_S = [0.1125, 0.5125, 1.2375, 1.7625, 2.3875]
EPS = 1e-10
MODULE_RELATIVE_PATH = "src/axm_uc/game_animation_runtime.py"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return sha256_bytes(payload)


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain one JSON object")
    return value


def git_head(root: Path) -> str:
    return subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()


def git_blob_sha(root: Path, relative_path: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), "hash-object", relative_path], text=True
    ).strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uc-root", required=True, type=Path)
    parser.add_argument("--expected-uc-commit", required=True)
    parser.add_argument("--sequence-evidence", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--exact-object-head", required=True)
    args = parser.parse_args()

    uc_root = args.uc_root.resolve()
    observed_uc_commit = git_head(uc_root)
    if observed_uc_commit != args.expected_uc_commit:
        raise AssertionError(f"UC runtime donor drift: {observed_uc_commit} != {args.expected_uc_commit}")

    module_path = uc_root / MODULE_RELATIVE_PATH
    if not module_path.is_file():
        raise FileNotFoundError(module_path)
    uc_module_sha256 = sha256_bytes(module_path.read_bytes())
    uc_module_git_blob_sha = git_blob_sha(uc_root, MODULE_RELATIVE_PATH)

    sys.path.insert(0, str(uc_root / "src"))
    from axm_uc.game_animation_runtime import replay_game_animation_runtime  # type: ignore

    sequence_path = args.sequence_evidence.resolve()
    sequence_bytes = sequence_path.read_bytes()
    sequence = load_json(sequence_path)
    if sequence.get("result") != "PASS_ORDERED_LATCH_RELEASE_LID_CLIP_REENGAGE_SEQUENCE":
        raise AssertionError("exact Object animation sequence evidence is not green")
    if sequence.get("exact_receiving_head") != args.exact_object_head:
        raise AssertionError("Object sequence evidence is not bound to this exact receiving head")
    if int(sequence.get("sample_rate_hz", 0)) != 40:
        raise AssertionError("unexpected Object sequence sample rate")
    duration_s = float(sequence.get("duration_s", -1.0))
    if abs(duration_s - 2.5) > EPS:
        raise AssertionError("unexpected Object sequence duration")
    sequence_id = str(sequence.get("sequence_id", ""))
    sequence_digest = str(sequence.get("sequence_digest", ""))
    if not sequence_id or len(sequence_digest) != 64:
        raise AssertionError("Object sequence identity missing")

    runtime = {
        "schema": "axm.game-animation-runtime/v0.1",
        "id": "object-equipment-case-target-clock-001",
        "initial_state": "idle",
        "clips": [
            {
                "name": "idle-neutral",
                "duration_s": 1.0,
                "loop": True,
                "root_motion_m": [0.0, 0.0, 0.0],
                "events": [],
            },
            {
                "name": sequence_id,
                "duration_s": duration_s,
                "loop": False,
                "root_motion_m": [0.0, 0.0, 0.0],
                "events": [
                    {"name": "latches_released", "time_s": 0.25},
                    {"name": "lid_motion_complete", "time_s": 2.25},
                ],
            },
        ],
        "states": [
            {
                "name": "idle",
                "clip": "idle-neutral",
                "speed": 1.0,
                "root_motion": "ignore",
                "completion_event": None,
            },
            {
                "name": "operate",
                "clip": sequence_id,
                "speed": 1.0,
                "root_motion": "ignore",
                "completion_event": "complete",
            },
        ],
        "transitions": [
            {"from": "idle", "event": "operate", "to": "operate", "blend_s": 0.0},
            {"from": "operate", "event": "complete", "to": "idle", "blend_s": 0.0},
        ],
    }

    commands: list[dict] = [{"event": "operate"}]
    prior = 0.0
    for checkpoint in CHECKPOINTS_S:
        if checkpoint <= prior or checkpoint >= duration_s:
            raise AssertionError("invalid bounded checkpoint schedule")
        commands.append({"dt": checkpoint - prior})
        prior = checkpoint
    commands.append({"dt": duration_s - prior})

    replay = replay_game_animation_runtime(runtime, commands)
    transcript = replay["transcript"]
    if len(transcript) != len(commands):
        raise AssertionError("UC runtime transcript length mismatch")
    if transcript[0]["state"] != "operate" or abs(float(transcript[0]["clip_time_s"])) > EPS:
        raise AssertionError("UC runtime did not enter Object operate state at neutral time")

    checkpoints = []
    for index, checkpoint in enumerate(CHECKPOINTS_S, start=1):
        row = transcript[index]
        if row["state"] != "operate" or row["clip"] != sequence_id:
            raise AssertionError(f"UC runtime left exact Object clip before checkpoint {checkpoint}")
        clip_time = float(row["clip_time_s"])
        if abs(clip_time - checkpoint) > EPS:
            raise AssertionError(f"UC runtime clip clock drift at {checkpoint}: {clip_time}")
        checkpoints.append(
            {
                "command_index": index,
                "time_s": checkpoint,
                "runtime_state": row["state"],
                "runtime_clip": row["clip"],
            }
        )

    final = transcript[-1]
    transitions = [item for item in final.get("emitted", []) if item.get("type") == "TRANSITION"]
    if final["state"] != "idle" or final["clip"] != "idle-neutral":
        raise AssertionError("UC runtime did not return to neutral idle after exact clip duration")
    if not any(item.get("automatic") is True and item.get("from") == "operate" and item.get("to") == "idle" for item in transitions):
        raise AssertionError("UC runtime completion transition missing")

    output = {
        "schema": SCHEMA,
        "result": RESULT,
        "exact_object_head": args.exact_object_head,
        "uc_runtime_commit": observed_uc_commit,
        "uc_runtime_module_path": MODULE_RELATIVE_PATH,
        "uc_runtime_module_git_blob_sha": uc_module_git_blob_sha,
        "uc_runtime_module_sha256": uc_module_sha256,
        "uc_runtime_source_sha256": replay["compiled"]["source_sha256"],
        "uc_runtime_commands_sha256": replay["commands_sha256"],
        "object_sequence_id": sequence_id,
        "object_sequence_digest": sequence_digest,
        "object_sequence_evidence_file_sha256": sha256_bytes(sequence_bytes),
        "object_sequence_evidence_canonical_sha256": canonical_sha256(sequence),
        "duration_s": duration_s,
        "sample_rate_hz": int(sequence["sample_rate_hz"]),
        "target_adapter_policy": "SEEK_TARGET_ANIMATIONPLAYER_TO_UC_CLIP_TIME_NO_RETIME",
        "checkpoints": checkpoints,
        "completion": {
            "final_runtime_state": final["state"],
            "final_runtime_clip": final["clip"],
            "automatic_operate_to_idle_transition": True,
            "terminal_pose_sampling_note": (
                "UC replay records the post-completion idle state after the exact 2.5 s boundary; "
                "this binding therefore proves target sampling only at interior checkpoints. The exact neutral "
                "target endpoint remains a separate target-host assertion."
            ),
        },
        "truth_boundary": {
            "uc_runtime_clock_executed": True,
            "uc_runtime_source_identity_preserved": True,
            "uc_runtime_git_blob_and_byte_sha256_distinguished": True,
            "object_sequence_identity_preserved": True,
            "runtime_clip_time_retimed": False,
            "target_engine_playback_observed_here": False,
            "wall_clock_pacing_observed": False,
            "controller_or_input_acceptance": False,
            "physics_or_collision_acceptance": False,
            "gameplay_acceptance": False,
            "final_motion_acceptance": False,
        },
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
