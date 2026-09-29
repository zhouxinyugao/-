"""调度内核单测（标准库 unittest，零额外依赖，换机即跑）。

    python -m unittest discover -s tests -v

覆盖点对应设计评审里提的 3 个 critical + 融合层骨头：
- finally unload（infer 抛异常也要卸载）
- params 通道
- KB 资源定位（type: kb 不是合法节点）
- payload 前缀校验 / meta 保护
- checkpoint：分段执行 + 断点续跑
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.engine import PayloadKeyError, WorkflowEngine  # noqa: E402
from core.registry import PluginRegistry  # noqa: E402
from plugin_base import BaseLLMPlugin, BaseSkillPlugin  # noqa: E402
from utils.schema_check import WorkflowConfigError, validate_workflow  # noqa: E402

PLUGINS_DIR = ROOT / "plugins"


# ---------------------------------------------------------------- 测试用插件


class FailPlugin(BaseLLMPlugin):
    """infer 一定抛异常的插件，用来验证 unload 是否仍被调用。"""

    plugin_name = "fail_dummy"

    def __init__(self) -> None:
        super().__init__()
        self.loaded = 0
        self.unloaded = 0

    def load(self) -> dict:
        self.loaded += 1
        return {"status": "ok"}

    def infer(self, workflow_data: dict) -> dict:
        raise RuntimeError("boom")

    def unload(self) -> dict:
        self.unloaded += 1
        return {"status": "ok"}


class BadCitizenPlugin(BaseSkillPlugin):
    """既改 meta 又写无前缀 payload 的插件，用来验证两道守卫。"""

    plugin_name = "bad_citizen"

    def run(self, workflow_data: dict) -> dict:
        workflow_data["meta"]["workflow_id"] = "HACKED"
        workflow_data["payload"]["bad_key"] = 1
        return workflow_data


def wf(*nodes) -> dict:
    return {"workflow_id": "test_wf", "nodes": list(nodes)}


def node(node_id: str, ntype: str, plugin_name: str, **kw) -> dict:
    return {"node_id": node_id, "type": ntype, "plugin_name": plugin_name, **kw}


# ---------------------------------------------------------------- 测试


class TestDiscovery(unittest.TestCase):
    def test_discover_dummy_plugins(self):
        registry = PluginRegistry.discover(PLUGINS_DIR)
        self.assertEqual(
            registry.names(), ["api_dummy", "kb_dummy", "llm_dummy", "skill_print_payload"]
        )
        self.assertEqual(registry.get("llm_dummy").plugin_type, "llm")
        self.assertEqual(registry.get("api_dummy").plugin_type, "api")
        self.assertEqual(registry.get("kb_dummy").plugin_type, "kb")
        self.assertEqual([], registry.warnings)


class TestEngineLifecycle(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.runs_dir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_unload_is_called_even_when_infer_raises(self):
        """critical-1：infer 抛异常也必须 unload，否则显存泄漏。"""
        plugin = FailPlugin()
        registry = PluginRegistry()
        registry.register(plugin)
        engine = WorkflowEngine(registry, self.runs_dir)
        with self.assertRaises(RuntimeError):
            engine.run(wf(node("n1", "llm", "fail_dummy")), user_input="x")
        self.assertEqual(1, plugin.loaded)
        self.assertEqual(1, plugin.unloaded)

    def test_end_to_end_serial_and_payload_flow(self):
        registry = PluginRegistry.discover(PLUGINS_DIR)
        engine = WorkflowEngine(registry, self.runs_dir)
        result = engine.run(
            wf(
                node("s1", "llm", "llm_dummy"),
                node("s2", "skill", "skill_print_payload"),
                node("s3", "api", "api_dummy", params={"model": "m1"}),
            ),
            user_input="西瓜",
        )
        self.assertEqual(["s1", "s2", "s3"], result.executed_nodes)
        self.assertEqual("done", result.status)
        self.assertEqual("dummy模型输出：西瓜", result.payload["s1.result"])
        self.assertEqual("远程API输出(model=m1)：西瓜", result.payload["s3.result"])
        self.assertIn("s2.payload_keys", result.payload)

    def test_params_channel(self):
        """critical-2：YAML params 能通过 self.params 传到插件里。"""
        registry = PluginRegistry.discover(PLUGINS_DIR)
        engine = WorkflowEngine(registry, self.runs_dir)
        result = engine.run(
            wf(node("s1", "api", "api_dummy", params={"model": "gpt-42"})), user_input="x"
        )
        self.assertIn("gpt-42", result.payload["s1.result"])

    def test_kb_is_resource_not_node(self):
        """critical-3：KB 只能挂 llm/api；type: kb 不是合法节点类型。"""
        with self.assertRaises(WorkflowConfigError):
            validate_workflow(wf(node("s1", "kb", "kb_dummy")))
        with self.assertRaises(WorkflowConfigError):
            validate_workflow(wf(node("s1", "skill", "skill_print_payload", kb_plugin_name="kb")))

    def test_kb_result_written_before_infer(self):
        registry = PluginRegistry.discover(PLUGINS_DIR)
        kb = registry.require("kb_dummy", "kb")
        kb.add_docs("ads_lib", [{"id": "d1", "text": "西瓜 夏天 解暑"}])
        engine = WorkflowEngine(registry, self.runs_dir)
        result = engine.run(
            wf(node("s1", "llm", "llm_dummy", kb_plugin_name="kb_dummy", kb_collection="ads_lib")),
            user_input="西瓜",
        )
        self.assertEqual(1, len(result.payload["kb_result"]))
        self.assertIn("KB 命中 1 条", result.payload["s1.result"])


class TestGuards(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.runs_dir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _registry(self) -> PluginRegistry:
        registry = PluginRegistry()
        registry.register(BadCitizenPlugin())
        return registry

    def test_meta_is_restored_and_warned(self):
        engine = WorkflowEngine(self._registry(), self.runs_dir)
        result = engine.run(wf(node("n1", "skill", "bad_citizen")), user_input="x")
        self.assertEqual("test_wf", result.workflow_data["meta"]["workflow_id"])
        self.assertTrue(any(e["event"] == "meta_guard" for e in result.trace))

    def test_payload_prefix_warning_vs_strict(self):
        engine = WorkflowEngine(self._registry(), self.runs_dir, strict_payload=False)
        result = engine.run(wf(node("n1", "skill", "bad_citizen")), user_input="x")
        self.assertTrue(any(e["event"] == "payload_prefix" for e in result.trace))

        strict = WorkflowEngine(self._registry(), self.runs_dir, strict_payload=True)
        with self.assertRaises(PayloadKeyError):
            strict.run(wf(node("n1", "skill", "bad_citizen")), user_input="x")


class TestCheckpoint(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.runs_dir = Path(self.tmp.name)
        self.registry = PluginRegistry.discover(PLUGINS_DIR)
        self.workflow = wf(
            node("s1", "llm", "llm_dummy"),
            node("s2", "skill", "skill_print_payload"),
            node("s3", "api", "api_dummy"),
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_stop_at_then_resume(self):
        """融合层骨头：分段执行（人机确认）+ 断点续跑。"""
        engine = WorkflowEngine(self.registry, self.runs_dir)
        first = engine.run(self.workflow, user_input="西瓜", stop_at="s2")
        self.assertEqual("paused", first.status)
        self.assertEqual(["s1", "s2"], first.executed_nodes)
        self.assertNotIn("s3.result", first.payload)

        second = engine.run(self.workflow, run_id=first.run_id, resume=True)
        self.assertEqual(["s3"], second.executed_nodes)
        self.assertEqual(["s1", "s2"], second.skipped_nodes)
        self.assertIn("s3.result", second.payload)
        self.assertIn("s1.result", second.payload)  # 上一段的产物仍在

    def test_failed_run_is_recorded(self):
        registry = PluginRegistry()
        registry.register(FailPlugin())
        engine = WorkflowEngine(registry, self.runs_dir)
        with self.assertRaises(RuntimeError):
            engine.run(wf(node("n1", "llm", "fail_dummy")), user_input="x")
        runs = engine.checkpoint.list_runs()
        self.assertEqual("failed", runs[-1]["status"])


class TestSchema(unittest.TestCase):
    def test_duplicate_node_id_rejected(self):
        with self.assertRaises(WorkflowConfigError):
            validate_workflow(wf(node("s1", "llm", "a"), node("s1", "llm", "b")))

    def test_empty_nodes_rejected(self):
        with self.assertRaises(WorkflowConfigError):
            validate_workflow({"workflow_id": "x", "nodes": []})


if __name__ == "__main__":
    unittest.main()
