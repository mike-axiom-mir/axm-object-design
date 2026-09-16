from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _fail(message: str) -> None:
    raise SystemExit("HOLD_UC_ASSET_INSTANCE_INTEGRATION " + message)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--uc-root", required=True)
    parser.add_argument("--expected-uc-commit", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    package_path = Path(args.package).resolve()
    uc_root = Path(args.uc_root).resolve()
    out_dir = Path(args.out_dir).resolve()
    materialized_dir = out_dir / "materialized-descriptor"

    observed_uc_commit = subprocess.check_output(
        ["git", "-C", str(uc_root), "rev-parse", "HEAD"], text=True
    ).strip()
    if observed_uc_commit != args.expected_uc_commit:
        _fail(
            f"UC_HEAD_MISMATCH expected={args.expected_uc_commit} observed={observed_uc_commit}"
        )

    sys.path.insert(0, str(uc_root / "src"))
    from axm_uc.asset_atoms import (  # noqa: E402
        compile_asset_package,
        materialize_asset_package,
        validate_asset_package,
    )

    raw = json.loads(package_path.read_text(encoding="utf-8"))
    normalized = validate_asset_package(raw)
    first = compile_asset_package(raw)
    second = compile_asset_package(raw)
    if first != second:
        _fail("NONDETERMINISTIC_COMPILE")

    package_sockets = [atom for atom in normalized["atoms"] if atom["kind"] == "socket"]
    instance_sockets = first["instance"]["sockets"]
    if package_sockets != instance_sockets:
        _fail("SOCKETS_CHANGED_OR_DROPPED_DURING_COMPILE")

    socket_names = sorted(atom["payload"]["name"] for atom in instance_sockets)
    if socket_names != ["left_service", "right_service"]:
        _fail(f"UNEXPECTED_SOCKET_SET names={socket_names}")

    if first["instance"]["resource_evidence"]["truth_status"] != "DECLARED_RESOURCE_REFERENCES_NOT_FETCHED":
        _fail("UNEXPECTED_RESOURCE_EVIDENCE_STATUS")

    if materialized_dir.exists():
        shutil.rmtree(materialized_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    materialized = materialize_asset_package(materialized_dir, raw, replace=True)

    package_file = materialized_dir / "asset.package.json"
    instance_file = materialized_dir / "asset.instance.json"
    if not package_file.is_file() or not instance_file.is_file():
        _fail("MATERIALIZED_DESCRIPTOR_FILES_MISSING")

    reopened_package = json.loads(package_file.read_text(encoding="utf-8"))
    reopened_instance = json.loads(instance_file.read_text(encoding="utf-8"))
    if reopened_package != first["package"]:
        _fail("MATERIALIZED_PACKAGE_DIFFERS_FROM_COMPILE")
    if reopened_instance != first["instance"]:
        _fail("MATERIALIZED_INSTANCE_DIFFERS_FROM_COMPILE")
    if materialized.get("package_digest") != first["package_digest"]:
        _fail("MATERIALIZED_PACKAGE_DIGEST_MISMATCH")
    if materialized.get("instance_digest") != first["instance"]["instance_digest"]:
        _fail("MATERIALIZED_INSTANCE_DIGEST_MISMATCH")

    report = {
        "schema": "axm.object-uc-asset-instance-integration/v0.1",
        "result": "PASS_EXACT_UC_ASSET_INSTANCE_HANDOFF",
        "source_repository": "mike-axiom-mir/axm-object-design",
        "asset_id": "modular-equipment-case-001",
        "package_file": package_path.name,
        "package_file_sha256": _sha256(package_path),
        "expected_uc_commit": args.expected_uc_commit,
        "observed_uc_commit": observed_uc_commit,
        "uc_asset_package_schema": normalized["schema"],
        "uc_asset_instance_schema": first["instance"]["schema"],
        "package_ref": first["instance"]["package_ref"],
        "package_digest": first["package_digest"],
        "instance_digest": first["instance"]["instance_digest"],
        "normalized_package_digest": _digest(first["package"]),
        "deterministic_compile_repeated_identically": True,
        "socket_count": len(instance_sockets),
        "socket_names": socket_names,
        "socket_atoms_preserved_exactly_from_validated_package": True,
        "materialized_package_sha256": _sha256(package_file),
        "materialized_instance_sha256": _sha256(instance_file),
        "materialized_files_reopened_equal_to_compiler_output": True,
        "uc_resource_evidence": first["instance"]["resource_evidence"],
        "truth_boundary": {
            "descriptor_schema_validated": True,
            "uc_asset_instance_compiled": True,
            "uc_descriptor_project_materialized": True,
            "socket_descriptors_preserved_by_compiler": True,
            "external_resource_bytes_fetched_or_verified_by_uc_compiler": False,
            "socket_transform_coordinate_semantics_rendered": False,
            "attachment_instantiated_in_3d": False,
            "physical_fit_tested": False,
            "collision_or_load_tested": False,
            "runtime_or_gameplay_acceptance": False,
        },
    }
    (out_dir / "uc-asset-instance-integration.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
