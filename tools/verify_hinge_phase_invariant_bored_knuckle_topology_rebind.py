from __future__ import annotations

import argparse, hashlib, json, math
from collections import defaultdict
from pathlib import Path

try:
    from tools.build_hinge_pin_annular_mesh import _build_candidate
except ModuleNotFoundError:
    from build_hinge_pin_annular_mesh import _build_candidate

SCHEMA = "axm.object-hinge-phase-invariant-bored-knuckle-topology-rebind/v0.1"
RESULT = "PASS_OBJECT_PHASE_INVARIANT_BORED_KNUCKLE_SUCCESSOR_GENUS1_TOPOLOGY_REBIND"
RULE = "SOURCE_SUCCESSOR_METRIC_ONLY_CHANGE_STILL_REQUIRES_EXACT_TOPOLOGY_CLASS_REBIND_BEFORE_PASS_TRANSFER"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _blob(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def _components(nodes, adjacency):
    left, count = set(nodes), 0
    while left:
        count += 1
        stack = [left.pop()]
        while stack:
            for nxt in adjacency.get(stack.pop(), ()):
                if nxt in left:
                    left.remove(nxt); stack.append(nxt)
    return count


def inspect(vertices, faces, declared=None):
    faces = [tuple(f) for f in faces]
    refs = sorted({v for f in faces for v in f})
    declared = refs if declared is None else list(declared)
    edges, tri_adj = defaultdict(list), defaultdict(set)
    degenerate = 0
    for fi, f in enumerate(faces):
        a, b, c = (vertices[i] for i in f)
        ux, uy, uz = b[0]-a[0], b[1]-a[1], b[2]-a[2]
        vx, vy, vz = c[0]-a[0], c[1]-a[1], c[2]-a[2]
        cross = (uy*vz-uz*vy, uz*vx-ux*vz, ux*vy-uy*vx)
        if len(set(f)) != 3 or sum(x*x for x in cross) <= 4e-24: degenerate += 1
        for x, y in ((f[0],f[1]),(f[1],f[2]),(f[2],f[0])):
            edges[tuple(sorted((x,y)))].append((x,y,fi))
    conflicts = 0
    for uses in edges.values():
        if len(uses) == 2:
            (a,b,fa),(c,d,fb)=uses
            tri_adj[fa].add(fb); tri_adj[fb].add(fa)
            conflicts += int(not (a==d and b==c))
    fan_counts = {}
    for v in declared:
        incident = [i for i,f in enumerate(faces) if v in f]
        adj = defaultdict(set)
        for edge, uses in edges.items():
            if v not in edge: continue
            ids = [u[2] for u in uses if u[2] in incident]
            for i in range(len(ids)):
                for j in range(i+1,len(ids)):
                    adj[ids[i]].add(ids[j]); adj[ids[j]].add(ids[i])
        fan_counts[v] = _components(incident, adj) if incident else 0
    boundary = sum(len(u)==1 for u in edges.values())
    nonmanifold = sum(len(u)>2 for u in edges.values())
    isolated = sum(v==0 for v in fan_counts.values())
    max_fans = max(fan_counts.values(), default=0)
    chi = len(refs)-len(edges)+len(faces)
    tri_components = _components(range(len(faces)), tri_adj)
    closed = boundary==0 and nonmanifold==0 and conflicts==0 and degenerate==0 and isolated==0 and max_fans==1 and tri_components==1
    genus = (2-chi)//2 if closed and (2-chi)>=0 and (2-chi)%2==0 else None
    return {"vertices":len(refs),"triangles":len(faces),"unique_edges":len(edges),"triangle_components":tri_components,
            "boundary_edges":boundary,"non_manifold_edges":nonmanifold,"orientation_conflicts":conflicts,
            "degenerate_triangles":degenerate,"isolated_vertices":isolated,"max_vertex_fan_components":max_fans,
            "euler_characteristic":chi,"orientable_genus":genus,"closed_orientable_vertex_manifold":closed}


def require(report, expected, label):
    for k,v in expected.items():
        if report.get(k) != v: raise AssertionError(f"{label} topology drift: {k}")
    if not report["closed_orientable_vertex_manifold"]: raise AssertionError(f"{label} not closed orientable vertex-manifold")


def solid_control(n=12):
    verts=[]
    for x in (-.5,.5):
        for i in range(n):
            a=2*math.pi*i/n; verts.append((x,math.cos(a),math.sin(a)))
    lc=len(verts); verts.append((-.5,0,0)); rc=len(verts); verts.append((.5,0,0)); faces=[]
    for i in range(n):
        j=(i+1)%n; l=i; lj=j; r=n+i; rj=n+j
        faces += [(l,lj,r),(lj,rj,r),(l,lc,lj),(r,rj,rc)]
    return verts, faces


def evaluate(host_path, annular_path, successor_path, topology_path, builder_path):
    host=json.loads(Path(host_path).read_text()); ann=json.loads(Path(annular_path).read_text())
    suc=json.loads(Path(successor_path).read_text()); con=json.loads(Path(topology_path).read_text())
    if con.get("schema") != SCHEMA or con.get("reusable_rule") != RULE: raise AssertionError("contract identity drift")
    if con.get("asset_id") != host.get("asset_id") or con.get("successor_id") != suc.get("successor_id"): raise AssertionError("asset/source-successor identity drift")
    if con["legacy_host_source_sha256"] != _sha256(Path(host_path)): raise AssertionError("host source identity drift")
    if con["successor_contract_git_blob_sha1"] != _blob(Path(successor_path)): raise AssertionError("source-successor contract blob drift")
    if con["predecessor_annular_contract_git_blob_sha1"] != _blob(Path(annular_path)): raise AssertionError("predecessor annular blob drift")
    if con["annular_builder_git_blob_sha1"] != _blob(Path(builder_path)): raise AssertionError("annular builder blob drift")
    auth=con["geometry_authority"]
    if auth.get("geometry_rebind_is_observation_only") is not True or auth.get("historical_pass_transferred") is not False: raise AssertionError("Geometry truth boundary drift")
    for k,v in auth.items():
        if k not in ("geometry_rebind_is_observation_only",) and k != "historical_pass_transferred" and v is not False: raise AssertionError(f"Geometry authority expansion: {k}")
    so=suc["source_owned_successor"]
    if so.get("automatic_downstream_adoption") is not False or so.get("legacy_host_source_rewritten") is not False or so.get("predecessor_source_successor_rewritten") is not False: raise AssertionError("source-owner continuity drift")
    old=float(ann["mesh_bore_radius_m"]); new=float(so["bore_circumradius_m"])
    if abs(old-con["expected_predecessor_bore_circumradius_m"])>1e-12 or abs(new-con["expected_successor_bore_circumradius_m"])>1e-12 or new<=old: raise AssertionError("bore-radius identity drift")
    before,_=_build_candidate(host,{"mesh_bore_radius_m":old}); after,_=_build_candidate(host,{"mesh_bore_radius_m":new})
    if before["faces"] != after["faces"] or before["groups"] != after["groups"]: raise AssertionError("metric-only successor changed topology records")
    deltas=[math.dist(a,b) for a,b in zip(before["vertices"],after["vertices"])]
    changed=sum(d>1e-15 for d in deltas); max_delta=max(deltas)
    if changed != con["expected_changed_vertex_positions"] or abs(max_delta-(new-old))>1e-12: raise AssertionError("geometric-delta evidence drift")
    pre_reports=[]; post_reports=[]
    for mesh,reports in ((before,pre_reports),(after,post_reports)):
        for g in mesh["groups"]:
            r=inspect(mesh["vertices"],mesh["faces"][g["first_face"]:g["first_face"]+g["face_count"]],g["vertex_indices"])
            require(r,con["expected_per_knuckle"],g["name"]); reports.append({"name":g["name"],**r})
    def agg(mesh,reports): return {"vertices":len(mesh["vertices"]),"triangles":len(mesh["faces"]),"unique_edges":sum(r["unique_edges"] for r in reports),"triangle_components":len(reports),"euler_characteristic_sum":sum(r["euler_characteristic"] for r in reports),"orientable_genus_sum":sum(r["orientable_genus"] for r in reports)}
    pre_agg,post_agg=agg(before,pre_reports),agg(after,post_reports)
    for label,a in (("predecessor",pre_agg),("successor",post_agg)):
        for k,v in con["expected_aggregate"].items():
            if a[k] != v: raise AssertionError(f"{label} aggregate topology drift: {k}")
    cv,cf=solid_control(con["expected_segments"]); control=inspect(cv,cf)
    if control["euler_characteristic"] != 2 or control["orientable_genus"] != 0: raise AssertionError("solid negative control drift")
    rejected=False
    try:
        exp=dict(con["expected_per_knuckle"]); exp.update(vertices=control["vertices"],triangles=control["triangles"],unique_edges=control["unique_edges"]); require(control,exp,"solid-control")
    except AssertionError: rejected=True
    if not rejected: raise AssertionError("genus gate accepted closed genus-0 solid")
    return {"schema":"axm.object-hinge-phase-invariant-bored-knuckle-topology-rebind-receipt/v0.1","result":RESULT,
            "asset_id":con["asset_id"],"successor_id":con["successor_id"],"hard_surface_donor_head":con["hard_surface_donor_head"],
            "predecessor_geometry_head":con["predecessor_geometry_head"],"predecessor_bore_circumradius_m":old,"successor_bore_circumradius_m":new,
            "bore_circumradius_delta_m":new-old,"changed_vertex_positions":changed,"maximum_vertex_position_delta_m":max_delta,
            "face_connectivity_identical_to_predecessor":True,"group_partition_identical_to_predecessor":True,"historical_pass_transferred":False,
            "predecessor_group_reports_rebuilt":pre_reports,"successor_group_reports":post_reports,"predecessor_aggregate_rebuilt":pre_agg,"successor_aggregate":post_agg,
            "closed_solid_cylinder_negative_control":{**control,"rejected_by_through_bore_gate":rejected},"geometry_lane_mutated_source_successor":False,
            "automatic_downstream_adoption":False,"reusable_rule":RULE,"truth_boundary":con["truth_boundary"]}


def main():
    p=argparse.ArgumentParser()
    for arg in ("host","annular-contract","successor-contract","topology-contract","annular-builder","out"): p.add_argument(f"--{arg}",required=True)
    a=p.parse_args(); out=Path(a.out); out.mkdir(parents=True,exist_ok=True)
    r=evaluate(a.host,a.annular_contract,a.successor_contract,a.topology_contract,a.annular_builder)
    (out/"hinge-phase-invariant-bored-knuckle-topology-rebind-receipt.json").write_text(json.dumps(r,indent=2,sort_keys=True)+"\n")
    print(r["result"])


if __name__ == "__main__": main()
