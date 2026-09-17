extends SceneTree

const GLB_PATH := "res://generated/object-rigid-components-rebound.glb"
const TECH_RECEIPT_PATH := "res://generated/uc-rigid-scene-handoff-receipt.json"
const SEQUENCE_PATH := "res://generated/lid-latch-motion-evidence.json"
const RIG_RECEIPT_PATH := "res://generated/front-latch-articulation.receipt.json"
const EFFECT_PATH := "res://generated/lid-open-release-motes-001.json"
const OWNER_HEAD_PATH := "res://generated/exact-vfx-head.txt"
const PRESENTATION_HEAD_PATH := "res://generated/exact-presentation-head.txt"
const RECEIPT_PATH := "res://vfx-lid-release-motes-wallclock-receipt.json"
const TRACE_PATH := "res://vfx-lid-release-motes-wallclock-trace.json"
const MOTION_NAME := "lid_latch_open_hold_close_vfx_wallclock_review"
const OWNER_HEAD := "7994d6f28050053f07dd355d8c54a983b0e8268b"
const OWNER_SEED := 41027
const PIXEL_THRESHOLD := 1.0 / 255.0
const EPS_DEG := 0.00001

class VfxFrameDriver:
    extends Node
    var player: AnimationPlayer
    var particles: Array = []
    var effect: Dictionary = {}
    var update_callable: Callable
    var active_count: int = 0

    func _process(_delta: float) -> void:
        if player == null or not update_callable.is_valid():
            active_count = 0
            return
        active_count = int(update_callable.call(particles, effect, player.current_animation_position, true))

