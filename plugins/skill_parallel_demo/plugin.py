"""示例：节点内并发 + 资产落盘引用。

演示两件事：
1. 用 ``core.concurrency.map_parallel`` 做节点内并发（默认 3 路，结果同序）
2. 用 ``core.assets.AssetsStore`` 把产物写成文件，**payload 里只放引用**

    python main.py run -w demo.yaml -i "西瓜" -v
"""

from __future__ import annotations

import time
from typing import Any, Dict

from core.assets import AssetsStore, payload_asset
from core.concurrency import map_parallel
from plugin_base import BaseSkillPlugin


class SkillParallelDemoPlugin(BaseSkillPlugin):
    plugin_name = "skill_parallel_demo"
    plugin_version = "0.1.0"
    plugin_description = "示例：节点内并发 + 资产只放引用"

    def run(self, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        items_key = self.params.get("items_key", "shots")
        # 优先从 payload 取（上游节点产出），取不到再用 params 里写死的列表
        items = workflow_data["payload"].get(items_key) or self.params.get("items", [])
        workers = int(self.params.get("concurrency", 3))
        fake_delay = float(self.params.get("delay", 0.05))

        def work(item: Any) -> str:
            time.sleep(fake_delay)  # 模拟一次耗时调用（真实场景是调 API 生成素片）
            return f"processed:{item}"

        results = map_parallel(work, items, max_workers=workers)

        # 产物落盘，payload 只留引用
        store = AssetsStore(
            outputs_root=self.params.get("outputs_root", "outputs"),
            workflow_id=workflow_data["meta"]["workflow_id"],
            run_id=self.params.get("run_id", "local"),
        )
        refs = []
        for i, text in enumerate(results, start=1):
            ref = store.save(f"item_{i:02d}.txt", text, subdir="parallel_demo")
            refs.append(ref)

        payload_asset(
            workflow_data["payload"],
            self.output_key(workflow_data, "assets"),
            refs[0] if refs else "",
            count=len(refs),
        )
        workflow_data["payload"][self.output_key(workflow_data, "results")] = results
        workflow_data["payload"][self.output_key(workflow_data, "refs")] = refs
        return workflow_data
