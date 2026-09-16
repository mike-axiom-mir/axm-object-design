extends SceneTree

const GLB_PATH := "res://generated/object-rigid-components-rebound.glb"
const TECH_RECEIPT_PATH := "res://generated/uc-rigid-scene-handoff-receipt.json"
const SEQUENCE_PATH := "res://generated/lid-latch-motion-evidence.json"
const RIG_RECEIPT_PATH := "res://generated/front-latch-articulation.receipt.json"
const TARGET_RECEIPT_PATH := "res://animationplayer-target-receipt.json"
const MOTION_NAME := "lid_latch_open_hold_close_discrete_review"
const EPS_DEG := 0.00001
const EPS_M := 0.000001

var receipt := {
    "schema": "axm.object-animationplayer-target-proof/v0.1",
    "state": "NOT_RUN",
    "promotion_effect": "NONE",
    "renderer_boundary": "Godot 4.7.2 GL Compatibility; exact UC rigid-scene import plus AnimationPlayer discrete authored-sample seeks. No wall-clock pacing, controller/state-machine, physics, gameplay or final-motion acceptance."
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
    receipt["state"] = "FAIL_TARGET_HOST_ANIMATIONPLAYER_PROOF"
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

func pixel_diff_count(a: Image, b: Image) -> int:
    if a.get_width() != b.get_width() or a.get_height() != b.get_height():
        return -1
    var changed := 0
    for y in range(a.get_height()):
        for x in range(a.get_width()):
            var p := a.get_pixel(x, y)
            var q := b.get_pixel(x, y)
            var delta: float = maxf(absf(p.r-q.r), maxf(absf(p.g-q.g), absf(p.b-q.b)))
            if delta > 0.035:
                changed += 1
    return changed

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
    if int(sequence.get("endpoint_inclusive_sample_count", 0)) != 101 or int(sequence.get("sample_rate_hz", 0)) != 40:
        fail("unexpected authored sequence sample grid")
        return
    if absf(float(sequence.get("duration_s", -1.0)) - 2.5) > 0.000001:
        fail("unexpected authored sequence duration")
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
        fail("front-panel-owned lever imported under lid")
        return

    var rig_by_station := station_lookup(rig.get("station_results", []))
    var sample0_stations := station_lookup(sequence["samples"][0]["stations"])
    if rig_by_station.size() != 2 or sample0_stations.size() != 2:
        fail("expected exactly two bilateral latch stations")
        return

    var pivot_by_station := {}
    var lever_node_by_station := {}
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
        lever_node_by_station[station_id] = lever

    var animation := Animation.new()
    animation.length = 2.5
    animation.loop_mode = Animation.LOOP_NONE
    var lid_track := add_discrete_rotation_track(animation, imported, lid, sequence["samples"], "lid_mathematical_rotation_deg", true)
    var latch_tracks := []
    for station_id in pivot_by_station.keys():
        latch_tracks.append(add_discrete_rotation_track(animation, imported, pivot_by_station[station_id], sequence["samples"], "latch_lever_angle_deg", true))
    if animation.track_get_key_count(lid_track) != 101:
        fail("lid AnimationPlayer track did not receive all 101 authored samples")
        return
    for track in latch_tracks:
        if animation.track_get_key_count(track) != 101:
            fail("latch AnimationPlayer track did not receive all 101 authored samples")
            return

    var player := AnimationPlayer.new()
    player.name = "AXM_SAMPLED_REVIEW_PLAYER"
    imported.add_child(player)
    player.root_node = NodePath("..")
    var library := AnimationLibrary.new()
    library.add_animation(MOTION_NAME, animation)
    player.add_animation_library("", library)

    var viewport := make_viewport(imported)
    for _i in range(10):
        await process_frame

    var start_keeper := {"latch_0_keeper": world_mesh_center(keeper0), "latch_1_keeper": world_mesh_center(keeper1)}
    var start_lever := {"latch_0_lever": world_mesh_center(lever0), "latch_1_lever": world_mesh_center(lever1)}

    player.play(MOTION_NAME)
    player.pause()

    var selected_indices := [0, 5, 10, 25, 40, 50, 60, 90, 95, 100]
    var observed := []
    var max_lid_error := 0.0
    var max_latch_error := 0.0
    var captures := {}
    var image_by_index := {}
    for sample_index in selected_indices:
        var row = sequence["samples"][sample_index]
        var t := float(row["time_s"])
        player.seek(t, true)
        player.advance(0.0)
        for _j in range(4):
            await process_frame

        var expected_lid := -float(row["lid_mathematical_rotation_deg"])
        var lid_error := absf(lid.rotation_degrees.x - expected_lid)
        max_lid_error = maxf(max_lid_error, lid_error)
        var station_observed := {}
        for station_id in pivot_by_station.keys():
            var expected_latch := -float(row["latch_lever_angle_deg"])
            var pivot = pivot_by_station[station_id] as Node3D
            var error_deg := absf(pivot.rotation_degrees.x - expected_latch)
            max_latch_error = maxf(max_latch_error, error_deg)
            station_observed[station_id] = {"expected_target_rotation_deg_x": expected_latch, "observed_target_rotation_deg_x": pivot.rotation_degrees.x, "abs_error_deg": error_deg}

        var image := viewport.get_texture().get_image()
        if image == null or image.is_empty() or visible_pixels(image) < 3000:
            fail("target capture empty or insufficient at sample " + str(sample_index))
            return
        var capture_path := "res://frame-%03d.png" % sample_index
        if image.save_png(capture_path) != OK:
            fail("could not save target capture at sample " + str(sample_index))
            return
        captures[str(sample_index)] = {"time_s": t, "sha256": sha256_file(capture_path), "path": capture_path}
        image_by_index[sample_index] = image
        observed.append({"index": sample_index, "time_s": t, "expected_lid_target_deg_x": expected_lid, "observed_lid_target_deg_x": lid.rotation_degrees.x, "lid_abs_error_deg": lid_error, "stations": station_observed})

    if max_lid_error > EPS_DEG or max_latch_error > EPS_DEG:
        fail("AnimationPlayer sampled seek diverged from exact authored target transforms")
        return

    player.seek(float(sequence["samples"][10]["time_s"]), true)
    player.advance(0.0)
    var release_keeper_drift := maxf(start_keeper["latch_0_keeper"].distance_to(world_mesh_center(keeper0)), start_keeper["latch_1_keeper"].distance_to(world_mesh_center(keeper1)))
    var release_lever_move := minf(start_lever["latch_0_lever"].distance_to(world_mesh_center(lever0)), start_lever["latch_1_lever"].distance_to(world_mesh_center(lever1)))
    if release_keeper_drift > EPS_M or release_lever_move < 0.001:
        fail("release-complete target state does not preserve closed lid while moving both levers")
        return

    player.seek(float(sequence["samples"][40]["time_s"]), true)
    player.advance(0.0)
    var peak_keeper_move := minf(start_keeper["latch_0_keeper"].distance_to(world_mesh_center(keeper0)), start_keeper["latch_1_keeper"].distance_to(world_mesh_center(keeper1)))
    if peak_keeper_move < 0.03:
        fail("peak lid sample did not move both lid-owned keeper meshes materially")
        return

    player.seek(float(sequence["samples"][100]["time_s"]), true)
    player.advance(0.0)
    var end_keeper_drift := maxf(start_keeper["latch_0_keeper"].distance_to(world_mesh_center(keeper0)), start_keeper["latch_1_keeper"].distance_to(world_mesh_center(keeper1)))
    var end_lever_drift := maxf(start_lever["latch_0_lever"].distance_to(world_mesh_center(lever0)), start_lever["latch_1_lever"].distance_to(world_mesh_center(lever1)))
    if end_keeper_drift > EPS_M or end_lever_drift > EPS_M:
        fail("authored terminal target state did not return exact moving proof components to neutral")
        return

    var release_pixels := pixel_diff_count(image_by_index[0], image_by_index[10])
    var open_pixels := pixel_diff_count(image_by_index[0], image_by_index[40])
    var endpoint_pixels := pixel_diff_count(image_by_index[0], image_by_index[100])
    if release_pixels < 50:
        fail("closed versus release-complete visual delta is too small")
        return
    if open_pixels < 1500:
        fail("closed versus peak-open visual delta is too small")
        return
    if endpoint_pixels > 25:
        fail("neutral endpoint render drift is larger than bounded proof tolerance")
        return

    receipt["state"] = "PASS_TARGET_HOST_DISCRETE_ANIMATIONPLAYER_SAMPLED_SEEK"
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
    receipt["animationplayer_track_count"] = animation.get_track_count()
    receipt["animationplayer_key_counts"] = [animation.track_get_key_count(lid_track), animation.track_get_key_count(latch_tracks[0]), animation.track_get_key_count(latch_tracks[1])]
    receipt["animation_update_mode"] = "DISCRETE_AUTHORED_SAMPLES"
    receipt["animation_interpolation"] = "NEAREST"
    receipt["coordinate_conversion"] = "source [x,y,z] -> UC/glTF [x,z,y]; handedness flip requires target +X rotation = negative source mathematical +X rotation"
    receipt["max_lid_sample_seek_error_deg"] = max_lid_error
    receipt["max_latch_sample_seek_error_deg"] = max_latch_error
    receipt["release_keeper_drift_m"] = release_keeper_drift
    receipt["release_min_lever_move_m"] = release_lever_move
    receipt["peak_min_keeper_move_m"] = peak_keeper_move
    receipt["endpoint_keeper_drift_m"] = end_keeper_drift
    receipt["endpoint_lever_drift_m"] = end_lever_drift
    receipt["closed_to_release_changed_pixels"] = release_pixels
    receipt["closed_to_peak_changed_pixels"] = open_pixels
    receipt["closed_to_endpoint_changed_pixels"] = endpoint_pixels
    receipt["selected_sample_observations"] = observed
    receipt["captures"] = captures
    receipt["truth_boundary"] = {
        "exact_uc_rebound_glb_imported": true,
        "exact_animation_sequence_consumed": true,
        "animationplayer_resource_authored_in_proof_host": true,
        "discrete_exact_authored_sample_seek_equivalence_observed": true,
        "source_owned_keeper_parentage_preserved": true,
        "latch_proof_pivots_bound_to_exact_rig_receipt": true,
        "wall_clock_40hz_playback_pacing_observed": false,
        "continuous_interpolation_between_authored_samples": false,
        "runtime_controller_or_state_machine": false,
        "collision_physics_or_latch_retention": false,
        "gameplay_acceptance": false,
        "final_motion_or_art_direction_acceptance": false,
        "target_device_performance_acceptance": false
    }
    write_receipt()
    print("AXM OBJECT ANIMATIONPLAYER TARGET ", JSON.stringify(receipt))
    quit(0)
