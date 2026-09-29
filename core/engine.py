"""调度内核。

职责（无业务逻辑）：扫描插件 -> 解析工作流 -> 串行驱动节点 -> 维护全局 workflow_data -> 落 checkpoint。

相对设计文档补齐的关键点：

1. **unload 放进 finally**：infer 抛异常也保证卸载（critical-1）。
2. **params 通道**：节点 params 通过 ``bind_params()`` 注入插件，并镜像到 ``meta["node_params"]``（critical-2）。
3. **KB 定性为资源**：只挂在 llm/api 节点，检索结果写入 ``payload["kb_result"]``；
   ``type: kb`` 不是合法节点类型（critical-3）。
4. **payload 前缀校验**：节点写完 diff payload，非 ``<node_id>.*`` 前缀的写入会告警，
   ``strict_payload=True`` 时直接报错。
5. **meta 保护**：插件改了 meta 顶层字段会被回滚并告警。
6. **checkpoint**：每个节点后落盘，支持 ``resume`` / ``start_from`` / ``stop_at``
   （断点续跑、分段执行、定点重跑的基础）。
7. **结构化 trace**：时间 / 级别 / node_id / 事件 / 耗时，外加 ``on_event`` 回调供 UI 订阅。
"""

from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.checkpoint import CheckpointStore
from plugin_base import BaseLLMPlugin, BaseSkillPlugin
from utils.schema_check import WorkflowConfigError, validate_workflow

#: 框架自己写入 payload 的白名单键（不受 node_id 前缀约束）
FRAMEWORK_PAYLOAD_KEYS = frozenset({"kb_result", "user_input"})

#: 插件不得修改的 meta 顶层字段（trace 由框架追加，不在此列）
META_PROTECTED_KEYS = ("workflow_id", "current_node_id", "node_params")


class EngineError(Exception):
    """调度内核异常。"""


class PayloadKeyError(EngineError):
    """payload 键不符合前缀约定。"""


@dataclass
class RunResult:
    """一次运行的返回值。"""

    run_id: str
    workflow_id: str
    workflow_data: Dict[str, Any]
    executed_nodes: List[str] = field(default_factory=list)
    skipped_nodes: List[str] = field(default_factory=list)
    status: str = "done"

    @property
    def payload(self) -> Dict[str, Any]:
        return self.workflow_data["payload"]

    @property
    def trace(self) -> List[Dict[str, Any]]:
        return self.workflow_data["meta"]["trace"]

    def __repr__(self) -> str:
        return (
            f"<RunResult {self.run_id} status={self.status} "
            f"executed={self.executed_nodes} skipped={self.skipped_nodes}>"
        )


