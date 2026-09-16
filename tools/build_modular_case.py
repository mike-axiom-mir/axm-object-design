from __future__ import annotations
import argparse, hashlib, json, math
from pathlib import Path

SCHEMA = "axm.object-hard-surface/v0.1"
RECEIPT_SCHEMA = "axm.object-hard-surface-receipt/v0.1"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def _add_box(mesh, name, center, size):
    cx, cy, cz = center
    sx, sy, sz = size
    x0, x1 = cx - sx/2, cx + sx/2
    y0, y1 = cy - sy/2, cy + sy/2
    z0, z1 = cz - sz/2, cz + sz/2
    verts = [
        (x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0),
        (x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1),
    ]
    base = len(mesh['vertices'])
    mesh['vertices'].extend(verts)
    faces = [
        (0,1,2),(0,2,3),(4,6,5),(4,7,6),
        (0,4,5),(0,5,1),(1,5,6),(1,6,2),
        (2,6,7),(2,7,3),(3,7,4),(3,4,0),
    ]
    mesh['faces'].extend(tuple(base+i for i in f) for f in faces)
    mesh['groups'].append({'name': name, 'first_face': len(mesh['faces'])-12, 'face_count': 12})


def _add_cylinder_x(mesh, name, center, length, radius, segments=12):
    cx, cy, cz = center
    base = len(mesh['vertices'])
    for x in (cx-length/2, cx+length/2):
        for i in range(segments):
            a = 2*math.pi*i/segments
            mesh['vertices'].append((x, cy+radius*math.cos(a), cz+radius*math.sin(a)))
    faces_before = len(mesh['faces'])
    for i in range(segments):
        j = (i+1) % segments
        a0, a1 = base+i, base+j
        b0, b1 = base+segments+i, base+segments+j
        mesh['faces'].append((a0,b0,b1))
        mesh['faces'].append((a0,b1,a1))
    # caps, triangulated as fans using implicit center vertices
    c0 = len(mesh['vertices']); mesh['vertices'].append((cx-length/2, cy, cz))
    c1 = len(mesh['vertices']); mesh['vertices'].append((cx+length/2, cy, cz))
    for i in range(segments):
        j = (i+1) % segments
        mesh['faces'].append((c0, base+j, base+i))
        mesh['faces'].append((c1, base+segments+i, base+segments+j))
    mesh['groups'].append({'name': name, 'first_face': faces_before, 'face_count': len(mesh['faces'])-faces_before})


