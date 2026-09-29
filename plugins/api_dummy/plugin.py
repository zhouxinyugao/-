"""最小示例 API 插件：模拟远程大模型调用（无本地显存，load/unload 为空操作）。

用来验证：4GB 显存 / v1 云端 API 为主场景下，`api` 类型能与 `llm` 类型互换。
"""

from __future__ import annotations

from typing import Any, Dict

from plugin_base import BaseAPIPlugin


class ApiDummyPlugin(BaseAPIPlugin):
    plugin_name = "api_dummy"
    plugin_version = "0.1.0"
    plugin_description = "最小示例：dummy 远程 API 模型"

    def infer(self, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        user_input = workflow_data["payload"].get("user_input", "")
        model = self.params.get("model", "unknown")
        workflow_data["payload"][self.output_key(workflow_data, "result")] = (
            f"远程API输出(model={model})：{user_input}"
        )
        return workflow_data
