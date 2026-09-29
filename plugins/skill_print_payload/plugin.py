"""最小示例 Skill 插件：打印当前 payload 的键，并把键列表写回。

Skill 插件无显存操作，只实现 run()。
"""

from __future__ import annotations

from typing import Any, Dict

from plugin_base import BaseSkillPlugin


class SkillPrintPayloadPlugin(BaseSkillPlugin):
    plugin_name = "skill_print_payload"
    plugin_version = "0.1.0"
    plugin_description = "打印 payload 键，并把键列表写回 payload"

    def run(self, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        keys = sorted(workflow_data["payload"])
        print(f"[skill_print_payload] payload keys = {keys}")
        workflow_data["payload"][self.output_key(workflow_data, "payload_keys")] = keys
        return workflow_data
