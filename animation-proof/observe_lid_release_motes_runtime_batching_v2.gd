extends SceneTree

const GLB := "res://generated/object-rigid-components-rebound.glb"
const TECH := "res://generated/uc-rigid-scene-handoff-receipt.json"
const SEQ := "res://generated/lid-latch-motion-evidence.json"
const RIG := "res://generated/front-latch-articulation.receipt.json"
const FX := "res://generated/lid-open-release-motes-001-irregularity-candidate-v2.json"
const PARENT := "res://generated/exact-runtime-parent-vfx-head.txt"
const OUT := "res://runtime-lid-release-mote-batching-v2-receipt.json"
const MOTION := "lid_latch_open_hold_close_runtime_batch_review"
const EXPECTED_PARENT := "bc114ee7ec876107892ccedeefc8e5020315488a"
const OWNER_SEED := 41027
const COUNT := 18
const LSB := 1.0 / 255.0

var receipt := {
    "schema":"axm.object-lid-release-mote-runtime-batching-v2/v0.1",
    "state":"NOT_RUN",
    "promotion_effect":"NONE",
    "renderer_boundary":"Godot 4.7.2 GL Compatibility / X11 / Mesa llvmpipe proof host; draw-call/resource/memory observations are not target-device acceptance."
}

func j(path:String)->Dictionary:
    if not FileAccess.file_exists(path): return {}
    var v=JSON.parse_string(FileAccess.get_file_as_string(path))
    return v as Dictionary if v is Dictionary else {}

func text(path:String)->String:
    return FileAccess.get_file_as_string(path).strip_edges() if FileAccess.file_exists(path) else ""

func sha(path:String)->String:
    var h:=HashingContext.new(); h.start(HashingContext.HASH_SHA256); h.update(FileAccess.get_file_as_bytes(path)); return h.finish().hex_encode()

func write(v:Dictionary)->void:
    var f:=FileAccess.open(OUT,FileAccess.WRITE)
    if f: f.store_string(JSON.stringify(v,"  ")+"\n"); f.close()

func die(m:String)->void:
    receipt["state"]="FAIL_RUNTIME_LID_RELEASE_MOTE_BATCHING_V2"; receipt["failure"]=m; write(receipt); push_error(m); quit(1)

func node_named(root:Node,wanted:String)->Node3D:
    if String(root.name)==wanted and root is Node3D: return root as Node3D
    for c in root.get_children():
        var n:=node_named(c,wanted)
        if n!=null: return n
    return null

func source_uc(a:Array)->Vector3:
    return Vector3(float(a[0]),float(a[2]),float(a[1]))

func by_station(rows:Array)->Dictionary:
    var d:={}
    for row in rows: d[String(row["station_id"])]=row
    return d

func bounds(mi:MeshInstance3D)->Dictionary:
    var a:=mi.mesh.get_aabb(); var lo:=Vector3(INF,INF,INF); var hi:=Vector3(-INF,-INF,-INF)
    for x in [0,1]:
        for y in [0,1]:
            for z in [0,1]:
                var p:=mi.global_transform*(a.position+Vector3(a.size.x*x,a.size.y*y,a.size.z*z))
                lo=Vector3(minf(lo.x,p.x),minf(lo.y,p.y),minf(lo.z,p.z)); hi=Vector3(maxf(hi.x,p.x),maxf(hi.y,p.y),maxf(hi.z,p.z))
    return {"min":lo,"max":hi}

func h01(seed:int,i:int,salt:int)->float:
    var v:int=(seed*1664525+(i+1)*1013904223+(salt+1)*374761393)&0x7fffffff
    v=((v^(v>>13))*1274126177)&0x7fffffff
    v=v^(v>>16)
    return float(v&0x7fffffff)/2147483647.0

