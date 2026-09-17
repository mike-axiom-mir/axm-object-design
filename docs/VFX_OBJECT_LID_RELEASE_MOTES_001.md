# Object VFX — Lid Release Motes 001

Status: **BOUNDED CANDIDATE / TARGET-HOST EVIDENCE REQUIRED**

This lane adds one visual-only reactive effect to the existing `modular-equipment-case-001` motion receiver. It does not retime or rewrite the Object Animation sequence.

## Exact dependency

- Animation parent: `07130d3481d69b5a4d8a399e86bd207d623dc87c`.
- Sequence: `lid-latch-open-hold-close-001`, 2.5 s at 40 Hz.
- Trigger phase: `play_exact_lid_clip`.
- Exact trigger boundary: `0.25 s`.
- Trigger semantics: `EXACT_ANIMATION_PHASE_BOUNDARY_NOT_GAMEPLAY_EVENT`.

The effect is deliberately tied to the already-authored Animation phase boundary rather than inventing a controller or gameplay event.

## Visual candidate

`lid-open-release-motes-001` is a deterministic analytic 18-mote burst derived from the imported neutral lid/body seam. The proof implementation uses billboard quads only so the visual behavior can be inspected repeatably in the exact existing Godot receiver.

The source label is:

`STYLIZED_VISUAL_RELEASE_MOTES_NOT_DUST_OR_FLUID_SIMULATION`

This is not a claim about dust, pressure, airflow or fluid dynamics.

## Fail-closed evidence contract

The dedicated target-host workflow must:

1. preserve the exact Object source and Animation sequence inherited from the parent head;
2. rebuild the exact Technical Art / UC rigid-scene donor and exact Rigging-backed sequence evidence;
3. reject a verifier-only +25 ms trigger-time drift before rendering;
4. render matched control/candidate frames in pinned Godot 4.7.2;
5. prove the VFX changes no lid or latch AnimationPlayer state;
6. require visible bounded deltas at 0.30 / 0.40 / 0.52 s;
7. require pixel identity before the trigger at 0.20 s and after the effect at 0.80 s;
8. retain exact source/effect/receiver identities and PNG evidence.

A green result is only a scoped visual reactive-effect proof in this receiver. Runtime/performance, production particles, gameplay/physics, Art Direction, Visual QA, CANON and production readiness remain separate gates.
