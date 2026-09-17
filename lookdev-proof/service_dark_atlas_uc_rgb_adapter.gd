extends SceneTree

const SOURCE_PATH := "res://service-dark-atlas-padded.png"
const OUTPUT_PATH := "res://generated/service-dark-atlas-uc-rgb.png"
const RECEIPT_PATH := "res://generated/service-dark-atlas-uc-rgb-receipt.json"

func write_receipt(data: Dictionary) -> void:
    var file := FileAccess.open(RECEIPT_PATH, FileAccess.WRITE)
    if file != null:
        file.store_string(JSON.stringify(data, "  ") + "\n")
        file.close()

func fail(message: String) -> void:
    write_receipt({
        "schema": "axm.object-service-dark-atlas-uc-rgb-adapter/v0.1",
        "state": "FAIL_RGB_TRANSPORT_DERIVATIVE",
        "failure": message,
        "promotion_effect": "NONE"
    })
    push_error(message)
    quit(1)

func _initialize() -> void:
    if not FileAccess.file_exists(SOURCE_PATH):
        fail("exact Materials padded atlas is missing")
        return
    var source := Image.load_from_file(SOURCE_PATH)
    if source == null or source.is_empty():
        fail("could not decode exact Materials padded atlas")
        return
    if source.get_width() != 512 or source.get_height() != 512:
        fail("Materials padded atlas dimensions drifted from 512x512")
        return

    var source_rgba := source.duplicate()
    source_rgba.convert(Image.FORMAT_RGBA8)
    var target := source_rgba.duplicate()
    target.convert(Image.FORMAT_RGB8)

    var max_rgb_delta := 0
    var min_source_alpha := 255
    var max_source_alpha := 0
    for y in range(source_rgba.get_height()):
        for x in range(source_rgba.get_width()):
            var a := source_rgba.get_pixel(x, y)
            var b := target.get_pixel(x, y)
            max_rgb_delta = maxi(max_rgb_delta, absi(int(round(a.r * 255.0)) - int(round(b.r * 255.0))))
            max_rgb_delta = maxi(max_rgb_delta, absi(int(round(a.g * 255.0)) - int(round(b.g * 255.0))))
            max_rgb_delta = maxi(max_rgb_delta, absi(int(round(a.b * 255.0)) - int(round(b.b * 255.0))))
            var alpha_byte := int(round(a.a * 255.0))
            min_source_alpha = mini(min_source_alpha, alpha_byte)
            max_source_alpha = maxi(max_source_alpha, alpha_byte)

    if max_rgb_delta != 0:
        fail("RGBA to RGB adapter changed source RGB channels")
        return
    if min_source_alpha != 255 or max_source_alpha != 255:
        fail("bounded Materials atlas is not fully opaque; alpha drop would be lossy")
        return
    if target.save_png(OUTPUT_PATH) != OK:
        fail("could not retain RGB transport derivative")
        return

    write_receipt({
        "schema": "axm.object-service-dark-atlas-uc-rgb-adapter/v0.1",
        "state": "PASS_EXACT_RGBA_TO_RGB_TRANSPORT_DERIVATIVE",
        "promotion_effect": "NONE",
        "width": target.get_width(),
        "height": target.get_height(),
        "source_format_after_decode": "RGBA8",
        "target_format": "RGB8",
        "max_rgb_channel_delta": max_rgb_delta,
        "min_source_alpha": min_source_alpha,
        "max_source_alpha": max_source_alpha,
        "truth_boundary": {
            "source_materials_png_modified": false,
            "rgb_channels_changed": false,
            "alpha_semantics_present": false,
            "production_texture_authored": false,
            "visual_acceptance": false
        }
    })
    quit(0)
