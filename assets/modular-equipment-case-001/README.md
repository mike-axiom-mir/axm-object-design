# Modular Equipment Case 001

Status: **structural hard-surface proof / visual review pending**

This is the first source-owned manufactured object in `axm-object-design`. It is deliberately small: one equipment-case body, sparse corner protection, two front latches, one five-knuckle coaxial lid hinge, and two bilateral side attachment plates.

The bounded reusable discovery under test is **explicit mechanical interface identity**. The exact source owns the physical plate locations and local basis vectors, while its descriptor projection reuses Universal Creation's existing `axm.asset-atom-package/v0.1` `socket` atom contract at pinned commit `87f93e1a27b2e3414f6422cd38e31b00e89d6a56`. That donor contract describes socket owner/name/transform/accepted tags/required state; it explicitly does not prove 3D attachment instantiation or fit.

## Exact proof scope

- deterministic source JSON -> generated OBJ;
- zero degenerate triangles;
- one coaxial hinge line with alternating body/lid knuckles;
- bounded minimum axial knuckle clearance;
- two mirrored side socket frames with normalized orthogonal normal/up bases;
- deterministic front/side SVG proof views;
- UC-compatible socket descriptor package projected from the same source;
- pinned UC descriptor validation in CI.

## Non-claims

No lid articulation is executed. No hinge sweep/self-collision is checked. No load-bearing, wall-thickness engineering, watertightness, collision, physics, gameplay, material/lookdev, renderer/runtime cost, Art Director acceptance, CANON or hard-surface mastery is claimed.

The interface pattern stays local to Object Design until another materially different manufactured asset independently proves the same source-owned need. It is **not** a request to add object-specific construction rules to Universal Creation.
