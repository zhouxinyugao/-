"""示例插件：创意标签剖析（对应 idea-tag-analysis skill 的第 1 步）。

定位演示用，不是真模型：用规则把点子拆成标签组，用来展示——
1) `api` 类型插件怎么写（远程 LLM 的占位实现，load/unload 是空操作）
2) `params` 通道怎么用（YAML 里声明 content_type，插件内 self.params 读取）
3) 输出键约定（<node_id>.xxx，避免跨节点覆盖）

真接 LLM 时，只需把 _mock_infer 换成真实 API 调用，其余不动。
"""

from __future__ import annotations

from typing import Any, Dict

from plugin_base import BaseAPIPlugin

# 演示用的极简规则库；真实场景应由 LLM 产出
_RULES = {
    "西瓜": {
        "品类": "生鲜水果",
        "卖点": ["爆汁", "高甜度", "冰镇解暑"],
        "视觉母题": ["绿皮红瓤", "切面水珠", "勺子挖球"],
        "场景": ["居家冰箱", "野餐草坪", "夜市摊位"],
    },
    "口红": {
        "品类": "美妆个护",
        "卖点": ["显白", "不拔干", "持久"],
        "视觉母题": ["唇部特写", "色号试色", "包装质感"],
        "场景": ["化妆台", "通勤补妆", "约会前"],
    },
}

_DEFAULT = {
    "品类": "未分类",
    "卖点": ["待补充"],
    "视觉母题": ["待补充"],
    "场景": ["待补充"],
}


class IdeaTaggerPlugin(BaseAPIPlugin):
    plugin_name = "idea_tagger"
    plugin_version = "0.1.0"
    plugin_description = "示例：把点子剖析成结构化标签组（远程 LLM 占位实现）"

    def infer(self, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        user_input = workflow_data["payload"].get("user_input", "")
        # params 通道：YAML 里声明的 content_type
        content_type = self.params.get("content_type", "未指定")

        base = dict(_DEFAULT)
        for keyword, tags in _RULES.items():
            if keyword in user_input:
                base = tags
                break

        label_group = {
            "content_type": content_type,
            "tags": base,
            "summary": f"{base['品类']} × {content_type}：围绕 {base['卖点'][0]} 做视觉",
        }
        workflow_data["payload"][self.output_key(workflow_data, "label_group")] = label_group
        return workflow_data

    def _mock_infer(self, text: str) -> Dict[str, Any]:  # pragma: no cover
        """真接 LLM 时替换这里即可。"""
        raise NotImplementedError
