extends SceneTree

const GLB_PATH := "res://generated/object-rigid-components-rebound.glb"
const TECH_RECEIPT_PATH := "res://generated/uc-rigid-scene-handoff-receipt.json"
const SEQUENCE_PATH := "res://generated/lid-latch-motion-evidence.json"
const LATCH_RIG_RECEIPT_PATH := "res://generated/front-latch-articulation.receipt.json"
const KEEPER_RIG_RECEIPT_PATH := "res://generated/lid-keeper-socket-binding.receipt.json"
const CONTRACT_PATH := "res://generated/lid-keeper-socket-motion-rebind-001.json"
const TARGET_RECEIPT_PATH := "res://keeper-socket-motion-rebind-receipt.json"
const MOTION_NAME := "lid_latch_open_hold_close_keeper_socket_rebind"
const EPS_DEG := 0.00001
const EPS_M := 0.000001

var receipt: Dictionary = {
    "schema": "axm.object-animation-keeper-socket-target-proof/v0.1",
    "state": "NOT_RUN",
    "promotion_effect": "NONE",
    "truth_boundary": {
        "runtime_controller_or_state_machine": false,
        "gameplay_acceptance": false,
        "scheduler_delivery_certified": false,
        "physics_or_latch_mechanism_accepted": false,
        "perceptual_acceptance": false
    }
}

func read_json(path: String) -> Dictionary:
    if not FileAccess.file_exists(path):
        return {}
    var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
    if parsed is Dictionary:
        return parsed as Dictionary
    return {}

func sha256_file(path: String) -> String:
    var ctx := HashingContext.new()
    ctx.start(HashingContext.HASH_SHA256)
    ctx.update(FileAccess.get_file_as_bytes(path))
    return ctx.finish().hex_encode()

func write_receipt() -> void:
    var file := FileAccess.open(TARGET_RECEIPT_PATH, FileAccess.WRITE)
    if file != null:
        file.store_string(JSON.stringify(receipt, "  ") + "\n")
        file.close()

func fail(message: String) -> void:
    receipt["state"] = "FAIL_TARGET_HOST_KEEPER_SOCKET_MOTION_REBIND"
    receipt["failure"] = message
    write_receipt()
    push_error(message)
    quit(1)

func find_node_named(root: Node, wanted: String) -> Node3D:
    if String(root.name) == wanted and root is Node3D:
        return root as Node3D
    for child_value in root.get_children():
        var child: Node = child_value as Node
        var found: Node3D = find_node_named(child, wanted)
        if found != null:
            return found
    return null

func mesh_center(node: Node3D) -> Vector3:
    if not (node is MeshInstance3D):
        fail("expected MeshInstance3D: " + String(node.name))
        return Vector3.ZERO
    var mesh_node: MeshInstance3D = node as MeshInstance3D
    if mesh_node.mesh == null:
        fail("mesh missing: " + String(node.name))
        return Vector3.ZERO
    return mesh_node.global_transform * mesh_node.mesh.get_aabb().get_center()

func source_to_uc(values: Array) -> Vector3:
    if values.size() != 3:
        fail("malformed source vec3")
        return Vector3.ZERO
    return Vector3(float(values[0]), float(values[2]), float(values[1]))

func station_lookup(rows: Array) -> Dictionary:
    var out: Dictionary = {}
    for row_value in rows:
        var row: Dictionary = row_value as Dictionary
        out[String(row["station_id"])] = row
    return out

func keeper_reference_lookup(keeper_rig: Dictionary) -> Dictionary:
    var out: Dictionary = {}
    var sweep: Array = keeper_rig.get("sweep", [])
    for row_value in sweep:
        var row: Dictionary = row_value as Dictionary
        var angle: int = int(row.get("open_angle_deg", -999))
        if angle == 0 or angle == 50 or angle == 100:
            var keepers: Dictionary = {}
            var keeper_rows: Array = row.get("keepers", [])
            for keeper_value in keeper_rows:
                var keeper: Dictionary = keeper_value as Dictionary
                var center_values: Array = keeper["center_m"]
                keepers[String(keeper["keeper"])] = source_to_uc(center_values)
            out[str(angle)] = keepers
    return out

func keeper_local_drift(lid: Node3D, keeper: Node3D, neutral_local: Vector3) -> float:
    return neutral_local.distance_to(lid.to_local(mesh_center(keeper)))

