"""资产落盘与引用约定。

老项目的产物是 MP4 / 图 / 音频 / 素材库这类大件，**不能塞进 payload**（会把 dict 撑爆，
也会让 checkpoint.json 变得巨大）。约定：

- **实体文件**落到 ``outputs/<workflow_id>/<run_id>/assets/<subdir>/<name>``
- **payload 里只放引用字符串**（相对项目根的路径），形如
  ``outputs/demo_001/xxx/assets/shots/shot_01.mp4``
- 框架提供 :meth:`AssetsStore.ref` / :meth:`save` / :meth:`abspath` 三个方法，
  插件不必自己拼路径（也就不会出现绝对路径硬编码）

``outputs/`` 已在 .gitignore 中，不入库；换机可安全丢弃。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict

_SAFE = re.compile(r"[^0-9A-Za-z._-]+")


def safe_name(name: str) -> str:
    """把任意字符串洗成安全文件名（中文保留，斜杠/冒号等换成下划线）。"""
    return _SAFE.sub("_", name).strip("._") or "unnamed"


class AssetsStore:
    """一次 run 的资产目录。"""

    def __init__(self, outputs_root: str | Path, workflow_id: str, run_id: str) -> None:
        # 解析成绝对路径，ref 才能稳定地相对"项目根"表示（换机/换工作目录都不变）
        self.outputs_root = Path(outputs_root).resolve()
        self.workflow_id = workflow_id
        self.run_id = run_id
        self.dir = self.outputs_root / safe_name(workflow_id) / safe_name(run_id) / "assets"
        self.dir.mkdir(parents=True, exist_ok=True)

    # ---------- 写入 ----------

    def save(self, name: str, data: bytes | str, subdir: str = "") -> str:
        """写入资产，返回引用字符串（相对项目根）。"""
        path = self._path(name, subdir)
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, str):
            path.write_text(data, encoding="utf-8")
        else:
            path.write_bytes(data)
        return self.ref(name, subdir)

    # ---------- 引用 ----------

    def ref(self, name: str, subdir: str = "") -> str:
        """生成引用字符串（相对项目根，POSIX 分隔符，换机通用）。"""
        return self._path(name, subdir).relative_to(self.outputs_root.parent).as_posix()

    def abspath(self, ref: str) -> Path:
        """把引用还原成本地绝对路径。"""
        return self.outputs_root.parent / ref

    def read(self, ref: str, binary: bool = True) -> bytes | str:
        path = self.abspath(ref)
        return path.read_bytes() if binary else path.read_text(encoding="utf-8")

    def exists(self, ref: str) -> bool:
        return self.abspath(ref).exists()

    # ---------- 内部 ----------

    def _path(self, name: str, subdir: str) -> Path:
        parts = [safe_name(p) for p in subdir.split("/") if p.strip()]
        return self.dir.joinpath(*parts, safe_name(name))

    def __repr__(self) -> str:
        return f"<AssetsStore {self.dir}>"


def payload_asset(payload: Dict[str, Any], key: str, ref: str, **meta: Any) -> Dict[str, Any]:
    """往 payload 里写资产引用的推荐写法（引用 + 可选元信息，不放实体）。

    例：``payload_asset(payload, "step_2.shot_01", ref, duration=3.0)``
    """
    payload[key] = {"ref": ref, **meta}
    return payload
