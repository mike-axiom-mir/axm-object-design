extends SceneTree

const GLB_PATH: String = "res://generated/object-rigid-components-rebound.glb"
const TECH_RECEIPT_PATH: String = "res://generated/uc-rigid-scene-handoff-receipt.json"
const SEQUENCE_PATH: String = "res://generated/lid-latch-motion-evidence.json"
const RIG_RECEIPT_PATH: String = "res://generated/front-latch-articulation.receipt.json"
const TARGET_RECEIPT_PATH: String = "res://animationplayer-interpolation-v3-receipt.json"
const MOTION_NAME: String = "lid_latch_open_hold_close_linear_review_v3"
const EPS_DEG: float = 0.0001
const EPS_M: float = 0.000001
const LID_ANALYTIC_ERROR_LIMIT_DEG: float = 0.09
const LATCH_ANALYTIC_ERROR_LIMIT_DEG: float = 0.35

var receipt: Dictionary = {
    "schema": "axm.object-animationplayer-interpolation-proof/v0.3",
    "state": "NOT_RUN",
    "promotion_effect": "NONE",
    "renderer_boundary": "Godot 4.7.2 GL Compatibility; exact UC rigid-scene import plus AnimationPlayer LINEAR continuous interpolation observed at every midpoint between the 101 authored 40 Hz samples. No wall-clock pacing, controller/state-machine, physics, gameplay or final-motion acceptance."
}

func read_json(path: String) -> Dictionary:
    if not FileAccess.file_exists(path):
        return {}
    var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
    return parsed as Dictionary if parsed is Dictionary else {}

func sha256_file(path: String) -> String:
    var bytes: PackedByteArray = FileAccess.get_file_as_bytes(path)
    var ctx: HashingContext = HashingContext.new()
    ctx.start(HashingContext.HASH_SHA256)
    ctx.update(bytes)
    return ctx.finish().hex_encode()

func write_receipt() -> void:
    var file: FileAccess = FileAccess.open(TARGET_RECEIPT_PATH, FileAccess.WRITE)
    if file != null:
        file.store_string(JSON.stringify(receipt, "  ") + "\n")
        file.close()

func fail(message: String) -> void:
    receipt["state"] = "FAIL_TARGET_HOST_LINEAR_INTERPOLATION_PROOF"
    receipt["failure"] = message
    write_receipt()
    push_error(message)
    quit(1)

func find_node(root: Node, wanted: String) -> Node3D:
    if String(root.name) == wanted and root is Node3D:
        return root as Node3D
    for child: Node in root.get_children():
        var found: Node3D = find_node(child, wanted)
        if found != null:
            return found
    return null

func world_mesh_center(node: Node3D) -> Vector3:
    if not (node is MeshInstance3D):
        fail("expected MeshInstance3D for " + String(node.name))
        return Vector3.ZERO
    var instance: MeshInstance3D = node as MeshInstance3D
    if instance.mesh == null:
        fail("mesh missing for " + String(node.name))
        return Vector3.ZERO
    return instance.global_transform * instance.mesh.get_aabb().get_center()

func source_to_uc(values: Array) -> Vector3:
    if values.size() != 3:
        fail("source pivot is not vec3")
        return Vector3.ZERO
    return Vector3(float(values[0]), float(values[2]), float(values[1]))

func station_lookup(rows: Array) -> Dictionary:
    var out: Dictionary = {}
    for row_value: Variant in rows:
        var row: Dictionary = row_value as Dictionary
        out[String(row["station_id"])] = row
    return out

func visible_pixels(image: Image) -> int:
    var bg: Color = Color(0.025, 0.030, 0.036, 1.0)
    var changed: int = 0
    for y: int in range(image.get_height()):
        for x: int in range(image.get_width()):
            var p: Color = image.get_pixel(x, y)
            var delta: float = maxf(absf(p.r-bg.r), maxf(absf(p.g-bg.g), absf(p.b-bg.b)))
            if delta > 0.035:
                changed += 1
    return changed