func specs(effect:Dictionary,seam_lo:Vector3,seam_hi:Vector3)->Array:
    var v:=effect["visual_source"] as Dictionary; var rgb:=v["color_srgb"] as Array; var out:=[]
    var base:=Color(float(rgb[0]),float(rgb[1]),float(rgb[2]),float(v["alpha_peak"])); var trigger:=float(effect["animation_dependency"]["trigger_time_s"])
    var modulation:=v["repair_modulation"] as Dictionary
    for i in range(int(v["particle_count"])):
        out.append({
            "start":Vector3(lerpf(seam_lo.x,seam_hi.x,h01(int(v["seed"]),i,1)),seam_lo.y+lerpf(-float(modulation["vertical_spawn_jitter_abs_max_m"]),float(modulation["vertical_spawn_jitter_abs_max_m"]),h01(int(v["seed"]),i,11)),lerpf(seam_lo.z,seam_hi.z,h01(int(v["seed"]),i,2))),
            "spawn":trigger+float(v["emission_span_s"])*h01(int(v["seed"]),i,3),
            "life":lerpf(float(v["lifetime_min_s"]),float(v["lifetime_max_s"]),h01(int(v["seed"]),i,4)),
            "size":lerpf(float(v["size_min_m"]),float(v["size_max_m"]),h01(int(v["seed"]),i,5)),
            "aspect":lerpf(float(modulation["billboard_aspect_min"]),float(modulation["billboard_aspect_max"]),h01(int(v["seed"]),i,9)),
            "alpha_scale":lerpf(float(modulation["alpha_scale_min"]),float(modulation["alpha_scale_max"]),h01(int(v["seed"]),i,10)),
            "curve_amp":lerpf(-float(modulation["curve_abs_max_m"]),float(modulation["curve_abs_max_m"]),h01(int(v["seed"]),i,12)),
            "curve_phase":TAU*h01(int(v["seed"]),i,13),
            "vel":Vector3(lerpf(-float(v["lateral_speed_abs_max_mps"]),float(v["lateral_speed_abs_max_mps"]),h01(int(v["seed"]),i,6)),lerpf(float(v["vertical_speed_min_mps"]),float(v["vertical_speed_max_mps"]),h01(int(v["seed"]),i,7)),-lerpf(float(v["camera_forward_speed_min_mps"]),float(v["camera_forward_speed_max_mps"]),h01(int(v["seed"]),i,8))),
            "color":base
        })
    return out

func state(s:Dictionary,effect:Dictionary,t:float,on:bool)->Dictionary:
    var age:=t-float(s["spawn"]); var life:=float(s["life"])
    if not on or age<0.0 or age>life: return {"visible":false,"pos":s["start"],"alpha":0.0}
    var u:=clampf(age/life,0.0,1.0); var p:Vector3=s["start"]; var vel:Vector3=s["vel"]
    p+=vel*age+Vector3(0,0.5*float(effect["visual_source"]["gravity_visual_mps2"])*age*age,0)
    var curve_window:=sin(PI*u); var phase:=float(s["curve_phase"]); var amp:=float(s["curve_amp"])*curve_window
    p+=Vector3(sin(PI*u+phase)*amp,cos(PI*u+phase)*amp*float(effect["visual_source"]["repair_modulation"]["curve_vertical_ratio"]),0)
    var c:Color=s["color"]; var a:=c.a*float(s["alpha_scale"])*pow(maxf(0.0,sin(PI*u)),0.75)
    return {"visible":a>0.005,"pos":p,"alpha":a}

func legacy_make(ss:Array,root:Node3D)->Dictionary:
    var rows:=[]
    for i in range(ss.size()):
        var s:=ss[i] as Dictionary; var q:=QuadMesh.new(); q.size=Vector2(float(s["size"]),float(s["size"])*float(s["aspect"]))
        var m:=StandardMaterial3D.new(); var c:Color=s["color"]; m.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED; m.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA; m.billboard_mode=BaseMaterial3D.BILLBOARD_ENABLED; m.albedo_color=Color(c.r,c.g,c.b,0); q.material=m
        var n:=MeshInstance3D.new(); n.mesh=q; n.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF; n.visible=false; root.add_child(n); rows.append({"node":n,"mat":m})
    return {"rows":rows,"mesh_instances":rows.size(),"quad_meshes":rows.size(),"materials":rows.size()}

