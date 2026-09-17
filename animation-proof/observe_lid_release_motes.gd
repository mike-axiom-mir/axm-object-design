extends SceneTree

const GLB_PATH := "res://generated/object-rigid-components-rebound.glb"
const TECH_RECEIPT_PATH := "res://generated/uc-rigid-scene-handoff-receipt.json"
const SEQUENCE_PATH := "res://generated/lid-latch-motion-evidence.json"
const RIG_RECEIPT_PATH := "res://generated/front-latch-articulation.receipt.json"
const EFFECT_PATH := "res://../assets/modular-equipment-case-001/lid-open-release-motes-001.json"
const EFFECT_HEAD_PATH := "res://generated/exact-vfx-head.txt"
const TARGET_RECEIPT_PATH := "res://vfx-lid-release-motes-receipt.json"
const MOTION_NAME := "lid_latch_open_hold_close_vfx_review"
const EPS_DEG := 0.00001
const EPS_M := 0.000001
const PIXEL_THRESHOLD := 1.0 / 255.0

var receipt := {
    "schema": "axm.object-reactive-vfx-target-proof/v0.1",
    "state": "NOT_RUN",
    "promotion_effect": "NONE",
    "renderer_boundary": "Godot 4.7.2 GL Compatibility / X11 / llvmpipe proof receiver. Deterministic analytic visual motes only; not a production particle runtime, fluid/dust simulation, physics, gameplay or performance proof."
}

func read_json(path: String) -> Dictionary:
    if not FileAccess.file_exists(path):
        return {}
    var parsed = JSON.parse_string(FileAccess.get_file_as_string(path))
    return parsed as Dictionary if parsed is Dictionary else {}

func read_text(path: String) -> String:
    if not FileAccess.file_exists(path):
        return ""
    return FileAccess.get_file_as_string(path).strip_edges()

func sha256_file(path: String) -> String:
    var bytes := FileAccess.get_file_as_bytes(path)
    var ctx := HashingContext.new()
    ctx.start(HashingContext.HASH_SHA256)
    ctx.update(bytes)
    return ctx.finish().hex_encode()

func write_receipt() -> void:
    var file := FileAccess.open(TARGET_RECEIPT_PATH, FileAccess.WRITE)
    if file != null:
        file.store_string(JSON.stringify(receipt, "  ") + "\n")
        file.close()

func fail(message: String) -> void:
    receipt["state"] = "FAIL_TARGET_HOST_REACTIVE_VFX_PROOF"
    receipt["failure"] = message
    write_receipt()
    push_error(message)
    quit(1)

func find_node(root: Node, wanted: String) -> Node3D:
    if String(root.name) == wanted and root is Node3D:
        return root as Node3D
    for child in root.get_children():
        var found := find_node(child, wanted)
        if found != null:
            return found
    return null

func source_to_uc(values: Array) -> Vector3:
    if values.size() != 3:
        fail("source pivot is not vec3")
        return Vector3.ZERO
    return Vector3(float(values[0]), float(values[2]), float(values[1]))

func station_lookup(rows: Array) -> Dictionary:
    var out := {}
    for row in rows:
        out[String(row["station_id"])] = row
    return out

func make_viewport(imported: Node3D) -> SubViewport:
    var viewport := SubViewport.new()
    viewport.size = Vector2i(820, 620)
    viewport.own_world_3d = true
    viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
    viewport.render_target_clear_mode = SubViewport.CLEAR_MODE_ALWAYS
    get_root().add_child(viewport)

    var root3d := Node3D.new()
    root3d.name = "VFX_REVIEW_WORLD"
    viewport.add_child(root3d)

    var env := Environment.new()
    env.background_mode = Environment.BG_COLOR
    env.background_color = Color(0.025, 0.030, 0.036, 1.0)
    env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
    env.ambient_light_color = Color(0.60, 0.64, 0.70, 1.0)
    env.ambient_light_energy = 0.75
    var world := WorldEnvironment.new()
    world.environment = env
    root3d.add_child(world)

    var key := DirectionalLight3D.new()
    key.light_energy = 2.0
    key.rotation_degrees = Vector3(-48.0, -32.0, 0.0)
    root3d.add_child(key)

    var fill := OmniLight3D.new()
    fill.light_energy = 2.1
    fill.omni_range = 4.0
    fill.position = Vector3(-1.0, 1.1, -0.8)
    root3d.add_child(fill)

    root3d.add_child(imported)

    var camera := Camera3D.new()
    camera.name = "VFX_REVIEW_CAMERA"
    camera.near = 0.03
    camera.far = 20.0
    camera.fov = 40.0
    root3d.add_child(camera)
    camera.look_at_from_position(Vector3(1.22, 0.82, -1.38), Vector3(0.0, 0.21, 0.0), Vector3.UP)
    camera.make_current()
    return viewport

