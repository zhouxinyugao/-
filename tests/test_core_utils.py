"""core.concurrency / core.assets 单测（对应验收清单：节点内并发、资产只放引用）。"""

from __future__ import annotations

import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.assets import AssetsStore, payload_asset, safe_name  # noqa: E402
from core.concurrency import ConcurrentError, map_parallel  # noqa: E402


class TestMapParallel(unittest.TestCase):
    def test_results_keep_input_order(self):
        self.assertEqual([2, 4, 6], map_parallel(lambda x: x * 2, [1, 2, 3], max_workers=3))

    def test_runs_concurrently(self):
        """3 个各睡 0.2s 的任务，并发后总耗时应明显小于串行 0.6s。"""
        start = time.perf_counter()
        map_parallel(lambda x: time.sleep(0.2) or x, [1, 2, 3], max_workers=3)
        self.assertLess(time.perf_counter() - start, 0.5)

    def test_progress_callback_reaches_total(self):
        seen = []
        map_parallel(lambda x: x, list(range(5)), max_workers=2, on_progress=lambda d, t: seen.append(d))
        self.assertEqual(5, len(seen))
        self.assertEqual(5, seen[-1])

    def test_fail_fast_raises_with_index(self):
        def boom(x):
            if x == 2:
                raise ValueError("bad")
            return x

        with self.assertRaises(ConcurrentError) as ctx:
            map_parallel(boom, [1, 2, 3], max_workers=1)
        self.assertEqual(1, ctx.exception.index)

    def test_fail_fast_false_keeps_others(self):
        def boom(x):
            if x == 2:
                raise ValueError("bad")
            return x

        results = map_parallel(boom, [1, 2, 3], max_workers=1, fail_fast=False)
        self.assertEqual([1, None, 3], results)

    def test_empty_items(self):
        self.assertEqual([], map_parallel(lambda x: x, [], max_workers=3))


class TestAssets(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "outputs"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_save_returns_project_relative_ref(self):
        store = AssetsStore(self.root, "demo_wf", "run_001")
        ref = store.save("shot_01.mp4", b"\x00\x01binary", subdir="shots")
        self.assertTrue(ref.startswith("outputs/demo_wf/run_001/assets/shots/"))
        self.assertTrue(ref.endswith("shot_01.mp4"))
        self.assertTrue(store.exists(ref))
        self.assertEqual(b"\x00\x01binary", store.read(ref))

    def test_text_asset_roundtrip(self):
        store = AssetsStore(self.root, "demo_wf", "run_001")
        ref = store.save("note.txt", "西瓜")
        self.assertEqual("西瓜", store.read(ref, binary=False))

    def test_payload_holds_ref_only(self):
        """payload 里只放引用，不放实体内容。"""
        store = AssetsStore(self.root, "demo_wf", "run_001")
        ref = store.save("a.txt", "hello")
        payload: dict = {}
        payload_asset(payload, "step_1.file", ref, bytes=5)
        self.assertEqual(payload["step_1.file"]["ref"], ref)
        self.assertNotIn("hello", str(payload))

    def test_safe_name(self):
        self.assertEqual("shot_01.mp4", safe_name("shot 01.mp4"))
        self.assertEqual("a_b", safe_name("a/b"))


if __name__ == "__main__":
    unittest.main()