func make_viewport(imported: Node3D) -> SubViewport:
    var viewport: SubViewport = SubViewport.new()
    viewport.size = Vector2i(820, 620)
    viewport.own_world_3d = true
    viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
    viewport.render_target_clear_mode = SubViewport.CLEAR_MODE_ALWAYS
    get_root().add_child(viewport)
    var root3d: Node3D = Node3D.new()
    viewport.add_child(root3d)
    var env: Environment = Environment.new()
    env.background_mode = Environment.BG_COLOR
    env.background_color = Color(0.025, 0.030, 0.036, 1.0)
    env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
    env.ambient_light_color = Color(0.60, 0.64, 0.70, 1.0)
    env.ambient_light_energy = 0.75
    var world: WorldEnvironment = WorldEnvironment.new()
    world.environment = env
    root3d.add_child(world)
    var key: DirectionalLight3D = DirectionalLight3D.new()
    key.light_energy = 2.0
    key.rotation_degrees = Vector3(-48.0, -32.0, 0.0)
    root3d.add_child(key)
    var fill: OmniLight3D = OmniLight3D.new()
    fill.light_energy = 2.1
    fill.omni_range = 4.0
    fill.position = Vector3(-1.0, 1.1, -0.8)
    root3d.add_child(fill)
    root3d.add_child(imported)
    var camera: Camera3D = Camera3D.new()
    camera.near = 0.03
    camera.far = 20.0
    camera.fov = 40.0
    root3d.add_child(camera)
    camera.look_at_from_position(Vector3(1.22, 0.82, -1.38), Vector3(0.0, 0.21, 0.0), Vector3.UP)
    camera.make_current()
    return viewport

func add_linear_rotation_track(animation: Animation, root: Node3D, node: Node3D, samples: Array, value_key: String) -> int:
    var track: int = animation.add_track(Animation.TYPE_VALUE)
    animation.track_set_path(track, NodePath(str(root.get_path_to(node)) + ":rotation_degrees"))
    animation.track_set_interpolation_type(track, Animation.INTERPOLATION_LINEAR)
    animation.value_track_set_update_mode(track, Animation.UPDATE_CONTINUOUS)
    for sample_value: Variant in samples:
        var sample: Dictionary = sample_value as Dictionary
        var target_deg: float = -float(sample[value_key])
        animation.track_insert_key(track, float(sample["time_s"]), Vector3(target_deg, 0.0, 0.0))
    return track

func smoothstep01(u: float) -> float:
    var x: float = clampf(u, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)

func analytic_latch_target_deg(t: float) -> float:
    if t <= 0.25:
        return -50.0 * smoothstep01(t / 0.25)
    if t <= 2.25:
        return -50.0
    return -50.0 * (1.0 - smoothstep01((t - 2.25) / 0.25))

func analytic_lid_target_deg(t: float) -> float:
    if t <= 0.25:
        return 0.0
    var local: float = t - 0.25
    if local <= 0.75:
        return 100.0 * smoothstep01(local / 0.75)
    if local <= 1.25:
        return 100.0
    if local <= 2.0:
        return 100.0 * (1.0 - smoothstep01((local - 1.25) / 0.75))
    return 0.0

