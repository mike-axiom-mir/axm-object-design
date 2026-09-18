#!/usr/bin/env python3
import argparse, json
from pathlib import Path

EXPECTED_PARENT='bc114ee7ec876107892ccedeefc8e5020315488a'
EXPECTED_EFFECT_SHA='9f16e2789e547f420781af09d2a90724ead5bf4155783c5ecfd96b8f4e8ff6d7'
EXPECTED_STATE='PASS_RUNTIME_LID_RELEASE_MOTE_V2_MULTIMESH_REBIND__HOLD_QA_TARGET_DEVICE'
EXPECTED_VFX_STATE='PASS_TARGET_HOST_OWNER_SEED_IRREGULARITY_V2_TWO_CONTEXT_PRESENTATION'


def fail(msg):
    raise SystemExit(msg)


def key(ctx, t):
    return (str(ctx), round(float(t), 3))


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--receipt', default='animation-proof/runtime-lid-release-mote-batching-v2-receipt.json')
    ap.add_argument('--vfx-receipt', default='.vfx-v2-evidence/animation-proof/vfx-lid-release-motes-irregularity-v2-receipt.json')
    args=ap.parse_args()
    p=Path(args.receipt)
    vp=Path(args.vfx_receipt)
    if not p.is_file(): fail(f'missing Runtime receipt: {p}')
    if not vp.is_file(): fail(f'missing exact VFX v2 receipt: {vp}')
    r=json.loads(p.read_text())
    v=json.loads(vp.read_text())

    if r.get('state') != EXPECTED_STATE: fail(f"unexpected Runtime state: {r.get('state')}")
    if r.get('runtime_parent_vfx_head') != EXPECTED_PARENT: fail('Runtime parent VFX v2 head drift')
    if r.get('effect_sha256') != EXPECTED_EFFECT_SHA: fail('VFX v2 effect byte identity drift')
    if r.get('owner_seed') != 41027 or r.get('particle_count') != 18: fail('owner effect identity drift')
    if r.get('parameter_sampling') != 'DECORRELATED_INTEGER_MIX_V2_IRREGULAR_MARKS': fail('v2 sampler identity drift')
    mod=r.get('repair_modulation',{})
    for name in ('billboard_aspect_min','billboard_aspect_max','alpha_scale_min','alpha_scale_max','vertical_spawn_jitter_abs_max_m','curve_abs_max_m','curve_vertical_ratio'):
        if name not in mod: fail(f'missing v2 repair modulation: {name}')

    if v.get('state') != EXPECTED_VFX_STATE: fail(f"exact VFX v2 donor not green: {v.get('state')}")
    if v.get('presentation_head') != EXPECTED_PARENT: fail('VFX v2 donor head drift')
    if v.get('owner_seed') != 41027: fail('VFX v2 donor seed drift')

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
    runtime_rows={key(row['context_id'],row['time_s']):row for row in comps}
    active_rows=0
    for row in comps:
        t=round(float(row['time_s']),2)
        active=int(row['active_particle_count'])
        c2b=row['control_vs_batched']
        l2b=row['legacy_vs_batched']
        if int(l2b.get('changed_pixels_over_1lsb',-1)) != 0:
            fail(f'legacy-vs-batched changed pixels exceed 1 LSB at {row["context_id"]} {t}: {l2b}')
        if int(l2b.get('max_rgb_delta_lsb',-1)) > 1:
            fail(f'legacy-vs-batched max raster delta >1 LSB at {row["context_id"]} {t}: {l2b}')
        if t < .25 or t >= .80:
            if active != 0 or int(c2b['changed_pixels_over_1lsb']) != 0:
                fail(f'inactive-window closure failed at {t}: {row}')
        else:
            active_rows += 1
            if active <= 0: fail(f'active row has no motes at {t}')
            if int(c2b['changed_pixels_over_1lsb']) < 80: fail(f'candidate visibility too low at {t}')
            if float(c2b['changed_fraction_over_1lsb']) > .08: fail(f'candidate visibility too broad at {t}')
    if active_rows != 4: fail(f'expected 4 active comparison rows, got {active_rows}')

    donor={key(row['context_id'],row['time_s']):row for row in v.get('static_context_checks',[])}
    checked=[]
    for k in (('continuity_three_quarter',.2),('continuity_three_quarter',.4),('continuity_three_quarter',.8),('left_oblique_seam',.4)):
        kk=key(*k)
        if kk not in donor or kk not in runtime_rows: fail(f'missing exact VFX-v2 bind row {kk}')
        expected=donor[kk]['candidate_sha256']
        observed=runtime_rows[kk]['legacy']['sha256']
        if observed != expected: fail(f'Runtime legacy does not reproduce exact VFX-v2 retained raster at {kk}: {observed} != {expected}')
        checked.append({'context_id':kk[0],'time_s':kk[1],'sha256':observed})

    visual=r.get('visual_tradeoff_summary',{})
    if int(visual.get('pair_count',-1)) != 6 or int(visual.get('active_pair_count',-1)) != 4: fail('visual summary count drift')
    if int(visual.get('total_active_legacy_vs_batched_changed_pixels_over_1lsb',-1)) != 0: fail('active visual drift exceeds 1 LSB')
    if int(visual.get('max_active_legacy_vs_batched_rgb_delta_lsb',-1)) > 1: fail('active visual max delta >1 LSB')
    if visual.get('art_direction_acceptance') is not False or visual.get('visual_qa_acceptance') is not False: fail('visual authority improperly promoted')

    tb=r.get('truth_boundary',{})
    required_true=('vfx_v2_effect_parameters_preserved','resource_representation_changed_only','proof_host_real_draw_call_reduction_measured','visual_delta_measured_not_auto_accepted')
    required_false=('owner_effect_parameters_modified_by_runtime','owner_seed_changed','animation_timing_or_easing_modified','production_particle_runtime_claimed','target_device_performance_acceptance','art_direction_final_acceptance','visual_qa_final_acceptance','gameplay_or_physics_claimed','uc_modified','canon_or_production_readiness')
    for k in required_true:
        if tb.get(k) is not True: fail(f'truth-boundary true missing: {k}')
    for k in required_false:
        if tb.get(k) is not False: fail(f'truth-boundary false missing: {k}')

    print(json.dumps({
        'result':'PASS_RUNTIME_LID_RELEASE_MOTE_V2_BATCHING_RECEIPT_VERIFIED',
        'draw_calls_before':before,
        'draw_calls_after':after,
        'draw_calls_saved':saved,
        'visual_pair_count':len(comps),
        'byte_identical_visual_pairs':visual.get('byte_identical_pairs'),
        'active_visual_changed_pixels_over_1lsb':visual.get('total_active_legacy_vs_batched_changed_pixels_over_1lsb'),
        'active_visual_max_delta_lsb':visual.get('max_active_legacy_vs_batched_rgb_delta_lsb'),
        'exact_vfx_v2_raster_bindings':checked,
    }, indent=2))

if __name__=='__main__': main()