func add_discrete_track(animation: Animation, root: Node3D, node: Node3D, samples: Array, value_key: String) -> int:
    var track: int = animation.add_track(Animation.TYPE_VALUE)
    animation.track_set_path(track, NodePath(str(root.get_path_to(node)) + ":rotation_degrees"))
    animation.track_set_interpolation_type(track, Animation.INTERPOLATION_NEAREST)
    animation.value_track_set_update_mode(track, Animation.UPDATE_DISCRETE)
    for sample_value in samples:
        var sample: Dictionary = sample_value as Dictionary
        var t: float = float(sample["time_s"])
        var deg: float = -float(sample[value_key])
        animation.track_insert_key(track, t, Vector3(deg, 0.0, 0.0))
    return track

func _initialize() -> void:
    var technical: Dictionary = read_json(TECH_RECEIPT_PATH)
    var sequence: Dictionary = read_json(SEQUENCE_PATH)
    var latch_rig: Dictionary = read_json(LATCH_RIG_RECEIPT_PATH)
    var keeper_rig: Dictionary = read_json(KEEPER_RIG_RECEIPT_PATH)
    var contract: Dictionary = read_json(CONTRACT_PATH)

    if contract.get("schema") != "axm.object-animation-keeper-socket-motion-rebind/v0.1":
        fail("keeper-socket Animation contract missing or unsupported")
        return
    var target_host: Dictionary = contract["target_host"]
    var sequence_contract: Dictionary = contract["sequence"]
    var keeper_dependency: Dictionary = contract["keeper_rig_dependency"]
    var lever_dependency: Dictionary = contract["lower_lever_animation_dependency"]

    if technical.get("result") != String(target_host["required_result"]):
        fail("technical-art rigid-scene donor missing or not green")
        return
    if sequence.get("result") != "PASS_ORDERED_LATCH_RELEASE_LID_CLIP_REENGAGE_SEQUENCE":
        fail("animation sequence prerequisite missing or not green")
        return
    if latch_rig.get("result") != String(lever_dependency["required_result"]):
        fail("lower-lever Rigging prerequisite missing or not green")
        return
    if keeper_rig.get("result") != String(keeper_dependency["required_result"]):
        fail("keeper-socket Rigging prerequisite missing or not green")
        return
    if String(keeper_rig.get("source_sha256", "")) != String(contract["host_source_sha256"]):
        fail("keeper source identity drift")
        return

    var keeper_identity: Dictionary = keeper_rig["identity"]
    if String(keeper_identity.get("ownership_head", "")) != String(keeper_dependency["ownership_head"]):
        fail("keeper ownership donor drift")
        return
    if String(keeper_identity.get("lid_rig_head", "")) != String(keeper_dependency["lid_rig_head"]):
        fail("keeper lid-rig donor drift")
        return
    if String(keeper_identity.get("previous_rigging_target_binding_head", "")) != String(keeper_dependency["previous_rigging_target_binding_head"]):
        fail("keeper prior Rigging donor drift")
        return
    if String(sequence.get("sequence_id", "")) != String(sequence_contract["sequence_id"]):
        fail("sequence identity drift")
        return
    if String(sequence.get("base_lid_clip_digest", "")) != String(sequence_contract["base_lid_clip_digest"]):
        fail("base lid clip digest drift")
        return
    if int(sequence.get("endpoint_inclusive_sample_count", 0)) != int(sequence_contract["endpoint_inclusive_sample_count"]):
        fail("authored sample count drift")
        return
    if int(sequence.get("sample_rate_hz", 0)) != int(sequence_contract["sample_rate_hz"]):
        fail("authored sample rate drift")
        return
    if absf(float(sequence.get("duration_s", -1.0)) - float(sequence_contract["duration_s"])) > 0.000001:
        fail("authored duration drift")
        return
    if not FileAccess.file_exists(GLB_PATH):
        fail("exact rebound GLB missing")
        return
    if sha256_file(GLB_PATH) != String(technical.get("rebound_glb_sha256", "")):
        fail("rebound GLB identity mismatch")
        return

    var document := GLTFDocument.new()
    var state := GLTFState.new()
    var error: Error = document.append_from_file(GLB_PATH, state)
    if error != OK:
        fail("GLTFDocument append_from_file failed: " + str(error))
        return
    var generated: Node = document.generate_scene(state)
    if generated == null or not (generated is Node3D):
        fail("GLTFDocument generate_scene returned no Node3D")
        return
    var imported: Node3D = generated as Node3D
    get_root().add_child(imported)

    var lid: Node3D = find_node_named(imported, "lid_shell")
    var keeper0: Node3D = find_node_named(imported, "latch_0_keeper")
    var keeper1: Node3D = find_node_named(imported, "latch_1_keeper")
    var lever0: Node3D = find_node_named(imported, "latch_0_lever")
    var lever1: Node3D = find_node_named(imported, "latch_1_lever")
    if lid == null or keeper0 == null or keeper1 == null or lever0 == null or lever1 == null:
        fail("required rigid component nodes missing")
        return
    if keeper0.get_parent() != lid or keeper1.get_parent() != lid:
        fail("source-owned keepers are not direct lid children")
        return
    if lever0.get_parent() == lid or lever1.get_parent() == lid:
        fail("front-panel-owned lever imported under lid")
        return

    for _i in range(3):
        await process_frame

    var neutral_keeper0_world: Vector3 = mesh_center(keeper0)
    var neutral_keeper1_world: Vector3 = mesh_center(keeper1)
    var neutral_keeper0_local: Vector3 = lid.to_local(neutral_keeper0_world)
    var neutral_keeper1_local: Vector3 = lid.to_local(neutral_keeper1_world)
    var neutral_lever0_world: Vector3 = mesh_center(lever0)
    var neutral_lever1_world: Vector3 = mesh_center(lever1)

    var rig_station_rows: Array = latch_rig.get("station_results", [])
    var rig_by_station: Dictionary = station_lookup(rig_station_rows)
    var samples: Array = sequence["samples"]
    var sample0: Dictionary = samples[0] as Dictionary
    var sample0_station_rows: Array = sample0["stations"]
    var sample0_stations: Dictionary = station_lookup(sample0_station_rows)
    if rig_by_station.size() != 2 or sample0_stations.size() != 2:
        fail("expected exactly two bilateral lower-lever stations")
        return

    var pivot_by_station: Dictionary = {}
    for station_id_value in sample0_stations.keys():
        var station_id: String = String(station_id_value)
        if not rig_by_station.has(station_id):
            fail("missing lower-lever rig row: " + station_id)
            return
        var station0: Dictionary = sample0_stations[station_id]
        var component: String = String(station0["lever_component"])
        var lever: Node3D = find_node_named(imported, component)
        if lever == null:
            fail("target lever node missing: " + component)
            return
        var rig_row: Dictionary = rig_by_station[station_id]
        var pivot_values: Array = rig_row["pivot_m"]
        var pivot := Node3D.new()
        pivot.name = "keeper_rebind_pivot_" + station_id
        pivot.position = source_to_uc(pivot_values)
        imported.add_child(pivot)
        lever.reparent(pivot, true)
        pivot_by_station[station_id] = pivot

    await process_frame
    await process_frame
    var wrapper_drift0: float = neutral_lever0_world.distance_to(mesh_center(lever0))
    var wrapper_drift1: float = neutral_lever1_world.distance_to(mesh_center(lever1))
    var neutral_wrapper_drift: float = maxf(wrapper_drift0, wrapper_drift1)
    if neutral_wrapper_drift > EPS_M:
        fail("proof-local lower-lever pivot wrappers changed neutral geometry")
        return

    var animation := Animation.new()
    animation.length = float(sequence["duration_s"])
    animation.loop_mode = Animation.LOOP_NONE
    var lid_track: int = add_discrete_track(animation, imported, lid, samples, "lid_mathematical_rotation_deg")
    var latch_tracks: Array = []
    for station_id_value in pivot_by_station.keys():
        var station_id: String = String(station_id_value)
        var pivot: Node3D = pivot_by_station[station_id]
        latch_tracks.append(add_discrete_track(animation, imported, pivot, samples, "latch_lever_angle_deg"))
    if animation.track_get_key_count(lid_track) != 101:
        fail("lid track did not receive 101 keys")
        return
    for track_value in latch_tracks:
        var track: int = int(track_value)
        if animation.track_get_key_count(track) != 101:
            fail("lower-lever track did not receive 101 keys")
            return

    var player := AnimationPlayer.new()
    player.name = "AXM_KEEPER_SOCKET_REBIND_PLAYER"
    imported.add_child(player)
    player.root_node = NodePath("..")
    var library := AnimationLibrary.new()
    library.add_animation(MOTION_NAME, animation)
    player.add_animation_library("", library)

    var refs: Dictionary = keeper_reference_lookup(keeper_rig)
    for required_angle in [0, 50, 100]:
        if not refs.has(str(required_angle)):
            fail("keeper Rigging receipt missing reference angle " + str(required_angle))
            return

    player.play(MOTION_NAME)
    player.pause()
    var max_lid_error_deg: float = 0.0
    var max_latch_error_deg: float = 0.0
    var max_keeper_local_drift_m: float = 0.0
    var max_rig_reference_center_error_m: float = 0.0
    var reference_hits: Dictionary = {"0": 0, "50": 0, "100": 0}
    var peak_min_keeper_move_m: float = 1000.0

    for row_value in samples:
        var row: Dictionary = row_value as Dictionary
        player.seek(float(row["time_s"]), true)
        player.advance(0.0)
        await process_frame

        var lid_error: float = absf(lid.rotation_degrees.x + float(row["lid_mathematical_rotation_deg"]))
        max_lid_error_deg = maxf(max_lid_error_deg, lid_error)
        for station_id_value in pivot_by_station.keys():
            var station_id: String = String(station_id_value)
            var pivot: Node3D = pivot_by_station[station_id]
            var latch_error: float = absf(pivot.rotation_degrees.x + float(row["latch_lever_angle_deg"]))
            max_latch_error_deg = maxf(max_latch_error_deg, latch_error)

        var drift0: float = keeper_local_drift(lid, keeper0, neutral_keeper0_local)
        var drift1: float = keeper_local_drift(lid, keeper1, neutral_keeper1_local)
        max_keeper_local_drift_m = maxf(max_keeper_local_drift_m, maxf(drift0, drift1))

        var open_angle: float = float(row["lid_open_angle_deg"])
        var ref_angle: int = -1
        for candidate in [0, 50, 100]:
            if absf(open_angle - float(candidate)) <= 0.0000001:
                ref_angle = int(candidate)
                break
        if ref_angle >= 0:
            var ref: Dictionary = refs[str(ref_angle)]
            var ref0: Vector3 = ref["latch_0_keeper"]
            var ref1: Vector3 = ref["latch_1_keeper"]
            var err0: float = mesh_center(keeper0).distance_to(ref0)
            var err1: float = mesh_center(keeper1).distance_to(ref1)
            max_rig_reference_center_error_m = maxf(max_rig_reference_center_error_m, maxf(err0, err1))
            reference_hits[str(ref_angle)] = int(reference_hits[str(ref_angle)]) + 1

        if absf(open_angle - 100.0) <= 0.0000001:
            var move0: float = neutral_keeper0_world.distance_to(mesh_center(keeper0))
            var move1: float = neutral_keeper1_world.distance_to(mesh_center(keeper1))
            peak_min_keeper_move_m = minf(peak_min_keeper_move_m, minf(move0, move1))

    if max_lid_error_deg > EPS_DEG or max_latch_error_deg > EPS_DEG:
        fail("AnimationPlayer authored-sample transform divergence")
        return
    if max_keeper_local_drift_m > EPS_M:
        fail("lid-owned keeper local socket drift during authored motion")
        return
    if max_rig_reference_center_error_m > EPS_M:
        fail("target-host keeper center diverged from Rigging reference")
        return
    if int(reference_hits["0"]) < 2 or int(reference_hits["50"]) < 2 or int(reference_hits["100"]) < 2:
        fail("insufficient exact 0/50/100 Rigging reference hits")
        return
    if peak_min_keeper_move_m < 0.03:
        fail("keeper did not leave neutral during 100-degree lid motion")
        return

    player.seek(0.0, true)
    player.advance(0.0)
    player.stop()
    player.play(MOTION_NAME)
    var live_frames: int = 0
    var live_max_keeper_local_drift_m: float = 0.0
    var live_max_lid_rotation_deg: float = 0.0
    while player.is_playing():
        await process_frame
        live_frames += 1
        var live_drift0: float = keeper_local_drift(lid, keeper0, neutral_keeper0_local)
        var live_drift1: float = keeper_local_drift(lid, keeper1, neutral_keeper1_local)
        live_max_keeper_local_drift_m = maxf(live_max_keeper_local_drift_m, maxf(live_drift0, live_drift1))
        live_max_lid_rotation_deg = maxf(live_max_lid_rotation_deg, absf(lid.rotation_degrees.x))
        if live_frames > 2000:
            fail("capture-free AnimationPlayer play-path guard exceeded")
            return

    if live_frames < 2 or live_max_lid_rotation_deg < 80.0:
        fail("capture-free AnimationPlayer path did not exercise meaningful motion")
        return
    if live_max_keeper_local_drift_m > EPS_M:
        fail("keeper local socket drift during capture-free play path")
        return

    player.seek(float(sequence["duration_s"]), true)
    player.advance(0.0)
    await process_frame
    var endpoint_keeper0_drift: float = neutral_keeper0_world.distance_to(mesh_center(keeper0))
    var endpoint_keeper1_drift: float = neutral_keeper1_world.distance_to(mesh_center(keeper1))
    var endpoint_keeper_world_drift_m: float = maxf(endpoint_keeper0_drift, endpoint_keeper1_drift)
    var endpoint_lever0_drift: float = neutral_lever0_world.distance_to(mesh_center(lever0))
    var endpoint_lever1_drift: float = neutral_lever1_world.distance_to(mesh_center(lever1))
    var endpoint_lever_world_drift_m: float = maxf(endpoint_lever0_drift, endpoint_lever1_drift)
    if endpoint_keeper_world_drift_m > EPS_M or endpoint_lever_world_drift_m > EPS_M:
        fail("unchanged sequence failed neutral endpoint closure")
        return

    receipt["state"] = "PASS_TARGET_HOST_KEEPER_SOCKET_MOTION_REBIND_101_SAMPLES"
    receipt["asset_id"] = String(contract["asset_id"])
    receipt["contract_id"] = String(contract["contract_id"])
    receipt["source_sha256"] = String(contract["host_source_sha256"])
    receipt["keeper_rig_head"] = String(keeper_dependency["exact_head"])
    receipt["technical_art_head"] = String(target_host["technical_art_head"])
    receipt["uc_head"] = String(target_host["uc_head"])
    receipt["sequence_id"] = String(sequence["sequence_id"])
    receipt["base_lid_clip_digest"] = String(sequence["base_lid_clip_digest"])
    receipt["duration_s"] = float(sequence["duration_s"])
    receipt["sample_rate_hz"] = int(sequence["sample_rate_hz"])
    receipt["authored_sample_count"] = int(sequence["endpoint_inclusive_sample_count"])
    receipt["animationplayer_track_count"] = animation.get_track_count()
    receipt["animationplayer_key_counts"] = [animation.track_get_key_count(lid_track), animation.track_get_key_count(int(latch_tracks[0])), animation.track_get_key_count(int(latch_tracks[1]))]
    receipt["max_lid_sample_seek_error_deg"] = max_lid_error_deg
    receipt["max_latch_sample_seek_error_deg"] = max_latch_error_deg
    receipt["max_keeper_lid_local_socket_drift_m"] = max_keeper_local_drift_m
    receipt["max_keeper_rig_reference_center_error_m"] = max_rig_reference_center_error_m
    receipt["rig_reference_hits"] = reference_hits
    receipt["peak_min_keeper_world_move_m"] = peak_min_keeper_move_m
    receipt["capture_free_play_path_frames"] = live_frames
    receipt["capture_free_play_path_max_lid_rotation_deg"] = live_max_lid_rotation_deg
    receipt["capture_free_play_path_max_keeper_local_socket_drift_m"] = live_max_keeper_local_drift_m
    receipt["endpoint_keeper_world_drift_m"] = endpoint_keeper_world_drift_m
    receipt["endpoint_lever_world_drift_m"] = endpoint_lever_world_drift_m
    receipt["motion_mutation"] = "NONE"
    receipt["renderer_boundary"] = "Godot 4.7.2 GL Compatibility target-host structural motion observation. Authored-sample seeks plus capture-free AnimationPlayer.play() exercise keeper socket continuity only; no scheduler delivery, controller/state-machine, physics/gameplay or perceptual acceptance."
    write_receipt()
    print(JSON.stringify(receipt, "  "))
    quit(0)
