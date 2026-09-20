extends SceneTree

const CORRECTED_GLB := "res://front-face-generated/geometry33-parity-corrected-rebound.glb"
const UNADAPTED_GLB := "res://front-face-generated/geometry33-unadapted-rebound.glb"
const SOURCE_RECEIPT := "res://front-face-generated/front-face-transport-receipt.json"
const TARGET_RECEIPT := "res://front-face-index-target-receipt.json"
const EXPECTED_GROUPS := 31
const EXPECTED_TRIANGLES := 812
const VOLUME_EPSILON := 1.0e-12
const MAGNITUDE_ABS_TOLERANCE := 1.0e-10
const MAGNITUDE_REL_TOLERANCE := 1.0e-6

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

func write_receipt(data: Dictionary) -> void:
    var file := FileAccess.open(TARGET_RECEIPT, FileAccess.WRITE)
    if file != null:
        file.store_string(JSON.stringify(data, "  ") + "\n")
        file.close()

func fail(message: String, data: Dictionary = {}) -> void:
    data["schema"] = "axm.object-technical-art-front-face-index-target/v0.1"
    data["state"] = "FAIL_OBJECT_FRONT_FACE_INDEX_TARGET_PROOF"
    data["failure"] = message
    data["promotion_effect"] = "NONE"
    write_receipt(data)
    push_error(message)
    quit(1)

func import_scene(path: String) -> Node3D:
    var document := GLTFDocument.new()
    var state := GLTFState.new()
    var error := document.append_from_file(path, state)
    if error != OK:
        return null
    var generated = document.generate_scene(state)
    return generated as Node3D if generated is Node3D else null

func sign_name(value: float) -> String:
    if value > VOLUME_EPSILON:
        return "POSITIVE"
    if value < -VOLUME_EPSILON:
        return "NEGATIVE"
    return "ZERO_OR_AMBIGUOUS"

func face_normal(a: Vector3, b: Vector3, c: Vector3) -> Vector3:
    var cross := (b - a).cross(c - a)
    if cross.length_squared() <= 1.0e-24:
        return Vector3.ZERO
    return cross.normalized()

func inspect_mesh_instance(instance: MeshInstance3D) -> Dictionary:
    if instance.mesh == null:
        return {"state": "FAIL_MISSING_MESH", "name": String(instance.name)}
    var triangle_count := 0
    var signed_volume := 0.0
    var min_face_to_vertex_normal_dot := 1.0
    var max_face_to_vertex_normal_dot := -1.0
    var observed_normal_samples := 0
    for surface_index in range(instance.mesh.get_surface_count()):
        var arrays := instance.mesh.surface_get_arrays(surface_index)
        var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
        var normals: PackedVector3Array = arrays[Mesh.ARRAY_NORMAL]
        var indices: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
        if vertices.is_empty():
            return {"state": "FAIL_EMPTY_SURFACE", "name": String(instance.name), "surface": surface_index}
        var local_indices := PackedInt32Array()
        if indices.is_empty():
            local_indices.resize(vertices.size())
            for i in range(vertices.size()):
                local_indices[i] = i
        else:
            local_indices = indices
        if local_indices.size() % 3 != 0:
            return {"state": "FAIL_NON_TRIANGULATED_INDEX_COUNT", "name": String(instance.name), "surface": surface_index}
        for cursor in range(0, local_indices.size(), 3):
            var ia := int(local_indices[cursor])
            var ib := int(local_indices[cursor + 1])
            var ic := int(local_indices[cursor + 2])
            if ia < 0 or ib < 0 or ic < 0 or ia >= vertices.size() or ib >= vertices.size() or ic >= vertices.size():
                return {"state": "FAIL_INDEX_RANGE", "name": String(instance.name), "surface": surface_index}
            var a := vertices[ia]
            var b := vertices[ib]
            var c := vertices[ic]
            signed_volume += a.dot(b.cross(c)) / 6.0
            triangle_count += 1
            var geometric_normal := face_normal(a, b, c)
            if geometric_normal == Vector3.ZERO:
                return {"state": "FAIL_DEGENERATE_TRIANGLE", "name": String(instance.name), "surface": surface_index}
            if not normals.is_empty():
                if normals.size() != vertices.size():
                    return {"state": "FAIL_NORMAL_COUNT", "name": String(instance.name), "surface": surface_index}
                for ni in [ia, ib, ic]:
                    var vertex_normal := normals[ni]
                    if vertex_normal.length_squared() <= 1.0e-24:
                        return {"state": "FAIL_ZERO_VERTEX_NORMAL", "name": String(instance.name), "surface": surface_index}
                    var alignment := geometric_normal.dot(vertex_normal.normalized())
                    min_face_to_vertex_normal_dot = minf(min_face_to_vertex_normal_dot, alignment)
                    max_face_to_vertex_normal_dot = maxf(max_face_to_vertex_normal_dot, alignment)
                    observed_normal_samples += 1
    return {
        "state": "PASS",
        "name": String(instance.name),
        "triangles": triangle_count,
        "signed_volume_m3": signed_volume,
        "signed_volume_sign": sign_name(signed_volume),
        "normal_samples": observed_normal_samples,
        "min_face_to_vertex_normal_dot": min_face_to_vertex_normal_dot if observed_normal_samples > 0 else null,
        "max_face_to_vertex_normal_dot": max_face_to_vertex_normal_dot if observed_normal_samples > 0 else null
    }