func _initialize() -> void:
    var technical: Dictionary = read_json(TECH_RECEIPT_PATH)
    var sequence: Dictionary = read_json(SEQUENCE_PATH)
    var rig: Dictionary = read_json(RIG_RECEIPT_PATH)
    if technical.get("result") != "PASS_OBJECT_SOURCE_OWNED_RIGID_PARTS_THROUGH_UC_SCENE_GRAPH":
        fail("technical-art rigid-scene donor missing or not green")
        return
    if sequence.get("result") != "PASS_ORDERED_LATCH_RELEASE_LID_CLIP_REENGAGE_SEQUENCE":
        fail("animation sequence prerequisite missing or not green")
        return
    if rig.get("result") != "PASS_BOUNDED_FRONT_LATCH_LEVER_ARTICULATION":
        fail("rigging articulation prerequisite missing or not green")
        return
    if not FileAccess.file_exists(GLB_PATH):
        fail("exact rebound GLB missing")
        return
    var glb_sha: String = sha256_file(GLB_PATH)
    if glb_sha != String(technical.get("rebound_glb_sha256", "")):
        fail("rebound GLB identity mismatch")
        return
    if int(sequence.get("endpoint_inclusive_sample_count", 0)) != 101 or int(sequence.get("sample_rate_hz", 0)) != 40 or absf(float(sequence.get("duration_s", -1.0)) - 2.5) > 0.000001:
        fail("unexpected authored sequence grid")
        return

    var document: GLTFDocument = GLTFDocument.new()
    var gltf_state: GLTFState = GLTFState.new()
    var error: Error = document.append_from_file(GLB_PATH, gltf_state)
    if error != OK:
        fail("GLTFDocument append_from_file failed: " + str(error))
        return
    var generated: Node = document.generate_scene(gltf_state)
    if generated == null or not (generated is Node3D):
        fail("GLTFDocument generate_scene returned no Node3D")
        return
    var imported: Node3D = generated as Node3D
    var lid: Node3D = find_node(imported, "lid_shell")
    var keeper0: Node3D = find_node(imported, "latch_0_keeper")
    var keeper1: Node3D = find_node(imported, "latch_1_keeper")
    var lever0: Node3D = find_node(imported, "latch_0_lever")
    var lever1: Node3D = find_node(imported, "latch_1_lever")
    if lid == null or keeper0 == null or keeper1 == null or lever0 == null or lever1 == null:
        fail("required rigid component nodes were not preserved by target import")
        return
    if keeper0.get_parent() != lid or keeper1.get_parent() != lid:
        fail("source-owned keepers are not direct lid children")
        return

    var viewport: SubViewport = make_viewport(imported)
    for _i: int in range(10):
        await process_frame

    var neutral0: Vector3 = world_mesh_center(lever0)
    var neutral1: Vector3 = world_mesh_center(lever1)
    var rig_rows: Array = rig.get("station_results", []) as Array
    var samples: Array = sequence.get("samples", []) as Array
    var first_sample: Dictionary = samples[0] as Dictionary
    var rig_by_station: Dictionary = station_lookup(rig_rows)
    var sample0_stations: Dictionary = station_lookup(first_sample.get("stations", []) as Array)
    if rig_by_station.size() != 2 or sample0_stations.size() != 2:
        fail("expected exactly two bilateral latch stations")
        return

    var pivot_by_station: Dictionary = {}
    for station_key: Variant in sample0_stations.keys():
        var station_id: String = String(station_key)
        if not rig_by_station.has(station_id):
            fail("sequence station missing exact rig row: " + station_id)
            return
        var station_sample: Dictionary = sample0_stations[station_id] as Dictionary
        var rig_row: Dictionary = rig_by_station[station_id] as Dictionary
        var component: String = String(station_sample["lever_component"])
        var lever: Node3D = find_node(imported, component)
        if lever == null:
            fail("target lever node missing: " + component)
            return
        var pivot: Node3D = Node3D.new()
        pivot.name = "animation_interp_v3_pivot_" + station_id
        pivot.position = source_to_uc(rig_row["pivot_m"] as Array)
        imported.add_child(pivot)
        lever.reparent(pivot, true)
        pivot_by_station[station_id] = pivot

    for _i: int in range(3):
        await process_frame
    var neutral_wrapper_drift: float = maxf(neutral0.distance_to(world_mesh_center(lever0)), neutral1.distance_to(world_mesh_center(lever1)))
    if neutral_wrapper_drift > EPS_M:
        fail("proof-local latch pivot insertion changed neutral target geometry")
        return

    var animation: Animation = Animation.new()
    animation.length = 2.5
    animation.loop_mode = Animation.LOOP_NONE
    var lid_track: int = add_linear_rotation_track(animation, imported, lid, samples, "lid_mathematical_rotation_deg")
    var latch_tracks: Array[int] = []
    for station_key: Variant in pivot_by_station.keys():
        var pivot: Node3D = pivot_by_station[String(station_key)] as Node3D
        latch_tracks.append(add_linear_rotation_track(animation, imported, pivot, samples, "latch_lever_angle_deg"))
    if animation.track_get_key_count(lid_track) != 101:
        fail("lid linear track did not receive all 101 authored samples")
        return
    for track: int in latch_tracks:
        if animation.track_get_key_count(track) != 101:
            fail("latch linear track did not receive all 101 authored samples")
            return

    var player: AnimationPlayer = AnimationPlayer.new()
    player.name = "AXM_LINEAR_INTERPOLATION_REVIEW_PLAYER_V3"
    imported.add_child(player)
    player.root_node = NodePath("..")
    var library: AnimationLibrary = AnimationLibrary.new()
    library.add_animation(MOTION_NAME, animation)
    player.add_animation_library("", library)
    player.play(MOTION_NAME)
    player.pause()

    var max_lid_linear_residual: float = 0.0
    var max_latch_linear_residual: float = 0.0
    var max_lid_analytic_error: float = 0.0
    var max_latch_analytic_error: float = 0.0
    var worst_lid_interval: int = -1
    var worst_latch_interval: int = -1
    var worst_lid_analytic_interval: int = -1
    var worst_latch_analytic_interval: int = -1
    var ordering_violation_count: int = 0
    var overshoot_violation_count: int = 0
    var captures: Dictionary = {}
    var capture_intervals: Dictionary = {4: true, 20: true, 49: true, 70: true, 95: true}

    for i: int in range(samples.size() - 1):
        var a: Dictionary = samples[i] as Dictionary
        var b: Dictionary = samples[i + 1] as Dictionary
        var t: float = (float(a["time_s"]) + float(b["time_s"])) * 0.5
        player.seek(t, true)
        player.advance(0.0)
        for _j: int in range(2):
            await process_frame

        var expected_lid_linear: float = -0.5 * (float(a["lid_mathematical_rotation_deg"]) + float(b["lid_mathematical_rotation_deg"]))
        var expected_latch_linear: float = -0.5 * (float(a["latch_lever_angle_deg"]) + float(b["latch_lever_angle_deg"]))
        var observed_lid: float = float(lid.rotation_degrees.x)
        var lid_linear_residual: float = absf(observed_lid - expected_lid_linear)
        if lid_linear_residual > max_lid_linear_residual:
            max_lid_linear_residual = lid_linear_residual
            worst_lid_interval = i
        var lid_analytic_error: float = absf(observed_lid - analytic_lid_target_deg(t))
        if lid_analytic_error > max_lid_analytic_error:
            max_lid_analytic_error = lid_analytic_error
            worst_lid_analytic_interval = i

        if observed_lid < -EPS_DEG or observed_lid > 100.0 + EPS_DEG:
            overshoot_violation_count += 1
        if t < 0.25 and absf(observed_lid) > EPS_DEG:
            ordering_violation_count += 1
        if t > 2.25 and absf(observed_lid) > EPS_DEG:
            ordering_violation_count += 1

        for station_key: Variant in pivot_by_station.keys():
            var pivot: Node3D = pivot_by_station[String(station_key)] as Node3D
            var observed_latch: float = float(pivot.rotation_degrees.x)
            var latch_linear_residual: float = absf(observed_latch - expected_latch_linear)
            if latch_linear_residual > max_latch_linear_residual:
                max_latch_linear_residual = latch_linear_residual
                worst_latch_interval = i
            var latch_analytic_error: float = absf(observed_latch - analytic_latch_target_deg(t))
            if latch_analytic_error > max_latch_analytic_error:
                max_latch_analytic_error = latch_analytic_error
                worst_latch_analytic_interval = i
            if observed_latch > EPS_DEG or observed_latch < -50.0 - EPS_DEG:
                overshoot_violation_count += 1
            if t > 0.25 and t < 2.25 and absf(observed_latch + 50.0) > EPS_DEG:
                ordering_violation_count += 1

        if capture_intervals.has(i):
            var image: Image = viewport.get_texture().get_image()
            if image == null or image.is_empty() or visible_pixels(image) < 3000:
                fail("interpolation capture empty or insufficient at interval " + str(i))
                return
            var capture_path: String = "res://interp-v3-%03d.png" % i
            if image.save_png(capture_path) != OK:
                fail("could not save interpolation capture at interval " + str(i))
                return
            captures[str(i)] = {"time_s": t, "sha256": sha256_file(capture_path), "path": capture_path}

    if max_lid_linear_residual > EPS_DEG or max_latch_linear_residual > EPS_DEG:
        fail("Godot linear interpolation diverged from adjacent authored-key interpolation")
        return
    if max_lid_analytic_error > LID_ANALYTIC_ERROR_LIMIT_DEG:
        fail("lid half-step interpolation exceeded bounded analytic smoothstep error")
        return
    if max_latch_analytic_error > LATCH_ANALYTIC_ERROR_LIMIT_DEG:
        fail("latch half-step interpolation exceeded bounded analytic smoothstep error")
        return
    if ordering_violation_count != 0:
        fail("linear interpolation violated release/lid/reengage ordering contract")
        return
    if overshoot_violation_count != 0:
        fail("linear interpolation overshot authored lid/latch envelopes")
        return

    player.seek(0.0, true)
    player.advance(0.0)
    var start_lid: float = float(lid.rotation_degrees.x)
    var start_latches: Dictionary = {}
    for station_key: Variant in pivot_by_station.keys():
        start_latches[String(station_key)] = float((pivot_by_station[String(station_key)] as Node3D).rotation_degrees.x)
    player.seek(2.5, true)
    player.advance(0.0)
    var end_lid: float = float(lid.rotation_degrees.x)
    var end_latches: Dictionary = {}
    for station_key: Variant in pivot_by_station.keys():
        end_latches[String(station_key)] = float((pivot_by_station[String(station_key)] as Node3D).rotation_degrees.x)
    if absf(start_lid) > EPS_DEG or absf(end_lid) > EPS_DEG:
        fail("linear track does not preserve neutral lid endpoints")
        return
    for station_key: Variant in pivot_by_station.keys():
        var station_id: String = String(station_key)
        if absf(float(start_latches[station_id])) > EPS_DEG or absf(float(end_latches[station_id])) > EPS_DEG:
            fail("linear track does not preserve neutral latch endpoints")
            return

    receipt["state"] = "PASS_TARGET_HOST_LINEAR_INTERPOLATION_SUBSAMPLE_FIDELITY"
    receipt["godot_version"] = Engine.get_version_info()
    receipt["glb_sha256"] = glb_sha
    receipt["technical_art_object_head"] = technical.get("source_repository_head")
    receipt["uc_commit"] = technical.get("observed_uc_commit")
    receipt["animation_sequence_head"] = sequence.get("exact_receiving_head")
    receipt["sequence_id"] = sequence.get("sequence_id")
    receipt["sequence_digest"] = sequence.get("sequence_digest")
    receipt["sample_rate_hz"] = sequence.get("sample_rate_hz")
    receipt["duration_s"] = sequence.get("duration_s")
    receipt["endpoint_inclusive_sample_count"] = sequence.get("endpoint_inclusive_sample_count")
    receipt["half_step_observation_count"] = samples.size() - 1
    receipt["animationplayer_track_count"] = animation.get_track_count()
    receipt["animationplayer_key_counts"] = [animation.track_get_key_count(lid_track), animation.track_get_key_count(latch_tracks[0]), animation.track_get_key_count(latch_tracks[1])]
    receipt["animation_update_mode"] = "CONTINUOUS"
    receipt["animation_interpolation"] = "LINEAR"
    receipt["target_space_signs"] = {"lid": "positive X", "latches": "negative X"}
    receipt["neutral_pivot_wrapper_max_drift_m"] = neutral_wrapper_drift
    receipt["max_lid_linear_residual_deg"] = max_lid_linear_residual
    receipt["max_latch_linear_residual_deg"] = max_latch_linear_residual
    receipt["max_lid_analytic_smoothstep_error_deg"] = max_lid_analytic_error
    receipt["max_latch_analytic_smoothstep_error_deg"] = max_latch_analytic_error
    receipt["worst_lid_linear_interval"] = worst_lid_interval
    receipt["worst_latch_linear_interval"] = worst_latch_interval
    receipt["worst_lid_analytic_interval"] = worst_lid_analytic_interval
    receipt["worst_latch_analytic_interval"] = worst_latch_analytic_interval
    receipt["lid_analytic_error_limit_deg"] = LID_ANALYTIC_ERROR_LIMIT_DEG
    receipt["latch_analytic_error_limit_deg"] = LATCH_ANALYTIC_ERROR_LIMIT_DEG
    receipt["ordering_violation_count"] = ordering_violation_count
    receipt["overshoot_violation_count"] = overshoot_violation_count
    receipt["neutral_start"] = {"lid_deg_x": start_lid, "latches_deg_x": start_latches}
    receipt["neutral_end"] = {"lid_deg_x": end_lid, "latches_deg_x": end_latches}
    receipt["captures"] = captures
    receipt["truth_boundary"] = {
        "exact_uc_rebound_glb_imported": true,
        "exact_animation_sequence_consumed": true,
        "animationplayer_linear_interpolation_observed": true,
        "every_authored_interval_midpoint_observed": true,
        "analytic_smoothstep_reference_compared_in_target_space": true,
        "release_lid_reengage_ordering_preserved_at_half_steps": true,
        "no_linear_overshoot_of_authored_angle_envelopes_observed": true,
        "proof_local_pivot_wrapper_preserves_neutral_target_geometry": true,
        "wall_clock_40hz_playback_pacing_observed": false,
        "runtime_controller_or_state_machine": false,
        "collision_physics_or_latch_retention": false,
        "gameplay_acceptance": false,
        "final_motion_or_art_direction_acceptance": false,
        "target_device_performance_acceptance": false
    }
    write_receipt()
    print("AXM OBJECT ANIMATIONPLAYER INTERPOLATION V3 ", JSON.stringify(receipt))
    quit(0)
