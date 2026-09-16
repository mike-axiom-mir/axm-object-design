from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from case_articulation import inspect_articulation

ASSET = ROOT / "assets" / "modular-equipment-case-001"
SOURCE_PATH = ASSET / "source.json"
PLAN_PATH = ASSET / "articulation.json"
OUT = ROOT / "evidence" / "modular-equipment-case-001-articulation"
OUT.mkdir(parents=True, exist_ok=True)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_side_proof(path: Path, report: dict) -> None:
    width = 1300
    height = 420
    panel_width = 240
    panel_gap = 15
    left = 25
    scale = 390.0
    y_min, y_max = -0.35, 0.55
    z_min, z_max = -0.02, 0.70

    def map_point(panel_index: int, point: list[float] | tuple[float, float]) -> tuple[float, float]:
        y, z = point
        panel_x = left + panel_index * (panel_width + panel_gap)
        px = panel_x + (y - y_min) * scale
        pz = 360 - (z - z_min) * scale
        return px, pz

    body = [(-0.24, 0.0), (0.24, 0.0), (0.24, 0.30), (-0.24, 0.30)]
    hinge_yz = (report["hinge_origin_m"][1], report["hinge_origin_m"][2])
    rows = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff"/>',
        '<text x="25" y="25" font-family="monospace" font-size="17">modular-equipment-case-001 — rigid lid articulation proof (side / YZ)</text>',
        '<text x="25" y="47" font-family="monospace" font-size="12">representative sampled poses only; visual direction, animation timing, runtime and gameplay acceptance are not claimed</text>',
    ]
    for index, pose in enumerate(report["representative_poses"]):
        bx = [map_point(index, point) for point in body]
        lx = [map_point(index, point) for point in pose["lid_corners_yz_m"]]
        hinge = map_point(index, hinge_yz)
        body_points = " ".join(f"{x:.2f},{z:.2f}" for x, z in bx)
        lid_points = " ".join(f"{x:.2f},{z:.2f}" for x, z in lx)
        rows.append(f'<polygon points="{body_points}" fill="#eeeeee" stroke="#222222" stroke-width="2"/>')
        rows.append(f'<polygon points="{lid_points}" fill="#dce8f5" stroke="#1f4f7a" stroke-width="2"/>')
        rows.append(f'<circle cx="{hinge[0]:.2f}" cy="{hinge[1]:.2f}" r="4" fill="#a00000"/>')
        rows.append(
            f'<text x="{left + index * (panel_width + panel_gap)}" y="390" font-family="monospace" font-size="12">'
            f'{pose["open_angle_deg"]:.0f} deg / gap {pose["body_shell_separating_margin_m"]:.6f} m</text>'
        )
    rows.append('</svg>')
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


source = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
source_sha256 = _sha256(SOURCE_PATH)
report = inspect_articulation(source, source_sha256, plan)

(OUT / "articulation.evidence.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
summary = {
    "gate": report["gate"],
    "asset_id": report["asset_id"],
    "source_sha256": report["source_sha256"],
    "plan_digest": report["plan_digest"],
    "joint_id": report["joint_id"],
    "hinge_axis": report["hinge_axis"],
    "hinge_origin_m": report["hinge_origin_m"],
    "angle_limit_deg": report["angle_limit_deg"],
    "sweep_step_deg": report["sweep_step_deg"],
    "sweep_sample_count": report["sweep_sample_count"],
    "sweep_minimum_body_shell_separating_margin_m": report["sweep_minimum_body_shell_separating_margin_m"],
    "sweep_minimum_separation_angle_deg": report["sweep_minimum_separation_angle_deg"],
    "sweep_maximum_lid_pairwise_rigidity_drift_m": report["sweep_maximum_lid_pairwise_rigidity_drift_m"],
    "representative_poses": [
        {
            "open_angle_deg": row["open_angle_deg"],
            "body_shell_separating_margin_m": row["body_shell_separating_margin_m"],
            "lid_pairwise_rigidity_max_drift_m": row["lid_pairwise_rigidity_max_drift_m"],
            "status": row["status"],
        }
        for row in report["representative_poses"]
    ],
    "assumptions": report["assumptions"],
    "truth": report["truth"],
}
(OUT / "articulation.summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
_write_side_proof(OUT / "articulation_side_proof.svg", report)

if report["gate"] != "PASS_SCOPED_LID_ARTICULATION":
    raise SystemExit(1)
print(json.dumps(summary, indent=2, sort_keys=True))