def build(source):
    if source.get('schema') != SCHEMA:
        raise ValueError(f"unsupported schema: {source.get('schema')}")
    d = source['dimensions_m']
    w, depth, body_h, lid_h, split_gap = d['width'], d['depth'], d['body_height'], d['lid_height'], d['split_gap']
    mesh = {'vertices': [], 'faces': [], 'groups': []}
    components = []
    def box(name, center, size, role):
        _add_box(mesh, name, center, size)
        components.append({'name': name, 'kind': 'box', 'center_m': center, 'size_m': size, 'role': role})
    def cylx(name, center, length, radius, role, segments=12):
        _add_cylinder_x(mesh, name, center, length, radius, segments)
        components.append({'name': name, 'kind': 'cylinder_x', 'center_m': center, 'length_m': length, 'radius_m': radius, 'role': role})

    # Primary manufactured masses.
    box('body_shell', [0,0,body_h/2], [w, depth, body_h], 'primary_shell')
    lid_z = body_h + split_gap + lid_h/2
    box('lid_shell', [0,0,lid_z], [w, depth, lid_h], 'lid_shell')

    # Front service panel and latch construction.
    panel_depth = source['front_panel']['depth']
    box('front_service_panel', [0, -(depth+panel_depth)/2, body_h*0.52], [w*0.60, panel_depth, body_h*0.52], 'service_panel')
    for idx, x in enumerate(source['latches']['x_positions']):
        box(f'latch_{idx}_keeper', [x, -(depth+0.022)/2, body_h+split_gap*0.5], [0.08, 0.022, 0.055], 'latch_keeper')
        box(f'latch_{idx}_lever', [x, -(depth+0.040)/2, body_h*0.86], [0.055, 0.018, 0.095], 'latch_lever')

    # Feet and corner guards remain sparse/readable rather than decorative density.
    for ix, x in enumerate((-w*0.41, w*0.41)):
        for iy, y in enumerate((-depth*0.39, depth*0.39)):
            box(f'foot_{ix}_{iy}', [x,y,0.018], [0.09,0.07,0.036], 'foot')
    guard_w, guard_d = 0.045, 0.045
    for ix, x in enumerate((-w/2-guard_w/2, w/2+guard_w/2)):
        for iy, y in enumerate((-depth/2-guard_d/2, depth/2+guard_d/2)):
            box(f'corner_guard_{ix}_{iy}', [x,y,body_h*0.52], [guard_w, guard_d, body_h*0.78], 'corner_guard')

    # Explicit mechanical articulation interface: one coaxial hinge line with alternating ownership.
    h = source['hinge']
    hy = depth/2 + h['offset_y']
    hz = body_h + h['offset_z']
    for k in h['knuckles']:
        cylx(f"hinge_{k['owner']}_{k['id']}", [k['center_x'], hy, hz], k['length'], h['knuckle_radius'], f"hinge_knuckle_{k['owner']}", h['segments'])
    cylx('hinge_pin', [0,hy,hz], h['pin_length'], h['pin_radius'], 'hinge_pin', h['segments'])

    # Explicit hard-point geometry and source-owned interface frames.
    sockets = []
    for s in source['sockets']:
        x,y,z = s['uc_descriptor']['transform']['position']
        nx,ny,nz = s['frame_basis']['normal']
        plate_t = s['plate_thickness']
        if abs(nx) == 1:
            box(f"socket_{s['id']}_plate", [x+nx*plate_t/2,y,z], [plate_t,s['footprint_m'][0],s['footprint_m'][1]], 'attachment_plate')
            for bi,(dy,dz) in enumerate(s['bolt_offsets_m']):
                cylx(f"socket_{s['id']}_bolt_{bi}", [x+nx*(plate_t+0.006), y+dy, z+dz], 0.012, 0.009, 'bolt_head', 10)
        sockets.append(s)

    return {
        'mesh': mesh,
        'components': components,
        'sockets': sockets,
        'hinge_axis': {'origin_m': [0,hy,hz], 'axis': [1,0,0]},
        'bounds_design_m': {
            'x': [-w/2-guard_w, w/2+guard_w],
            'y': [-depth/2-guard_d, depth/2+max(guard_d,h['offset_y']+h['knuckle_radius'])],
            'z': [0, body_h+split_gap+lid_h],
        },
    }


def _write_obj(path: Path, result):
    m = result['mesh']
    lines = ['# generated by axm-object-design build_modular_case.py']
    for v in m['vertices']:
        lines.append('v %.9f %.9f %.9f' % tuple(v))
    groups_by_first = {g['first_face']: g for g in m['groups']}
    for idx,f in enumerate(m['faces']):
        if idx in groups_by_first:
            lines.append('g ' + groups_by_first[idx]['name'])
        lines.append('f %d %d %d' % tuple(i+1 for i in f))
    path.write_text('\n'.join(lines)+'\n', encoding='utf-8')


def _write_proof_svg(path: Path, result):
    components = result['components']
    W, H = 1200, 520
    def map_front(x,z):
        return 60 + (x + 0.5) * 520, 460 - z * 900
    def map_side(y,z):
        return 670 + (y + 0.35) * 600, 460 - z * 900
    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
             '<rect x="0" y="0" width="1200" height="520" fill="#ffffff"/>',
             '<text x="60" y="30" font-family="monospace" font-size="18">modular-equipment-case-001 — structural proof views (not visual acceptance)</text>',
             '<text x="60" y="55" font-family="monospace" font-size="15">front / XZ</text>',
             '<text x="670" y="55" font-family="monospace" font-size="15">side / YZ</text>']
    for c in components:
        stroke='#222222'
        fill='none'
        if c['kind']=='box':
            cx,cy,cz=c['center_m']; sx,sy,sz=c['size_m']
            x0,z1=map_front(cx-sx/2, cz+sz/2); x1,z0=map_front(cx+sx/2, cz-sz/2)
            lines.append(f'<rect x="{x0:.2f}" y="{z1:.2f}" width="{x1-x0:.2f}" height="{z0-z1:.2f}" fill="{fill}" stroke="{stroke}" stroke-width="1"/>')
            y0,z1s=map_side(cy-sy/2, cz+sz/2); y1,z0s=map_side(cy+sy/2, cz-sz/2)
            lines.append(f'<rect x="{y0:.2f}" y="{z1s:.2f}" width="{y1-y0:.2f}" height="{z0s-z1s:.2f}" fill="{fill}" stroke="{stroke}" stroke-width="1"/>')
        else:
            cx,cy,cz=c['center_m']; length=c['length_m']; r=c['radius_m']
            x0,z1=map_front(cx-length/2, cz+r); x1,z0=map_front(cx+length/2, cz-r)
            lines.append(f'<rect x="{x0:.2f}" y="{z1:.2f}" width="{x1-x0:.2f}" height="{z0-z1:.2f}" fill="{fill}" stroke="{stroke}" stroke-width="1"/>')
            sy,sz=map_side(cy,cz)
            lines.append(f'<circle cx="{sy:.2f}" cy="{sz:.2f}" r="{r*900:.2f}" fill="{fill}" stroke="{stroke}" stroke-width="1"/>')
    # Socket axes are explicit source evidence, not inferred from mesh normals.
    for s in result['sockets']:
        ox,oy,oz=s['uc_descriptor']['transform']['position']; nx,ny,nz=s['frame_basis']['normal']
        px,pz=map_front(ox,oz); qx,qz=map_front(ox+nx*0.06,oz+nz*0.06)
        lines.append(f'<line x1="{px:.2f}" y1="{pz:.2f}" x2="{qx:.2f}" y2="{qz:.2f}" stroke="#aa0000" stroke-width="3"/>')
        py,pzs=map_side(oy,oz); qy,qzs=map_side(oy+ny*0.06,oz+nz*0.06)
        lines.append(f'<line x1="{py:.2f}" y1="{pzs:.2f}" x2="{qy:.2f}" y2="{qzs:.2f}" stroke="#aa0000" stroke-width="3"/>')
    lines.append('<text x="60" y="505" font-family="monospace" font-size="12">red marks: declared socket normals; hinge/socket load, motion, collision and runtime acceptance are untested</text>')
    lines.append('</svg>')
    path.write_text('\n'.join(lines)+'\n', encoding='utf-8')


