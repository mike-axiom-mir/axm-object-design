extends SceneTree

const GLB_PATH := "res://generated/current-ta-successor002/object-rigid-components-hinge-successor002-rebound.glb"
const TA_RECEIPT_PATH := "res://generated/current-ta-successor002/object-hinge-successor002-ta-transport-rebind-receipt.json"
const TA_TARGET_RECEIPT_PATH := "res://generated/current-ta-successor002/hinge-successor002-target-transport-receipt.json"
const ANIMATION_INPUT_PATH := "res://generated/hinge-phase-invariant-successor-motion/godot-input.json"
const RECEIPT_PATH := "res://successor002-current-ta-animationplayer-receipt.json"
const MOTION_NAME := "object_successor002_current_ta_lid_sequence"
const ANGLE_TOL_DEG := 0.00001
const POSITION_TOL_M := 0.000001
const WALL_CLOCK_TIMEOUT_US := 8000000
const HINGE_NAMES := ["hinge_body_b0", "hinge_lid_l0", "hinge_body_b1", "hinge_lid_l1", "hinge_body_b2"]
const LID_NAMES := ["hinge_lid_l0", "hinge_lid_l1"]
const BODY_NAMES := ["hinge_body_b0", "hinge_body_b1", "hinge_body_b2"]

var receipt := {
    "schema": "axm.object-animation-successor002-current-ta-motion/v0.1",
    "result": "NOT_RUN",
    "truth_boundary": {
        "exact_current_ta_successor_receiver_consumed": true,
        "source_motion_retimed_or_reauthored": false,
        "wall_clock_source_slot_delivery_proven": false,
        "runtime_controller_or_state_machine_accepted": false,
        "input_or_gameplay_accepted": false,
        "physics_or_collision_accepted": false,
        "target_device_performance_accepted": false,
        "final_motion_style_or_art_qa_accepted": false,
        "source_successor_default_adopted": false,
        "canon_or_production_ready": false
    }
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
    var file := FileAccess.open(RECEIPT_PATH, FileAccess.WRITE)
    if file != null:
        file.store_string(JSON.stringify(receipt, "  ") + "\n")
        file.close()

func fail(message: String) -> void:
    receipt["result"] = "FAIL_OBJECT_ANIMATION_SUCCESSOR002_CURRENT_TA_MOTION"
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
        fail("CURRENT_TA_MOTION_MISMATCH expected MeshInstance3D for " + String(node.name))
        return Vector3.ZERO
    var instance := node as MeshInstance3D
    if instance.mesh == null:
        fail("CURRENT_TA_MOTION_MISMATCH mesh missing for " + String(node.name))
        return Vector3.ZERO
    return instance.global_transform * instance.mesh.get_aabb().get_center()

func max_body_drift(nodes: Dictionary, neutral: Dictionary) -> float:
    var result := 0.0
    for name in BODY_NAMES:
        result = maxf(result, world_mesh_center(nodes[name]).distance_to(neutral[name]))
    return result

func max_lid_move(nodes: Dictionary, neutral: Dictionary) -> float:
    var result := 0.0
    for name in LID_NAMES:
        result = maxf(result, world_mesh_center(nodes[name]).distance_to(neutral[name]))
    return result

func max_endpoint_drift(nodes: Dictionary, neutral: Dictionary) -> float:
    var result := 0.0
    for name in HINGE_NAMES:
        result = maxf(result, world_mesh_center(nodes[name]).distance_to(neutral[name]))
    return result

func _initialize() -> void:
    call_deferred("_run_observation")

func _run_observation() -> void:
    var ta := read_json(TA_RECEIPT_PATH)
    var ta_target := read_json(TA_TARGET_RECEIPT_PATH)
    var payload := read_json(ANIMATION_INPUT_PATH)

    if ta.get("result") != "PASS_OBJECT_HINGE_SUCCESSOR002_TA_SCENE_REBIND_TO_CURRENT_UC__HOLD_DEFAULT_RUNTIME_VISUAL":
        fail("CURRENT_TA_MOTION_MISMATCH Technical Art successor-002 receipt missing or not green")
        return
    if ta_target.get("result") != "PASS_OBJECT_HINGE_SUCCESSOR002_CURRENT_UC_GODOT_TRIANGLE_TRANSPORT":
        fail("CURRENT_TA_MOTION_MISMATCH Technical Art Godot transport receipt missing or not green")
        return
    if payload.get("schema") != "axm.object-animation-phase-invariant-hinge-successor-godot-input/v0.1":
        fail("CURRENT_TA_MOTION_MISMATCH exact Animation successor input missing")
        return
    if String(payload.get("source_successor_head", "")) != String(ta.get("hard_surface_head", "")):
        fail("CURRENT_TA_MOTION_MISMATCH Hard-Surface successor identity drift")
        return
    if String(payload.get("rigging_receiver_head", "")) != String(ta.get("rigging_head", "")):
        fail("CURRENT_TA_MOTION_MISMATCH Rigging receiver identity drift")
        return
    if bool(payload.get("production_default_adoption", true)) or bool(payload.get("automatic_downstream_adoption", true)):
        fail("CURRENT_TA_MOTION_MISMATCH downstream adoption authority inflated")
        return
    if int(payload.get("sample_rate_hz", 0)) != 40 or int(payload.get("endpoint_inclusive_sample_count", 0)) != 101:
        fail("CURRENT_TA_MOTION_MISMATCH authored sample grid drift")
        return
    if absf(float(payload.get("duration_s", -1.0)) - 2.5) > 0.000001:
        fail("CURRENT_TA_MOTION_MISMATCH authored duration drift")
        return
    if not FileAccess.file_exists(GLB_PATH):
        fail("CURRENT_TA_MOTION_MISMATCH exact successor-002 rebound GLB missing")
        return
    var glb_sha := sha256_file(GLB_PATH)
    if glb_sha != String(ta.get("successor_rebound_glb_sha256", "")):
        fail("CURRENT_TA_MOTION_MISMATCH successor-002 rebound GLB byte identity mismatch")
        return

    var document := GLTFDocument.new()
    var state := GLTFState.new()
    var error := document.append_from_file(GLB_PATH, state)
    if error != OK:
        fail("CURRENT_TA_MOTION_MISMATCH GLTFDocument append_from_file failed: " + str(error))
        return
    var generated = document.generate_scene(state)
    if generated == null or not (generated is Node3D):
        fail("CURRENT_TA_MOTION_MISMATCH GLTFDocument generate_scene returned no Node3D")
        return
    var imported := generated as Node3D
    get_root().add_child(imported)

    var lid := find_node(imported, "lid_shell")
    if lid == null:
        fail("CURRENT_TA_MOTION_MISMATCH lid_shell missing from imported receiver")
        return

    var nodes: Dictionary = {}
    for name in HINGE_NAMES:
        var node := find_node(imported, name)
        if node == null:
            fail("CURRENT_TA_MOTION_MISMATCH missing imported hinge component " + name)
            return
        nodes[name] = node
        if name in LID_NAMES and node.get_parent() != lid:
            fail("CURRENT_TA_MOTION_MISMATCH lid-owned hinge parentage drift: " + name)
            return
        if name in BODY_NAMES and node.get_parent() == lid:
            fail("CURRENT_TA_MOTION_MISMATCH body-owned hinge parentage drift: " + name)
            return

    await process_frame

    var neutral: Dictionary = {}
    for name in HINGE_NAMES:
        neutral[name] = world_mesh_center(nodes[name])

    var mutation := OS.get_environment("AXM_MUTATE_BODY_PARENT")
    if mutation != "":
        if not nodes.has(mutation) or not (mutation in BODY_NAMES):
            fail("CURRENT_TA_MOTION_MISMATCH invalid parent-mutation target")
            return
        (nodes[mutation] as Node3D).reparent(lid, true)

    var samples: Array = payload.get("samples", [])
    if samples.size() != 101:
        fail("CURRENT_TA_MOTION_MISMATCH source sample count drift")
        return

    var animation := Animation.new()
    animation.length = 2.5
    animation.loop_mode = Animation.LOOP_NONE
    var track := animation.add_track(Animation.TYPE_VALUE)
    animation.track_set_path(track, NodePath(str(imported.get_path_to(lid)) + ":rotation:x"))
    animation.track_set_interpolation_type(track, Animation.INTERPOLATION_NEAREST)
    animation.value_track_set_update_mode(track, Animation.UPDATE_DISCRETE)

    var peak_authored_deg := -1.0
    for sample_value in samples:
        var sample := sample_value as Dictionary
        var open_deg := float(sample.get("lid_open_angle_deg", -1.0))
        if open_deg < -0.000001 or open_deg > 110.000001:
            fail("CURRENT_TA_MOTION_MISMATCH authored lid motion escaped exact Rigging owner range")
            return
        peak_authored_deg = maxf(peak_authored_deg, open_deg)
        animation.track_insert_key(track, float(sample["time_s"]), deg_to_rad(open_deg))
    if animation.track_get_key_count(track) != 101 or absf(peak_authored_deg - 100.0) > 0.000001:
        fail("CURRENT_TA_MOTION_MISMATCH frozen 101-key / 100-degree source motion drift")
        return

    var player := AnimationPlayer.new()
    player.name = "AXM_SUCCESSOR002_CURRENT_TA_MOTION_PLAYER"
    imported.add_child(player)
    player.root_node = NodePath("..")
    var library := AnimationLibrary.new()
    library.add_animation(MOTION_NAME, animation)
    player.add_animation_library("", library)
    player.play(MOTION_NAME)
    player.pause()

    var max_seek_angle_error_deg := 0.0
    var sampled_max_body_drift_m := 0.0
    var sampled_max_lid_move_m := 0.0
    var selected := []
    var selected_indices := [0, 10, 25, 40, 50, 60, 90, 95, 100]

    for sample_value in samples:
        var sample := sample_value as Dictionary
        var sample_index := int(sample["index"])
        var expected_deg := float(sample["lid_open_angle_deg"])
        player.seek(float(sample["time_s"]), true)
        player.advance(0.0)
        var observed_deg := rad_to_deg(lid.rotation.x)
        var angle_error := absf(observed_deg - expected_deg)
        max_seek_angle_error_deg = maxf(max_seek_angle_error_deg, angle_error)
        sampled_max_body_drift_m = maxf(sampled_max_body_drift_m, max_body_drift(nodes, neutral))
        sampled_max_lid_move_m = maxf(sampled_max_lid_move_m, max_lid_move(nodes, neutral))
        if sample_index in selected_indices:
            selected.append({
                "index": sample_index,
                "time_s": float(sample["time_s"]),
                "expected_lid_deg_x": expected_deg,
                "observed_lid_deg_x": observed_deg,
                "abs_error_deg": angle_error
            })

    if max_seek_angle_error_deg > ANGLE_TOL_DEG:
        fail("CURRENT_TA_MOTION_MISMATCH AnimationPlayer sampled seek diverged from frozen authored lid angles")
        return
    if sampled_max_body_drift_m > POSITION_TOL_M:
        fail("CURRENT_TA_MOTION_MISMATCH body-owned successor hinge moved under sampled lid animation")
        return
    if sampled_max_lid_move_m < 0.005:
        fail("CURRENT_TA_MOTION_MISMATCH lid-owned successor hinge did not receive sampled lid motion")
        return

    player.seek(2.5, true)
    player.advance(0.0)
    var sampled_endpoint_drift_m := max_endpoint_drift(nodes, neutral)
    if sampled_endpoint_drift_m > POSITION_TOL_M:
        fail("CURRENT_TA_MOTION_MISMATCH sampled endpoint did not return successor hinge to neutral")
        return

    player.stop()
    player.play(MOTION_NAME)
    var wall_start_us := Time.get_ticks_usec()
    var wall_frames := 0
    var wall_peak_lid_deg := rad_to_deg(lid.rotation.x)
    var wall_max_body_drift_m := 0.0
    var wall_max_lid_move_m := 0.0
    while player.is_playing():
        await process_frame
        wall_frames += 1
        wall_peak_lid_deg = maxf(wall_peak_lid_deg, rad_to_deg(lid.rotation.x))
        wall_max_body_drift_m = maxf(wall_max_body_drift_m, max_body_drift(nodes, neutral))
        wall_max_lid_move_m = maxf(wall_max_lid_move_m, max_lid_move(nodes, neutral))
        if Time.get_ticks_usec() - wall_start_us > WALL_CLOCK_TIMEOUT_US:
            fail("CURRENT_TA_MOTION_MISMATCH natural AnimationPlayer playback exceeded bounded timeout")
            return

    var wall_elapsed_s := float(Time.get_ticks_usec() - wall_start_us) / 1000000.0
    var wall_endpoint_drift_m := max_endpoint_drift(nodes, neutral)
    if wall_frames < 2:
        fail("CURRENT_TA_MOTION_MISMATCH natural AnimationPlayer playback produced insufficient process observations")
        return
    if wall_peak_lid_deg < 99.9:
        fail("CURRENT_TA_MOTION_MISMATCH natural AnimationPlayer playback did not reach the frozen open hold")
        return
    if wall_max_body_drift_m > POSITION_TOL_M:
        fail("CURRENT_TA_MOTION_MISMATCH body-owned successor hinge moved during natural AnimationPlayer playback")
        return
    if wall_max_lid_move_m < 0.005:
        fail("CURRENT_TA_MOTION_MISMATCH lid-owned successor hinge did not move during natural AnimationPlayer playback")
        return
    if wall_endpoint_drift_m > POSITION_TOL_M:
        fail("CURRENT_TA_MOTION_MISMATCH natural AnimationPlayer playback did not close at neutral")
        return

    receipt["result"] = "PASS_OBJECT_ANIMATION_SUCCESSOR002_CURRENT_TA_ANIMATIONPLAYER_MOTION"
    receipt["exact_animation_head"] = payload.get("exact_animation_head")
    receipt["technical_art_head"] = ta.get("technical_art_head")
    receipt["hard_surface_successor_head"] = ta.get("hard_surface_head")
    receipt["geometry_head"] = ta.get("geometry_head")
    receipt["rigging_head"] = ta.get("rigging_head")
    receipt["uc_head"] = ta.get("uc_head")
    receipt["successor_rebound_glb_sha256"] = glb_sha
    receipt["sample_rate_hz"] = 40
    receipt["duration_s"] = 2.5
    receipt["endpoint_inclusive_sample_count"] = 101
    receipt["animationplayer_track_count"] = 1
    receipt["animationplayer_key_count"] = animation.track_get_key_count(track)
    receipt["animation_interpolation"] = "NEAREST"
    receipt["animation_update_mode"] = "DISCRETE_AUTHORED_SAMPLES"
    receipt["peak_authored_lid_deg"] = peak_authored_deg
    receipt["sampled_max_lid_angle_error_deg"] = max_seek_angle_error_deg
    receipt["sampled_max_body_knuckle_world_drift_m"] = sampled_max_body_drift_m
    receipt["sampled_max_lid_knuckle_world_move_m"] = sampled_max_lid_move_m
    receipt["sampled_endpoint_parent_motion_closure_m"] = sampled_endpoint_drift_m
    receipt["selected_sample_observations"] = selected
    receipt["wall_clock_playback_completed"] = true
    receipt["wall_clock_elapsed_s"] = wall_elapsed_s
    receipt["wall_clock_process_observations"] = wall_frames
    receipt["wall_clock_peak_lid_deg"] = wall_peak_lid_deg
    receipt["wall_clock_max_body_knuckle_world_drift_m"] = wall_max_body_drift_m
    receipt["wall_clock_max_lid_knuckle_world_move_m"] = wall_max_lid_move_m
    receipt["wall_clock_endpoint_parent_motion_closure_m"] = wall_endpoint_drift_m
    receipt["negative_parent_mutation_requested"] = mutation
    receipt["godot_version"] = Engine.get_version_info()
    write_receipt()
    print("AXM OBJECT ANIMATION SUCCESSOR002 CURRENT TA ", JSON.stringify(receipt))
    quit(0)