func add_discrete_rotation_track(animation: Animation, root: Node3D, node: Node3D, samples: Array, value_key: String, flip_sign: bool) -> int:
    var track := animation.add_track(Animation.TYPE_VALUE)
    var path := str(root.get_path_to(node)) + ":rotation_degrees"
    animation.track_set_path(track, NodePath(path))
    animation.track_set_interpolation_type(track, Animation.INTERPOLATION_NEAREST)
    animation.value_track_set_update_mode(track, Animation.UPDATE_DISCRETE)
    for sample in samples:
        var deg := float(sample[value_key])
        if flip_sign:
            deg = -deg
        animation.track_insert_key(track, float(sample["time_s"]), Vector3(deg, 0.0, 0.0))
    return track

func mesh_world_bounds(instance: MeshInstance3D) -> Dictionary:
    var aabb := instance.mesh.get_aabb()
    var minp := Vector3(INF, INF, INF)
    var maxp := Vector3(-INF, -INF, -INF)
    for ix in [0, 1]:
        for iy in [0, 1]:
            for iz in [0, 1]:
                var local := aabb.position + Vector3(aabb.size.x * ix, aabb.size.y * iy, aabb.size.z * iz)
                var world := instance.global_transform * local
                minp.x = minf(minp.x, world.x)
                minp.y = minf(minp.y, world.y)
                minp.z = minf(minp.z, world.z)
                maxp.x = maxf(maxp.x, world.x)
                maxp.y = maxf(maxp.y, world.y)
                maxp.z = maxf(maxp.z, world.z)
    return {"min": minp, "max": maxp}

func hash01(seed: int, index: int, salt: int) -> float:
    var value := (seed + (index + 1) * 1103515245 + (salt + 1) * 12345) & 0x7fffffff
    return float(value % 10000) / 9999.0

func validate_effect_contract(effect: Dictionary, sequence_contract: Dictionary) -> String:
    if String(effect.get("schema", "")) != "axm.object-reactive-vfx/v0.1":
        return "unexpected effect schema"
    if String(effect.get("asset_id", "")) != "modular-equipment-case-001":
        return "unexpected effect asset"
    var dep := effect.get("animation_dependency", {}) as Dictionary
    if String(dep.get("sequence_id", "")) != String(sequence_contract.get("sequence_id", "")):
        return "sequence identity drift"
    if int(dep.get("sample_rate_hz", 0)) != int(sequence_contract.get("sample_rate_hz", 0)):
        return "sample-rate drift"
    if absf(float(dep.get("duration_s", -1.0)) - float(sequence_contract.get("duration_s", -2.0))) > 0.000001:
        return "sequence duration drift"
    var wanted_phase := String(dep.get("trigger_phase_id", ""))
    var matched := false
    var exact_start := -1.0
    for phase in sequence_contract.get("phases", []):
        if String(phase.get("id", "")) == wanted_phase:
            matched = true
            exact_start = float(phase.get("start_s", -1.0))
            break
    if not matched:
        return "trigger phase missing"
    if absf(float(dep.get("trigger_time_s", -2.0)) - exact_start) > 0.000001:
        return "trigger time is not the exact declared Animation phase boundary"
    if String(dep.get("trigger_semantics", "")) != "EXACT_ANIMATION_PHASE_BOUNDARY_NOT_GAMEPLAY_EVENT":
        return "trigger semantics promoted beyond visual phase binding"
    var visual := effect.get("visual_source", {}) as Dictionary
    if String(visual.get("source_label", "")) != "STYLIZED_VISUAL_RELEASE_MOTES_NOT_DUST_OR_FLUID_SIMULATION":
        return "visual source semantics drift"
    if int(visual.get("particle_count", 0)) < 1 or int(visual.get("particle_count", 0)) > 64:
        return "particle count outside bounded review envelope"
    return ""