def _triangle_area(a,b,c):
    ux,uy,uz = b[0]-a[0],b[1]-a[1],b[2]-a[2]
    vx,vy,vz = c[0]-a[0],c[1]-a[1],c[2]-a[2]
    cx,cy,cz = uy*vz-uz*vy, uz*vx-ux*vz, ux*vy-uy*vx
    return 0.5*math.sqrt(cx*cx+cy*cy+cz*cz)


def verify(source, result):
    m = result['mesh']
    verts, faces = m['vertices'], m['faces']
    deg = 0
    for f in faces:
        if any(i < 0 or i >= len(verts) for i in f):
            raise AssertionError('face index out of bounds')
        if _triangle_area(*(verts[i] for i in f)) <= 1e-12:
            deg += 1
    # hinge: all knuckle centers lie on declared x axis and are non-overlapping along x.
    h = source['hinge']
    intervals = []
    for k in sorted(h['knuckles'], key=lambda x: x['center_x']):
        intervals.append((k['center_x']-k['length']/2, k['center_x']+k['length']/2, k['owner'], k['id']))
    min_gap = min(intervals[i+1][0]-intervals[i][1] for i in range(len(intervals)-1))
    if min_gap < h['min_axial_clearance'] - 1e-9:
        raise AssertionError(f'hinge axial clearance violated: {min_gap}')
    # socket frames: normalized, orthogonal, and bilateral mirrored pair.
    sockets = source['sockets']
    for s in sockets:
        n,u = s['frame_basis']['normal'],s['frame_basis']['up']
        nl = math.sqrt(sum(v*v for v in n)); ul = math.sqrt(sum(v*v for v in u)); dot = sum(a*b for a,b in zip(n,u))
        if abs(nl-1)>1e-9 or abs(ul-1)>1e-9 or abs(dot)>1e-9:
            raise AssertionError(f"socket frame not orthonormal: {s['id']}")
    if len(sockets) != 2:
        raise AssertionError('v0.1 proof requires exactly two bilateral sockets')
    a,b = sockets
    mirrored = (
        abs(a['uc_descriptor']['transform']['position'][0] + b['uc_descriptor']['transform']['position'][0]) < 1e-9 and
        abs(a['uc_descriptor']['transform']['position'][1] - b['uc_descriptor']['transform']['position'][1]) < 1e-9 and
        abs(a['uc_descriptor']['transform']['position'][2] - b['uc_descriptor']['transform']['position'][2]) < 1e-9 and
        a['frame_basis']['normal'][0] == -b['frame_basis']['normal'][0] and a['frame_basis']['up'] == b['frame_basis']['up']
    )
    if not mirrored:
        raise AssertionError('socket pair is not bilateral-mirrored')
    return {
        'schema': RECEIPT_SCHEMA,
        'result': 'PASS_STRUCTURAL_INTERFACE_PROOF',
        'asset_id': source['asset_id'],
        'vertex_count': len(verts),
        'triangle_count': len(faces),
        'degenerate_triangles': deg,
        'component_count': len(result['components']),
        'socket_count': len(sockets),
        'socket_contract_donor': source['socket_contract_donor'],
        'hinge_knuckle_count': len(h['knuckles']),
        'hinge_min_measured_axial_clearance_m': round(min_gap, 9),
        'hinge_required_min_axial_clearance_m': h['min_axial_clearance'],
        'hinge_axis': result['hinge_axis'],
        'bounds_design_m': result['bounds_design_m'],
        'claims': {
            'structural_geometry_generated': True,
            'interface_frames_checked': True,
            'hinge_coaxial_layout_checked': True,
            'hinge_motion_tested': False,
            'load_bearing_tested': False,
            'collision_tested': False,
            'materials_or_lookdev_tested': False,
            'runtime_tested': False,
            'visual_acceptance': False,
        }
    }


