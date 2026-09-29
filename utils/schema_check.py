"""工作流 YAML 的结构校验。

只做**结构**校验（字段、类型、唯一性、node type 合法性）；
插件是否存在、类型是否匹配，由 engine 在解析节点时结合注册表校验。
"""

from __future__ import annotations

from typing import Any, Dict, List

VALID_NODE_TYPES = ("llm", "api", "skill")

#: KB 只能挂在 llm/api 节点上（设计文档第 3 条 critical 缺陷的定性结论）
KB_ALLOWED_TYPES = ("llm", "api")


class WorkflowConfigError(ValueError):
    """工作流配置不合法。"""


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise WorkflowConfigError(msg)


def validate_workflow(cfg: Any) -> Dict[str, Any]:
    """校验并返回规范化后的工作流配置（dict）。不合法直接抛 WorkflowConfigError。"""
    _require(isinstance(cfg, dict), "工作流配置必须是 dict（YAML 顶层为 mapping）")

    workflow_id = cfg.get("workflow_id")
    _require(isinstance(workflow_id, str) and workflow_id.strip(), "缺少 workflow_id 或不是非空字符串")

    nodes = cfg.get("nodes")
    _require(isinstance(nodes, list) and len(nodes) > 0, "nodes 必须是非空数组")

    seen_ids: List[str] = []
    normalized_nodes = []
    for i, node in enumerate(nodes):
        where = f"nodes[{i}]"
        _require(isinstance(node, dict), f"{where} 必须是 mapping")

        node_id = node.get("node_id")
        _require(isinstance(node_id, str) and node_id.strip(), f"{where} 缺少 node_id")
        _require(node_id not in seen_ids, f"{where} node_id 重复：{node_id!r}")
        seen_ids.append(node_id)

        ntype = node.get("type")
        _require(
            ntype in VALID_NODE_TYPES,
            f"{where}({node_id}) type 必须是 {VALID_NODE_TYPES} 之一，当前为 {ntype!r}",
        )

        plugin_name = node.get("plugin_name")
        _require(
            isinstance(plugin_name, str) and plugin_name.strip(),
            f"{where}({node_id}) 缺少 plugin_name",
        )

        params = node.get("params") or {}
        _require(isinstance(params, dict), f"{where}({node_id}) params 必须是 mapping")

        kb_plugin_name = node.get("kb_plugin_name")
        kb_collection = node.get("kb_collection")
        if kb_plugin_name is not None or kb_collection is not None:
            _require(
                ntype in KB_ALLOWED_TYPES,
                f"{where}({node_id}) 只有 {KB_ALLOWED_TYPES} 节点能绑定知识库，当前 type={ntype!r}",
            )
            _require(
                isinstance(kb_plugin_name, str) and kb_plugin_name.strip(),
                f"{where}({node_id}) 绑定知识库时必须提供 kb_plugin_name",
            )

        normalized_nodes.append(
            {
                "node_id": node_id,
                "type": ntype,
                "plugin_name": plugin_name,
                "params": params,
                "kb_plugin_name": kb_plugin_name,
                "kb_collection": kb_collection,
            }
        )

    return {"workflow_id": workflow_id, "nodes": normalized_nodes}
