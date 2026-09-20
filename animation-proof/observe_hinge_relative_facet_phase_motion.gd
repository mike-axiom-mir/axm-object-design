extends SceneTree

const INPUT_PATH := "res://generated/hinge-relative-facet-phase-motion/godot-input.json"
const RECEIPT_PATH := "res://hinge-relative-facet-phase-motion-godot-receipt.json"
const MOTION_NAME := "object_hinge_relative_facet_phase_motion_rebind"
const POSITION_TOL_M := 0.000001
const PHASE_TOL_DEG := 0.001

var receipt := {
    "schema": "axm.object-animation-relative-facet-phase-godot-evidence/v0.1",
    "result": "NOT_RUN",
    "truth_boundary": {
        "source_successor_bounded_animation_proof_consumed": true,
        "source_owner_phase_preservation_observed": true,
        "production_default_adoption": false,
        "technical_art_target_host_adopted": false,
        "runtime_controller_or_state_machine_accepted": false,
        "physics_or_collision_accepted": false,
        "gameplay_accepted": false,
        "target_device_performance_accepted": false,
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
        fail("RELATIVE_FACET_PHASE_MOTION_MISMATCH invalid vec3 payload")
        return Vector3.ZERO
    return Vector3(float(values[0]), float(values[1]), float(values[2]))

func rotate_local_x(v: Vector3, angle_deg: float) -> Vector3:
    var a := deg_to_rad(angle_deg)
    var c := cos(a)
    var s := sin(a)
    return Vector3(v.x, v.y * c - v.z * s, v.y * s + v.z * c)

func phase_deg(point: Vector3, origin: Vector3) -> float:
    return rad_to_deg(atan2(point.z - origin.z, point.y - origin.y))

func phase_delta_deg(a: float, b: float) -> float:
    return absf(wrapf(a - b + 180.0, 0.0, 360.0) - 180.0)

func write_receipt() -> void:
    var file := FileAccess.open(RECEIPT_PATH, FileAccess.WRITE)
    if file != null:
        file.store_string(JSON.stringify(receipt, "  ") + "\n")
        file.close()

func fail(message: String) -> void:
    receipt["result"] = "FAIL_OBJECT_ANIMATION_GODOT_RELATIVE_FACET_PHASE_MOTION_REBIND"
    receipt["failure"] = message
    write_receipt()
    push_error(message)
    quit(1)

func expected_position(sample: Dictionary, witness_id: String) -> Vector3:
    var mapping = sample.get("expected_witness_world_positions_m", {})
    if not mapping.has(witness_id):
        fail("RELATIVE_FACET_PHASE_MOTION_MISMATCH expected position missing for " + witness_id)
        return Vector3.ZERO
    return vec3(mapping[witness_id])

func expected_phase(sample: Dictionary, witness_id: String) -> float:
    var mapping = sample.get("expected_effective_phase_deg", {})
    if not mapping.has(witness_id):
        fail("RELATIVE_FACET_PHASE_MOTION_MISMATCH expected phase missing for " + witness_id)
        return 0.0
    return float(mapping[witness_id])

func _initialize() -> void:
    call_deferred("_run_observation")

func _run_observation() -> void:
    var payload := read_json(INPUT_PATH)
    if payload.get("schema") != "axm.object-animation-relative-facet-phase-godot-input/v0.1":
        fail("RELATIVE_FACET_PHASE_MOTION_MISMATCH missing exact Animation input")
        return
    if not bool(payload.get("bounded_animation_candidate_adopted", false)):
        fail("RELATIVE_FACET_PHASE_MOTION_MISMATCH bounded Animation candidate opt-in missing")
        return
    if bool(payload.get("production_default_adoption", true)) or bool(payload.get("automatic_downstream_adoption", true)):
        fail("RELATIVE_FACET_PHASE_MOTION_MISMATCH source/default adoption inflated")
        return
    if bool(payload.get("technical_art_target_host_adopted", true)):
        fail("RELATIVE_FACET_PHASE_MOTION_MISMATCH Technical Art authority inflated")
        return
    if bool(payload.get("runtime_controller_or_state_machine_accepted", true)) or bool(payload.get("gameplay_accepted", true)):
        fail("RELATIVE_FACET_PHASE_MOTION_MISMATCH Runtime/gameplay authority inflated")
        return
    if int(payload.get("sample_rate_hz", 0)) != 40 or int(payload.get("endpoint_inclusive_sample_count", 0)) != 101:
        fail("RELATIVE_FACET_PHASE_MOTION_MISMATCH authored sample grid drift")
        return
    if absf(float(payload.get("duration_s", -1.0)) - 2.5) > 0.000001:
        fail("RELATIVE_FACET_PHASE_MOTION_MISMATCH duration drift")
        return
    if absf(float(payload.get("body_phase_deg", 999.0))) > 0.000001:
        fail("RELATIVE_FACET_PHASE_MOTION_MISMATCH body source phase drift")
        return
    if absf(float(payload.get("lid_phase_deg", 999.0)) - 15.0) > 0.000001:
        fail("RELATIVE_FACET_PHASE_MOTION_MISMATCH lid source phase drift")
        return
    if absf(float(payload.get("relative_lid_minus_body_phase_deg", 999.0)) - 15.0) > 0.000001:
        fail("RELATIVE_FACET_PHASE_MOTION_MISMATCH relative source phase drift")
        return
    if float(payload.get("phase_independent_radial_clearance_lower_bound_m", 0.0)) < 0.001 - 0.000000000001:
        fail("RELATIVE_FACET_PHASE_MOTION_MISMATCH pinned radial lower bound drift")
        return

    var axis := vec3(payload["hinge_axis"])
    if axis.distance_to(Vector3(1.0, 0.0, 0.0)) > 0.000000001:
        fail("RELATIVE_FACET_PHASE_MOTION_MISMATCH hinge axis drift")
        return
    var origin := vec3(payload["hinge_origin_m"])
    var rig_limit: Array = payload.get("rig_angle_limit_deg", [])
    if rig_limit.size() != 2 or absf(float(rig_limit[0])) > 0.000001 or absf(float(rig_limit[1]) - 110.0) > 0.000001:
        fail("RELATIVE_FACET_PHASE_MOTION_MISMATCH Rigging owner range drift")
        return

    var samples: Array = payload.get("samples", [])
    var witnesses: Array = payload.get("witnesses", [])
    if samples.size() != 101 or witnesses.size() != 10:
        fail("RELATIVE_FACET_PHASE_MOTION_MISMATCH witness/sample count drift")
        return

    var stage := Node3D.new()
    stage.name = "AXM_ANIMATION_RELATIVE_FACET_PHASE_STAGE"
    get_root().add_child(stage)

    var body := Node3D.new()
    body.name = "body_shell"
    stage.add_child(body)

    var lid := Node3D.new()
    lid.name = "lid_shell"
    lid.position = origin
    stage.add_child(lid)

    var parent_mutation := OS.get_environment("AXM_MUTATE_PARENT")
    var phase_mutation := OS.get_environment("AXM_MUTATE_PHASE")
    var nodes := {}
    var owners := {}
    var radial_kinds := {}
    var expected_parent_names := {}
    for row_value in witnesses:
        var row := row_value as Dictionary
        var wid := String(row.get("id", ""))
        var owner := String(row.get("owner", ""))
        var expected_parent := String(row.get("expected_parent", ""))
        if wid == "" or not (owner in ["body", "lid"]) or not (expected_parent in ["lid_shell", "body_shell"]):
            fail("RELATIVE_FACET_PHASE_MOTION_MISMATCH invalid witness payload")
            return
        var actual_parent := expected_parent
        if parent_mutation == wid:
            actual_parent = "body_shell" if expected_parent == "lid_shell" else "lid_shell"

        var node := Node3D.new()
        node.name = wid
        var neutral := vec3(row["neutral_witness_m"])
        if actual_parent == "lid_shell":
            node.position = neutral - origin
            if phase_mutation == wid:
                node.position = rotate_local_x(node.position, -15.0)
            lid.add_child(node)
        else:
            node.position = neutral
            if phase_mutation == wid:
                var local := neutral - origin
                node.position = origin + rotate_local_x(local, 15.0)
            body.add_child(node)
        nodes[wid] = node
        owners[wid] = owner
        radial_kinds[wid] = String(row.get("radial_kind", ""))
        expected_parent_names[wid] = expected_parent

    var animation := Animation.new()
    animation.length = 2.5
    animation.loop_mode = Animation.LOOP_NONE
    var track := animation.add_track(Animation.TYPE_VALUE)
    animation.track_set_path(track, NodePath("lid_shell:rotation:x"))
    animation.track_set_interpolation_type(track, Animation.INTERPOLATION_NEAREST)
    animation.value_track_set_update_mode(track, Animation.UPDATE_DISCRETE)

    var peak_open_angle := -1.0
    var peak_sample_index := -1
    for sample_value in samples:
        var sample := sample_value as Dictionary
        var open_angle := float(sample["lid_open_angle_deg"])
        if open_angle > peak_open_angle:
            peak_open_angle = open_angle
            peak_sample_index = int(sample["index"])
        if open_angle < -0.000001 or open_angle > 110.000001:
            fail("RELATIVE_FACET_PHASE_MOTION_MISMATCH authored motion escaped Rigging range")
            return
        animation.track_insert_key(track, float(sample["time_s"]), deg_to_rad(float(sample["lid_mathematical_rotation_deg"])))
    if animation.track_get_key_count(track) != 101:
        fail("RELATIVE_FACET_PHASE_MOTION_MISMATCH AnimationPlayer track lost authored keys")
        return
    if absf(peak_open_angle - 100.0) > 0.000001:
        fail("RELATIVE_FACET_PHASE_MOTION_MISMATCH frozen 100deg peak drift")
        return

    var player := AnimationPlayer.new()
    player.name = "AXM_RELATIVE_FACET_PHASE_PLAYER"
    stage.add_child(player)
    player.root_node = NodePath("..")
    var library := AnimationLibrary.new()
    library.add_animation(MOTION_NAME, animation)
    player.add_animation_library("", library)
    player.play(MOTION_NAME)
    player.pause()

    var neutral_positions := {}
    var max_position_residual := 0.0
    var max_phase_residual := 0.0
    var max_body_world_drift := 0.0
    var max_lid_outer_world_move := 0.0
    var max_lid_bore_world_move := 0.0
    var observed_sample_count := 0
    var observed_initial_lid_phase := 0.0
    var observed_peak_lid_phase := 0.0

    for sample_value in samples:
        var sample := sample_value as Dictionary
        var sample_index := int(sample["index"])
        player.seek(float(sample["time_s"]), true)
        player.advance(0.0)
        observed_sample_count += 1

        for row_value in witnesses:
            var row := row_value as Dictionary
            var wid := String(row["id"])
            var node = nodes[wid] as Node3D
            var expected := expected_position(sample, wid)
            var observed: Vector3 = node.global_position
            var residual := observed.distance_to(expected)
            max_position_residual = maxf(max_position_residual, residual)
            if residual > POSITION_TOL_M:
                fail("RELATIVE_FACET_PHASE_MOTION_MISMATCH %s sample=%d position residual_m=%.12f" % [wid, sample_index, residual])
                return

            var observed_phase := phase_deg(observed, origin)
            var expected_phase_deg := expected_phase(sample, wid)
            var phase_residual := phase_delta_deg(observed_phase, expected_phase_deg)
            max_phase_residual = maxf(max_phase_residual, phase_residual)
            if phase_residual > PHASE_TOL_DEG:
                fail("RELATIVE_FACET_PHASE_MOTION_MISMATCH %s sample=%d phase residual_deg=%.9f" % [wid, sample_index, phase_residual])
                return

            if sample_index == 0:
                neutral_positions[wid] = observed
                if wid == "l0_outer":
                    observed_initial_lid_phase = observed_phase
            elif String(owners[wid]) == "body":
                max_body_world_drift = maxf(max_body_world_drift, observed.distance_to(neutral_positions[wid]))
            elif String(radial_kinds[wid]) == "outer":
                max_lid_outer_world_move = maxf(max_lid_outer_world_move, observed.distance_to(neutral_positions[wid]))
            else:
                max_lid_bore_world_move = maxf(max_lid_bore_world_move, observed.distance_to(neutral_positions[wid]))

            if sample_index == peak_sample_index and wid == "l0_outer":
                observed_peak_lid_phase = observed_phase

    player.seek(2.5, true)
    player.advance(0.0)
    var endpoint_closure := 0.0
    for row_value in witnesses:
        var row := row_value as Dictionary
        var wid := String(row["id"])
        endpoint_closure = maxf(endpoint_closure, (nodes[wid] as Node3D).global_position.distance_to(neutral_positions[wid]))
        var expected_parent := String(expected_parent_names[wid])
        var actual_parent := String((nodes[wid] as Node3D).get_parent().name)
        if actual_parent != expected_parent:
            fail("RELATIVE_FACET_PHASE_MOTION_MISMATCH parent identity drift for " + wid)
            return

    if max_body_world_drift > POSITION_TOL_M:
        fail("RELATIVE_FACET_PHASE_MOTION_MISMATCH body-owned phase witness moved under lid animation")
        return
    if max_lid_outer_world_move < 0.03 or max_lid_bore_world_move < 0.015:
        fail("RELATIVE_FACET_PHASE_MOTION_MISMATCH lid-owned phase witnesses did not receive expected motion")
        return
    if endpoint_closure > POSITION_TOL_M:
        fail("RELATIVE_FACET_PHASE_MOTION_MISMATCH endpoint did not close")
        return
    if phase_delta_deg(observed_initial_lid_phase, 15.0) > PHASE_TOL_DEG:
        fail("RELATIVE_FACET_PHASE_MOTION_MISMATCH source +15deg lid phase missing at neutral")
        return
    if phase_delta_deg(observed_peak_lid_phase, -85.0) > PHASE_TOL_DEG:
        fail("RELATIVE_FACET_PHASE_MOTION_MISMATCH source phase was not composed once with -100deg peak motion")
        return

    receipt["result"] = "PASS_OBJECT_ANIMATION_GODOT_RELATIVE_FACET_PHASE_MOTION_REBIND"
    receipt["exact_animation_head"] = payload["exact_animation_head"]
    receipt["asset_id"] = payload["asset_id"]
    receipt["source_successor_head"] = payload["source_successor_head"]
    receipt["source_successor_blob"] = payload["source_successor_blob"]
    receipt["rigging_receiver_head"] = payload["rigging_receiver_head"]
    receipt["rigging_receiver_blob"] = payload["rigging_receiver_blob"]
    receipt["sample_rate_hz"] = 40
    receipt["duration_s"] = 2.5
    receipt["endpoint_inclusive_sample_count"] = 101
    receipt["observed_sample_count"] = observed_sample_count
    receipt["animationplayer_track_count"] = 1
    receipt["animationplayer_key_count"] = animation.track_get_key_count(track)
    receipt["animation_interpolation"] = "NEAREST"
    receipt["animation_update_mode"] = "DISCRETE_AUTHORED_SAMPLES"
    receipt["body_source_phase_deg"] = 0.0
    receipt["lid_source_phase_deg"] = 15.0
    receipt["peak_sample_index"] = peak_sample_index
    receipt["peak_lid_open_angle_deg"] = peak_open_angle
    receipt["observed_initial_lid_outer_phase_deg"] = observed_initial_lid_phase
    receipt["observed_peak_lid_outer_phase_deg"] = observed_peak_lid_phase
    receipt["maximum_world_position_residual_m"] = max_position_residual
    receipt["maximum_effective_phase_residual_deg"] = max_phase_residual
    receipt["maximum_body_witness_world_drift_m"] = max_body_world_drift
    receipt["maximum_lid_outer_witness_world_move_m"] = max_lid_outer_world_move
    receipt["maximum_lid_bore_witness_world_move_m"] = max_lid_bore_world_move
    receipt["endpoint_witness_closure_m"] = endpoint_closure
    receipt["phase_independent_radial_clearance_lower_bound_m"] = payload["phase_independent_radial_clearance_lower_bound_m"]
    receipt["negative_parent_mutation_requested"] = parent_mutation
    receipt["negative_phase_mutation_requested"] = phase_mutation
    write_receipt()
    print(JSON.stringify(receipt, "  "))
    quit(0)