func batch_make(ss:Array,root:Node3D)->Dictionary:
    var c:Color=(ss[0] as Dictionary)["color"]
    var m:=StandardMaterial3D.new(); m.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED; m.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA; m.billboard_mode=BaseMaterial3D.BILLBOARD_ENABLED; m.billboard_keep_scale=true; m.vertex_color_use_as_albedo=true; m.albedo_color=Color(c.r,c.g,c.b,1)
    var q:=QuadMesh.new(); q.size=Vector2.ONE; q.material=m
    var mm:=MultiMesh.new(); mm.transform_format=MultiMesh.TRANSFORM_3D; mm.use_colors=true; mm.instance_count=ss.size(); mm.mesh=q
    for i in range(ss.size()):
        var s:=ss[i] as Dictionary; var z:=float(s["size"]); var y:=z*float(s["aspect"]); mm.set_instance_transform(i,Transform3D(Basis.IDENTITY.scaled(Vector3(z,y,1)),s["start"] as Vector3)); mm.set_instance_color(i,Color(1,1,1,0))
    var n:=MultiMeshInstance3D.new(); n.multimesh=mm; n.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF; n.visible=false; root.add_child(n)
    return {"node":n,"mm":mm,"multimesh_instances":1,"multimeshes":1,"quad_meshes":1,"materials":1}

func legacy_set(x:Dictionary,ss:Array,effect:Dictionary,t:float,on:bool)->int:
    var a:=0; var rows:=x["rows"] as Array
    for i in range(ss.size()):
        var s:=ss[i] as Dictionary; var st:=state(s,effect,t,on); var r:=rows[i] as Dictionary; var n:MeshInstance3D=r["node"]; var m:StandardMaterial3D=r["mat"]; var c:Color=s["color"]
        n.position=st["pos"] as Vector3; m.albedo_color=Color(c.r,c.g,c.b,float(st["alpha"])); n.visible=bool(st["visible"]); a+=1 if n.visible else 0
    return a

func batch_set(x:Dictionary,ss:Array,effect:Dictionary,t:float,on:bool)->int:
    var a:=0; var n:MultiMeshInstance3D=x["node"]; var mm:MultiMesh=x["mm"]
    for i in range(ss.size()):
        var s:=ss[i] as Dictionary; var st:=state(s,effect,t,on); var z:=float(s["size"]); var y:=z*float(s["aspect"]); mm.set_instance_transform(i,Transform3D(Basis.IDENTITY.scaled(Vector3(z,y,1)),st["pos"] as Vector3))
        if bool(st["visible"]): mm.set_instance_color(i,Color(1,1,1,float(st["alpha"]))); a+=1
        else: mm.set_instance_color(i,Color(1,1,1,0))
    n.visible=on and a>0; return a

func metrics()->Dictionary:
    return {
        "objects":RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_OBJECTS_IN_FRAME),
        "primitives":RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME),
        "draw_calls":RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME),
        "texture_mem":RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TEXTURE_MEM_USED),
        "buffer_mem":RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_BUFFER_MEM_USED),
        "video_mem":RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_VIDEO_MEM_USED)
    }

func diff(a:Image,b:Image)->Dictionary:
    var changed:=0; var maxd:=0.0
    for y in range(a.get_height()):
        for x in range(a.get_width()):
            var p:=a.get_pixel(x,y); var q:=b.get_pixel(x,y); var d:=maxf(absf(p.r-q.r),maxf(absf(p.g-q.g),absf(p.b-q.b))); maxd=maxf(maxd,d); changed+=1 if d>LSB else 0
    return {"changed_pixels_over_1lsb":changed,"changed_fraction_over_1lsb":float(changed)/float(a.get_width()*a.get_height()),"max_rgb_delta_lsb":int(round(maxd*255.0))}

func camera_set(cam:Camera3D,id:String)->bool:
    if id=="continuity_three_quarter": cam.fov=40; cam.look_at_from_position(Vector3(1.22,0.82,-1.38),Vector3(0,0.21,0),Vector3.UP); return true
    if id=="left_oblique_seam": cam.fov=42; cam.look_at_from_position(Vector3(-1.10,0.72,-1.24),Vector3(0,0.23,-0.04),Vector3.UP); return true
    return false

