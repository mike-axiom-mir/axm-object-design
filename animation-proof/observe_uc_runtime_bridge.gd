extends "res://observe_interpolation_v3.gd"

const BRIDGE_PATH: String = "res://generated/uc-animation-runtime-bridge.json"
const BRIDGE_RECEIPT_PATH: String = "res://uc-runtime-godot-bridge-receipt.json"
const BRIDGE_MOTION_NAME: String = "uc_runtime_clock_bound_object_motion"

func write_receipt() -> void:
    var file: FileAccess = FileAccess.open(BRIDGE_RECEIPT_PATH, FileAccess.WRITE)
    if file != null:
        file.store_string(JSON.stringify(receipt, "  ") + "\n")
        file.close()

func fail(message: String) -> void:
    receipt["state"] = "FAIL_UC_RUNTIME_CLOCK_TO_GODOT_ANIMATIONPLAYER_CHECKPOINTS"
    receipt["failure"] = message
    write_receipt()
    push_error(message)
    quit(1)

func linear_target(samples: Array, time_s: float, value_key: String) -> float:
    var sample_rate: float = 40.0
    var index_f: float = time_s * sample_rate
    var lo: int = floori(index_f)
    var hi: int = mini(lo + 1, samples.size() - 1)
    var fraction: float = index_f - float(lo)
    var a: Dictionary = samples[lo] as Dictionary
    var b: Dictionary = samples[hi] as Dictionary
    return -lerpf(float(a[value_key]), float(b[value_key]), fraction)

