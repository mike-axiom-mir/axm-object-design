extends SceneTree

const GLB_PATH := "res://generated/object-rigid-components-rebound.glb"
const TECH_RECEIPT_PATH := "res://generated/uc-rigid-scene-handoff-receipt.json"
const SEQUENCE_PATH := "res://generated/lid-latch-motion-evidence.json"
const RIG_RECEIPT_PATH := "res://generated/front-latch-articulation.receipt.json"
const TARGET_RECEIPT_PATH := "res://wall-clock-target-receipt.json"
const MOTION_NAME := "lid_latch_open_hold_close_wall_clock_review"
const EPS_DEG := 0.0001
const EPS_M := 0.000001
const MAX_WALL_CLOCK_S := 4.0

var receipt := {
    "schema": "axm.object-animationplayer-wall-clock-proof/v0.1",
    "state": "NOT_RUN",
    "promotion_effect": "NONE",
    "renderer_boundary": "Godot 4.7.2 GL Compatibility proof-host wall-clock AnimationPlayer presentation of the exact discrete authored samples. This is scheduler/presentation characterization, not controller/state-machine, gameplay, target-device performance or final motion acceptance."
}

func read_json(path: String) -> Dictionary:
    if not FileAccess.file_exists(path):
        return {}
    var parsed = JSON.parse_string(FileAccess.get_file_as_string(path))
    return parsed as Dictionary if parsed is Dictionary else {}

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
    receipt["state"] = "FAIL_PROOF_HOST_WALL_CLOCK_ANIMATIONPLAYER_TRACE"
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

func world_mesh_center(node: Node3D) -> Vector3:
    if not (node is MeshInstance3D):
        fail("expected MeshInstance3D for " + String(node.name))
        return Vector3.ZERO
    var instance := node as MeshInstance3D
    if instance.mesh == null:
        fail("mesh missing for " + String(node.name))
        return Vector3.ZERO
    return instance.global_transform * instance.mesh.get_aabb().get_center()

func source_to_uc(values: Array) -> Vector3:
    if values.size() != 3:
        fail("source pivot is not vec3")
        return Vector3.ZERO
    return Vector3(float(values[0]), float(values[2]), float(values[1]))

func visible_pixels(image: Image) -> int:
    var bg := Color(0.025, 0.030, 0.036, 1.0)
    var changed := 0
    for y in range(image.get_height()):
        for x in range(image.get_width()):
            var p := image.get_pixel(x, y)
            var delta: float = maxf(absf(p.r-bg.r), maxf(absf(p.g-bg.g), absf(p.b-bg.b)))
            if delta > 0.035:
                changed += 1
    return changed

func make_viewport(imported: Node3D) -> SubViewport:
    var viewport := SubViewport.new()
    viewport.size = Vector2i(820, 620)
    viewport.own_world_3d = true
    viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
    viewport.render_target_clear_mode = SubViewport.CLEAR_MODE_ALWAYS
    get_root().add_child(viewport)

    var root3d := Node3D.new()
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

func station_lookup(rows: Array) -> Dictionary:
    var out := {}
    for row in rows:
        out[String(row["station_id"])] = row
    return out

func expected_sample_index(position_s: float, sample_rate_hz: int, count: int) -> int:
    var index := int(floor(maxf(position_s, 0.0) * float(sample_rate_hz) + 0.000001))
    return clampi(index, 0, count - 1)

