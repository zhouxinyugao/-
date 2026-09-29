"""示例插件：标签组 → 分镜（对应文生视频第 2 步）。

演示：skill 类型插件怎么写、上游产物怎么读（params 指定 key）、
以及产出的大件只放引用、不塞进 payload。
"""

from __future__ import annotations

from typing import Any, Dict

from plugin_base import BaseSkillPlugin


class TagToShotsPlugin(BaseSkillPlugin):
    plugin_name = "tag_to_shots"
    plugin_version = "0.1.0"
    plugin_description = "示例：把标签组转成若干条分镜文案"

    def run(self, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        # 上游键由 params 指定，避免插件之间硬编码耦合
        tags_key = self.params.get("label_group_key", "")
        shot_count = int(self.params.get("shot_count", 3))

        label_group = workflow_data["payload"].get(tags_key)
        if label_group is None:
            raise RuntimeError(f"payload 里找不到上游产物：{tags_key}")

        tags = label_group["tags"]
        motifs = tags.get("视觉母题", [])
        scenes = tags.get("场景", [])
        selling = tags.get("卖点", [])

        shots = []
        for i in range(shot_count):
            motif = motifs[i % len(motifs)] if motifs else "主视觉"
            scene = scenes[i % len(scenes)] if scenes else "通用场景"
            point = selling[i % len(selling)] if selling else "核心卖点"
            shots.append(
                {
                    "index": i + 1,
                    "duration": "0-3s",
                    "scene": scene,
                    "motif": motif,
                    "narration": f"突出「{point}」，画面落在{motif}",
                }
            )

        workflow_data["payload"][self.output_key(workflow_data, "shots")] = shots
        return workflow_data
