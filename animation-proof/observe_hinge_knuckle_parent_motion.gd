extends SceneTree

const INPUT_PATH := "res://generated/hinge-knuckle-parent-motion/godot-input.json"
const RECEIPT_PATH := "res://hinge-knuckle-parent-motion-godot-receipt.json"
const MOTION_NAME := "object_hinge_knuckle_parent_motion_rebind"
const POSITION_TOL_M := 0.000001

var receipt := {
    "schema": "axm.object-animation-hinge-knuckle-parent-motion-godot-evidence/v0.1",
    "result": "NOT_RUN",
    "truth_boundary": {
        "historical_source_only": true,
        "bored_knuckle_successor_adopted": false,
        "technical_art_target_host_parenting_accepted": false,
        "runtime_controller_or_state_machine_accepted": false,
        "physics_or_collision_accepted": false,
        "gameplay_accepted": false,
        "final_visual_motion_accepted": false,
        "canon_or_production_ready": false
    }
}

func read_json(path: String) -> Dictionary:
    if not FileAccess.file_exists(path):
        return {}
    var parsed = JSON.parse_string(FileAccess.get_file_as_string(path))
    return parsed as Dictionary if parsed is Dictionary else {}

func vec3(values: Array) -> Vector3:
    if values.size() != 3:
        fail("PARENT_MOTION_MISMATCH invalid vec3 payload")
        return Vector3.ZERO
    return Vector3(float(values[0]), float(values[1]), float(values[2]))

func write_receipt() -> void:
    var file := FileAccess.open(RECEIPT_PATH, FileAccess.WRITE)
    if file != null:
        file.store_string(JSON.stringify(receipt, "  ") + "\n")
        file.close()

func fail(message: String) -> void:
    receipt["result"] = "FAIL_OBJECT_ANIMATION_GODOT_HINGE_KNUCKLE_PARENT_MOTION_REBIND"
    receipt["failure"] = message
    write_receipt()
    push_error(message)
    quit(1)

func expected_position(sample: Dictionary, knuckle_id: String) -> Vector3:
    var mapping = sample.get("expected_knuckle_world_positions_m", {})
    if not mapping.has(knuckle_id):
        fail("PARENT_MOTION_MISMATCH expected position missing for " + knuckle_id)
        return Vector3.ZERO
    return vec3(mapping[knuckle_id])

func _initialize() -> void:
    call_deferred("_run_observation")