func _initialize() -> void:
    var technical := read_json(TECH_RECEIPT_PATH)
    var sequence := read_json(SEQUENCE_PATH)
    var rig := read_json(RIG_RECEIPT_PATH)
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
    var glb_sha := sha256_file(GLB_PATH)
    if glb_sha != String(technical.get("rebound_glb_sha256", "")):
        fail("rebound GLB identity mismatch")
        return

    var samples: Array = sequence.get("samples", [])
    var sample_count := int(sequence.get("endpoint_inclusive_sample_count", 0))
    var sample_rate_hz := int(sequence.get("sample_rate_hz", 0))
    var duration_s := float(sequence.get("duration_s", -1.0))
    if sample_count != 101 or samples.size() != 101 or sample_rate_hz != 40 or absf(duration_s - 2.5) > 0.000001:
        fail("unexpected authored sequence grid")
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
    if keeper0.get_parent() != lid or keeper1.get_parent() != lid:
        fail("source-owned keepers are not direct lid children")
        return
    if lever0.get_parent() == lid or lever1.get_parent() == lid:
        fail("front-panel-owned levers imported under lid")
        return

    var viewport := make_viewport(imported)
    for _i in range(10):
        await process_frame

    var neutral_lever_before_wrappers := {
        "latch_0_lever": world_mesh_center(lever0),
        "latch_1_lever": world_mesh_center(lever1)
    }
    var rig_by_station := station_lookup(rig.get("station_results", []))
    var sample0_stations := station_lookup(samples[0]["stations"])
    if rig_by_station.size() != 2 or sample0_stations.size() != 2:
        fail("expected exactly two bilateral latch stations")
        return

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
        pivot.name = "animation_pivot_" + String(station_id)
        pivot.position = source_to_uc(rig_by_station[station_id]["pivot_m"])
        imported.add_child(pivot)
        lever.reparent(pivot, true)
        pivot_by_station[station_id] = pivot

    for _i in range(3):
        await process_frame
    var neutral_pivot_wrapper_max_drift := maxf(
        neutral_lever_before_wrappers["latch_0_lever"].distance_to(world_mesh_center(lever0)),
        neutral_lever_before_wrappers["latch_1_lever"].distance_to(world_mesh_center(lever1))
    )
    if neutral_pivot_wrapper_max_drift > EPS_M:
        fail("proof-local latch pivot insertion changed neutral target geometry")
        return

    var animation := Animation.new()
    animation.length = duration_s
    animation.loop_mode = Animation.LOOP_NONE
    var lid_track := add_discrete_rotation_track(animation, imported, lid, samples, "lid_mathematical_rotation_deg", true)
    var latch_tracks := []
    for station_id in pivot_by_station.keys():
        latch_tracks.append(add_discrete_rotation_track(animation, imported, pivot_by_station[station_id], samples, "latch_lever_angle_deg", true))
    if animation.track_get_key_count(lid_track) != sample_count:
        fail("lid AnimationPlayer track did not receive all authored samples")
        return
    for track in latch_tracks:
        if animation.track_get_key_count(track) != sample_count:
            fail("latch AnimationPlayer track did not receive all authored samples")
            return

    var player := AnimationPlayer.new()
    player.name = "AXM_WALL_CLOCK_REVIEW_PLAYER"
    imported.add_child(player)
    player.root_node = NodePath("..")
    var library := AnimationLibrary.new()
    library.add_animation(MOTION_NAME, animation)
    player.add_animation_library("", library)

    var start_keeper := {
        "latch_0_keeper": world_mesh_center(keeper0),
        "latch_1_keeper": world_mesh_center(keeper1)
    }
    var start_lever := {
        "latch_0_lever": world_mesh_center(lever0),
        "latch_1_lever": world_mesh_center(lever1)
    }

    var requested_capture_indices := [0, 9, 10, 11, 39, 40, 41, 89, 90, 91, 100]
    var captured_requested := {}
    var captures := []
    var trace := []
    var observed_indices := {}
    var missed_or_repeated_step_count := 0
    var index_jump_max := 0
    var current_position_monotonic_violations := 0
    var ordering_violations := 0
    var max_lid_error := 0.0
    var max_latch_error := 0.0
    var previous_position := -1.0
    var previous_index := -1
    var previous_wall_us := -1
    var min_frame_dt_ms := 1.0e30
    var max_frame_dt_ms := 0.0
    var sum_frame_dt_ms := 0.0
    var frame_dt_count := 0

    player.play(MOTION_NAME)
    var wall_start_us := Time.get_ticks_usec()

    while true:
        await process_frame
        var wall_now_us := Time.get_ticks_usec()
        var elapsed_s := float(wall_now_us - wall_start_us) / 1000000.0
        var position_s := float(player.current_animation_position)
        if previous_position >= 0.0 and position_s + 0.000001 < previous_position:
            current_position_monotonic_violations += 1
        if previous_wall_us >= 0:
            var dt_ms := float(wall_now_us - previous_wall_us) / 1000.0
            min_frame_dt_ms = minf(min_frame_dt_ms, dt_ms)
            max_frame_dt_ms = maxf(max_frame_dt_ms, dt_ms)
            sum_frame_dt_ms += dt_ms
            frame_dt_count += 1
        previous_wall_us = wall_now_us

        var sample_index := expected_sample_index(position_s, sample_rate_hz, sample_count)
        observed_indices[sample_index] = true
        if previous_index >= 0:
            var jump := sample_index - previous_index
            index_jump_max = maxi(index_jump_max, jump)
            if jump != 0 and jump != 1:
                missed_or_repeated_step_count += 1
        previous_index = sample_index
        previous_position = position_s

        var row = samples[sample_index]
        var expected_lid := -float(row["lid_mathematical_rotation_deg"])
        var lid_error := absf(lid.rotation_degrees.x - expected_lid)
        max_lid_error = maxf(max_lid_error, lid_error)
        var expected_latch := -float(row["latch_lever_angle_deg"])
        var station_errors := {}
        var min_latch_abs := 1.0e30
        for station_id in pivot_by_station.keys():
            var pivot = pivot_by_station[station_id] as Node3D
            var latch_error := absf(pivot.rotation_degrees.x - expected_latch)
            max_latch_error = maxf(max_latch_error, latch_error)
            min_latch_abs = minf(min_latch_abs, absf(pivot.rotation_degrees.x))
            station_errors[station_id] = latch_error
        if absf(lid.rotation_degrees.x) > 0.001 and min_latch_abs < 49.999:
            ordering_violations += 1

        trace.append({
            "wall_elapsed_s": elapsed_s,
            "animation_position_s": position_s,
            "expected_sample_index": sample_index,
            "observed_lid_deg_x": lid.rotation_degrees.x,
            "expected_lid_deg_x": expected_lid,
            "lid_abs_error_deg": lid_error,
            "expected_latch_deg_x": expected_latch,
            "station_abs_errors_deg": station_errors
        })

        for requested_index in requested_capture_indices:
            if captured_requested.has(requested_index):
                continue
            if sample_index >= requested_index:
                var image := viewport.get_texture().get_image()
                if image == null or image.is_empty() or visible_pixels(image) < 3000:
                    fail("wall-clock target capture empty near requested sample " + str(requested_index))
                    return
                var capture_path := "res://wallclock-request-%03d-observed-%03d.png" % [requested_index, sample_index]
                if image.save_png(capture_path) != OK:
                    fail("could not save wall-clock target capture")
                    return
                captured_requested[requested_index] = true
                captures.append({
                    "requested_sample_index": requested_index,
                    "observed_sample_index": sample_index,
                    "animation_position_s": position_s,
                    "wall_elapsed_s": elapsed_s,
                    "sha256": sha256_file(capture_path),
                    "path": capture_path
                })

        if not player.is_playing():
            break
        if elapsed_s > MAX_WALL_CLOCK_S:
            fail("wall-clock playback did not complete inside bounded proof-host timeout")
            return

    # Give the terminal target transform/render one frame to settle and retain it if sample 100 was skipped by the live frame loop.
    await process_frame
    var wall_end_us := Time.get_ticks_usec()
    var wall_duration_s := float(wall_end_us - wall_start_us) / 1000000.0
    var terminal_row = samples[sample_count - 1]
    var terminal_lid_error := absf(lid.rotation_degrees.x + float(terminal_row["lid_mathematical_rotation_deg"]))
    max_lid_error = maxf(max_lid_error, terminal_lid_error)
    for station_id in pivot_by_station.keys():
        var pivot = pivot_by_station[station_id] as Node3D
        max_latch_error = maxf(max_latch_error, absf(pivot.rotation_degrees.x + float(terminal_row["latch_lever_angle_deg"])))

    if not captured_requested.has(100):
        var end_image := viewport.get_texture().get_image()
        if end_image == null or end_image.is_empty() or visible_pixels(end_image) < 3000:
            fail("terminal wall-clock target capture empty")
            return
        var end_path := "res://wallclock-request-100-observed-100.png"
        if end_image.save_png(end_path) != OK:
            fail("could not save terminal wall-clock target capture")
            return
        captured_requested[100] = true
        captures.append({
            "requested_sample_index": 100,
            "observed_sample_index": 100,
            "animation_position_s": duration_s,
            "wall_elapsed_s": wall_duration_s,
            "sha256": sha256_file(end_path),
            "path": end_path
        })

    var end_keeper_drift := maxf(
        start_keeper["latch_0_keeper"].distance_to(world_mesh_center(keeper0)),
        start_keeper["latch_1_keeper"].distance_to(world_mesh_center(keeper1))
    )
    var end_lever_drift := maxf(
        start_lever["latch_0_lever"].distance_to(world_mesh_center(lever0)),
        start_lever["latch_1_lever"].distance_to(world_mesh_center(lever1))
    )

    var observed_index_list := []
    for key in observed_indices.keys():
        observed_index_list.append(int(key))
    observed_index_list.sort()
    var missing_indices := []
    for i in range(sample_count):
        if not observed_indices.has(i):
            missing_indices.append(i)
    var slot_coverage := float(observed_index_list.size()) / float(sample_count)
    var mean_frame_dt_ms := sum_frame_dt_ms / float(maxi(frame_dt_count, 1))

    if trace.size() < 60:
        fail("wall-clock trace is too sparse to characterize the full clip")
        return
    if slot_coverage < 0.70:
        fail("wall-clock trace observed too little of the authored sample grid")
        return
    if current_position_monotonic_violations != 0:
        fail("AnimationPlayer current position moved backwards during non-looping playback")
        return
    if ordering_violations != 0:
        fail("observed target transforms violated the source-bound Animation ordering contract")
        return
    if max_lid_error > EPS_DEG or max_latch_error > EPS_DEG:
        fail("wall-clock AnimationPlayer target transforms diverged from current discrete authored sample state")
        return
    if end_keeper_drift > EPS_M or end_lever_drift > EPS_M:
        fail("wall-clock playback endpoint did not return source-owned moving proof components to neutral")
        return
    if wall_duration_s < 2.0 or wall_duration_s > MAX_WALL_CLOCK_S:
        fail("proof-host wall-clock completion duration fell outside characterization envelope")
        return

    receipt["state"] = "PASS_PROOF_HOST_WALL_CLOCK_ANIMATIONPLAYER_TRACE_CAPTURED"
    receipt["godot_version"] = Engine.get_version_info()
    receipt["glb_sha256"] = glb_sha
    receipt["technical_art_object_head"] = technical.get("source_repository_head")
    receipt["uc_commit"] = technical.get("observed_uc_commit")
    receipt["animation_sequence_head"] = sequence.get("exact_receiving_head")
    receipt["sequence_id"] = sequence.get("sequence_id")
    receipt["sequence_digest"] = sequence.get("sequence_digest")
    receipt["sample_rate_hz"] = sample_rate_hz
    receipt["duration_s"] = duration_s
    receipt["endpoint_inclusive_sample_count"] = sample_count
    receipt["animationplayer_track_count"] = animation.get_track_count()
    receipt["animationplayer_key_counts"] = [animation.track_get_key_count(lid_track), animation.track_get_key_count(latch_tracks[0]), animation.track_get_key_count(latch_tracks[1])]
    receipt["animation_update_mode"] = "DISCRETE_AUTHORED_SAMPLES"
    receipt["animation_interpolation"] = "NEAREST"
    receipt["playback_invocation"] = "AnimationPlayer.play"
    receipt["proof_host_wall_clock_duration_s"] = wall_duration_s
    receipt["trace_frame_count"] = trace.size()
    receipt["observed_authored_sample_indices"] = observed_index_list
    receipt["observed_authored_sample_count"] = observed_index_list.size()
    receipt["authored_sample_slot_coverage_ratio"] = slot_coverage
    receipt["missing_authored_sample_indices"] = missing_indices
    receipt["maximum_observed_sample_index_jump"] = index_jump_max
    receipt["non_unit_sample_index_jump_events"] = missed_or_repeated_step_count
    receipt["process_frame_dt_ms"] = {
        "minimum": 0.0 if frame_dt_count == 0 else min_frame_dt_ms,
        "mean": mean_frame_dt_ms,
        "maximum": max_frame_dt_ms,
        "count": frame_dt_count
    }
    receipt["current_position_monotonic_violations"] = current_position_monotonic_violations
    receipt["ordering_violations"] = ordering_violations
    receipt["max_lid_discrete_state_error_deg"] = max_lid_error
    receipt["max_latch_discrete_state_error_deg"] = max_latch_error
    receipt["neutral_pivot_wrapper_max_drift_m"] = neutral_pivot_wrapper_max_drift
    receipt["endpoint_keeper_drift_m"] = end_keeper_drift
    receipt["endpoint_lever_drift_m"] = end_lever_drift
    receipt["capture_count"] = captures.size()
    receipt["captures"] = captures
    receipt["trace"] = trace
    receipt["truth_boundary"] = {
        "exact_uc_rebound_glb_imported": true,
        "exact_animation_sequence_consumed": true,
        "animationplayer_resource_authored_in_proof_host": true,
        "animationplayer_play_wall_clock_presentation_observed": true,
        "discrete_authored_state_correspondence_observed": true,
        "process_frame_slot_coverage_is_characterization_not_authored_40hz_delivery_guarantee": true,
        "display_scanout_timing_observed": false,
        "continuous_interpolation_between_authored_samples": false,
        "runtime_controller_or_state_machine": false,
        "collision_physics_or_latch_retention": false,
        "gameplay_acceptance": false,
        "final_motion_or_art_direction_acceptance": false,
        "target_device_performance_acceptance": false,
        "production_readiness": false
    }
    write_receipt()
    print("AXM OBJECT WALL CLOCK PLAYBACK ", JSON.stringify(receipt))
    quit(0)
