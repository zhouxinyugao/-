"""最小示例 LLM 插件：把 user_input 原样包装后写回 payload。

用来验证：插件自动发现、load/infer/unload 生命周期、<node_id>.* 输出键约定。
"""

from __future__ import annotations

from typing import Any, Dict

from plugin_base import BaseLLMPlugin


class LlmDummyPlugin(BaseLLMPlugin):
    plugin_name = "llm_dummy"
    plugin_version = "0.1.0"
    plugin_description = "最小示例：dummy 本地模型"

    def load(self) -> Dict[str, Any]:
        print("[llm_dummy] 模拟加载模型")
        return {"status": "ok"}

    def infer(self, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        user_input = workflow_data["payload"].get("user_input", "")
        kb_result = workflow_data["payload"].get("kb_result")
        suffix = f"（KB 命中 {len(kb_result)} 条）" if kb_result else ""
        # 用 output_key 保证写入 <node_id>.result，满足框架的前缀校验
        workflow_data["payload"][self.output_key(workflow_data, "result")] = (
            f"dummy模型输出：{user_input}{suffix}"
        )
        return workflow_data

    def unload(self) -> Dict[str, Any]:
        print("[llm_dummy] 模拟卸载模型，释放显存")
        return {"status": "ok"}