func collect_meshes(node: Node, out: Dictionary) -> Dictionary:
    if node is MeshInstance3D:
        var metrics := inspect_mesh_instance(node as MeshInstance3D)
        if String(metrics.get("state", "")) != "PASS":
            return metrics
        var name := String(metrics["name"])
        if out.has(name):
            return {"state": "FAIL_DUPLICATE_MESH_NAME", "name": name}
        out[name] = metrics
    for child in node.get_children():
        var child_result := collect_meshes(child, out)
        if String(child_result.get("state", "PASS")) != "PASS":
            return child_result
    return {"state": "PASS"}

func inspect_variant(path: String) -> Dictionary:
    var imported := import_scene(path)
    if imported == null:
        return {"state": "FAIL_IMPORT", "path": path}
    var groups := {}
    var collected := collect_meshes(imported, groups)
    if String(collected.get("state", "")) != "PASS":
        imported.free()
        return collected
    var total_triangles := 0
    var positive_groups := 0
    var negative_groups := 0
    var ambiguous_groups := 0
    var min_normal_alignment := 1.0
    var max_normal_alignment := -1.0
    var normal_samples := 0
    for name in groups.keys():
        var metrics: Dictionary = groups[name]
        total_triangles += int(metrics["triangles"])
        var sign := String(metrics["signed_volume_sign"])
        if sign == "POSITIVE":
            positive_groups += 1
        elif sign == "NEGATIVE":
            negative_groups += 1
        else:
            ambiguous_groups += 1
        if int(metrics["normal_samples"]) > 0:
            min_normal_alignment = minf(min_normal_alignment, float(metrics["min_face_to_vertex_normal_dot"]))
            max_normal_alignment = maxf(max_normal_alignment, float(metrics["max_face_to_vertex_normal_dot"]))
            normal_samples += int(metrics["normal_samples"])
    imported.free()
    return {
        "state": "PASS",
        "glb_sha256": sha256_file(path),
        "mesh_groups": groups,
        "mesh_group_count": groups.size(),
        "triangles": total_triangles,
        "positive_signed_volume_groups": positive_groups,
        "negative_signed_volume_groups": negative_groups,
        "ambiguous_signed_volume_groups": ambiguous_groups,
        "normal_samples": normal_samples,
        "minimum_face_to_vertex_normal_dot": min_normal_alignment if normal_samples > 0 else null,
        "maximum_face_to_vertex_normal_dot": max_normal_alignment if normal_samples > 0 else null
    }

