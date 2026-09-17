from __future__ import annotations

"""Run the selected-roughness UC transport with container-independent scalar recovery.

The Materials-owned identity is the exact base-level R8 scalar sequence. Its retained
historical Godot PNG is an RGBA8 serialization whose RGB channels are equal and whose
alpha is opaque; the container is evidence, not policy. The first Technical Art run
correctly failed because it assumed that retained PNG was L8. This runner repairs only
that receiving boundary: accept bounded L8 or grayscale-equivalent opaque RGBA8 and
recover the same semantic scalar bytes before the existing transport proof executes.
"""

import struct
import zlib

import build_object_service_dark_selected_roughness_uc_transport as transport

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def decode_selected_scalar_png(data: bytes) -> tuple[int, int, bytes, list[str]]:
    if not isinstance(data, bytes) or len(data) < 45 or data[:8] != PNG_SIGNATURE:
        raise AssertionError("selected roughness donor is not a bounded PNG")

    cursor = 8
    compressed = bytearray()
    ancillary: list[str] = []
    kinds: list[bytes] = []
    size: tuple[int, int] | None = None
    channels: int | None = None

    while cursor + 12 <= len(data):
        length = struct.unpack_from(">I", data, cursor)[0]
        kind = data[cursor + 4 : cursor + 8]
        end = cursor + 8 + length
        if end + 4 > len(data):
            raise AssertionError("selected roughness PNG chunk exceeds payload")
        payload = data[cursor + 8 : end]
        crc = struct.unpack_from(">I", data, end)[0]
        if zlib.crc32(kind + payload) & 0xFFFFFFFF != crc:
            raise AssertionError("selected roughness PNG CRC mismatch")

        if kind == b"IHDR":
            if kinds or length != 13:
                raise AssertionError("selected roughness PNG header order/length invalid")
            width, height, bits, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", payload)
            if bits != 8 or compression != 0 or filtering != 0 or interlace != 0:
                raise AssertionError("selected roughness donor must remain 8-bit noninterlaced PNG")
            if color == 0:
                channels = 1
            elif color == 6:
                channels = 4
            else:
                raise AssertionError("selected roughness donor must be L8 or opaque grayscale-equivalent RGBA8")
            if (width, height) != (512, 512):
                raise AssertionError("selected roughness donor dimensions drift")
            size = width, height
        elif kind == b"IDAT":
            compressed.extend(payload)
        elif kind == b"IEND":
            if length != 0:
                raise AssertionError("selected roughness PNG IEND payload invalid")
        elif kind and kind[0] & 32:
            ancillary.append(kind.decode("ascii", "replace"))
        else:
            raise AssertionError(f"unsupported critical selected roughness PNG chunk: {kind!r}")

        kinds.append(kind)
        cursor = end + 4

    if cursor != len(data) or not kinds or kinds[0] != b"IHDR" or kinds[-1] != b"IEND" or size is None or channels is None:
        raise AssertionError("selected roughness PNG chunk sequence invalid")
    if not compressed:
        raise AssertionError("selected roughness PNG contains no image data")

    width, height = size
    stride = width * channels
    expected = height * (stride + 1)
    decoder = zlib.decompressobj()
    raw = decoder.decompress(bytes(compressed), expected + 1)
    if len(raw) != expected or not decoder.eof or decoder.unused_data:
        raise AssertionError("selected roughness PNG scanlines are truncated or oversized")

    pixels = bytearray(stride * height)
    for y in range(height):
        src = y * (stride + 1)
        filter_kind = raw[src]
        if filter_kind > 4:
            raise AssertionError("selected roughness PNG scanline filter unsupported")
        dest = y * stride
        for x in range(stride):
            a = pixels[dest + x - channels] if x >= channels else 0
            b = pixels[dest + x - stride] if y else 0
            c = pixels[dest + x - stride - channels] if y and x >= channels else 0
            if filter_kind == 0:
                prediction = 0
            elif filter_kind == 1:
                prediction = a
            elif filter_kind == 2:
                prediction = b
            elif filter_kind == 3:
                prediction = (a + b) // 2
            else:
                prediction = _paeth(a, b, c)
            pixels[dest + x] = (raw[src + 1 + x] + prediction) & 0xFF

    if channels == 1:
        scalar = bytes(pixels)
    else:
        scalar_bytes = bytearray(width * height)
        for index in range(width * height):
            offset = index * 4
            r, g, b, a = pixels[offset : offset + 4]
            if r != g or r != b or a != 255:
                raise AssertionError("retained RGBA selected roughness PNG is not grayscale-equivalent opaque scalar evidence")
            scalar_bytes[index] = r
        scalar = bytes(scalar_bytes)

    return width, height, scalar, ancillary


if __name__ == "__main__":
    transport.decode_l8_png = decode_selected_scalar_png
    transport.main()