func diff_metrics(a: Image, b: Image) -> Dictionary:
    if a.get_width() != b.get_width() or a.get_height() != b.get_height():
        return {"changed_pixels": -1}
    var changed := 0
    var minx := a.get_width()
    var miny := a.get_height()
    var maxx := -1
    var maxy := -1
    var max_delta := 0.0
    for y in range(a.get_height()):
        for x in range(a.get_width()):
            var p := a.get_pixel(x, y)
            var q := b.get_pixel(x, y)
            var delta := maxf(absf(p.r - q.r), maxf(absf(p.g - q.g), absf(p.b - q.b)))
            max_delta = maxf(max_delta, delta)
            if delta > PIXEL_THRESHOLD:
                changed += 1
                minx = mini(minx, x)
                miny = mini(miny, y)
                maxx = maxi(maxx, x)
                maxy = maxi(maxy, y)
    var bbox := []
    if changed > 0:
        bbox = [minx, miny, maxx + 1, maxy + 1]
    return {
        "changed_pixels": changed,
        "changed_fraction": float(changed) / float(a.get_width() * a.get_height()),
        "max_rgb_delta": max_delta,
        "bbox_half_open": bbox
    }

func make_particles(effect: Dictionary, seam_min: Vector3, seam_max: Vector3, root: Node3D) -> Array:
    var visual := effect["visual_source"] as Dictionary
    var seed := int(visual["seed"])
    var count := int(visual["particle_count"])
    var color_values := visual["color_srgb"] as Array
    var base_color := Color(float(color_values[0]), float(color_values[1]), float(color_values[2]), float(visual["alpha_peak"]))
    var particles := []
    for i in range(count):
        var start_x := lerpf(seam_min.x, seam_max.x, hash01(seed, i, 1))
        var start_z := lerpf(seam_min.z, seam_max.z, hash01(seed, i, 2))
        var spawn := float(effect["animation_dependency"]["trigger_time_s"]) + float(visual["emission_span_s"]) * hash01(seed, i, 3)
        var lifetime := lerpf(float(visual["lifetime_min_s"]), float(visual["lifetime_max_s"]), hash01(seed, i, 4))
        var size := lerpf(float(visual["size_min_m"]), float(visual["size_max_m"]), hash01(seed, i, 5))
        var vx := lerpf(-float(visual["lateral_speed_abs_max_mps"]), float(visual["lateral_speed_abs_max_mps"]), hash01(seed, i, 6))
        var vy := lerpf(float(visual["vertical_speed_min_mps"]), float(visual["vertical_speed_max_mps"]), hash01(seed, i, 7))
        var vz := -lerpf(float(visual["camera_forward_speed_min_mps"]), float(visual["camera_forward_speed_max_mps"]), hash01(seed, i, 8))
        var quad := QuadMesh.new()
        quad.size = Vector2(size, size)
        var material := StandardMaterial3D.new()
        material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
        material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
        material.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
        material.albedo_color = Color(base_color.r, base_color.g, base_color.b, 0.0)
        quad.material = material
        var node := MeshInstance3D.new()
        node.name = "release_mote_%02d" % i
        node.mesh = quad
        node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
        node.visible = false
        root.add_child(node)
        particles.append({
            "node": node,
            "material": material,
            "start": Vector3(start_x, seam_min.y, start_z),
            "spawn": spawn,
            "lifetime": lifetime,
            "velocity": Vector3(vx, vy, vz),
            "base_color": base_color
        })
    return particles