var receipt := {
    "schema": "axm.object-reactive-vfx-wallclock-presentation/v0.1",
    "state": "NOT_RUN",
    "promotion_effect": "NONE",
    "renderer_boundary": "Godot 4.7.2 GL Compatibility / X11 / llvmpipe proof receiver. Timing trace uses real AnimationPlayer.play() with no viewport image readback or disk writes inside the timed loop. Review-frame capture is a separate instrumented playback and is not timing authority."
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
    var ctx := HashingContext.new()
    ctx.start(HashingContext.HASH_SHA256)
    ctx.update(FileAccess.get_file_as_bytes(path))
    return ctx.finish().hex_encode()

func write_json(path: String, value: Variant) -> void:
    var file := FileAccess.open(path, FileAccess.WRITE)
    if file != null:
        file.store_string(JSON.stringify(value, "  ") + "\n")
        file.close()

func fail(message: String) -> void:
    receipt["state"] = "FAIL_TARGET_HOST_OWNER_SEED_WALLCLOCK_PRESENTATION"
    receipt["failure"] = message
    write_json(RECEIPT_PATH, receipt)
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
        return Vector3.ZERO
    return Vector3(float(values[0]), float(values[2]), float(values[1]))

func station_lookup(rows: Array) -> Dictionary:
    var out := {}
    for row in rows:
        out[String(row["station_id"])] = row
    return out

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

func make_particles(effect: Dictionary, seam_min: Vector3, seam_max: Vector3, root: Node3D) -> Array:
    var visual := effect["visual_source"] as Dictionary
    var seed := int(visual["seed"])
    var count := int(visual["particle_count"])
    var rgb := visual["color_srgb"] as Array
    var base_color := Color(float(rgb[0]), float(rgb[1]), float(rgb[2]), float(visual["alpha_peak"]))
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
        node.name = "wallclock_release_mote_%02d" % i
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
        var node: MeshInstance3D = particle["node"]
        var material: StandardMaterial3D = particle["material"]
        var age := time_s - float(particle["spawn"])
        var lifetime := float(particle["lifetime"])
        if not enabled or age < 0.0 or age > lifetime:
            node.visible = false
            material.albedo_color.a = 0.0
            continue
        active += 1
        var u := clampf(age / lifetime, 0.0, 1.0)
        var start: Vector3 = particle["start"]
        var velocity: Vector3 = particle["velocity"]
        node.position = start + velocity * age + Vector3(0.0, 0.5 * gravity * age * age, 0.0)
        var c: Color = particle["base_color"]
        var alpha := c.a * pow(maxf(0.0, sin(PI * u)), 0.75)
        material.albedo_color = Color(c.r, c.g, c.b, alpha)
        node.visible = alpha > 0.005
    return active

func add_discrete_rotation_track(animation: Animation, root: Node3D, node: Node3D, samples: Array, value_key: String) -> int:
    var track := animation.add_track(Animation.TYPE_VALUE)
    animation.track_set_path(track, NodePath(str(root.get_path_to(node)) + ":rotation_degrees"))
    animation.track_set_interpolation_type(track, Animation.INTERPOLATION_NEAREST)
    animation.value_track_set_update_mode(track, Animation.UPDATE_DISCRETE)
    for sample in samples:
        animation.track_insert_key(track, float(sample["time_s"]), Vector3(-float(sample[value_key]), 0.0, 0.0))
    return track

func diff_metrics(a: Image, b: Image) -> Dictionary:
    if a.get_width() != b.get_width() or a.get_height() != b.get_height():
        return {"changed_pixels": -1, "max_rgb_delta": -1.0}
    var changed := 0
    var max_delta := 0.0
    for y in range(a.get_height()):
        for x in range(a.get_width()):
            var p := a.get_pixel(x, y)
            var q := b.get_pixel(x, y)
            var delta := maxf(absf(p.r - q.r), maxf(absf(p.g - q.g), absf(p.b - q.b)))
            max_delta = maxf(max_delta, delta)
            if delta > PIXEL_THRESHOLD:
                changed += 1
    return {
        "changed_pixels": changed,
        "changed_fraction": float(changed) / float(a.get_width() * a.get_height()),
        "max_rgb_delta": max_delta
    }

func set_camera_context(camera: Camera3D, context_id: String) -> Dictionary:
    if context_id == "continuity_three_quarter":
        camera.fov = 40.0
        camera.look_at_from_position(Vector3(1.22, 0.82, -1.38), Vector3(0.0, 0.21, 0.0), Vector3.UP)
        return {"id": context_id, "position": [1.22, 0.82, -1.38], "look_at": [0.0, 0.21, 0.0], "fov_deg": 40.0}
    if context_id == "left_oblique_seam":
        camera.fov = 42.0
        camera.look_at_from_position(Vector3(-1.10, 0.72, -1.24), Vector3(0.0, 0.23, -0.04), Vector3.UP)
        return {"id": context_id, "position": [-1.10, 0.72, -1.24], "look_at": [0.0, 0.23, -0.04], "fov_deg": 42.0}
    return {}

func make_viewport(imported: Node3D) -> Dictionary:
    var viewport := SubViewport.new()
    viewport.size = Vector2i(820, 620)
    viewport.own_world_3d = true
    viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
    viewport.render_target_clear_mode = SubViewport.CLEAR_MODE_ALWAYS
    get_root().add_child(viewport)
    var root3d := Node3D.new()
    root3d.name = "VFX_WALLCLOCK_REVIEW_WORLD"
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
    camera.near = 0.03
    camera.far = 20.0
    root3d.add_child(camera)
    set_camera_context(camera, "continuity_three_quarter")
    camera.make_current()
    return {"viewport": viewport, "root3d": root3d, "camera": camera}

func run_timing_trace(player: AnimationPlayer, driver: VfxFrameDriver, duration_s: float) -> Dictionary:
    set_particle_state(driver.particles, driver.effect, 0.0, false)
    driver.set_process(true)
    player.stop()
    player.play(MOTION_NAME)
    var start_usec := Time.get_ticks_usec()
    var rows := []
    var last_position := -1.0
    var nonmonotonic_positions := 0
    var pre_inactive_seen := false
    var active_seen := false
    var post_inactive_seen := false
    while player.is_playing():
        await RenderingServer.frame_post_draw
        var now_usec := Time.get_ticks_usec()
        var wall_s := float(now_usec - start_usec) / 1000000.0
        var position_s := float(player.current_animation_position)
        if last_position >= 0.0 and position_s + 0.000001 < last_position:
            nonmonotonic_positions += 1
        last_position = position_s
        var active_count := int(driver.active_count)
        if position_s < 0.24 and active_count == 0:
            pre_inactive_seen = true
        if position_s >= 0.25 and position_s <= 0.79 and active_count > 0:
            active_seen = true
        if position_s >= 0.80 and active_count == 0:
            post_inactive_seen = true
        rows.append({
            "wall_elapsed_s": wall_s,
            "animation_position_s": position_s,
            "active_particle_count": active_count
        })
        if wall_s > duration_s + 1.5:
            fail("wall-clock playback exceeded bounded safety window")
            return {}
    var end_usec := Time.get_ticks_usec()
    var elapsed_s := float(end_usec - start_usec) / 1000000.0
    return {
        "mode": "REAL_ANIMATIONPLAYER_PLAY_CAPTURE_FREE_TIMING_TRACE",
        "viewport_image_readbacks_inside_timed_loop": 0,
        "disk_writes_inside_timed_loop": 0,
        "animation_duration_s": duration_s,
        "wall_elapsed_s": elapsed_s,
        "sample_count": rows.size(),
        "nonmonotonic_position_count": nonmonotonic_positions,
        "pre_trigger_inactive_seen": pre_inactive_seen,
        "active_window_seen": active_seen,
        "post_effect_inactive_seen": post_inactive_seen,
        "rows": rows
    }

func run_capture_pass(viewport: SubViewport, camera: Camera3D, player: AnimationPlayer, driver: VfxFrameDriver, context_id: String) -> Dictionary:
    var camera_contract := set_camera_context(camera, context_id)
    if camera_contract.is_empty():
        fail("unknown review camera context: " + context_id)
        return {}
    set_particle_state(driver.particles, driver.effect, 0.0, false)
    driver.set_process(true)
    player.stop()
    player.play(MOTION_NAME)
    var frames := []
    var frame_index := 0
    var active_frames := 0
    var pre_frames := 0
    var post_frames := 0
    while player.is_playing():
        await RenderingServer.frame_post_draw
        var position_s := float(player.current_animation_position)
        var active_count := int(driver.active_count)
        if position_s >= 0.12 and position_s <= 0.92 and frame_index < 40:
            var image := viewport.get_texture().get_image()
            if image == null or image.is_empty():
                fail("empty presentation frame for " + context_id)
                return {}
            var tag := "%02d-%04dms" % [frame_index, int(round(position_s * 1000.0))]
            var path := "res://wallclock-%s-%s.png" % [context_id, tag]
            if image.save_png(path) != OK:
                fail("could not save presentation frame for " + context_id)
                return {}
            frames.append({
                "index": frame_index,
                "animation_position_s": position_s,
                "active_particle_count": active_count,
                "sha256": sha256_file(path),
                "path": path.trim_prefix("res://")
            })
            frame_index += 1
            if position_s < 0.25:
                pre_frames += 1
            elif position_s <= 0.79 and active_count > 0:
                active_frames += 1
            elif position_s >= 0.80:
                post_frames += 1
        if position_s > 0.94:
            player.stop()
            break
    return {
        "context": camera_contract,
        "mode": "INSTRUMENTED_REAL_PLAYBACK_VISUAL_CAPTURE_NOT_TIMING_AUTHORITY",
        "frame_count": frames.size(),
        "pre_trigger_frame_count": pre_frames,
        "active_frame_count": active_frames,
        "post_effect_frame_count": post_frames,
        "frames": frames
    }

func static_ab(viewport: SubViewport, camera: Camera3D, player: AnimationPlayer, driver: VfxFrameDriver, context_id: String, time_s: float) -> Dictionary:
    set_camera_context(camera, context_id)
    driver.set_process(false)
    player.stop()
    player.play(MOTION_NAME)
    player.pause()
    player.seek(time_s, true)
    player.advance(0.0)
    set_particle_state(driver.particles, driver.effect, time_s, false)
    for _i in range(3):
        await process_frame
    var control_lid := find_node(player.get_parent(), "lid_shell").rotation_degrees
    var control := viewport.get_texture().get_image()
    if control == null or control.is_empty():
        fail("empty static control")
        return {}
    var control_path := "res://static-%s-%04dms-control.png" % [context_id, int(round(time_s * 1000.0))]
    if control.save_png(control_path) != OK:
        fail("could not save static control")
        return {}
    var active_count := set_particle_state(driver.particles, driver.effect, time_s, true)
    for _j in range(3):
        await process_frame
    var candidate_lid := find_node(player.get_parent(), "lid_shell").rotation_degrees
    if control_lid.distance_to(candidate_lid) > EPS_DEG:
        fail("VFX changed lid state during static A/B")
        return {}
    var candidate := viewport.get_texture().get_image()
    if candidate == null or candidate.is_empty():
        fail("empty static candidate")
        return {}
    var candidate_path := "res://static-%s-%04dms-candidate.png" % [context_id, int(round(time_s * 1000.0))]
    if candidate.save_png(candidate_path) != OK:
        fail("could not save static candidate")
        return {}
    return {
        "context_id": context_id,
        "time_s": time_s,
        "active_particle_count": active_count,
        "control_sha256": sha256_file(control_path),
        "candidate_sha256": sha256_file(candidate_path),
        "diff": diff_metrics(control, candidate)
    }

func _initialize() -> void:
    var technical := read_json(TECH_RECEIPT_PATH)
    var sequence := read_json(SEQUENCE_PATH)
    var rig := read_json(RIG_RECEIPT_PATH)
    var effect := read_json(EFFECT_PATH)
    var owner_head := read_text(OWNER_HEAD_PATH)
    var presentation_head := read_text(PRESENTATION_HEAD_PATH)
    if technical.get("result") != "PASS_OBJECT_SOURCE_OWNED_RIGID_PARTS_THROUGH_UC_SCENE_GRAPH":
        fail("exact Technical Art donor receipt missing")
        return
    if sequence.get("result") != "PASS_ORDERED_LATCH_RELEASE_LID_CLIP_REENGAGE_SEQUENCE":
        fail("exact Animation sequence receipt missing")
        return
    if rig.get("result") != "PASS_BOUNDED_FRONT_LATCH_LEVER_ARTICULATION":
        fail("exact Rigging receipt missing")
        return
    if owner_head != OWNER_HEAD:
        fail("owner VFX head drift")
        return
    if presentation_head.is_empty():
        fail("presentation head identity missing")
        return
    if int(effect.get("visual_source", {}).get("seed", -1)) != OWNER_SEED:
        fail("owner seed drift")
        return
    if int(effect.get("visual_source", {}).get("particle_count", 0)) != 18:
        fail("owner particle count drift")
        return
    if float(effect.get("animation_dependency", {}).get("trigger_time_s", -1.0)) != 0.25:
        fail("owner trigger-time drift")
        return
    if String(effect.get("animation_dependency", {}).get("trigger_semantics", "")) != "EXACT_ANIMATION_PHASE_BOUNDARY_NOT_GAMEPLAY_EVENT":
        fail("effect semantics promoted beyond Animation phase binding")
        return
    if String(effect.get("visual_source", {}).get("source_label", "")) != "STYLIZED_VISUAL_RELEASE_MOTES_NOT_DUST_OR_FLUID_SIMULATION":
        fail("effect source semantics drift")
        return
    if not FileAccess.file_exists(GLB_PATH):
        fail("exact owner rebound GLB missing")
        return
    var glb_sha := sha256_file(GLB_PATH)
    if glb_sha != String(technical.get("rebound_glb_sha256", "")):
        fail("owner rebound GLB identity mismatch")
        return

    var document := GLTFDocument.new()
    var state := GLTFState.new()
    var error := document.append_from_file(GLB_PATH, state)
    if error != OK:
        fail("GLTFDocument append failed: " + str(error))
        return
    var generated = document.generate_scene(state)
    if generated == null or not (generated is Node3D):
        fail("GLTFDocument generate_scene returned no Node3D")
        return
    var imported := generated as Node3D
    var lid := find_node(imported, "lid_shell")
    if lid == null or not (lid is MeshInstance3D):
        fail("required lid_shell missing")
        return

    var view := make_viewport(imported)
    var viewport: SubViewport = view["viewport"]
    var root3d: Node3D = view["root3d"]
    var camera: Camera3D = view["camera"]
    for _warmup in range(8):
        await process_frame

    var bounds := mesh_world_bounds(lid as MeshInstance3D)
    var bmin: Vector3 = bounds["min"]
    var bmax: Vector3 = bounds["max"]
    var seam_min := Vector3(bmin.x + 0.07, bmin.y + 0.012, bmin.z - 0.008)
    var seam_max := Vector3(bmax.x - 0.07, bmin.y + 0.012, bmin.z + 0.018)
    var effect_root := Node3D.new()
    effect_root.name = "LID_RELEASE_MOTES_VFX_WALLCLOCK"
    root3d.add_child(effect_root)
    var particles := make_particles(effect, seam_min, seam_max, effect_root)

    var sample0_stations := station_lookup(sequence["samples"][0]["stations"])
    var rig_by_station := station_lookup(rig.get("station_results", []))
    var pivot_by_station := {}
    for station_id in sample0_stations.keys():
        if not rig_by_station.has(station_id):
            fail("sequence station missing exact rig row")
            return
        var component := String(sample0_stations[station_id]["lever_component"])
        var lever := find_node(imported, component)
        if lever == null:
            fail("target lever node missing: " + component)
            return
        var pivot := Node3D.new()
        pivot.name = "vfx_wallclock_pivot_" + String(station_id)
        pivot.position = source_to_uc(rig_by_station[station_id]["pivot_m"])
        imported.add_child(pivot)
        lever.reparent(pivot, true)
        pivot_by_station[station_id] = pivot

    var animation := Animation.new()
    animation.length = float(sequence["duration_s"])
    animation.loop_mode = Animation.LOOP_NONE
    var lid_track := add_discrete_rotation_track(animation, imported, lid, sequence["samples"], "lid_mathematical_rotation_deg")
    var latch_tracks := []
    for station_id in pivot_by_station.keys():
        latch_tracks.append(add_discrete_rotation_track(animation, imported, pivot_by_station[station_id], sequence["samples"], "latch_lever_angle_deg"))
    if animation.track_get_key_count(lid_track) != int(sequence["endpoint_inclusive_sample_count"]):
        fail("lid AnimationPlayer key count drift")
        return
    for track in latch_tracks:
        if animation.track_get_key_count(track) != int(sequence["endpoint_inclusive_sample_count"]):
            fail("latch AnimationPlayer key count drift")
            return

    var player := AnimationPlayer.new()
    player.name = "AXM_VFX_WALLCLOCK_PLAYER"
    imported.add_child(player)
    player.root_node = NodePath("..")
    var library := AnimationLibrary.new()
    library.add_animation(MOTION_NAME, animation)
    player.add_animation_library("", library)

    var driver := VfxFrameDriver.new()
    driver.name = "AXM_VFX_FRAME_DRIVER"
    driver.player = player
    driver.particles = particles
    driver.effect = effect
    driver.update_callable = Callable(self, "set_particle_state")
    driver.process_priority = 100
    imported.add_child(driver)

    var timing_trace := await run_timing_trace(player, driver, float(sequence["duration_s"]))
    if timing_trace.is_empty():
        return
    if int(timing_trace["sample_count"]) < 10:
        fail("wall-clock trace too sparse")
        return
    if int(timing_trace["nonmonotonic_position_count"]) != 0:
        fail("wall-clock AnimationPlayer position regressed")
        return
    if not bool(timing_trace["pre_trigger_inactive_seen"]) or not bool(timing_trace["active_window_seen"]) or not bool(timing_trace["post_effect_inactive_seen"]):
        fail("wall-clock trace did not observe pre/active/post effect states")
        return
    write_json(TRACE_PATH, timing_trace)

    var capture_contexts := []
    for context_id in ["continuity_three_quarter", "left_oblique_seam"]:
        var capture := await run_capture_pass(viewport, camera, player, driver, context_id)
        if capture.is_empty():
            return
        if int(capture["frame_count"]) < 5 or int(capture["active_frame_count"]) < 2:
            fail("presentation capture too sparse in " + context_id)
            return
        capture_contexts.append(capture)

    var static_checks := []
    for context_id in ["continuity_three_quarter", "left_oblique_seam"]:
        for time_s in [0.20, 0.40, 0.80]:
            var check := await static_ab(viewport, camera, player, driver, context_id, time_s)
            if check.is_empty():
                return
            var changed := int(check["diff"]["changed_pixels"])
            if time_s == 0.40:
                if int(check["active_particle_count"]) <= 0 or changed < 80:
                    fail("effect is not visibly observed in required context at 0.40 s: " + context_id)
                    return
            else:
                if int(check["active_particle_count"]) != 0 or changed != 0:
                    fail("pre/post effect closure failed in context: " + context_id)
                    return
            static_checks.append(check)

    receipt["state"] = "PASS_TARGET_HOST_OWNER_SEED_WALLCLOCK_TWO_CONTEXT_PRESENTATION"
    receipt["decision"] = "PASS_OWNER_41027_REAL_PLAYBACK_PRESENTATION_SURFACE__HOLD_FINAL_ART_QA_AND_TARGET_DEVICE"
    receipt["presentation_head"] = presentation_head
    receipt["owner_vfx_head"] = owner_head
    receipt["owner_seed"] = OWNER_SEED
    receipt["effect_sha256"] = sha256_file(EFFECT_PATH)
    receipt["glb_sha256"] = glb_sha
    receipt["godot_version"] = Engine.get_version_info()
    receipt["sequence_id"] = sequence.get("sequence_id")
    receipt["sequence_digest"] = sequence.get("sequence_digest")
    receipt["animation_duration_s"] = sequence.get("duration_s")
    receipt["sample_rate_hz"] = sequence.get("sample_rate_hz")
    receipt["trigger_time_s"] = effect["animation_dependency"].get("trigger_time_s")
    receipt["effect_source_label"] = effect["visual_source"].get("source_label")
    receipt["derived_emitter_seam"] = {
        "min": [seam_min.x, seam_min.y, seam_min.z],
        "max": [seam_max.x, seam_max.y, seam_max.z]
    }
    receipt["timing_trace_summary"] = {
        "mode": timing_trace["mode"],
        "viewport_image_readbacks_inside_timed_loop": timing_trace["viewport_image_readbacks_inside_timed_loop"],
        "disk_writes_inside_timed_loop": timing_trace["disk_writes_inside_timed_loop"],
        "wall_elapsed_s": timing_trace["wall_elapsed_s"],
        "sample_count": timing_trace["sample_count"],
        "pre_trigger_inactive_seen": timing_trace["pre_trigger_inactive_seen"],
        "active_window_seen": timing_trace["active_window_seen"],
        "post_effect_inactive_seen": timing_trace["post_effect_inactive_seen"]
    }
    receipt["capture_contexts"] = capture_contexts
    receipt["static_context_checks"] = static_checks
    receipt["truth_boundary"] = {
        "real_animationplayer_play_path_exercised": true,
        "timed_trace_has_viewport_readback_or_disk_write": false,
        "two_fixed_seam_observing_contexts_rendered": true,
        "pre_and_post_effect_pixel_closure_in_both_contexts": true,
        "owner_effect_parameters_modified": false,
        "owner_seed_changed": false,
        "animation_timing_or_easing_modified": false,
        "gameplay_event_semantics_claimed": false,
        "physical_dust_pressure_airflow_or_fluid_simulation": false,
        "collision_damage_or_interaction": false,
        "production_particle_runtime": false,
        "target_device_performance_acceptance": false,
        "art_direction_final_acceptance": false,
        "visual_qa_final_acceptance": false,
        "canon_or_production_readiness": false
    }
    write_json(RECEIPT_PATH, receipt)
    print("AXM OBJECT VFX WALLCLOCK ", JSON.stringify(receipt))
    quit(0)
