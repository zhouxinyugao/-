"""ai_framework CLI 入口（调度内核）。

用法::

    python main.py list-plugins
    python main.py run --workflow workflow/demo.yaml --input "西瓜，夏天解暑"
    python main.py run --workflow workflow/demo.yaml --input "..." --stop-at step_2   # 跑到某节点暂停
    python main.py run --workflow workflow/demo.yaml --resume <run_id>               # 断点续跑
    python main.py run --workflow workflow/demo.yaml --from-node step_2 --resume <run_id>  # 定点重跑
    python main.py runs
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))  # 让 `from plugin_base import ...` 在插件里可用

import yaml  # noqa: E402

from core.engine import WorkflowEngine  # noqa: E402
from core.registry import PluginRegistry  # noqa: E402
from utils.schema_check import WorkflowConfigError  # noqa: E402

PLUGINS_DIR = ROOT / "plugins"
RUNS_DIR = ROOT / "runs"
WORKFLOW_DIR = ROOT / "workflow"


def load_workflow(path: str | Path) -> dict:
    p = Path(path)
    if not p.is_absolute() and not p.exists():
        candidate = WORKFLOW_DIR / p.name
        if candidate.exists():
            p = candidate
    if not p.exists():
        raise FileNotFoundError(f"工作流文件不存在：{path}")
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    if data is None:
        raise WorkflowConfigError(f"工作流文件为空：{p}")
    return data


def build_registry() -> PluginRegistry:
    registry = PluginRegistry.discover(PLUGINS_DIR)
    for w in registry.warnings:
        print(f"[warn] {w}", file=sys.stderr)
    return registry


def cmd_list_plugins(_args: argparse.Namespace) -> int:
    registry = build_registry()
    if not len(registry):
        print("未发现任何插件")
        return 1
    print(f"{'NAME':<24}{'TYPE':<8}{'VERSION':<10}DESCRIPTION")
    for name, plugin in registry.items():
        print(
            f"{name:<24}{plugin.plugin_type:<8}{plugin.plugin_version:<10}{plugin.plugin_description}"
        )
    return 0


def cmd_runs(_args: argparse.Namespace) -> int:
    engine = WorkflowEngine(PluginRegistry(), RUNS_DIR)
    runs = engine.checkpoint.list_runs()
    if not runs:
        print("暂无运行记录")
        return 0
    for r in runs:
        print(
            f"{r['run_id']}  status={r['status']:<8} "
            f"completed={len(r['completed_nodes'])}  updated={r['updated_at']}"
        )
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    registry = build_registry()
    engine = WorkflowEngine(
        registry,
        RUNS_DIR,
        on_event=(lambda e: print(f"  · [{e['level']}] {e['node_id']} {e['event']}: {e['message']}"))
        if args.verbose
        else None,
        strict_payload=args.strict_payload,
    )

    workflow = load_workflow(args.workflow)
    user_input: object
    if args.input_file:
        user_input = Path(args.input_file).read_text(encoding="utf-8")
    else:
        user_input = args.input or ""

    result = engine.run(
        workflow,
        user_input=user_input,
        run_id=args.run_id,
        resume=args.resume,
        start_from=args.from_node,
        stop_at=args.stop_at,
    )

    print(f"\n=== run {result.run_id} -> {result.status} ===")
    print(f"executed: {result.executed_nodes or '(无)'}")
    print(f"skipped : {result.skipped_nodes or '(无)'}")
    print("payload:")
    print(json.dumps(result.payload, ensure_ascii=False, indent=2))
    print(f"\ncheckpoint: {engine.checkpoint.dir_of(result.run_id) / 'checkpoint.json'}")
    if result.status != "done":
        print(f"继续：python main.py run --workflow {args.workflow} --resume {result.run_id}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai_framework", description="轻量插件式 AI 工作流调度框架")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list-plugins", help="列出已发现的插件").set_defaults(func=cmd_list_plugins)
    sub.add_parser("runs", help="列出历史运行记录").set_defaults(func=cmd_runs)

    p_run = sub.add_parser("run", help="执行一条工作流")
    p_run.add_argument("--workflow", "-w", required=True, help="YAML 路径（也可只给文件名，自动在 workflow/ 下找）")
    p_run.add_argument("--input", "-i", default="", help="用户输入，写入 payload['user_input']")
    p_run.add_argument("--input-file", default=None, help="从文件读取用户输入")
    p_run.add_argument("--run-id", default=None, help="指定 run_id（不指定则自动生成）")
    p_run.add_argument("--resume", action="store_true", help="从 checkpoint 恢复执行")
    p_run.add_argument("--from-node", default=None, help="从指定节点开始（配合 --resume 做定点重跑）")
    p_run.add_argument("--stop-at", default=None, help="执行到指定节点后暂停")
    p_run.add_argument("--strict-payload", action="store_true", help="payload 键不符合前缀约定时报错而非告警")
    p_run.add_argument("--verbose", "-v", action="store_true", help="实时打印 trace")
    p_run.set_defaults(func=cmd_run)
    return parser


def main(argv: list | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (WorkflowConfigError, FileNotFoundError, KeyError, TypeError) as exc:
        print(f"[error] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
