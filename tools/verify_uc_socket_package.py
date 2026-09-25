from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--package', required=True)
    ap.add_argument('--uc-root', required=True)
    ap.add_argument('--expected-uc-commit', required=True)
    ap.add_argument('--report', required=True)
    args=ap.parse_args()
    uc=Path(args.uc_root).resolve()
    observed=subprocess.check_output(['git','-C',str(uc),'rev-parse','HEAD'], text=True).strip()
    if observed != args.expected_uc_commit:
        raise SystemExit(f'HOLD_UC_HEAD_MISMATCH expected={args.expected_uc_commit} observed={observed}')
    sys.path.insert(0,str(uc/'src'))
    from axm_uc.asset_atoms import validate_asset_package
    raw=json.loads(Path(args.package).read_text(encoding='utf-8'))
    normalized=validate_asset_package(raw)
    sockets=[a for a in normalized['atoms'] if a['kind']=='socket']
    names=sorted(a['payload']['name'] for a in sockets)
    if names != ['left_service','right_service']:
        raise SystemExit(f'HOLD_UNEXPECTED_SOCKET_SET {names}')
    report={
        'schema':'axm.object-uc-socket-validation/v0.1',
        'result':'PASS_PINNED_UC_SOCKET_DESCRIPTOR_VALIDATION',
        'expected_uc_commit':args.expected_uc_commit,
        'observed_uc_commit':observed,
        'asset_package_schema':normalized['schema'],
        'package_id':normalized['id'],
        'package_version':normalized['version'],
        'atom_count':normalized['validation']['atom_count'],
        'atom_kinds':normalized['validation']['atom_kinds'],
        'socket_count':len(sockets),
        'socket_names':names,
        'truth_boundary':{
            'descriptor_schema_validated':True,
            'attachment_instantiated_in_3d':False,
            'physical_fit_tested':False,
            'load_tested':False,
            'collision_tested':False,
            'runtime_tested':False,
            'gameplay_acceptance':False
        }
    }
    Path(args.report).write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(report,sort_keys=True))

if __name__=='__main__':
    main()
