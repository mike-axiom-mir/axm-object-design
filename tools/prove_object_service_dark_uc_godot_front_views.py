from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

SCHEMA = "axm.object-service-dark-uc-godot-front-view-proof/v0.1"
TRANSPORT_RESULT = "PASS_OBJECT_SERVICE_DARK_EXACT_ATLAS_RGB_TO_CURRENT_UC_TEXTURED_GLB"
FINAL_RESULT = "PASS_OBJECT_SERVICE_DARK_EXACT_ATLAS_RGB_TO_CURRENT_UC_TEXTURED_GLB_TO_GODOT_FRONT_VIEWS"
REQUIRED_CHECKS = (
    "actual-rendering-backend",
    "exact-imported-source",
    "native-target-geometry-agreement",
    "target-texture-bindings-decoded",
    "all-target-images-and-asset-masks",
)

# The bounded Object proof publishes two intentionally one-sided source surfaces.
# Their target-space front normals are -Y (inner lid) and -Z (front panel).
TARGET_FRONT_NORMALS = {
    "lid_inner_service_surface": [0.0, -1.0, 0.0],
    "front_service_panel_outer_service_surface": [0.0, 0.0, -1.0],
}

# UC's generic observer intentionally bounds elevation to [-0.1, 1.45].
# These two Object-local evidence views remain inside that contract while placing
# the camera on the front side of both source-owned one-sided planes.
FRONT_VIEWS = (
    {"yaw": 2.45, "elevation": -0.08},
    {"yaw": -2.45, "elevation": -0.08},
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def view_direction(view: dict[str, float]) -> list[float]:
    yaw = float(view["yaw"])
    elevation = float(view["elevation"])
    return [
        math.sin(yaw) * math.cos(elevation),
        math.sin(elevation),
        math.cos(yaw) * math.cos(elevation),
    ]


def dot(a: list[float], b: list[float]) -> float:
    return sum(float(x) * float(y) for x, y in zip(a, b))


def prove_view_sidedness() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, view in enumerate(FRONT_VIEWS):
        direction = view_direction(view)
        dots = {surface_id: dot(normal, direction) for surface_id, normal in TARGET_FRONT_NORMALS.items()}
        if any(value <= 0.0 for value in dots.values()):
            raise AssertionError(f"front-view contract does not face every bounded source surface: {dots}")
        rows.append(
            {
                "view_index": index,
                "view": dict(view),
                "camera_direction_from_asset": direction,
                "front_normal_dot_camera_direction": dots,
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uc-root", required=True)
    parser.add_argument("--transport-dir", default="creations/technical-art-proof/generated")
    parser.add_argument("--out", default="creations/technical-art-proof/godot-front-view-proof")
    parser.add_argument("--expected-uc-head", required=True)
    args = parser.parse_args()

    root = Path.cwd().resolve()
    uc_root = Path(args.uc_root).resolve()
    transport_dir = Path(args.transport_dir).resolve()
    out_dir = Path(args.out).resolve()
    transport_receipt_path = transport_dir / "technical-art-uc-texture-transport-receipt.json"
    glb_path = transport_dir / "service-dark-two-surface.glb"

    if not transport_receipt_path.is_file() or not glb_path.is_file():
        raise AssertionError("exact Technical Art texture-transport prerequisite is missing")
    transport = json.loads(transport_receipt_path.read_text(encoding="utf-8"))
    if transport.get("result") != TRANSPORT_RESULT:
        raise AssertionError(f"unexpected transport prerequisite result: {transport.get('result')}")

    technical_art_head = git(root, "rev-parse", "HEAD")
    uc_head = git(uc_root, "rev-parse", "HEAD")
    if transport.get("technical_art_head") != technical_art_head:
        raise AssertionError("transport receipt is not bound to the exact Technical Art head")
    if transport.get("uc_head") != args.expected_uc_head or uc_head != args.expected_uc_head:
        raise AssertionError("UC identity drift at target-host proof boundary")
    if transport.get("glb_sha256") != sha256_file(glb_path):
        raise AssertionError("transported GLB identity drift before target-host observation")
    if transport.get("truth_boundary", {}).get("uc_product_modified") is not False:
        raise AssertionError("transport prerequisite unexpectedly claims a UC product modification")

    view_evidence = prove_view_sidedness()

    sys.path.insert(0, str(uc_root / "src"))
    from axm_uc.material_pipeline import observe_station, run_station  # type: ignore

    if out_dir.exists():
        shutil.rmtree(out_dir)
    godot_dir = out_dir / "godot-target"
    godot_inputs = {
        "path": relative(root, godot_dir),
        "asset": relative(root, glb_path),
        "options": {
            "engine": "godot",
            "width": 640,
            "height": 480,
            "pose_samples": 2,
            "views": [dict(row) for row in FRONT_VIEWS],
            "playback": None,
        },
    }
    report = run_station(root, "validate-godot-target", godot_inputs)
    observation = observe_station(root, "validate-godot-target", godot_inputs)
    if report.get("status") != "PASS" or observation.get("status") != "PASS":
        raise AssertionError(f"UC Godot front-view target observation failed: {report}")

    checks = {row["type"]: bool(row["passed"]) for row in report.get("checks", [])}
    for required in REQUIRED_CHECKS:
        if checks.get(required) is not True:
            raise AssertionError(f"UC Godot target did not close required transport check: {required}")

    images = report.get("images", [])
    if len(images) != len(FRONT_VIEWS):
        raise AssertionError("UC Godot target did not retain every bounded front-side evidence view")
    if any(int(row.get("visible_pixels", 0)) <= 0 for row in images):
        raise AssertionError(f"front-side evidence view lost the bounded Object surfaces: {images}")

    out_dir.mkdir(parents=True, exist_ok=True)
    receipt = {
        "schema": SCHEMA,
        "result": FINAL_RESULT,
        "technical_art_head": technical_art_head,
        "materials_authority_head": transport.get("materials_authority_head"),
        "uc_head": uc_head,
        "uc_product_modified": False,
        "transport_receipt_sha256": sha256_file(transport_receipt_path),
        "glb_sha256": sha256_file(glb_path),
        "view_policy": "OBJECT_SOURCE_FRONT_SIDE_EVIDENCE_VIEWS_WITHIN_EXISTING_UC_BOUNDS",
        "target_front_normals": TARGET_FRONT_NORMALS,
        "view_sidedness_evidence": view_evidence,
        "godot_status": report.get("status"),
        "godot_observation_status": observation.get("status"),
        "godot_backend": report.get("backend"),
        "godot_checks": report.get("checks", []),
        "godot_images": images,
        "truth_boundary": {
            "source_surface_sidedness_changed": False,
            "source_normals_changed": False,
            "material_double_sidedness_enabled": False,
            "materials_atlas_policy_changed": False,
            "uc_camera_contract_changed": False,
            "uc_product_modified": False,
            "target_specific_view_selection_owned_by_technical_art": True,
            "production_uv_adopted": False,
            "production_texture_authored": False,
            "tangent_space_production_quality_accepted": False,
            "runtime_cost_accepted": False,
            "final_art_direction_accepted": False,
            "final_visual_qa_accepted": False,
            "canon": False,
            "production_ready": False,
        },
    }
    receipt_path = out_dir / "technical-art-uc-godot-front-view-receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
