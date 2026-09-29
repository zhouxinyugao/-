"""Checkpoint 持久化：把每条 run 的 workflow_data 与执行进度落盘，支持断点续跑。

目录约定::

    runs/<run_id>/checkpoint.json

``run_id`` 形如 ``demo_001-20260930-014700-a1b2c3``。
state 结构::

    {
      "run_id": ..., "workflow_id": ..., "status": "running|paused|done|failed",
      "created_at": ..., "updated_at": ...,
      "completed_nodes": ["step_1", ...],
      "workflow_data": {"payload": {...}, "meta": {...}},
      "error": null
    }

V0.1 直接把 workflow_data 整份写入 JSON（简单、可读、够用）。
后续若 payload 里出现大件资产，应改为「payload 只放引用 + 资产单独落 outputs/」。
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class CheckpointStore:
    """简单的文件系统 checkpoint 存储。"""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    # ---------- run ----------

    def new_run_id(self, workflow_id: str) -> str:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        return f"{workflow_id}-{ts}-{uuid.uuid4().hex[:6]}"

    def dir_of(self, run_id: str) -> Path:
        return self.root / run_id

    # ---------- 读写 ----------

    def save(
        self,
        run_id: str,
        workflow_id: str,
        workflow_data: Dict[str, Any],
        completed_nodes: List[str],
        status: str = "running",
        error: Optional[str] = None,
    ) -> Path:
        d = self.dir_of(run_id)
        d.mkdir(parents=True, exist_ok=True)
        path = d / "checkpoint.json"

        prev = self.load(run_id) or {}
        state = {
            "run_id": run_id,
            "workflow_id": workflow_id,
            "status": status,
            "created_at": prev.get("created_at", _now()),
            "updated_at": _now(),
            "completed_nodes": list(completed_nodes),
            "workflow_data": workflow_data,
            "error": error,
        }
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)  # 原子替换，避免写到一半断电留下坏文件
        return path

    def load(self, run_id: str) -> Optional[Dict[str, Any]]:
        path = self.dir_of(run_id) / "checkpoint.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def latest_run_id(self, workflow_id: Optional[str] = None) -> Optional[str]:
        """取最近一次 run；可按 workflow_id 过滤。"""
        candidates = []
        for d in self.root.iterdir() if self.root.exists() else []:
            if not d.is_dir() or not (d / "checkpoint.json").exists():
                continue
            if workflow_id and not d.name.startswith(workflow_id + "-"):
                continue
            candidates.append(d)
        if not candidates:
            return None
        newest = max(candidates, key=lambda p: (p / "checkpoint.json").stat().st_mtime)
        return newest.name

    def list_runs(self) -> List[Dict[str, Any]]:
        runs = []
        for d in sorted(self.root.iterdir()) if self.root.exists() else []:
            if not d.is_dir():
                continue
            state = self.load(d.name)
            if state is None:
                continue
            runs.append(
                {
                    "run_id": state.get("run_id", d.name),
                    "workflow_id": state.get("workflow_id", ""),
                    "status": state.get("status", ""),
                    "updated_at": state.get("updated_at", ""),
                    "completed_nodes": state.get("completed_nodes", []),
                }
            )
        return runs