func _initialize() -> void:
    receipt = {
        "schema": "axm.object-uc-runtime-godot-clock-handoff-proof/v0.1",
        "state": "NOT_RUN",
        "promotion_effect": "NONE",
        "renderer_boundary": "Godot 4.7.2 GL Compatibility; consumes a retained UC adapter-neutral runtime replay handoff and seeks the exact Object AnimationPlayer clip to the UC-provided clip times. No embedded Python runtime, wall-clock pacing, controller/input, physics, gameplay or final-motion acceptance."
    }

    var technical: Dictionary = read_json(TECH_RECEIPT_PATH)
    var sequence: Dictionary = read_json(SEQUENCE_PATH)
    var rig: Dictionary = read_json(RIG_RECEIPT_PATH)
    var bridge: Dictionary = read_json(BRIDGE_PATH)
    if technical.get("result") != "PASS_OBJECT_SOURCE_OWNED_RIGID_PARTS_THROUGH_UC_SCENE_GRAPH":
        fail("technical-art rigid-scene donor missing or not green")
        return
    if sequence.get("result") != "PASS_ORDERED_LATCH_RELEASE_LID_CLIP_REENGAGE_SEQUENCE":
        fail("animation sequence prerequisite missing or not green")
        return
    if rig.get("result") != "PASS_BOUNDED_FRONT_LATCH_LEVER_ARTICULATION":
        fail("rigging articulation prerequisite missing or not green")
        return
    if bridge.get("result") != "PASS_UC_RUNTIME_OBJECT_TARGET_CLOCK_BINDING":
        fail("UC runtime clock binding missing or not green")
        return
    if bridge.get("target_adapter_policy") != "SEEK_TARGET_ANIMATIONPLAYER_TO_UC_CLIP_TIME_NO_RETIME":
        fail("unexpected target adapter policy")
        return
    if bridge.get("object_sequence_id") != sequence.get("sequence_id") or bridge.get("object_sequence_digest") != sequence.get("sequence_digest"):
        fail("UC runtime bridge is not bound to this exact Object sequence identity")
        return
    if bridge.get("exact_object_head") != sequence.get("exact_receiving_head"):
        fail("UC runtime bridge and sequence receiving heads differ")
        return
    if not FileAccess.file_exists(GLB_PATH):
        fail("exact rebound GLB missing")
        return
    var glb_sha: String = sha256_file(GLB_PATH)
    if glb_sha != String(technical.get("rebound_glb_sha256", "")):
        fail("rebound GLB identity mismatch")
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
        pivot.name = "uc_runtime_bridge_pivot_" + station_id
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
    player.name = "AXM_UC_RUNTIME_CLOCK_BRIDGE_PLAYER"
    imported.add_child(player)
    player.root_node = NodePath("..")
    var library: AnimationLibrary = AnimationLibrary.new()
    library.add_animation(BRIDGE_MOTION_NAME, animation)
    player.add_animation_library("", library)
    player.play(BRIDGE_MOTION_NAME)
    player.pause()

    var checkpoints: Array = bridge.get("checkpoints", []) as Array
    if checkpoints.size() != 5:
        fail("expected five retained UC runtime checkpoints")
        return

    var max_lid_clock_residual: float = 0.0
    var max_latch_clock_residual: float = 0.0
    var ordering_violation_count: int = 0
    var captures: Dictionary = {}
    var prior_time: float = -1.0

    for i: int in range(checkpoints.size()):
        var checkpoint: Dictionary = checkpoints[i] as Dictionary
        var t: float = float(checkpoint.get("time_s", -1.0))
        if t <= prior_time or t <= 0.0 or t >= 2.5:
            fail("invalid or unordered UC runtime checkpoint")
            return
        prior_time = t
        if checkpoint.get("runtime_state") != "operate" or checkpoint.get("runtime_clip") != sequence.get("sequence_id"):
            fail("UC runtime checkpoint left the exact Object operate clip")
            return

        player.seek(t, true)
        player.advance(0.0)
        for _j: int in range(2):
            await process_frame

        var expected_lid: float = linear_target(samples, t, "lid_mathematical_rotation_deg")
        var expected_latch: float = linear_target(samples, t, "latch_lever_angle_deg")
        var observed_lid: float = float(lid.rotation_degrees.x)
        var lid_residual: float = absf(observed_lid - expected_lid)
        max_lid_clock_residual = maxf(max_lid_clock_residual, lid_residual)
        if lid_residual > EPS_DEG:
            fail("Godot lid pose diverged from exact UC runtime clip-time handoff")
            return

        if t < 0.25 and absf(observed_lid) > EPS_DEG:
            ordering_violation_count += 1
        if t > 2.25 and absf(observed_lid) > EPS_DEG:
            ordering_violation_count += 1

        for station_key: Variant in pivot_by_station.keys():
            var pivot: Node3D = pivot_by_station[String(station_key)] as Node3D
            var observed_latch: float = float(pivot.rotation_degrees.x)
            var latch_residual: float = absf(observed_latch - expected_latch)
            max_latch_clock_residual = maxf(max_latch_clock_residual, latch_residual)
            if latch_residual > EPS_DEG:
                fail("Godot latch pose diverged from exact UC runtime clip-time handoff")
                return
            if t > 0.25 and t < 2.25 and absf(observed_latch + 50.0) > EPS_DEG:
                ordering_violation_count += 1

        var image: Image = viewport.get_texture().get_image()
        if image == null or image.is_empty() or visible_pixels(image) < 3000:
            fail("UC runtime bridge capture empty or insufficient at checkpoint " + str(i))
            return
        var capture_path: String = "res://uc-runtime-bridge-%02d.png" % i
        if image.save_png(capture_path) != OK:
            fail("could not save UC runtime bridge capture at checkpoint " + str(i))
            return
        captures[str(i)] = {"time_s": t, "sha256": sha256_file(capture_path), "path": capture_path}

    if ordering_violation_count != 0:
        fail("UC runtime checkpoint handoff violated release/lid/reengage ordering")
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
        fail("exact neutral lid endpoints were not preserved")
        return
    for station_key: Variant in pivot_by_station.keys():
        var station_id: String = String(station_key)
        if absf(float(start_latches[station_id])) > EPS_DEG or absf(float(end_latches[station_id])) > EPS_DEG:
            fail("exact neutral latch endpoints were not preserved")
            return

    receipt["state"] = "PASS_UC_RUNTIME_CLOCK_TO_GODOT_ANIMATIONPLAYER_CHECKPOINTS"
    receipt["godot_version"] = Engine.get_version_info()
    receipt["glb_sha256"] = glb_sha
    receipt["technical_art_object_head"] = technical.get("source_repository_head")
    receipt["uc_rigid_scene_commit"] = technical.get("observed_uc_commit")
    receipt["uc_runtime_commit"] = bridge.get("uc_runtime_commit")
    receipt["uc_runtime_module_sha256"] = bridge.get("uc_runtime_module_sha256")
    receipt["uc_runtime_source_sha256"] = bridge.get("uc_runtime_source_sha256")
    receipt["uc_runtime_commands_sha256"] = bridge.get("uc_runtime_commands_sha256")
    receipt["animation_sequence_head"] = sequence.get("exact_receiving_head")
    receipt["sequence_id"] = sequence.get("sequence_id")
    receipt["sequence_digest"] = sequence.get("sequence_digest")
    receipt["target_adapter_policy"] = bridge.get("target_adapter_policy")
    receipt["checkpoint_count"] = checkpoints.size()
    receipt["max_lid_clock_handoff_residual_deg"] = max_lid_clock_residual
    receipt["max_latch_clock_handoff_residual_deg"] = max_latch_clock_residual
    receipt["neutral_pivot_wrapper_max_drift_m"] = neutral_wrapper_drift
    receipt["ordering_violation_count"] = ordering_violation_count
    receipt["neutral_start"] = {"lid_deg_x": start_lid, "latches_deg_x": start_latches}
    receipt["neutral_end"] = {"lid_deg_x": end_lid, "latches_deg_x": end_latches}
    receipt["captures"] = captures
    receipt["truth_boundary"] = {
        "uc_adapter_neutral_runtime_replay_consumed": true,
        "exact_uc_runtime_clip_times_consumed_by_godot": true,
        "exact_animationplayer_target_pose_observed_at_each_checkpoint": true,
        "runtime_clip_retimed_by_technical_art": false,
        "embedded_uc_python_runtime_inside_godot": false,
        "wall_clock_playback_pacing_observed": false,
        "runtime_controller_or_input": false,
        "collision_physics_or_latch_retention": false,
        "gameplay_acceptance": false,
        "final_motion_or_art_direction_acceptance": false,
        "target_device_performance_acceptance": false
    }
    write_receipt()
    print("AXM UC RUNTIME -> GODOT CLOCK BRIDGE ", JSON.stringify(receipt))
    quit(0)
