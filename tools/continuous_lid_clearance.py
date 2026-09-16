from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from case_articulation import digest, inspect_articulation

CERT_SCHEMA = "axm.object-continuous-shell-clearance-certificate/v0.1"
RESULT = "PASS_CONTINUOUS_BODY_LID_SHELL_CLEARANCE_CERTIFICATE"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    return float(value)


def certify_continuous_shell_clearance(
    source: dict[str, Any],
    source_sha256: str,
    plan: dict[str, Any],
) -> dict[str, Any]:
    sampled = inspect_articulation(source, source_sha256, plan)

    hinge = source["hinge"]
    dimensions = source["dimensions_m"]
    offset_y = _finite(hinge.get("offset_y"), "hinge.offset_y")
    offset_z = _finite(hinge.get("offset_z"), "hinge.offset_z")
    split_gap = _finite(dimensions.get("split_gap"), "dimensions_m.split_gap")

    if hinge.get("axis") != [1, 0, 0]:
        raise ValueError("continuous certificate requires exact +X source hinge axis")
    if plan["joint"].get("opening_rotation_sign") != -1:
        raise ValueError("continuous certificate requires opening_rotation_sign=-1")
    if sampled["angle_limit_deg"] != [0.0, 110.0]:
        raise ValueError("continuous certificate is bound to exact 0..110 degree envelope")
    if offset_y <= 0.0:
        raise ValueError("continuous certificate requires hinge.offset_y > 0")
    if offset_z < 0.0 or offset_z > split_gap:
        raise ValueError("continuous certificate requires 0 <= hinge.offset_z <= split_gap")

    bottom_relative_z = split_gap - offset_z

    # 0..90 degrees: with clockwise rotation about +X, sin(theta) and cos(theta)
    # are non-negative, so the rear-bottom lid corner is the global minimum-z
    # corner. Its body-top clearance is a concave function on this interval;
    # therefore its minimum occurs at one endpoint.
    first_lower_bound = min(split_gap, offset_z + offset_y)

    # 90..110 degrees: cos(theta) <= 0 and sin(theta) >= 0, so the same
    # rear-bottom corner is the global minimum-y lid corner. Its rearward gap is
    # offset_y*(1-cos(theta)) + bottom_relative_z*sin(theta), which is bounded
    # below by offset_y because both remaining terms are non-negative.
    second_lower_bound = offset_y

    intervals = [
        {
            "open_angle_interval_deg": [0.0, 90.0],
            "separating_axis": "global_z",
            "limiting_lid_corner": "rear_bottom",
            "gap_formula": (
                "hinge.offset_z + hinge.offset_y*sin(theta) + "
                "(split_gap-hinge.offset_z)*cos(theta)"
            ),
            "proof": (
                "rear_bottom is global minimum-z for theta in [0,90]; the gap function "
                "is concave there, so the minimum is one endpoint"
            ),
            "certified_lower_bound_m": round(first_lower_bound, 12),
        },
        {
            "open_angle_interval_deg": [90.0, 110.0],
            "separating_axis": "global_y",
            "limiting_lid_corner": "rear_bottom",
            "gap_formula": (
                "hinge.offset_y*(1-cos(theta)) + "
                "(split_gap-hinge.offset_z)*sin(theta)"
            ),
            "proof": (
                "rear_bottom is global minimum-y for theta in [90,110]; "
                "(1-cos(theta))>=1 and the sine term is non-negative"
            ),
            "certified_lower_bound_m": round(second_lower_bound, 12),
        },
    ]
    certified_minimum = min(first_lower_bound, second_lower_bound)
    if certified_minimum <= 0.0:
        raise ValueError("continuous shell-clearance lower bound is not positive")
    if sampled["sweep_minimum_body_shell_separating_margin_m"] + 1e-12 < certified_minimum:
        raise ValueError("sampled SAT cross-check contradicts continuous certificate")

    return {
        "schema": CERT_SCHEMA,
        "result": RESULT,
        "asset_id": source["asset_id"],
        "source_sha256": source_sha256,
        "plan_digest": digest(plan),
        "joint_id": plan["joint"]["id"],
        "hinge_axis": sampled["hinge_axis"],
        "hinge_origin_m": sampled["hinge_origin_m"],
        "angle_limit_deg": sampled["angle_limit_deg"],
        "certificate_method": "piecewise_analytic_separating_axis",
        "intervals": intervals,
        "continuous_certified_minimum_separation_m": round(certified_minimum, 12),
        "sampled_sat_crosscheck": {
            "sample_count": sampled["sweep_sample_count"],
            "step_deg": sampled["sweep_step_deg"],
            "minimum_separation_m": sampled["sweep_minimum_body_shell_separating_margin_m"],
            "minimum_separation_angle_deg": sampled["sweep_minimum_separation_angle_deg"],
            "all_samples_pass": sampled["gate"] == "PASS_SCOPED_LID_ARTICULATION",
        },
        "truth": {
            "proves": (
                "For the exact source bytes, exact articulation plan and rigid body/lid shell rectangles, "
                "body_shell and lid_shell remain separated continuously for every open angle from 0 through "
                "110 degrees. The existing integer-degree SAT sweep remains as an independent sampled cross-check."
            ),
            "does_not_prove": (
                "Full-component collision freedom involving latches, guards, sockets, service modules or other "
                "attachments; latch articulation; hinge strength, wear, friction, damping, spring or motor behavior; "
                "animation timing/quality; target-engine/controller playback; runtime performance; gameplay; visual "
                "acceptance; production engineering; CANON; or Rigging mastery."
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    source_path = Path(args.source)
    plan_path = Path(args.plan)
    out_path = Path(args.out)
    source = json.loads(source_path.read_text(encoding="utf-8"))
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    report = certify_continuous_shell_clearance(source, _sha256(source_path), plan)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
