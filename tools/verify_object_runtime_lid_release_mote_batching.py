#!/usr/bin/env python3
import argparse, json
from pathlib import Path

EXPECTED_PARENT='1fc2eb89b7869b81a97614a586e04375a7ad0547'
EXPECTED_STATE='PASS_RUNTIME_LID_RELEASE_MOTE_MULTIMESH_BATCHING__HOLD_ART_QA_TARGET_DEVICE'


def fail(msg):
    raise SystemExit(msg)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--receipt', default='animation-proof/runtime-lid-release-mote-batching-receipt.json')
    args=ap.parse_args()
    p=Path(args.receipt)
    if not p.is_file(): fail(f'missing receipt: {p}')
    r=json.loads(p.read_text())
    if r.get('state') != EXPECTED_STATE: fail(f"unexpected state: {r.get('state')}")
    if r.get('runtime_parent_vfx_head') != EXPECTED_PARENT: fail('runtime parent VFX head drift')
    if r.get('owner_seed') != 41027 or r.get('particle_count') != 18: fail('owner effect identity drift')

    shape=r.get('resource_shape',{})
    old=shape.get('legacy',{})
    new=shape.get('batched',{})
    if [old.get('mesh_instance_resources'),old.get('quad_mesh_resources'),old.get('material_resources')] != [18,18,18]:
        fail(f'legacy resource shape drift: {old}')
    if [new.get('multimesh_instance_resources'),new.get('multimesh_resources'),new.get('quad_mesh_resources'),new.get('material_resources')] != [1,1,1,1]:
        fail(f'batched resource shape drift: {new}')

    probe=r.get('draw_call_probe_040s_continuity',{})
    if probe.get('active_particle_count') != 18: fail(f"expected 18 active particles at 0.40 s: {probe}")
    before=int(probe.get('legacy_draw_calls_in_frame',-1))
    after=int(probe.get('batched_draw_calls_in_frame',-1))
    saved=int(probe.get('draw_calls_saved',-1))
    if before <= 0 or after < 0 or after >= before: fail(f'draw-call reduction missing: {before}->{after}')
    if saved != before-after or saved <= 0: fail(f'draw-call saving mismatch: {probe}')
    expected_frac=(before-after)/before
    if abs(float(probe.get('draw_call_reduction_fraction',-1))-expected_frac) > 1e-12: fail('draw-call reduction fraction mismatch')

    comps=r.get('visual_comparisons',[])
    if len(comps) != 6: fail(f'expected 6 visual comparisons, got {len(comps)}')
    active_rows=0
    for row in comps:
        t=round(float(row['time_s']),2)
        active=int(row['active_particle_count'])
        c2b=row['control_vs_batched']
        l2b=row['legacy_vs_batched']
        if int(l2b.get('changed_pixels_over_1lsb',-1)) < 0 or int(l2b.get('max_rgb_delta_lsb',-1)) < 0:
            fail('invalid legacy-vs-batched visual metrics')
        if t < .25 or t >= .80:
            if active != 0 or int(c2b['changed_pixels_over_1lsb']) != 0:
                fail(f'inactive-window closure failed at {t}: {row}')
        else:
            active_rows += 1
            if active <= 0: fail(f'active row has no motes at {t}')
            if int(c2b['changed_pixels_over_1lsb']) < 80: fail(f'candidate visibility too low at {t}')
            if float(c2b['changed_fraction_over_1lsb']) > .08: fail(f'candidate visibility too broad at {t}')
    if active_rows != 4: fail(f'expected 4 active comparison rows, got {active_rows}')

    visual=r.get('visual_tradeoff_summary',{})
    if int(visual.get('pair_count',-1)) != 6 or int(visual.get('active_pair_count',-1)) != 4: fail('visual summary count drift')
    if visual.get('art_direction_acceptance') is not False or visual.get('visual_qa_acceptance') is not False: fail('visual authority improperly promoted')

    tb=r.get('truth_boundary',{})
    required_true=('resource_representation_changed_only','proof_host_real_draw_call_reduction_measured','visual_delta_measured_not_auto_accepted')
    required_false=('owner_effect_parameters_modified','owner_seed_changed','animation_timing_or_easing_modified','production_particle_runtime_claimed','target_device_performance_acceptance','art_direction_final_acceptance','visual_qa_final_acceptance','gameplay_or_physics_claimed','uc_modified','canon_or_production_readiness')
    for k in required_true:
        if tb.get(k) is not True: fail(f'truth-boundary true missing: {k}')
    for k in required_false:
        if tb.get(k) is not False: fail(f'truth-boundary false missing: {k}')

    print(json.dumps({
        'result':'PASS_RUNTIME_LID_RELEASE_MOTE_BATCHING_RECEIPT_VERIFIED',
        'draw_calls_before':before,
        'draw_calls_after':after,
        'draw_calls_saved':saved,
        'visual_pair_count':len(comps),
        'byte_identical_visual_pairs':visual.get('byte_identical_pairs'),
        'active_visual_changed_pixels':visual.get('total_active_legacy_vs_batched_changed_pixels_over_1lsb'),
        'active_visual_max_delta_lsb':visual.get('max_active_legacy_vs_batched_rgb_delta_lsb'),
    }, indent=2))

if __name__=='__main__': main()