func world(imported:Node3D)->Dictionary:
    var vp:=SubViewport.new(); vp.size=Vector2i(820,620); vp.own_world_3d=true; vp.render_target_update_mode=SubViewport.UPDATE_ALWAYS; vp.render_target_clear_mode=SubViewport.CLEAR_MODE_ALWAYS; get_root().add_child(vp)
    var root:=Node3D.new(); vp.add_child(root); var e:=Environment.new(); e.background_mode=Environment.BG_COLOR; e.background_color=Color(0.025,0.030,0.036,1); e.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR; e.ambient_light_color=Color(0.60,0.64,0.70,1); e.ambient_light_energy=0.75; var we:=WorldEnvironment.new(); we.environment=e; root.add_child(we)
    var sun:=DirectionalLight3D.new(); sun.light_energy=2; sun.rotation_degrees=Vector3(-48,-32,0); root.add_child(sun); var fill:=OmniLight3D.new(); fill.light_energy=2.1; fill.omni_range=4; fill.position=Vector3(-1,1.1,-0.8); root.add_child(fill); root.add_child(imported)
    var cam:=Camera3D.new(); cam.near=.03; cam.far=20; root.add_child(cam); camera_set(cam,"continuity_three_quarter"); cam.make_current(); return {"vp":vp,"root":root,"cam":cam}

func track(anim:Animation,root:Node3D,n:Node3D,samples:Array,key:String)->void:
    var tr:=anim.add_track(Animation.TYPE_VALUE); anim.track_set_path(tr,NodePath(str(root.get_path_to(n))+":rotation_degrees")); anim.track_set_interpolation_type(tr,Animation.INTERPOLATION_NEAREST); anim.value_track_set_update_mode(tr,Animation.UPDATE_DISCRETE)
    for s in samples: anim.track_insert_key(tr,float(s["time_s"]),Vector3(-float(s[key]),0,0))

func pose(p:AnimationPlayer,t:float)->void:
    p.stop(); p.play(MOTION); p.pause(); p.seek(t,true); p.advance(0)

func capture(vp:SubViewport,cam:Camera3D,p:AnimationPlayer,old:Dictionary,new:Dictionary,ss:Array,effect:Dictionary,cid:String,t:float,mode:String)->Dictionary:
    if not camera_set(cam,cid): die("unknown camera"); return {}
    pose(p,t); legacy_set(old,ss,effect,t,false); batch_set(new,ss,effect,t,false); var active:=0
    if mode=="legacy": active=legacy_set(old,ss,effect,t,true)
    elif mode=="batched": active=batch_set(new,ss,effect,t,true)
    elif mode!="control": die("unknown mode"); return {}
    for _i in range(4): await process_frame
    await RenderingServer.frame_post_draw
    var m:=metrics(); var img:=vp.get_texture().get_image()
    if img==null or img.is_empty(): die("empty image"); return {}
    var path:="res://runtime-mote-%s-%04dms-%s.png"%[cid,int(round(t*1000.0)),mode]
    if img.save_png(path)!=OK: die("save failed"); return {}
    return {"active":active,"metrics":m,"sha256":sha(path),"path":path.trim_prefix("res://"),"image":img}