class WorkflowEngine:
    """串行执行工作流的内核。可 headless 使用（供 UI / 服务调用）。"""

    def __init__(
        self,
        registry,
        runs_dir: str | Path,
        on_event: Optional[Callable[[Dict[str, Any]], None]] = None,
        strict_payload: bool = False,
    ) -> None:
        self.registry = registry
        self.checkpoint = CheckpointStore(runs_dir)
        self.on_event = on_event
        self.strict_payload = strict_payload
        self._keep_alive_loaded: List[BaseLLMPlugin] = []

    # ------------------------------------------------------------------ 对外

    def run(
        self,
        workflow: Dict[str, Any],
        user_input: Any = None,
        run_id: Optional[str] = None,
        resume: bool = False,
        start_from: Optional[str] = None,
        stop_at: Optional[str] = None,
    ) -> RunResult:
        """执行一条工作流。

        :param resume: 从已有 checkpoint 恢复，跳过已完成的节点
        :param start_from: 从指定 node_id 开始（之前的节点视为已完成，不执行）
        :param stop_at: 执行到指定 node_id 后暂停（status=paused，可再 resume 继续）
        """
        cfg = validate_workflow(workflow)
        workflow_id = cfg["workflow_id"]
        nodes = cfg["nodes"]
        node_ids = [n["node_id"] for n in nodes]

        completed: List[str] = []
        if resume:
            rid = run_id or self.checkpoint.latest_run_id(workflow_id)
            if rid is None:
                raise EngineError(f"没有可恢复的 run（workflow_id={workflow_id}）")
            state = self.checkpoint.load(rid)
            if state is None:
                raise EngineError(f"checkpoint 读取失败：{rid}")
            run_id, workflow_data = rid, state["workflow_data"]
            completed = list(state.get("completed_nodes", []))
            self._emit(workflow_data, "info", "", "resume", f"从 {rid} 恢复，已完成 {completed}")
        else:
            run_id = run_id or self.checkpoint.new_run_id(workflow_id)
            workflow_data = self._init_data(workflow_id, user_input)
            self.checkpoint.save(run_id, workflow_id, workflow_data, completed, "running")

        completed_set = set(completed)

        # 定点重跑：start_from 之前的节点视为已完成
        if start_from:
            if start_from not in node_ids:
                raise EngineError(f"start_from={start_from!r} 不在节点列表中：{node_ids}")
            for nid in node_ids[: node_ids.index(start_from)]:
                completed_set.add(nid)
        if stop_at and stop_at not in node_ids:
            raise EngineError(f"stop_at={stop_at!r} 不在节点列表中：{node_ids}")

        executed: List[str] = []
        skipped: List[str] = []
        stopped = False

        try:
            try:
                for node in nodes:
                    nid = node["node_id"]
                    if nid in completed_set:
                        skipped.append(nid)
                        continue
                    workflow_data = self._run_node(node, workflow_data)
                    executed.append(nid)
                    completed_set.add(nid)
                    completed.append(nid)
                    self.checkpoint.save(run_id, workflow_id, workflow_data, completed, "running")
                    if stop_at and nid == stop_at:
                        stopped = True
                        break
            finally:
                # 无论成功、失败还是中途暂停，都要释放 keep_alive 的模型
                self._unload_keep_alive(workflow_data)
        except Exception as exc:  # noqa: BLE001 - fail-fast，但要留下现场
            self.checkpoint.save(
                run_id, workflow_id, workflow_data, completed, "failed", error=repr(exc)
            )
            raise

        status = "paused" if stopped else "done"
        self.checkpoint.save(run_id, workflow_id, workflow_data, completed, status)
        return RunResult(run_id, workflow_id, workflow_data, executed, skipped, status)

    # ------------------------------------------------------------------ 单节点

    def _run_node(self, node: Dict[str, Any], workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        nid = node["node_id"]
        meta = workflow_data["meta"]
        meta["current_node_id"] = nid
        meta["node_params"] = dict(node["params"])  # params 通道的镜像，供 trace 排查

        payload_before = copy.deepcopy(workflow_data["payload"])
        meta_before = {k: copy.deepcopy(v) for k, v in meta.items() if k != "trace"}
        started = time.perf_counter()

        self._emit(workflow_data, "info", nid, "node_start", f"{nid} 开始（type={node['type']}）")
        try:
            if node["type"] in ("llm", "api"):
                workflow_data = self._run_model_node(node, workflow_data)
            else:
                plugin = self.registry.require(node["plugin_name"], "skill")
                plugin.bind_params(node["params"])
                out = plugin.run(workflow_data)
                workflow_data = self._accept_output(out, workflow_data, node["plugin_name"])

            self._guard_meta(workflow_data, meta_before, nid)
            self._guard_payload_keys(workflow_data, payload_before, nid)
        except Exception as exc:  # noqa: BLE001
            self._emit(workflow_data, "error", nid, "node_failed", f"{type(exc).__name__}: {exc}")
            raise
        finally:
            self._emit(
                workflow_data,
                "info",
                nid,
                "node_end",
                f"{nid} 结束",
                duration_ms=(time.perf_counter() - started) * 1000,
            )
        return workflow_data

    def _run_model_node(self, node: Dict[str, Any], workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        nid = node["node_id"]
        plugin = self.registry.require(node["plugin_name"], node["type"])
        plugin.bind_params(node["params"])

        loaded = False
        try:
            res = plugin.load()  # type: ignore[union-attr]
            loaded = True
            self._emit(workflow_data, "info", nid, "load", f"{plugin.plugin_name} loaded: {res}")

            if node["kb_plugin_name"]:
                self._retrieve_kb(node, workflow_data)

            out = plugin.infer(workflow_data)  # type: ignore[union-attr]
            workflow_data = self._accept_output(out, workflow_data, plugin.plugin_name)
        finally:
            # critical-1：infer 抛异常也要卸载；load 失败则无需卸载（没东西可卸）
            if loaded:
                if getattr(plugin, "keep_alive", False):
                    if plugin not in self._keep_alive_loaded:  # type: ignore[arg-type]
                        self._keep_alive_loaded.append(plugin)  # type: ignore[arg-type]
                    self._emit(workflow_data, "info", nid, "keep_alive", "延迟到流程结束再卸载")
                else:
                    self._safe_unload(plugin, workflow_data, nid)  # type: ignore[arg-type]
        return workflow_data

    def _retrieve_kb(self, node: Dict[str, Any], workflow_data: Dict[str, Any]) -> None:
        nid = node["node_id"]
        plugin = self.registry.require(node["kb_plugin_name"], "kb")
        collection = node["kb_collection"] or "default"
        query_text = node["params"].get("kb_query") or workflow_data["payload"].get("user_input", "")
        docs = plugin.query(collection, str(query_text))
        workflow_data["payload"]["kb_result"] = docs
        self._emit(workflow_data, "info", nid, "kb_query", f"{collection} -> {len(docs)} 条")

    def _accept_output(
        self, out: Any, workflow_data: Dict[str, Any], plugin_name: str
    ) -> Dict[str, Any]:
        """插件可以原地改 workflow_data 后返回 None，也可以返回新的 workflow_data。"""
        if out is None:
            return workflow_data
        if not isinstance(out, dict):
            raise EngineError(f"插件 {plugin_name} 必须返回 dict 或 None，实际返回 {type(out).__name__}")
        if "payload" not in out or "meta" not in out:
            raise EngineError(f"插件 {plugin_name} 返回的 dict 缺少 payload / meta 顶层键")
        return out

    # ------------------------------------------------------------------ 守卫

    def _guard_meta(
        self, workflow_data: Dict[str, Any], meta_before: Dict[str, Any], nid: str
    ) -> None:
        """插件只能读 meta，不能改；改了就回滚并告警。"""
        meta = workflow_data["meta"]
        changed = []
        for key, value in meta_before.items():
            if key in META_PROTECTED_KEYS and meta.get(key) != value:
                meta[key] = value
                changed.append(key)
        if changed:
            self._emit(
                workflow_data,
                "warning",
                nid,
                "meta_guard",
                f"插件试图修改受保护的 meta 字段 {changed}，已回滚",
            )

    def _guard_payload_keys(
        self, workflow_data: Dict[str, Any], payload_before: Dict[str, Any], nid: str
    ) -> None:
        """强制 <node_id>.* 前缀，避免跨节点覆盖（设计文档风险点 3）。"""
        prefix = f"{nid}."
        violations = []
        for key, value in workflow_data["payload"].items():
            if key in payload_before and payload_before[key] == value:
                continue  # 未改动
            if key.startswith(prefix) or key in FRAMEWORK_PAYLOAD_KEYS:
                continue
            violations.append(key)
        if not violations:
            return
        msg = f"节点 {nid} 写入/覆盖了非 {prefix}* 前缀的 payload 键：{violations}"
        if self.strict_payload:
            raise PayloadKeyError(msg)
        self._emit(workflow_data, "warning", nid, "payload_prefix", msg)

    # ------------------------------------------------------------------ 生命周期

    def _safe_unload(self, plugin: BaseLLMPlugin, workflow_data: Dict[str, Any], nid: str) -> None:
        try:
            plugin.unload()
            self._emit(workflow_data, "info", nid, "unload", f"{plugin.plugin_name} unloaded")
        except Exception as exc:  # noqa: BLE001 - 卸载失败不能掩盖主流程错误
            self._emit(
                workflow_data,
                "warning",
                nid,
                "unload_failed",
                f"{plugin.plugin_name} 卸载失败：{exc!r}",
            )

    def _unload_keep_alive(self, workflow_data: Dict[str, Any]) -> None:
        for plugin in reversed(self._keep_alive_loaded):
            self._safe_unload(plugin, workflow_data, "")
        self._keep_alive_loaded.clear()

    # ------------------------------------------------------------------ 工具

    @staticmethod
    def _init_data(workflow_id: str, user_input: Any) -> Dict[str, Any]:
        return {
            "payload": {"user_input": user_input},
            "meta": {"workflow_id": workflow_id, "current_node_id": "", "trace": []},
        }

    def _emit(
        self,
        workflow_data: Dict[str, Any],
        level: str,
        node_id: str,
        event: str,
        message: str,
        duration_ms: Optional[float] = None,
    ) -> None:
        rec: Dict[str, Any] = {
            "ts": datetime.now().astimezone().isoformat(timespec="milliseconds"),
            "level": level,
            "node_id": node_id,
            "event": event,
            "message": message,
        }
        if duration_ms is not None:
            rec["duration_ms"] = round(duration_ms, 2)
        workflow_data.setdefault("meta", {}).setdefault("trace", []).append(rec)
        if self.on_event:
            self.on_event(rec)


__all__ = [
    "WorkflowEngine",
    "RunResult",
    "EngineError",
    "PayloadKeyError",
    "WorkflowConfigError",
    "FRAMEWORK_PAYLOAD_KEYS",
]
