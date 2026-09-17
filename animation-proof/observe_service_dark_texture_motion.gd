extends SceneTree

const GLB_PATH := "res://generated/service-dark-two-surface.glb"
const TECH_RECEIPT_PATH := "res://generated/technical-art-uc-texture-transport-receipt.json"
const SEQUENCE_PATH := "res://generated/lid-latch-motion-evidence.json"
const CONTRACT_PATH := "res://generated/service-dark-texture-motion-rebind-001.json"
const TARGET_RECEIPT_PATH := "res://service-dark-texture-motion-rebind-receipt.json"
const SAMPLE_CSV_PATH := "res://service-dark-texture-motion-samples.csv"
const MOTION_NAME := "service_dark_lid_motion_rebind_discrete_review"

var receipt := {
    "schema": "axm.object-animation-service-dark-texture-motion-rebind-evidence/v0.1",
    "result": "NOT_RUN",
    "promotion_effect": "NONE",
    "renderer_boundary": "Godot 4.7.2 target-host structural/material import plus AnimationPlayer discrete authored-sample seeks. No continuous interpolation, wall-clock delivery, final lookdev, controller/state-machine, physics or gameplay acceptance."
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

func fail(code: String, message: String) -> void:
    receipt["result"] = code
    receipt["failure"] = message
    write_receipt()
    push_error(code + ": " + message)
    quit(1)

func vec3_from(value: Variant, label: String) -> Vector3:
    if not (value is Array) or value.size() != 3:
        fail("FAIL_CONTRACT_IDENTITY", label + " is not a three-element array")
        return Vector3.ZERO
    return Vector3(float(value[0]), float(value[1]), float(value[2]))

func source_to_uc(source: Vector3) -> Vector3:
    return Vector3(source.x, source.z, source.y)

func find_node(root: Node, wanted: String) -> Node3D:
    if String(root.name) == wanted and root is Node3D:
        return root as Node3D
    for child in root.get_children():
        var found := find_node(child, wanted)
        if found != null:
            return found
    return null

func surface_data(node: Node3D, label: String) -> Dictionary:
    if not (node is MeshInstance3D):
        fail("FAIL_TARGET_SURFACE_IMPORT", label + " is not MeshInstance3D")
        return {}
    var instance := node as MeshInstance3D
    if instance.mesh == null or instance.mesh.get_surface_count() != 1:
        fail("FAIL_TARGET_SURFACE_IMPORT", label + " must contain exactly one imported mesh surface")
        return {}
    var arrays := instance.mesh.surface_get_arrays(0)
    var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
    var uvs: PackedVector2Array = arrays[Mesh.ARRAY_TEX_UV]
    var indices: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
    var material := instance.mesh.surface_get_material(0)
    if material == null:
        fail("FAIL_TARGET_TEXTURE_BINDING", label + " imported material is missing")
        return {}
    var texture_value: Variant = material.get("albedo_texture")
    if not (texture_value is Texture2D):
        fail("FAIL_TARGET_TEXTURE_BINDING", label + " imported albedo texture is missing")
        return {}
    var texture := texture_value as Texture2D
    return {
        "node": instance,
        "vertices": vertices,
        "uvs": uvs,
        "indices": indices,
        "material": material,
        "texture": texture,
        "texture_width": texture.get_width(),
        "texture_height": texture.get_height()
    }

func world_vertices(node: Node3D, local_vertices: PackedVector3Array) -> Array:
    var out: Array = []
    for vertex in local_vertices:
        out.append(node.global_transform * vertex)
    return out

func max_point_error(a: Array, b: Array) -> float:
    if a.size() != b.size():
        return INF
    var worst := 0.0
    for i in range(a.size()):
        worst = maxf(worst, (a[i] as Vector3).distance_to(b[i] as Vector3))
    return worst

func max_uv_error(a: PackedVector2Array, b: PackedVector2Array) -> float:
    if a.size() != b.size():
        return INF
    var worst := 0.0
    for i in range(a.size()):
        worst = maxf(worst, a[i].distance_to(b[i]))
    return worst

func expected_world_vertices(neutral: Array, hinge: Vector3, target_angle_deg: float) -> Array:
    var rotation := Basis(Vector3.RIGHT, deg_to_rad(target_angle_deg))
    var out: Array = []
    for point in neutral:
        out.append(hinge + rotation * ((point as Vector3) - hinge))
    return out

func _initialize() -> void:
    var contract := read_json(CONTRACT_PATH)
    var technical := read_json(TECH_RECEIPT_PATH)
    var sequence := read_json(SEQUENCE_PATH)

    if contract.get("schema") != "axm.object-animation-service-dark-texture-motion-rebind/v0.1":
        fail("FAIL_CONTRACT_IDENTITY", "service-dark Animation contract missing or wrong schema")
        return
    if contract.get("motion_mutation_policy") != "FORBIDDEN_REBIND_ONLY":
        fail("FAIL_CONTRACT_IDENTITY", "motion mutation policy drift")
        return

    var tech_dep: Dictionary = contract.get("technical_art_dependency", {})
    if technical.get("result") != tech_dep.get("required_transport_result"):
        fail("FAIL_TECHNICAL_ART_DEPENDENCY", "Technical Art transport prerequisite missing or not green")
        return
    if technical.get("technical_art_head") != tech_dep.get("exact_head"):
        fail("FAIL_TECHNICAL_ART_DEPENDENCY", "Technical Art head mismatch")
        return
    if technical.get("materials_authority_head") != tech_dep.get("materials_authority_head"):
        fail("FAIL_TECHNICAL_ART_DEPENDENCY", "Materials authority identity mismatch")
        return
    if technical.get("uc_head") != tech_dep.get("uc_head"):
        fail("FAIL_TECHNICAL_ART_DEPENDENCY", "UC identity mismatch")
        return
    if technical.get("glb_sha256") != tech_dep.get("glb_sha256"):
        fail("FAIL_TECHNICAL_ART_DEPENDENCY", "Technical Art receipt GLB identity mismatch")
        return
    if not FileAccess.file_exists(GLB_PATH) or sha256_file(GLB_PATH) != String(tech_dep.get("glb_sha256", "")):
        fail("FAIL_TECHNICAL_ART_DEPENDENCY", "exact Technical Art GLB bytes missing or drifted")
        return

    var motion: Dictionary = contract.get("motion_identity", {})
    if sequence.get("result") != "PASS_ORDERED_LATCH_RELEASE_LID_CLIP_REENGAGE_SEQUENCE":
        fail("FAIL_MOTION_DEPENDENCY", "exact lid/latch sequence prerequisite missing or not green")
        return
    if sequence.get("sequence_id") != motion.get("sequence_id"):
        fail("FAIL_MOTION_DEPENDENCY", "sequence identity mismatch")
        return
    if sequence.get("base_lid_clip_digest") != motion.get("base_lid_clip_digest"):
        fail("FAIL_MOTION_DEPENDENCY", "base lid clip digest mismatch")
        return
    if int(sequence.get("endpoint_inclusive_sample_count", 0)) != int(motion.get("endpoint_inclusive_sample_count", 0)):
        fail("FAIL_MOTION_DEPENDENCY", "sample-count mismatch")
        return
    if int(sequence.get("sample_rate_hz", 0)) != int(motion.get("sample_rate_hz", 0)):
        fail("FAIL_MOTION_DEPENDENCY", "sample-rate mismatch")
        return
    if absf(float(sequence.get("duration_s", -1.0)) - float(motion.get("duration_s", -2.0))) > 0.000001:
        fail("FAIL_MOTION_DEPENDENCY", "duration mismatch")
        return

    var hinge_contract: Dictionary = contract.get("source_hinge", {})
    var source_hinge := vec3_from(hinge_contract.get("origin_source_m", []), "source hinge origin")
    var target_hinge := vec3_from(hinge_contract.get("target_origin_uc_m", []), "target hinge origin")
    var mapped_hinge := source_to_uc(source_hinge)
    if mapped_hinge.distance_to(target_hinge) > 0.000000001:
        fail("FAIL_TARGET_HINGE_IDENTITY_DRIFT", "declared target hinge is not the exact source->UC mapped hinge")
        return
    var target_axis := vec3_from(hinge_contract.get("target_axis_uc", []), "target hinge axis")
    if target_axis.distance_to(Vector3.RIGHT) > 0.000000001:
        fail("FAIL_TARGET_HINGE_IDENTITY_DRIFT", "target hinge axis drift")
        return
    var target_sign := float(hinge_contract.get("source_positive_angle_to_target_sign", 0.0))
    if absf(target_sign + 1.0) > 0.000000001:
        fail("FAIL_TARGET_HINGE_IDENTITY_DRIFT", "source-to-target angle-sign mapping drift")
        return

    var document := GLTFDocument.new()
    var state := GLTFState.new()
    var append_error := document.append_from_file(GLB_PATH, state)
    if append_error != OK:
        fail("FAIL_TARGET_SURFACE_IMPORT", "GLTFDocument append_from_file failed: " + str(append_error))
        return
    var generated = document.generate_scene(state)
    if generated == null or not (generated is Node3D):
        fail("FAIL_TARGET_SURFACE_IMPORT", "GLTFDocument generate_scene returned no Node3D")
        return
    var imported := generated as Node3D
    get_root().add_child(imported)
    await process_frame

    var lid := find_node(imported, "lid_inner_service_surface")
    var front := find_node(imported, "front_service_panel_outer_service_surface")
    if lid == null or front == null:
        fail("FAIL_TARGET_SURFACE_IMPORT", "required Technical Art surface node names were not preserved")
        return

    var lid_data := surface_data(lid, "lid_inner_service_surface")
    var front_data := surface_data(front, "front_service_panel_outer_service_surface")
    var ownership: Dictionary = contract.get("surface_ownership", {})
    for surface_id in ["lid_inner_service_surface", "front_service_panel_outer_service_surface"]:
        if not ownership.has(surface_id):
            fail("FAIL_CONTRACT_IDENTITY", "missing ownership row for " + surface_id)
            return
    if lid_data["vertices"].size() != int(ownership["lid_inner_service_surface"]["expected_vertex_count"]) or lid_data["indices"].size() != int(ownership["lid_inner_service_surface"]["expected_index_count"]) or lid_data["uvs"].size() != int(ownership["lid_inner_service_surface"]["expected_uv_count"]):
        fail("FAIL_TARGET_SURFACE_IMPORT", "lid-inner target surface count drift")
        return
    if front_data["vertices"].size() != int(ownership["front_service_panel_outer_service_surface"]["expected_vertex_count"]) or front_data["indices"].size() != int(ownership["front_service_panel_outer_service_surface"]["expected_index_count"]) or front_data["uvs"].size() != int(ownership["front_service_panel_outer_service_surface"]["expected_uv_count"]):
        fail("FAIL_TARGET_SURFACE_IMPORT", "front-panel target surface count drift")
        return

    var target_host: Dictionary = contract.get("target_host", {})
    for data in [lid_data, front_data]:
        if int(data["texture_width"]) != int(target_host.get("required_texture_width_px", 0)) or int(data["texture_height"]) != int(target_host.get("required_texture_height_px", 0)):
            fail("FAIL_TARGET_TEXTURE_BINDING", "embedded service-dark texture dimensions drift")
            return

    var neutral_lid_world := world_vertices(lid, lid_data["vertices"])
    var neutral_front_world := world_vertices(front, front_data["vertices"])
    var neutral_lid_uvs: PackedVector2Array = lid_data["uvs"].duplicate()
    var neutral_front_uvs: PackedVector2Array = front_data["uvs"].duplicate()
    var initial_lid_material: Material = lid_data["material"]
    var initial_front_material: Material = front_data["material"]
    var initial_lid_texture: Texture2D = lid_data["texture"]
    var initial_front_texture: Texture2D = front_data["texture"]

    var pivot := Node3D.new()
    pivot.name = "animation_pivot_service_dark_lid_inner"
    pivot.position = target_hinge
    imported.add_child(pivot)
    lid.reparent(pivot, true)
    for _i in range(2):
        await process_frame

    var wrapper_drift := max_point_error(neutral_lid_world, world_vertices(lid, lid_data["vertices"]))
    var pos_tol := float(target_host.get("position_tolerance_m", 0.000001))
    var uv_tol := float(target_host.get("uv_tolerance", 0.0000001))
    if wrapper_drift > pos_tol:
        fail("FAIL_PROOF_WRAPPER_NEUTRAL_DRIFT", "proof-local hinge wrapper changed neutral lid surface")
        return

    var animation := Animation.new()
    animation.length = float(sequence["duration_s"])
    animation.loop_mode = Animation.LOOP_NONE
    var track := animation.add_track(Animation.TYPE_VALUE)
    animation.track_set_path(track, NodePath(str(imported.get_path_to(pivot)) + ":rotation_degrees"))
    animation.track_set_interpolation_type(track, Animation.INTERPOLATION_NEAREST)
    animation.value_track_set_update_mode(track, Animation.UPDATE_DISCRETE)
    for sample in sequence["samples"]:
        var source_angle := float(sample["lid_mathematical_rotation_deg"])
        animation.track_insert_key(track, float(sample["time_s"]), Vector3(target_sign * source_angle, 0.0, 0.0))
    if animation.track_get_key_count(track) != int(motion["endpoint_inclusive_sample_count"]):
        fail("FAIL_TARGET_ANIMATIONPLAYER_BINDING", "AnimationPlayer did not receive all authored lid samples")
        return

    var player := AnimationPlayer.new()
    player.name = "AXM_SERVICE_DARK_TEXTURE_MOTION_PLAYER"
    imported.add_child(player)
    player.root_node = NodePath("..")
    var library := AnimationLibrary.new()
    library.add_animation(MOTION_NAME, animation)
    player.add_animation_library("", library)
    player.play(MOTION_NAME)
    player.pause()

    var csv := FileAccess.open(SAMPLE_CSV_PATH, FileAccess.WRITE)
    if csv == null:
        fail("FAIL_EVIDENCE_IO", "could not create sample CSV")
        return
    csv.store_line("sample_index,time_s,lid_source_deg,lid_target_deg,max_lid_vertex_error_m,max_front_static_drift_m,max_lid_uv_drift,max_front_uv_drift,max_lid_displacement_from_neutral_m")

    var max_vertex_error := 0.0
    var max_front_drift := 0.0
    var max_lid_uv_drift := 0.0
    var max_front_uv_drift := 0.0
    var max_lid_displacement := 0.0
    var representative: Array = []
    var representative_indices := {0: true, 10: true, 40: true, 50: true, 60: true, 90: true, 100: true}

    for sample_index in range(sequence["samples"].size()):
        var row: Dictionary = sequence["samples"][sample_index]
        var time_s := float(row["time_s"])
        var source_angle := float(row["lid_mathematical_rotation_deg"])
        var target_angle := target_sign * source_angle
        player.seek(time_s, true)
        player.advance(0.0)

        var observed_lid := world_vertices(lid, lid_data["vertices"])
        var expected_lid := expected_world_vertices(neutral_lid_world, target_hinge, target_angle)
        var lid_error := max_point_error(expected_lid, observed_lid)
        var front_drift := max_point_error(neutral_front_world, world_vertices(front, front_data["vertices"]))
        var lid_uv_drift := max_uv_error(neutral_lid_uvs, (lid as MeshInstance3D).mesh.surface_get_arrays(0)[Mesh.ARRAY_TEX_UV])
        var front_uv_drift := max_uv_error(neutral_front_uvs, (front as MeshInstance3D).mesh.surface_get_arrays(0)[Mesh.ARRAY_TEX_UV])
        var lid_displacement := max_point_error(neutral_lid_world, observed_lid)

        max_vertex_error = maxf(max_vertex_error, lid_error)
        max_front_drift = maxf(max_front_drift, front_drift)
        max_lid_uv_drift = maxf(max_lid_uv_drift, lid_uv_drift)
        max_front_uv_drift = maxf(max_front_uv_drift, front_uv_drift)
        max_lid_displacement = maxf(max_lid_displacement, lid_displacement)

        csv.store_line("%d,%.9f,%.9f,%.9f,%.12g,%.12g,%.12g,%.12g,%.12g" % [sample_index, time_s, source_angle, target_angle, lid_error, front_drift, lid_uv_drift, front_uv_drift, lid_displacement])
        if representative_indices.has(sample_index):
            representative.append({
                "sample_index": sample_index,
                "time_s": time_s,
                "lid_source_deg": source_angle,
                "lid_target_deg": target_angle,
                "max_lid_vertex_error_m": lid_error,
                "front_static_drift_m": front_drift,
                "lid_uv_drift": lid_uv_drift,
                "lid_displacement_from_neutral_m": lid_displacement
            })
    csv.close()

    player.seek(float(sequence["duration_s"]), true)
    player.advance(0.0)
    var endpoint_lid_drift := max_point_error(neutral_lid_world, world_vertices(lid, lid_data["vertices"]))
    var endpoint_front_drift := max_point_error(neutral_front_world, world_vertices(front, front_data["vertices"]))
    if max_vertex_error > pos_tol:
        fail("FAIL_TARGET_MOTION_POSITION_REBIND", "moving lid-inner target surface diverged from exact hinge transform")
        return
    if max_front_drift > pos_tol or endpoint_front_drift > pos_tol:
        fail("FAIL_STATIC_OWNER_DRIFT", "front-panel-owned service surface moved during lid animation")
        return
    if max_lid_uv_drift > uv_tol or max_front_uv_drift > uv_tol:
        fail("FAIL_TARGET_UV_STABILITY", "service-dark UV coordinates changed during motion")
        return
    if endpoint_lid_drift > pos_tol:
        fail("FAIL_TARGET_LOOP_CLOSURE", "lid-inner surface did not return to neutral at authored endpoint")
        return
    if max_lid_displacement < 0.1:
        fail("FAIL_TARGET_MOTION_NOT_EXERCISED", "lid-inner target surface did not move materially")
        return

    var final_lid_material := (lid as MeshInstance3D).mesh.surface_get_material(0)
    var final_front_material := (front as MeshInstance3D).mesh.surface_get_material(0)
    var final_lid_texture: Variant = final_lid_material.get("albedo_texture") if final_lid_material != null else null
    var final_front_texture: Variant = final_front_material.get("albedo_texture") if final_front_material != null else null
    if final_lid_material != initial_lid_material or final_front_material != initial_front_material:
        fail("FAIL_TARGET_MATERIAL_IDENTITY", "surface material resource identity changed during motion")
        return
    if final_lid_texture != initial_lid_texture or final_front_texture != initial_front_texture:
        fail("FAIL_TARGET_TEXTURE_BINDING", "embedded texture resource identity changed during motion")
        return

    receipt = {
        "schema": "axm.object-animation-service-dark-texture-motion-rebind-evidence/v0.1",
        "result": "PASS_TARGET_HOST_SERVICE_DARK_TEXTURE_SURFACE_MOTION_REBIND_101_SAMPLES",
        "promotion_effect": "NONE",
        "glb_sha256": sha256_file(GLB_PATH),
        "technical_art_head": technical["technical_art_head"],
        "materials_authority_head": technical["materials_authority_head"],
        "uc_head": technical["uc_head"],
        "sequence_id": sequence["sequence_id"],
        "base_lid_clip_digest": sequence["base_lid_clip_digest"],
        "sample_rate_hz": sequence["sample_rate_hz"],
        "duration_s": sequence["duration_s"],
        "sample_count": sequence["endpoint_inclusive_sample_count"],
        "target_hinge_uc_m": [target_hinge.x, target_hinge.y, target_hinge.z],
        "source_positive_angle_to_target_sign": target_sign,
        "max_proof_wrapper_neutral_drift_m": wrapper_drift,
        "max_lid_world_vertex_error_m": max_vertex_error,
        "max_front_static_drift_m": max_front_drift,
        "max_lid_uv_drift": max_lid_uv_drift,
        "max_front_uv_drift": max_front_uv_drift,
        "max_lid_displacement_from_neutral_m": max_lid_displacement,
        "endpoint_lid_neutral_drift_m": endpoint_lid_drift,
        "endpoint_front_neutral_drift_m": endpoint_front_drift,
        "lid_texture_size_px": [initial_lid_texture.get_width(), initial_lid_texture.get_height()],
        "front_texture_size_px": [initial_front_texture.get_width(), initial_front_texture.get_height()],
        "material_resource_identity_stable": true,
        "texture_resource_identity_stable": true,
        "representative_samples": representative,
        "truth_boundary": contract["truth_boundary"],
        "renderer_boundary": "Godot 4.7.2 GLTFDocument import plus AnimationPlayer discrete authored-sample seeks over the exact Technical Art textured GLB. This does not establish continuous interpolation, wall-clock pacing, tangent-space quality, production UV/texture adoption, final visual acceptance, runtime-controller/state-machine behavior, physics/collision, input/gameplay, CANON or production readiness."
    }
    write_receipt()
    print(JSON.stringify(receipt, "  "))
    quit(0)