func _initialize()->void:
    var tech:=j(TECH); var seq:=j(SEQ); var rig:=j(RIG); var effect:=j(FX); var parent:=text(PARENT)
    if parent!=EXPECTED_PARENT: die("Runtime parent VFX head drift"); return
    if tech.get("result")!="PASS_OBJECT_SOURCE_OWNED_RIGID_PARTS_THROUGH_UC_SCENE_GRAPH": die("Technical Art donor not green"); return
    if seq.get("result")!="PASS_ORDERED_LATCH_RELEASE_LID_CLIP_REENGAGE_SEQUENCE": die("Animation donor not green"); return
    if rig.get("result")!="PASS_BOUNDED_FRONT_LATCH_LEVER_ARTICULATION": die("Rigging donor not green"); return
    if int(effect.get("visual_source",{}).get("seed",-1))!=OWNER_SEED or int(effect.get("visual_source",{}).get("particle_count",0))!=COUNT: die("owner mote identity drift"); return
    if String(effect.get("visual_source",{}).get("source_label",""))!="STYLIZED_VISUAL_RELEASE_MOTES_NOT_DUST_OR_FLUID_SIMULATION": die("effect semantics drift"); return
    if String(effect.get("visual_source",{}).get("parameter_sampling",""))!="DECORRELATED_INTEGER_MIX_V2_IRREGULAR_MARKS": die("v2 sampler identity drift"); return
    if (effect.get("visual_source",{}).get("repair_modulation",{}) as Dictionary).is_empty(): die("v2 repair modulation missing"); return
    if not FileAccess.file_exists(GLB) or sha(GLB)!=String(tech.get("rebound_glb_sha256","")): die("GLB identity mismatch"); return

    var doc:=GLTFDocument.new(); var gs:=GLTFState.new(); if doc.append_from_file(GLB,gs)!=OK: die("GLB append failed"); return
    var scene=doc.generate_scene(gs); if scene==null or not (scene is Node3D): die("scene generation failed"); return
    var imported:=scene as Node3D; var lid:=node_named(imported,"lid_shell")
    if lid==null or not (lid is MeshInstance3D): die("lid missing"); return
    var w:=world(imported); var vp:SubViewport=w["vp"]; var root:Node3D=w["root"]; var cam:Camera3D=w["cam"]
    for _i in range(8): await process_frame
    var b:=bounds(lid as MeshInstance3D); var lo:Vector3=b["min"]; var hi:Vector3=b["max"]; var seam_lo:=Vector3(lo.x+.07,lo.y+.012,lo.z-.008); var seam_hi:=Vector3(hi.x-.07,lo.y+.012,lo.z+.018); var ss:=specs(effect,seam_lo,seam_hi)
    var fxroot:=Node3D.new(); root.add_child(fxroot); var old:=legacy_make(ss,fxroot); var new:=batch_make(ss,fxroot)

    var s0:=by_station(seq["samples"][0]["stations"]); var rr:=by_station(rig.get("station_results",[])); var pivots:=[]
    for sid in s0.keys():
        var lever:=node_named(imported,String(s0[sid]["lever_component"])); if lever==null: die("lever missing"); return
        var pv:=Node3D.new(); pv.position=source_uc(rr[sid]["pivot_m"]); imported.add_child(pv); lever.reparent(pv,true); pivots.append({"id":sid,"node":pv})
    var anim:=Animation.new(); anim.length=float(seq["duration_s"]); anim.loop_mode=Animation.LOOP_NONE; track(anim,imported,lid,seq["samples"],"lid_mathematical_rotation_deg")
    for row in pivots: track(anim,imported,row["node"],seq["samples"],"latch_lever_angle_deg")
    var player:=AnimationPlayer.new(); imported.add_child(player); player.root_node=NodePath(".."); var lib:=AnimationLibrary.new(); lib.add_animation(MOTION,anim); player.add_animation_library("",lib)

    var plan:=[["continuity_three_quarter",.20],["continuity_three_quarter",.30],["continuity_three_quarter",.40],["continuity_three_quarter",.52],["continuity_three_quarter",.80],["left_oblique_seam",.40]]
    var rows:=[]; var same:=0; var active_pairs:=0; var active_changed:=0; var max_delta:=0; var probe:={}
    for e in plan:
        var cid:=String(e[0]); var t:=float(e[1]); var ctl:=await capture(vp,cam,player,old,new,ss,effect,cid,t,"control"); var a:=await capture(vp,cam,player,old,new,ss,effect,cid,t,"legacy"); var z:=await capture(vp,cam,player,old,new,ss,effect,cid,t,"batched")
        if int(a["active"])!=int(z["active"]): die("active-count drift"); return
        var ca:=diff(ctl["image"],a["image"]); var cz:=diff(ctl["image"],z["image"]); var az:=diff(a["image"],z["image"]); var ac:=int(z["active"])
        if t<.25 or t>=.80:
            if ac!=0 or int(ca["changed_pixels_over_1lsb"])!=0 or int(cz["changed_pixels_over_1lsb"])!=0: die("inactive closure failed"); return
        else:
            if ac<=0 or int(cz["changed_pixels_over_1lsb"])<80 or float(cz["changed_fraction_over_1lsb"])>.08: die("batched active visibility escaped owner envelope"); return
            active_pairs+=1; active_changed+=int(az["changed_pixels_over_1lsb"]); max_delta=maxi(max_delta,int(az["max_rgb_delta_lsb"]))
        if int(az["changed_pixels_over_1lsb"])==0 and int(az["max_rgb_delta_lsb"])==0: same+=1
        var row={"context_id":cid,"time_s":t,"active_particle_count":ac,"control":{"sha256":ctl["sha256"],"metrics":ctl["metrics"],"path":ctl["path"]},"legacy":{"sha256":a["sha256"],"metrics":a["metrics"],"path":a["path"]},"batched":{"sha256":z["sha256"],"metrics":z["metrics"],"path":z["path"]},"control_vs_legacy":ca,"control_vs_batched":cz,"legacy_vs_batched":az}; rows.append(row)
        if cid=="continuity_three_quarter" and absf(t-.40)<.000001: probe=row

    var before:=int(probe["legacy"]["metrics"]["draw_calls"]); var after:=int(probe["batched"]["metrics"]["draw_calls"])
    if after>=before: die("real draw calls did not fall"); return
    receipt["state"]="PASS_RUNTIME_LID_RELEASE_MOTE_V2_MULTIMESH_REBIND__HOLD_QA_TARGET_DEVICE"
    receipt["decision"]="PASS_ONE_MULTIMESH_REBINDS_EXACT_VFX_V2_IRREGULARITY_WITH_REAL_DRAW_CALL_REDUCTION__NO_AUTO_ADOPTION"
    receipt["runtime_parent_vfx_head"]=parent; receipt["owner_seed"]=OWNER_SEED; receipt["parameter_sampling"]=effect["visual_source"].get("parameter_sampling"); receipt["repair_modulation"]=effect["visual_source"].get("repair_modulation"); receipt["particle_count"]=COUNT; receipt["effect_sha256"]=sha(FX); receipt["glb_sha256"]=sha(GLB); receipt["godot_version"]=Engine.get_version_info(); receipt["derived_emitter_seam"]={"min":[seam_lo.x,seam_lo.y,seam_lo.z],"max":[seam_hi.x,seam_hi.y,seam_hi.z]}
    receipt["resource_shape"]={"legacy":{"mesh_instance_resources":old["mesh_instances"],"quad_mesh_resources":old["quad_meshes"],"material_resources":old["materials"]},"batched":{"multimesh_instance_resources":new["multimesh_instances"],"multimesh_resources":new["multimeshes"],"quad_mesh_resources":new["quad_meshes"],"material_resources":new["materials"]}}
    receipt["draw_call_probe_040s_continuity"]={"active_particle_count":probe["active_particle_count"],"legacy_draw_calls_in_frame":before,"batched_draw_calls_in_frame":after,"draw_calls_saved":before-after,"draw_call_reduction_fraction":float(before-after)/float(before),"legacy_objects_in_frame":probe["legacy"]["metrics"]["objects"],"batched_objects_in_frame":probe["batched"]["metrics"]["objects"],"legacy_primitives_in_frame":probe["legacy"]["metrics"]["primitives"],"batched_primitives_in_frame":probe["batched"]["metrics"]["primitives"],"legacy_buffer_mem_used_bytes":probe["legacy"]["metrics"]["buffer_mem"],"batched_buffer_mem_used_bytes":probe["batched"]["metrics"]["buffer_mem"],"legacy_video_mem_used_bytes":probe["legacy"]["metrics"]["video_mem"],"batched_video_mem_used_bytes":probe["batched"]["metrics"]["video_mem"]}
    receipt["visual_comparisons"]=rows; receipt["visual_tradeoff_summary"]={"pair_count":rows.size(),"byte_identical_pairs":same,"active_pair_count":active_pairs,"total_active_legacy_vs_batched_changed_pixels_over_1lsb":active_changed,"max_active_legacy_vs_batched_rgb_delta_lsb":max_delta,"art_direction_acceptance":false,"visual_qa_acceptance":false}
    receipt["truth_boundary"]={"owner_effect_parameters_modified_by_runtime":false,"vfx_v2_effect_parameters_preserved":true,"owner_seed_changed":false,"animation_timing_or_easing_modified":false,"resource_representation_changed_only":true,"proof_host_real_draw_call_reduction_measured":true,"visual_delta_measured_not_auto_accepted":true,"production_particle_runtime_claimed":false,"target_device_performance_acceptance":false,"art_direction_final_acceptance":false,"visual_qa_final_acceptance":false,"gameplay_or_physics_claimed":false,"uc_modified":false,"canon_or_production_readiness":false}
    write(receipt); print("AXM OBJECT RUNTIME MOTE V2 BATCHING ",JSON.stringify(receipt)); quit(0)
