#!/usr/bin/env python3
"""Verify that a historical Technical Art evidence lane remains byte-stable.

This guard is intentionally lane-scoped. It protects the files that define a
previously proven evidence path while allowing later, unrelated Technical Art
lanes to coexist on the same long-lived branch.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys


def git_bytes(*args: str) -> bytes:
    return subprocess.check_output(["git", *args])


def git_text(*args: str) -> str:
    return git_bytes(*args).decode("utf-8").strip()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    p.add_argument("--baseline", required=True, help="Previously proven commit")
    p.add_argument(
        "--protected",
        action="append",
        required=True,
        help="Lane-owned path that must remain byte-identical to the baseline; repeatable",
    )
    p.add_argument("--receipt", help="Optional JSON receipt path")
    return p


def fail(message: str) -> None:
    raise SystemExit(message)


def main() -> int:
    args = parser().parse_args()
    baseline = git_text("rev-parse", args.baseline)
    head = git_text("rev-parse", "HEAD")

    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", baseline, head],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if ancestor.returncode != 0:
        fail(f"baseline is not an ancestor of HEAD: {baseline} -> {head}")

    protected = []
    for raw in args.protected:
        path = pathlib.PurePosixPath(raw).as_posix()
        if path.startswith("../") or path == ".." or path.startswith("/"):
            fail(f"protected path escapes repository: {raw}")
        if path in [entry["path"] for entry in protected]:
            fail(f"duplicate protected path: {path}")

        try:
            baseline_bytes = git_bytes("show", f"{baseline}:{path}")
            head_bytes = git_bytes("show", f"HEAD:{path}")
        except subprocess.CalledProcessError as exc:
            fail(f"protected path missing from baseline or HEAD: {path} ({exc})")

        worktree_path = pathlib.Path(path)
        if not worktree_path.is_file():
            fail(f"protected path missing from worktree: {path}")
        worktree_bytes = worktree_path.read_bytes()

        baseline_sha = sha256(baseline_bytes)
        head_sha = sha256(head_bytes)
        worktree_sha = sha256(worktree_bytes)
        if head_bytes != baseline_bytes:
            fail(
                "protected committed lane file drift: "
                f"{path} baseline_sha256={baseline_sha} head_sha256={head_sha}"
            )
        if worktree_bytes != head_bytes:
            fail(
                "protected worktree lane file drift: "
                f"{path} head_sha256={head_sha} worktree_sha256={worktree_sha}"
            )

        protected.append(
            {
                "path": path,
                "sha256": baseline_sha,
                "byte_count": len(baseline_bytes),
            }
        )

    receipt = {
        "schema": "axm.ta-evidence-lane-continuity/v0.1",
        "result": "PASS_TA_EVIDENCE_LANE_PROTECTED_FILES_UNCHANGED",
        "baseline_commit": baseline,
        "current_head": head,
        "protected_file_count": len(protected),
        "protected_files": protected,
        "scope": {
            "protects": "only the named historical evidence-lane files",
            "allows": "unrelated additive sibling lanes on the same branch",
            "does_not_prove": [
                "sibling-lane correctness",
                "domain acceptance",
                "default adoption",
                "CANON",
                "production readiness",
            ],
        },
    }

    if args.receipt:
        out = pathlib.Path(args.receipt)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
