extends SceneTree

const GLB_PATH: String = "res://generated/object-rigid-components-rebound.glb"
const TECH_RECEIPT_PATH: String = "res://generated/uc-rigid-scene-handoff-receipt.json"
const SEQUENCE_PATH: String = "res://generated/lid-latch-motion-evidence.json"
const RIG_RECEIPT_PATH: String = "res://generated/front-latch-articulation.receipt.json"
const TARGET_RECEIPT_PATH: String = "res://runtime-animation-key-budget-receipt.json"
const DENSE_RESOURCE_PATH: String = "res://runtime-animation-dense-control.tres"
const COMPACT_RESOURCE_PATH: String = "res://runtime-animation-constant-span-compact.tres"
const DENSE_NAME: String = "dense_101_key_control"
const COMPACT_NAME: String = "constant_span_compact"
const EPS_DEG: float = 0.0001
const EPS_M: float = 0.000001
const FLAT_EPS_DEG: float = 0.000000001

var receipt: Dictionary = {
    "schema": "axm.object-animationplayer-key-budget-proof/v0.1",
    "state": "NOT_RUN",
    "promotion_effect": "NONE",
    "optimization_policy": "REMOVE_ONLY_INTERIOR_KEYS_WHERE_PREVIOUS_CURRENT_NEXT_TARGET_VALUES_ARE_EQUAL",
    "renderer_boundary": "Godot 4.7.2 GL Compatibility; exact UC rigid-scene import; proof-resource serialization and deterministic seek comparison only. No wall-clock/device memory/FPS/controller claim."
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

func file_size(path: String) -> int:
    return FileAccess.get_file_as_bytes(path).size()

func write_receipt() -> void:
    var file: FileAccess = FileAccess.open(TARGET_RECEIPT_PATH, FileAccess.WRITE)
    if file != null:
        file.store_string(JSON.stringify(receipt, "  ") + "\n")
        file.close()

func fail(message: String) -> void:
    receipt["state"] = "FAIL_TARGET_HOST_ANIMATION_KEY_BUDGET_PROOF"
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

func target_value(sample: Dictionary, value_key: String) -> float:
    return -float(sample[value_key])

func dense_indices(samples: Array) -> Array[int]:
    var out: Array[int] = []
    for i: int in range(samples.size()):
        out.append(i)
    return out

func lossless_constant_span_indices(samples: Array, value_key: String) -> Array[int]:
    var out: Array[int] = []
    for i: int in range(samples.size()):
        if i == 0 or i == samples.size() - 1:
            out.append(i)
            continue
        var prev: float = target_value(samples[i - 1] as Dictionary, value_key)
        var cur: float = target_value(samples[i] as Dictionary, value_key)
        var next: float = target_value(samples[i + 1] as Dictionary, value_key)
        var flat_left: bool = absf(prev - cur) <= FLAT_EPS_DEG
        var flat_right: bool = absf(cur - next) <= FLAT_EPS_DEG
        if not (flat_left and flat_right):
            out.append(i)
    return out

func add_rotation_track(animation: Animation, root: Node3D, node: Node3D, samples: Array, value_key: String, indices: Array[int]) -> int:
    var track: int = animation.add_track(Animation.TYPE_VALUE)
    animation.track_set_path(track, NodePath(str(root.get_path_to(node)) + ":rotation_degrees"))
    animation.track_set_interpolation_type(track, Animation.INTERPOLATION_LINEAR)
    animation.value_track_set_update_mode(track, Animation.UPDATE_CONTINUOUS)
    for index: int in indices:
        var sample: Dictionary = samples[index] as Dictionary
        animation.track_insert_key(track, float(sample["time_s"]), Vector3(target_value(sample, value_key), 0.0, 0.0))
    return track

func build_animation(imported: Node3D, lid: Node3D, pivots: Dictionary, samples: Array, lid_indices: Array[int], latch_indices: Array[int]) -> Dictionary:
    var animation: Animation = Animation.new()
    animation.length = 2.5
    animation.loop_mode = Animation.LOOP_NONE
    var lid_track: int = add_rotation_track(animation, imported, lid, samples, "lid_mathematical_rotation_deg", lid_indices)
    var latch_tracks: Array[int] = []
    var station_ids: Array = pivots.keys()
    station_ids.sort()
    for station_value: Variant in station_ids:
        var station_id: String = String(station_value)
        var pivot: Node3D = pivots[station_id] as Node3D
        latch_tracks.append(add_rotation_track(animation, imported, pivot, samples, "latch_lever_angle_deg", latch_indices))
    return {"animation": animation, "lid_track": lid_track, "latch_tracks": latch_tracks}

func sample_state(player: AnimationPlayer, animation_name: String, t: float, lid: Node3D, pivots: Dictionary, lever0: Node3D, lever1: Node3D) -> Dictionary:
    player.stop()
    player.play(animation_name)
    player.pause()
    player.seek(t, true)
    player.advance(0.0)
    var station_ids: Array = pivots.keys()
    station_ids.sort()
    var latch_values: Dictionary = {}
    for station_value: Variant in station_ids:
        var station_id: String = String(station_value)
        latch_values[station_id] = float((pivots[station_id] as Node3D).rotation_degrees.x)
    return {
        "lid_deg": float(lid.rotation_degrees.x),
        "latches_deg": latch_values,
        "lid_center": world_mesh_center(lid),
        "lever0_center": world_mesh_center(lever0),
        "lever1_center": world_mesh_center(lever1)
    }

func collect_mesh_resource_ids(node: Node, rows: Array) -> void:
    if node is MeshInstance3D:
        var instance: MeshInstance3D = node as MeshInstance3D
        var row: Dictionary = {"name": String(instance.name), "node_id": int(instance.get_instance_id()), "mesh_id": 0, "material_ids": []}
        if instance.mesh != null:
            row["mesh_id"] = int(instance.mesh.get_instance_id())
            var material_ids: Array[int] = []
            for surface: int in range(instance.mesh.get_surface_count()):
                var material: Material = instance.mesh.surface_get_material(surface)
                material_ids.append(int(material.get_instance_id()) if material != null else 0)
            row["material_ids"] = material_ids
        rows.append(row)
    for child: Node in node.get_children():
        collect_mesh_resource_ids(child, rows)

func mesh_resource_snapshot(root: Node) -> Array:
    var rows: Array = []
    collect_mesh_resource_ids(root, rows)
    rows.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return String(a["name"]) < String(b["name"]))
    return rows