func set_particle_state(particles: Array, effect: Dictionary, time_s: float, enabled: bool) -> int:
    var gravity := float(effect["visual_source"]["gravity_visual_mps2"])
    var active := 0
    for particle in particles:
        var node := particle["node"] as MeshInstance3D
        var material := particle["material"] as StandardMaterial3D
        var age := time_s - float(particle["spawn"])
        var lifetime := float(particle["lifetime"])
        if not enabled or age < 0.0 or age > lifetime:
            node.visible = false
            material.albedo_color.a = 0.0
            continue
        active += 1
        var u := clampf(age / lifetime, 0.0, 1.0)
        var start := particle["start"] as Vector3
        var velocity := particle["velocity"] as Vector3
        node.position = start + velocity * age + Vector3(0.0, 0.5 * gravity * age * age, 0.0)
        var alpha := float(particle["base_color"].a) * pow(maxf(0.0, sin(PI * u)), 0.75)
        var c := particle["base_color"] as Color
        material.albedo_color = Color(c.r, c.g, c.b, alpha)
        node.visible = alpha > 0.005
    return active

func _initialize() -> void:
    var technical := read_json(TECH_RECEIPT_PATH)
    var sequence := read_json(SEQUENCE_PATH)
    var rig := read_json(RIG_RECEIPT_PATH)
    var effect := read_json(EFFECT_PATH)
    var effect_head := read_text(EFFECT_HEAD_PATH)
    var sequence_contract := read_json("res://../assets/modular-equipment-case-001/lid-latch-motion-sequence-001.json")

    if technical.get("result") != "PASS_OBJECT_SOURCE_OWNED_RIGID_PARTS_THROUGH_UC_SCENE_GRAPH":
        fail("technical-art rigid-scene donor missing or not green")
        return
    if sequence.get("result") != "PASS_ORDERED_LATCH_RELEASE_LID_CLIP_REENGAGE_SEQUENCE":
        fail("animation sequence prerequisite missing or not green")
        return
    if rig.get("result") != "PASS_BOUNDED_FRONT_LATCH_LEVER_ARTICULATION":
        fail("rigging articulation prerequisite missing or not green")
        return
    if effect_head.is_empty():
        fail("exact VFX head identity missing")
        return
    if String(effect.get("source_sha256", "")) != String(sequence.get("host_source_sha256", "")):
        fail("effect source identity does not match exact Animation source")
        return
    var contract_error := validate_effect_contract(effect, sequence_contract)
    if not contract_error.is_empty():
        fail(contract_error)
        return

    var negative := effect.duplicate(true)
    var negative_dep := negative["animation_dependency"] as Dictionary
    negative_dep["trigger_time_s"] = float(negative_dep["trigger_time_s"]) + 0.025
    negative["animation_dependency"] = negative_dep
    if validate_effect_contract(negative, sequence_contract).is_empty():
        fail("negative control failed: trigger-time drift was accepted")
        return

    if not FileAccess.file_exists(GLB_PATH):
        fail("exact rebound GLB missing")
        return
    var glb_sha := sha256_file(GLB_PATH)
    if glb_sha != String(technical.get("rebound_glb_sha256", "")):
        fail("rebound GLB identity mismatch")
        return

    var document := GLTFDocument.new()
    var state := GLTFState.new()
    var error := document.append_from_file(GLB_PATH, state)
    if error != OK:
        fail("GLTFDocument append_from_file failed: " + str(error))
        return
    var generated = document.generate_scene(state)
    if generated == null or not (generated is Node3D):
        fail("GLTFDocument generate_scene returned no Node3D")
        return
    var imported := generated as Node3D

    var lid := find_node(imported, "lid_shell")
    var keeper0 := find_node(imported, "latch_0_keeper")
    var keeper1 := find_node(imported, "latch_1_keeper")
    var lever0 := find_node(imported, "latch_0_lever")
    var lever1 := find_node(imported, "latch_1_lever")
    if lid == null or keeper0 == null or keeper1 == null or lever0 == null or lever1 == null:
        fail("required rigid component nodes were not preserved by target import")
        return
    if not (lid is MeshInstance3D):
        fail("lid shell is not a MeshInstance3D")
        return

    var viewport := make_viewport(imported)
    for _i in range(10):
        await process_frame

    var neutral_bounds := mesh_world_bounds(lid as MeshInstance3D)
    var bmin := neutral_bounds["min"] as Vector3
    var bmax := neutral_bounds["max"] as Vector3
    var seam_min := Vector3(bmin.x + 0.07, bmin.y + 0.010, bmax.z - 0.020)
    var seam_max := Vector3(bmax.x - 0.07, bmin.y + 0.010, bmax.z + 0.004)

    var root3d := imported.get_parent() as Node3D
    var effect_root := Node3D.new()
    effect_root.name = "LID_RELEASE_MOTES_VFX"
    root3d.add_child(effect_root)
    var particles := make_particles(effect, seam_min, seam_max, effect_root)

    var sample0_stations := station_lookup(sequence["samples"][0]["stations"])
    var rig_by_station := station_lookup(rig.get("station_results", []))
    var pivot_by_station := {}
    for station_id in sample0_stations.keys():
        if not rig_by_station.has(station_id):
            fail("sequence station missing exact rig row: " + String(station_id))
            return
        var component := String(sample0_stations[station_id]["lever_component"])
        var lever := find_node(imported, component)
        if lever == null:
            fail("target lever node missing: " + component)
            return
        var pivot := Node3D.new()
        pivot.name = "vfx_animation_pivot_" + String(station_id)
        pivot.position = source_to_uc(rig_by_station[station_id]["pivot_m"])
        imported.add_child(pivot)
        lever.reparent(pivot, true)
        pivot_by_station[station_id] = pivot

    var animation := Animation.new()
    animation.length = float(sequence["duration_s"])
    animation.loop_mode = Animation.LOOP_NONE
    var lid_track := add_discrete_rotation_track(animation, imported, lid, sequence["samples"], "lid_mathematical_rotation_deg", true)
    var latch_tracks := []
    for station_id in pivot_by_station.keys():
        latch_tracks.append(add_discrete_rotation_track(animation, imported, pivot_by_station[station_id], sequence["samples"], "latch_lever_angle_deg", true))
    if animation.track_get_key_count(lid_track) != int(sequence["endpoint_inclusive_sample_count"]):
        fail("lid AnimationPlayer track key count drift")
        return
    for track in latch_tracks:
        if animation.track_get_key_count(track) != int(sequence["endpoint_inclusive_sample_count"]):
            fail("latch AnimationPlayer track key count drift")
            return

    var player := AnimationPlayer.new()
    player.name = "AXM_VFX_REVIEW_PLAYER"
    imported.add_child(player)
    player.root_node = NodePath("..")
    var library := AnimationLibrary.new()
    library.add_animation(MOTION_NAME, animation)
    player.add_animation_library("", library)
    player.play(MOTION_NAME)
    player.pause()

    var verification := effect["verification"] as Dictionary
    var times := [float(verification["pre_trigger_time_s"])]
    for value in verification["active_times_s"]:
        times.append(float(value))
    times.append(float(verification["post_effect_time_s"]))

    var observations := []
    var active_changed_min := 1 << 30
    var active_changed_max := 0
    var active_fraction_max := 0.0
    var inactive_changed_max := 0
    for time_s in times:
        player.seek(time_s, true)
        player.advance(0.0)
        set_particle_state(particles, effect, time_s, false)
        for _j in range(4):
            await process_frame
        var control_lid := lid.rotation_degrees
        var control_latches := []
        for station_id in pivot_by_station.keys():
            control_latches.append((pivot_by_station[station_id] as Node3D).rotation_degrees)
        var control := viewport.get_texture().get_image()
        if control == null or control.is_empty():
            fail("empty control render at " + str(time_s))
            return
        var tag := "%04d" % int(round(time_s * 1000.0))
        var control_path := "res://vfx-control-%sms.png" % tag
        if control.save_png(control_path) != OK:
            fail("could not save control render at " + str(time_s))
            return

        var active_count := set_particle_state(particles, effect, time_s, true)
        for _k in range(4):
            await process_frame
        var candidate_lid := lid.rotation_degrees
        if control_lid.distance_to(candidate_lid) > EPS_DEG:
            fail("VFX changed lid animation state at " + str(time_s))
            return
        var latch_i := 0
        for station_id in pivot_by_station.keys():
            if (pivot_by_station[station_id] as Node3D).rotation_degrees.distance_to(control_latches[latch_i]) > EPS_DEG:
                fail("VFX changed latch animation state at " + str(time_s))
                return
            latch_i += 1
        var candidate := viewport.get_texture().get_image()
        if candidate == null or candidate.is_empty():
            fail("empty candidate render at " + str(time_s))
            return
        var candidate_path := "res://vfx-candidate-%sms.png" % tag
        if candidate.save_png(candidate_path) != OK:
            fail("could not save candidate render at " + str(time_s))
            return

        var metrics := diff_metrics(control, candidate)
        var changed := int(metrics["changed_pixels"])
        var is_active := time_s >= float(effect["animation_dependency"]["trigger_time_s"]) and active_count > 0
        if is_active:
            active_changed_min = mini(active_changed_min, changed)
            active_changed_max = maxi(active_changed_max, changed)
            active_fraction_max = maxf(active_fraction_max, float(metrics["changed_fraction"]))
            if changed < int(verification["minimum_active_changed_pixels"]):
                fail("active VFX is not materially visible at " + str(time_s))
                return
            if float(metrics["changed_fraction"]) > float(verification["maximum_active_changed_frame_fraction"]):
                fail("active VFX changed too much of the retained frame at " + str(time_s))
                return
        else:
            inactive_changed_max = maxi(inactive_changed_max, changed)
            if active_count != 0:
                fail("inactive review time still has active mote state at " + str(time_s))
                return
            if changed > int(verification["inactive_changed_pixels_max"]):
                fail("inactive candidate differs from exact control at " + str(time_s))
                return

        observations.append({
            "time_s": time_s,
            "active_particle_count": active_count,
            "control_sha256": sha256_file(control_path),
            "candidate_sha256": sha256_file(candidate_path),
            "diff": metrics,
            "lid_rotation_deg": [candidate_lid.x, candidate_lid.y, candidate_lid.z]
        })

    receipt["state"] = "PASS_TARGET_HOST_PHASE_BOUND_LID_RELEASE_MOTES"
    receipt["effect_id"] = effect.get("effect_id")
    receipt["effect_head"] = effect_head
    receipt["effect_source_label"] = effect["visual_source"].get("source_label")
    receipt["godot_version"] = Engine.get_version_info()
    receipt["glb_sha256"] = glb_sha
    receipt["technical_art_object_head"] = technical.get("source_repository_head")
    receipt["uc_commit"] = technical.get("observed_uc_commit")
    receipt["animation_sequence_head"] = sequence.get("exact_receiving_head")
    receipt["sequence_id"] = sequence.get("sequence_id")
    receipt["sequence_digest"] = sequence.get("sequence_digest")
    receipt["trigger_time_s"] = effect["animation_dependency"].get("trigger_time_s")
    receipt["trigger_phase_id"] = effect["animation_dependency"].get("trigger_phase_id")
    receipt["particle_count"] = effect["visual_source"].get("particle_count")
    receipt["neutral_lid_world_bounds"] = {
        "min": [bmin.x, bmin.y, bmin.z],
        "max": [bmax.x, bmax.y, bmax.z]
    }
    receipt["derived_emitter_seam"] = {
        "min": [seam_min.x, seam_min.y, seam_min.z],
        "max": [seam_max.x, seam_max.y, seam_max.z]
    }
    receipt["observations"] = observations
    receipt["active_changed_pixels_min"] = active_changed_min
    receipt["active_changed_pixels_max"] = active_changed_max
    receipt["active_changed_frame_fraction_max"] = active_fraction_max
    receipt["inactive_changed_pixels_max"] = inactive_changed_max
    receipt["negative_control_trigger_time_drift_rejected"] = true
    receipt["truth_boundary"] = {
        "exact_uc_rebound_glb_imported": true,
        "exact_animation_sequence_consumed": true,
        "animation_timing_or_easing_modified": false,
        "object_geometry_or_material_modified": false,
        "vfx_changes_object_animation_state": false,
        "phase_boundary_binding_observed": true,
        "analytic_visual_motes_rendered_in_real_godot": true,
        "production_particle_runtime": false,
        "physical_dust_pressure_airflow_or_fluid_simulation": false,
        "runtime_controller_or_gameplay_event": false,
        "collision_damage_or_interaction": false,
        "target_device_performance_acceptance": false,
        "art_direction_acceptance": false,
        "visual_qa_acceptance": false,
        "canon_or_production_readiness": false
    }
    write_receipt()
    print("AXM OBJECT VFX TARGET ", JSON.stringify(receipt))
    quit(0)
