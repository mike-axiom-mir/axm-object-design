from __future__ import annotations
import argparse, hashlib, json, math
from pathlib import Path

MODULE_SCHEMA = "axm.object-service-module/v0.1"
RECEIPT_SCHEMA = "axm.object-service-module-fit-receipt/v0.1"

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def build_local_mesh(module):
    f=module["interface"]; b=module["body"]
    stand=f["standoff_from_socket_origin_m"]; depth=b["depth_m"]
    width,height=f["footprint_m"]
    x0,x1=stand,stand+depth; y0,y1=-width/2,width/2; z0,z1=-height/2,height/2
    verts=[(x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0),(x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1)]
    faces=[(0,1,2),(0,2,3),(4,6,5),(4,7,6),(0,4,5),(0,5,1),(1,5,6),(1,6,2),(2,6,7),(2,7,3),(3,7,4),(3,4,0)]
    return {"vertices":verts,"faces":faces}

def area(a,b,c):
    u=[b[i]-a[i] for i in range(3)]; v=[c[i]-a[i] for i in range(3)]
    q=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
    return 0.5*math.sqrt(sum(x*x for x in q))

def verify(host,module,mesh):
    if module.get("schema") != MODULE_SCHEMA: raise AssertionError("module schema mismatch")
    if module.get("host_asset_id") != host.get("asset_id"): raise AssertionError("host identity mismatch")
    if any(area(*(mesh["vertices"][i] for i in face)) <= 1e-12 for face in mesh["faces"]):
        raise AssertionError("degenerate module triangle")
    results=[]
    for socket in host["sockets"]:
        if module["accepted_socket_tag"] not in socket["uc_descriptor"]["accepts"]:
            raise AssertionError("socket tag rejected")
        hw,hh=socket["footprint_m"]; mw,mh=module["interface"]["footprint_m"]
        if mw>hw+1e-12 or mh>hh+1e-12: raise AssertionError("module footprint exceeds host plate")
        hb=socket["bolt_offsets_m"]; mb=module["interface"]["bolt_offsets_m"]
        if len(hb)!=len(mb): raise AssertionError("mount point count mismatch")
        residual=max((math.dist(a,b) for a,b in zip(hb,mb)),default=0.0)
        if residual>1e-9: raise AssertionError("mount pattern mismatch")
        n=socket["frame_basis"]["normal"]; p=socket["uc_descriptor"]["transform"]["position"]
        outer=[p[i]+n[i]*socket["plate_thickness"] for i in range(3)]
        stand=module["interface"]["standoff_from_socket_origin_m"]
        inner=[p[i]+n[i]*stand for i in range(3)]
        clearance=sum((inner[i]-outer[i])*n[i] for i in range(3))
        if clearance < module["interface"]["min_body_clearance_from_host_plate_outer_face_m"]-1e-9:
            raise AssertionError("body clearance violated")
        results.append({"socket_id":socket["id"],"socket_name":socket["uc_descriptor"]["name"],"normal":n,"mount_pattern_residual_m":residual,"body_clearance_m":clearance,"footprint_margin_m":[hw-mw,hh-mh],"result":"PASS_SOURCE_FRAME_AND_MOUNT_PATTERN_FIT"})
    if len(results)!=2 or results[0]["normal"][0] != -results[1]["normal"][0]:
        raise AssertionError("bilateral host mismatch")
    return {"schema":RECEIPT_SCHEMA,"result":"PASS_BILATERAL_SERVICE_MODULE_FIT_PROOF","host_asset_id":host["asset_id"],"module_asset_id":module["asset_id"],"module_vertices":len(mesh["vertices"]),"module_triangles":len(mesh["faces"]),"socket_results":results,"truth_boundary":{"source_frame_and_mount_pattern_fit":True,"body_standoff_clearance":True,"engineering_load":False,"manufacturing_tolerance_stack":False,"full_mesh_collision_solver":False,"runtime_attachment":False,"gameplay_acceptance":False,"visual_acceptance":False}}

def write_obj(path,mesh):
    lines=["# utility-module-001 local geometry; +X maps to socket outward"]
    lines += ["v %.9f %.9f %.9f"%v for v in mesh["vertices"]]
    lines += ["f %d %d %d"%tuple(i+1 for i in face) for face in mesh["faces"]]
    Path(path).write_text("\n".join(lines)+"\n",encoding="utf-8")

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--host",required=True); ap.add_argument("--module",required=True); ap.add_argument("--out",required=True)
    a=ap.parse_args(); out=Path(a.out); out.mkdir(parents=True,exist_ok=True)
    host=json.loads(Path(a.host).read_text()); module=json.loads(Path(a.module).read_text()); mesh=build_local_mesh(module); receipt=verify(host,module,mesh)
    obj=out/"utility-module-001.obj"; write_obj(obj,mesh)
    receipt.update({"host_source_sha256":sha(a.host),"module_source_sha256":sha(a.module),"module_obj_sha256":sha(obj)})
    (out/"fit_receipt.json").write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(receipt,sort_keys=True))
if __name__=="__main__": main()