func max_state_delta(a: Dictionary, b: Dictionary) -> Dictionary:
    var max_deg: float = absf(float(a["lid_deg"]) - float(b["lid_deg"]))
    var al: Dictionary = a["latches_deg"] as Dictionary
    var bl: Dictionary = b["latches_deg"] as Dictionary
    for key: Variant in al.keys():
        max_deg = maxf(max_deg, absf(float(al[key]) - float(bl[key])))
    var max_m: float = (a["lid_center"] as Vector3).distance_to(b["lid_center"] as Vector3)
    max_m = maxf(max_m, (a["lever0_center"] as Vector3).distance_to(b["lever0_center"] as Vector3))
    max_m = maxf(max_m, (a["lever1_center"] as Vector3).distance_to(b["lever1_center"] as Vector3))
    return {"max_deg": max_deg, "max_m": max_m}

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
    for _i: int in range(8):
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
        pivot.name = "runtime_key_budget_pivot_" + station_id
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

    var resource_snapshot_before: Array = mesh_resource_snapshot(imported)
    var all_indices: Array[int] = dense_indices(samples)
    var compact_lid_indices: Array[int] = lossless_constant_span_indices(samples, "lid_mathematical_rotation_deg")
    var compact_latch_indices: Array[int] = lossless_constant_span_indices(samples, "latch_lever_angle_deg")
    if all_indices.size() != 101:
        fail("dense key source is not 101 samples")
        return
    if compact_lid_indices.size() != 64 or compact_latch_indices.size() != 22:
        fail("unexpected lossless constant-span key counts")
        return

    var dense_build: Dictionary = build_animation(imported, lid, pivot_by_station, samples, all_indices, all_indices)
    var compact_build: Dictionary = build_animation(imported, lid, pivot_by_station, samples, compact_lid_indices, compact_latch_indices)
    var dense_animation: Animation = dense_build["animation"] as Animation
    var compact_animation: Animation = compact_build["animation"] as Animation
    var dense_latch_tracks: Array[int] = dense_build["latch_tracks"] as Array[int]
    var compact_latch_tracks: Array[int] = compact_build["latch_tracks"] as Array[int]
    var dense_counts: Array[int] = [dense_animation.track_get_key_count(int(dense_build["lid_track"])), dense_animation.track_get_key_count(dense_latch_tracks[0]), dense_animation.track_get_key_count(dense_latch_tracks[1])]
    var compact_counts: Array[int] = [compact_animation.track_get_key_count(int(compact_build["lid_track"])), compact_animation.track_get_key_count(compact_latch_tracks[0]), compact_animation.track_get_key_count(compact_latch_tracks[1])]
    if dense_counts != [101, 101, 101] or compact_counts != [64, 22, 22]:
        fail("track key counts do not match the bounded lossless compaction contract")
        return

    if ResourceSaver.save(dense_animation, DENSE_RESOURCE_PATH) != OK:
        fail("could not serialize dense control Animation resource")
        return
    if ResourceSaver.save(compact_animation, COMPACT_RESOURCE_PATH) != OK:
        fail("could not serialize compact Animation resource")
        return
    var dense_bytes: int = file_size(DENSE_RESOURCE_PATH)
    var compact_bytes: int = file_size(COMPACT_RESOURCE_PATH)
    if dense_bytes <= 0 or compact_bytes <= 0 or compact_bytes >= dense_bytes:
        fail("serialized compact Animation resource did not reduce proof-resource bytes")
        return

    var player: AnimationPlayer = AnimationPlayer.new()
    player.name = "AXM_RUNTIME_KEY_BUDGET_PLAYER"
    imported.add_child(player)
    player.root_node = NodePath("..")
    var library: AnimationLibrary = AnimationLibrary.new()
    library.add_animation(DENSE_NAME, dense_animation)
    library.add_animation(COMPACT_NAME, compact_animation)
    player.add_animation_library("", library)

    var max_rotation_delta_deg: float = 0.0
    var max_world_center_delta_m: float = 0.0
    var observation_count: int = 0
    var capture_times: Array[float] = [0.1125, 0.5125, 1.2375, 1.7625, 2.3875]
    var capture_rows: Array = []
    var compare_times: Array[float] = []
    for i: int in range(samples.size()):
        compare_times.append(float((samples[i] as Dictionary)["time_s"]))
        if i < samples.size() - 1:
            compare_times.append((float((samples[i] as Dictionary)["time_s"]) + float((samples[i + 1] as Dictionary)["time_s"])) * 0.5)

    for t: float in compare_times:
        var dense_state: Dictionary = sample_state(player, DENSE_NAME, t, lid, pivot_by_station, lever0, lever1)
        var compact_state: Dictionary = sample_state(player, COMPACT_NAME, t, lid, pivot_by_station, lever0, lever1)
        var delta: Dictionary = max_state_delta(dense_state, compact_state)
        max_rotation_delta_deg = maxf(max_rotation_delta_deg, float(delta["max_deg"]))
        max_world_center_delta_m = maxf(max_world_center_delta_m, float(delta["max_m"]))
        observation_count += 1

    if observation_count != 201:
        fail("expected 201 authored-key plus midpoint comparisons")
        return
    if max_rotation_delta_deg > EPS_DEG or max_world_center_delta_m > EPS_M:
        fail("constant-span key compaction changed target-host motion")
        return

    for capture_index: int in range(capture_times.size()):
        var t: float = capture_times[capture_index]
        sample_state(player, DENSE_NAME, t, lid, pivot_by_station, lever0, lever1)
        for _a: int in range(2):
            await process_frame
        var dense_image: Image = viewport.get_texture().get_image()
        if dense_image == null or dense_image.is_empty() or visible_pixels(dense_image) < 3000:
            fail("dense capture empty at " + str(t))
            return
        var dense_path: String = "res://runtime-key-budget-dense-%02d.png" % capture_index
        if dense_image.save_png(dense_path) != OK:
            fail("could not save dense capture")
            return

        sample_state(player, COMPACT_NAME, t, lid, pivot_by_station, lever0, lever1)
        for _b: int in range(2):
            await process_frame
        var compact_image: Image = viewport.get_texture().get_image()
        if compact_image == null or compact_image.is_empty() or visible_pixels(compact_image) < 3000:
            fail("compact capture empty at " + str(t))
            return
        var compact_path: String = "res://runtime-key-budget-compact-%02d.png" % capture_index
        if compact_image.save_png(compact_path) != OK:
            fail("could not save compact capture")
            return
        var dense_hash: String = sha256_file(dense_path)
        var compact_hash: String = sha256_file(compact_path)
        if dense_hash != compact_hash:
            fail("matched dense/compact retained capture differs at " + str(t))
            return
        capture_rows.append({"time_s": t, "dense_sha256": dense_hash, "compact_sha256": compact_hash, "byte_identical_png": true})

    var resource_snapshot_after: Array = mesh_resource_snapshot(imported)
    if resource_snapshot_before != resource_snapshot_after:
        fail("mesh/material/node resource identity changed during key-budget proof")
        return

    var dense_total_keys: int = dense_counts[0] + dense_counts[1] + dense_counts[2]
    var compact_total_keys: int = compact_counts[0] + compact_counts[1] + compact_counts[2]
    var key_reduction: int = dense_total_keys - compact_total_keys
    var key_reduction_pct: float = 100.0 * float(key_reduction) / float(dense_total_keys)
    var serialized_reduction: int = dense_bytes - compact_bytes
    var serialized_reduction_pct: float = 100.0 * float(serialized_reduction) / float(dense_bytes)

    receipt["state"] = "PASS_LOSSLESS_CONSTANT_SPAN_ANIMATION_KEY_COMPACTION"
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
    receipt["dense_key_counts"] = dense_counts
    receipt["compact_key_counts"] = compact_counts
    receipt["dense_total_keys"] = dense_total_keys
    receipt["compact_total_keys"] = compact_total_keys
    receipt["keys_removed"] = key_reduction
    receipt["key_reduction_percent"] = key_reduction_pct
    receipt["dense_serialized_resource_bytes"] = dense_bytes
    receipt["compact_serialized_resource_bytes"] = compact_bytes
    receipt["serialized_resource_bytes_removed"] = serialized_reduction
    receipt["serialized_resource_reduction_percent"] = serialized_reduction_pct
    receipt["dense_resource_sha256"] = sha256_file(DENSE_RESOURCE_PATH)
    receipt["compact_resource_sha256"] = sha256_file(COMPACT_RESOURCE_PATH)
    receipt["comparison_time_count"] = observation_count
    receipt["max_rotation_delta_deg"] = max_rotation_delta_deg
    receipt["max_world_mesh_center_delta_m"] = max_world_center_delta_m
    receipt["neutral_pivot_wrapper_max_drift_m"] = neutral_wrapper_drift
    receipt["matched_capture_count"] = capture_rows.size()
    receipt["captures"] = capture_rows
    receipt["mesh_resource_snapshot"] = resource_snapshot_after
    receipt["visual_tradeoff"] = "NONE_OBSERVED_FIVE_MATCHED_PNG_PAIRS_BYTE_IDENTICAL"
    receipt["truth_boundary"] = {
        "exact_animation_donor_consumed": true,
        "exact_uc_rebound_glb_imported": true,
        "only_interior_keys_of_flat_constant_spans_removed": true,
        "all_authored_keys_and_all_interval_midpoints_compared": true,
        "matched_retained_png_pairs_byte_identical": true,
        "mesh_material_node_resource_identity_preserved": true,
        "serialized_proof_resource_bytes_measured": true,
        "runtime_heap_or_vram_memory_measured": false,
        "wall_clock_playback_or_scheduler_profiled": false,
        "target_device_fps_or_gpu_time_measured": false,
        "controller_or_gameplay_acceptance": false,
        "final_animation_or_art_direction_acceptance": false
    }
    write_receipt()
    print("AXM OBJECT RUNTIME ANIMATION KEY BUDGET ", JSON.stringify(receipt))
    quit(0)
