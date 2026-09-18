from __future__ import annotations

import hashlib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets/modular-equipment-case-001/source.json"
SOURCE_RIG_BINDING = ROOT / "assets/modular-equipment-case-001/front-latch-source-rig-binding-002.json"

SOURCE_SHA256 = "49b1f9ed9865893d6de6f1ec8f069576732df694853fde4e3fcff366de32644a"
SOURCE_RIG_BINDING_SHA256 = "615f8ff34cc0897fd399345301efce1ca9cb0aa58e86caca92b914049b89adce"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class LatchTransitionIdentityTests(unittest.TestCase):
    def test_exact_host_source_bytes_are_pinned(self) -> None:
        self.assertEqual(sha256(SOURCE), SOURCE_SHA256)

    def test_exact_source_rig_binding_bytes_are_pinned(self) -> None:
        self.assertEqual(sha256(SOURCE_RIG_BINDING), SOURCE_RIG_BINDING_SHA256)


if __name__ == "__main__":
    unittest.main()