def build_uc_socket_package(source, result, obj_sha256):
    bounds=result['bounds_design_m']
    width=bounds['x'][1]-bounds['x'][0]; depth=bounds['y'][1]-bounds['y'][0]; height=bounds['z'][1]-bounds['z'][0]
    atoms=[
        {
            'id':'case-shape','kind':'shape','purpose':'Generated modular equipment case mesh descriptor.','uses':[],
            'payload':{
                'dimension':'3d','representation':'mesh',
                'source':{'uri':'local://generated/modular-equipment-case-001.obj','mime_type':'model/obj','digest':'sha256:'+obj_sha256,'color_space':'not-applicable'},
                'bounds':{'width':width,'height':height,'depth':depth,'unit':'meter'}
            }
        },
        {
            'id':'case-part','kind':'part','purpose':'Source-owned manufactured case part used only as the socket owner.','uses':['case-shape'],
            'payload':{'role':'modular equipment case','shape':'case-shape','children':[],'transform':{'position':[0,0,0],'rotation_euler':[0,0,0],'scale':[1,1,1]},'tags':['equipment-case','hard-surface','socket-owner']}
        }
    ]
    roots=['case-part']
    for s in source['sockets']:
        atom={'id':s['id'],'kind':'socket','purpose':'Descriptor-only attachment socket projected from the exact object source.','uses':['case-part'],'payload':s['uc_descriptor']}
        atoms.append(atom); roots.append(s['id'])
    return {
        'schema':source['socket_contract_donor']['schema'],
        'id':'axm.object.modular-equipment-case-001',
        'version':'0.1.0',
        'asset_class':'object.equipment-case',
        'root_atoms':roots,
        'atoms':atoms,
        'provenance':{
            'kind':'local-authored-source',
            'basis':'Self-authored deterministic case geometry with socket descriptors projected from the exact source; UC donor validates descriptor structure only.',
            'creator':'AXM 3D Studio Hard-Surface Specialist',
            'source_uri':'local://assets/modular-equipment-case-001/source.json'
        },
        'limitations':[
            'socket descriptors do not prove physical fit, load, collision, attachment instantiation or gameplay behavior',
            'the OBJ is a structural proof mesh and has no final materials or Art Director acceptance',
            'hinge geometry is structurally checked but hinge motion is not tested'
        ]
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', required=True)
    ap.add_argument('--out-dir', required=True)
    args = ap.parse_args()
    src_path = Path(args.source)
    out = Path(args.out_dir); out.mkdir(parents=True, exist_ok=True)
    source = json.loads(src_path.read_text(encoding='utf-8'))
    result = build(source)
    obj = out/'modular-equipment-case-001.obj'
    _write_obj(obj, result)
    _write_proof_svg(out/'proof-front-side.svg', result)
    receipt = verify(source, result)
    receipt['source_sha256'] = _sha256(src_path)
    receipt['obj_sha256'] = _sha256(obj)
    receipt['proof_svg_sha256'] = _sha256(out/'proof-front-side.svg')
    package=build_uc_socket_package(source, result, receipt['obj_sha256'])
    (out/'uc-socket-package.json').write_text(json.dumps(package, indent=2, sort_keys=True)+'\n', encoding='utf-8')
    receipt['uc_socket_package_sha256'] = _sha256(out/'uc-socket-package.json')
    (out/'structural-receipt.json').write_text(json.dumps(receipt, indent=2, sort_keys=True)+'\n', encoding='utf-8')
    print(json.dumps(receipt, sort_keys=True))

if __name__ == '__main__':
    main()