func _run_observation() -> void:
    var payload := read_json(INPUT_PATH)
    if payload.get("schema") != "axm.object-animation-hinge-knuckle-parent-motion-godot-input/v0.1":
        fail("PARENT_MOTION_MISMATCH missing exact Animation parent-motion input")
        return
    if bool(payload.get("bored_knuckle_successor_adopted", true)):
        fail("PARENT_MOTION_MISMATCH bored-knuckle successor silently adopted")
        return
    if int(payload.get("sample_rate_hz", 0)) != 40 or int(payload.get("endpoint_inclusive_sample_count", 0)) != 101:
        fail("PARENT_MOTION_MISMATCH authored sample grid drift")
        return
    if absf(float(payload.get("duration_s", -1.0)) - 2.5) > 0.000001:
        fail("PARENT_MOTION_MISMATCH authored duration drift")
        return
    var axis := vec3(payload["hinge_axis"])
    if axis.distance_to(Vector3(1.0, 0.0, 0.0)) > 0.000000001:
        fail("PARENT_MOTION_MISMATCH hinge axis drift")
        return

    var samples: Array = payload.get("samples", [])
    var knuckles: Array = payload.get("knuckles", [])
    if samples.size() != 101 or knuckles.size() != 5:
        fail("PARENT_MOTION_MISMATCH bounded source/sample count drift")
        return

    var stage := Node3D.new()
    stage.name = "AXM_ANIMATION_PARENT_MOTION_STAGE"
    get_root().add_child(stage)

    var body := Node3D.new()
    body.name = "body_shell"
    stage.add_child(body)

    var lid := Node3D.new()
    lid.name = "lid_shell"
    lid.position = vec3(payload["hinge_origin_m"])
    stage.add_child(lid)

    var mutation := OS.get_environment("AXM_MUTATE_PARENT")
    var nodes := {}
    var expected_parent_names := {}
    for row_value in knuckles:
        var row := row_value as Dictionary
        var kid := String(row.get("id", ""))
        var expected_parent := String(row.get("expected_parent", ""))
        if kid == "" or not (expected_parent in ["lid_shell", "body_shell"]):
            fail("PARENT_MOTION_MISMATCH invalid knuckle parent payload")
            return
        var actual_parent := expected_parent
        if mutation == kid:
            actual_parent = "body_shell" if expected_parent == "lid_shell" else "lid_shell"

        var node := Node3D.new()
        node.name = kid
        var neutral := vec3(row["neutral_witness_m"])
        if actual_parent == "lid_shell":
            node.position = neutral - lid.position
            lid.add_child(node)
        else:
            node.position = neutral
            body.add_child(node)
        nodes[kid] = node
        expected_parent_names[kid] = expected_parent

    var animation := Animation.new()
    animation.length = 2.5
    animation.loop_mode = Animation.LOOP_NONE
    var track := animation.add_track(Animation.TYPE_VALUE)
    animation.track_set_path(track, NodePath("lid_shell:rotation:x"))
    animation.track_set_interpolation_type(track, Animation.INTERPOLATION_NEAREST)
    animation.value_track_set_update_mode(track, Animation.UPDATE_DISCRETE)
    for sample_value in samples:
        var sample := sample_value as Dictionary
        animation.track_insert_key(
            track,
            float(sample["time_s"]),
            deg_to_rad(float(sample["lid_mathematical_rotation_deg"]))
        )
    if animation.track_get_key_count(track) != 101:
        fail("PARENT_MOTION_MISMATCH AnimationPlayer track lost authored keys")
        return

    var player := AnimationPlayer.new()
    player.name = "AXM_HINGE_KNUCKLE_PARENT_MOTION_PLAYER"
    stage.add_child(player)
    player.root_node = NodePath("..")
    var library := AnimationLibrary.new()
    library.add_animation(MOTION_NAME, animation)
    player.add_animation_library("", library)
    player.play(MOTION_NAME)
    player.pause()

    var max_position_residual := 0.0
    var max_body_world_drift := 0.0
    var max_lid_world_move := 0.0
    var neutral_positions := {}
    var observed_sample_count := 0
    var peak_sample_index := -1
    var peak_open_angle := -1.0

    for sample_value in samples:
        var sample := sample_value as Dictionary
        var sample_index := int(sample["index"])
        var t := float(sample["time_s"])
        player.seek(t, true)
        player.advance(0.0)
        observed_sample_count += 1

        var open_angle := float(sample["lid_open_angle_deg"])
        if open_angle > peak_open_angle:
            peak_open_angle = open_angle
            peak_sample_index = sample_index

        for row_value in knuckles:
            var row := row_value as Dictionary
            var kid := String(row["id"])
            var node = nodes[kid] as Node3D
            var expected := expected_position(sample, kid)
            var observed: Vector3 = node.global_position
            var residual: float = observed.distance_to(expected)
            max_position_residual = maxf(max_position_residual, residual)
            if residual > POSITION_TOL_M:
                fail(
                    "PARENT_MOTION_MISMATCH %s sample=%d expected=%s observed=%s residual_m=%.12f" %
                    [kid, sample_index, str(expected), str(observed), residual]
                )
                return

            if sample_index == 0:
                neutral_positions[kid] = observed
            elif String(row["owner"]) == "body":
                max_body_world_drift = maxf(max_body_world_drift, observed.distance_to(neutral_positions[kid]))
            else:
                max_lid_world_move = maxf(max_lid_world_move, observed.distance_to(neutral_positions[kid]))

    player.seek(2.5, true)
    player.advance(0.0)
    var endpoint_closure := 0.0
    for row_value in knuckles:
        var row := row_value as Dictionary
        var kid := String(row["id"])
        endpoint_closure = maxf(endpoint_closure, (nodes[kid] as Node3D).global_position.distance_to(neutral_positions[kid]))

    if max_body_world_drift > POSITION_TOL_M:
        fail("PARENT_MOTION_MISMATCH body-owned knuckle moved under lid animation")
        return
    if max_lid_world_move < 0.001:
        fail("PARENT_MOTION_MISMATCH lid-owned knuckles did not receive lid motion")
        return
    if endpoint_closure > POSITION_TOL_M:
        fail("PARENT_MOTION_MISMATCH endpoint did not return hinge knuckles to neutral")
        return

    for row_value in knuckles:
        var row := row_value as Dictionary
        var kid := String(row["id"])
        var expected_parent := String(expected_parent_names[kid])
        var actual_parent := String((nodes[kid] as Node3D).get_parent().name)
        if actual_parent != expected_parent:
            fail("PARENT_MOTION_MISMATCH parent identity drift for " + kid)
            return

    receipt["result"] = "PASS_OBJECT_ANIMATION_GODOT_HINGE_KNUCKLE_PARENT_MOTION_REBIND"
    receipt["exact_animation_head"] = payload["exact_animation_head"]
    receipt["asset_id"] = payload["asset_id"]
    receipt["host_source_sha256"] = payload["host_source_sha256"]
    receipt["rigging_parent_head"] = payload["rigging_parent_head"]
    receipt["rigging_parent_result"] = payload["rigging_parent_result"]
    receipt["known_unconsumed_hard_surface_successor_head"] = payload["known_unconsumed_hard_surface_successor_head"]
    receipt["sample_rate_hz"] = 40
    receipt["duration_s"] = 2.5
    receipt["endpoint_inclusive_sample_count"] = 101
    receipt["animationplayer_track_count"] = 1
    receipt["animationplayer_key_count"] = animation.track_get_key_count(track)
    receipt["animation_interpolation"] = "NEAREST"
    receipt["animation_update_mode"] = "DISCRETE_AUTHORED_SAMPLES"
    receipt["observed_sample_count"] = observed_sample_count
    receipt["peak_sample_index"] = peak_sample_index
    receipt["peak_lid_open_angle_deg"] = peak_open_angle
    receipt["maximum_world_position_residual_m"] = max_position_residual
    receipt["maximum_body_knuckle_world_drift_m"] = max_body_world_drift
    receipt["maximum_lid_knuckle_world_move_m"] = max_lid_world_move
    receipt["endpoint_parent_motion_closure_m"] = endpoint_closure
    receipt["moving_lid_knuckles"] = ["l0", "l1"]
    receipt["fixed_body_knuckles"] = ["b0", "b1", "b2"]
    receipt["negative_parent_mutation_requested"] = mutation
    write_receipt()
    print(JSON.stringify(receipt, "  "))
    quit(0)