func _initialize() -> void:
    var source := read_json(SOURCE_RECEIPT)
    if source.get("result") != "PASS_OBJECT_GEOMETRY33_SOURCE_EXTERIOR_TO_CURRENT_UC_GLTF_PARITY_BRIDGE_READY":
        fail("Technical Art source transport receipt missing or not green")
        return
    if not FileAccess.file_exists(CORRECTED_GLB) or not FileAccess.file_exists(UNADAPTED_GLB):
        fail("front-face GLB evidence inputs missing")
        return
    if sha256_file(CORRECTED_GLB) != String(source["corrected_transport"]["glb_sha256"]):
        fail("corrected GLB byte identity drift")
        return
    if sha256_file(UNADAPTED_GLB) != String(source["unadapted_negative_control"]["glb_sha256"]):
        fail("unadapted GLB byte identity drift")
        return

    var corrected := inspect_variant(CORRECTED_GLB)
    if String(corrected.get("state", "")) != "PASS":
        fail("corrected Godot import inspection failed: %s" % JSON.stringify(corrected))
        return
    var unadapted := inspect_variant(UNADAPTED_GLB)
    if String(unadapted.get("state", "")) != "PASS":
        fail("unadapted Godot import inspection failed: %s" % JSON.stringify(unadapted))
        return

    var receipt := {
        "schema": "axm.object-technical-art-front-face-index-target/v0.1",
        "state": "PASS_EVIDENCE",
        "result": "PENDING",
        "renderer": {
            "engine": "Godot",
            "version": Engine.get_version_info().get("string", "unknown"),
            "rendering_method": "gl_compatibility",
            "adapter": RenderingServer.get_video_adapter_name()
        },
        "source_transport_receipt_sha256": sha256_file(SOURCE_RECEIPT),
        "corrected": corrected,
        "unadapted_negative": unadapted,
        "same_group_names": true,
        "opposite_signed_volume_groups": 0,
        "matching_signed_volume_magnitude_groups": 0,
        "maximum_signed_volume_magnitude_delta_m3": 0.0,
        "maximum_signed_volume_relative_delta": 0.0,
        "promotion_effect": "NONE"
    }

    if int(corrected["mesh_group_count"]) != EXPECTED_GROUPS or int(unadapted["mesh_group_count"]) != EXPECTED_GROUPS:
        receipt["state"] = "FAIL_GROUP_COUNT"
    elif int(corrected["triangles"]) != EXPECTED_TRIANGLES or int(unadapted["triangles"]) != EXPECTED_TRIANGLES:
        receipt["state"] = "FAIL_TRIANGLE_COUNT"
    else:
        var corrected_groups: Dictionary = corrected["mesh_groups"]
        var unadapted_groups: Dictionary = unadapted["mesh_groups"]
        var corrected_names := corrected_groups.keys()
        var unadapted_names := unadapted_groups.keys()
        corrected_names.sort()
        unadapted_names.sort()
        if corrected_names != unadapted_names:
            receipt["same_group_names"] = false
            receipt["state"] = "FAIL_GROUP_IDENTITY"
        else:
            for name in corrected_names:
                var c: Dictionary = corrected_groups[name]
                var u: Dictionary = unadapted_groups[name]
                if int(c["triangles"]) != int(u["triangles"]):
                    receipt["state"] = "FAIL_GROUP_TRIANGLE_COUNT"
                    receipt["failure_group"] = name
                    break
                var cv := float(c["signed_volume_m3"])
                var uv := float(u["signed_volume_m3"])
                if absf(cv) <= VOLUME_EPSILON or absf(uv) <= VOLUME_EPSILON:
                    receipt["state"] = "FAIL_AMBIGUOUS_SIGNED_VOLUME"
                    receipt["failure_group"] = name
                    break
                if signf(cv) == -signf(uv):
                    receipt["opposite_signed_volume_groups"] += 1
                var magnitude_delta := absf(absf(cv) - absf(uv))
                var denominator := maxf(absf(cv), absf(uv))
                var relative_delta := magnitude_delta / denominator if denominator > 0.0 else 0.0
                receipt["maximum_signed_volume_magnitude_delta_m3"] = maxf(float(receipt["maximum_signed_volume_magnitude_delta_m3"]), magnitude_delta)
                receipt["maximum_signed_volume_relative_delta"] = maxf(float(receipt["maximum_signed_volume_relative_delta"]), relative_delta)
                if magnitude_delta <= MAGNITUDE_ABS_TOLERANCE or relative_delta <= MAGNITUDE_REL_TOLERANCE:
                    receipt["matching_signed_volume_magnitude_groups"] += 1
            if String(receipt["state"]) == "PASS_EVIDENCE":
                if int(receipt["opposite_signed_volume_groups"]) != EXPECTED_GROUPS:
                    receipt["state"] = "FAIL_ORIENTATION_NEGATIVE_NOT_DISTINGUISHED"
                elif int(receipt["matching_signed_volume_magnitude_groups"]) != EXPECTED_GROUPS:
                    receipt["state"] = "FAIL_ORIENTATION_PAIR_MAGNITUDE_DRIFT"

    if String(receipt["state"]) == "PASS_EVIDENCE":
        receipt["result"] = "PASS_OBJECT_GEOMETRY33_CURRENT_UC_GLTF_GODOT_IMPORTED_INDEX_PARITY_DISTINGUISHED"
        receipt["decision"] = "REAL_GODOT_IMPORTED_INDEX_ARRAYS_PRESERVE_A_DETERMINISTIC_OPPOSITE_ORIENTATION_BETWEEN_THE_PARITY_CORRECTED_SOURCE_EXTERIOR_PATH_AND_THE_UNADAPTED_NEGATIVE__RECEIVER_SIGN_RECORDED_NOT_GLOBALIZED"
    else:
        receipt["result"] = "HOLD_FRONT_FACE_INDEX_TRANSPORT"

    receipt["truth_boundary"] = {
        "source_exterior_intent_owned_by_hard_surface": true,
        "orientation_candidate_owned_by_geometry": true,
        "transport_parity_adapter_owned_by_technical_art": true,
        "real_current_uc_glb_import_observed": true,
        "real_godot_imported_index_arrays_observed": true,
        "renderer_cull_silhouette_used_as_primary_oracle": false,
        "global_godot_front_face_rule_claimed": false,
        "materials_or_visual_qa_acceptance_transferred": false,
        "runtime_or_target_device_acceptance": false,
        "source_geometry_adopted": false,
        "uc_modified": false,
        "canon_or_production_readiness": false
    }
    write_receipt(receipt)
    print("AXM OBJECT TECHNICAL ART FRONT FACE INDEX TARGET ", JSON.stringify(receipt))
    quit(0 if String(receipt["state"]) == "PASS_EVIDENCE" else 1)
