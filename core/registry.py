"""插件注册与发现。

发现约定（补齐了设计文档里没写明的部分）：

1. 扫描 ``plugins/`` 下每个子目录的 ``plugin.py``；也支持 ``plugins/<name>.py`` 单文件形式。
2. 导入模块后，取**该模块内定义**（``cls.__module__ == module.__name__``）的
   ``BasePlugin`` 非抽象子类；一个文件可以定义多个插件类，各自注册。
3. 导入失败的插件：**记录 warning 后跳过**，不让一个坏插件拖垮整个框架。
4. 类名重复 / ``plugin_name`` 冲突：保留先注册的，后到的记 warning 跳过；
   显式调用 :meth:`register` 时冲突直接报错（配置错误应 fail-fast）。
5. 因为插件里写 ``from plugin_base import ...``，发现前会把项目根插入 ``sys.path``。
"""

from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path
from typing import Dict, Iterator, List, Optional

from plugin_base import BasePlugin


class PluginConflictError(Exception):
    """插件名冲突。"""


class PluginRegistry:
    """插件注册表：``plugin_name`` -> 插件实例。"""

    def __init__(self) -> None:
        self._plugins: Dict[str, BasePlugin] = {}
        #: 发现过程中被跳过的插件及原因（导入失败、缺 plugin_name、重名…）
        self.warnings: List[str] = []

    # ---------- 注册 ----------

    def register(self, plugin: BasePlugin, override: bool = False) -> None:
        name = plugin.plugin_name
        if not name:
            raise PluginConflictError(f"插件 {type(plugin).__name__} 未声明 plugin_name")
        if name in self._plugins and not override:
            raise PluginConflictError(
                f"插件名冲突：{name!r} 已被 {type(self._plugins[name]).__name__} 占用"
            )
        self._plugins[name] = plugin

    def _register_soft(self, plugin: BasePlugin, source: str) -> None:
        """发现阶段用：冲突只记 warning，不中断。"""
        try:
            self.register(plugin)
        except PluginConflictError as exc:
            self.warnings.append(f"{source}: {exc}（已跳过）")

    # ---------- 查询 ----------

    def get(self, name: str) -> Optional[BasePlugin]:
        return self._plugins.get(name)

    def require(self, name: str, plugin_type: str | None = None) -> BasePlugin:
        """按名取插件，可同时校验类型；取不到或类型不符直接报错（fail-fast）。"""
        plugin = self._plugins.get(name)
        if plugin is None:
            raise KeyError(
                f"未找到插件 {name!r}；已注册：{sorted(self._plugins)}"
                + (f"；发现阶段跳过：{self.warnings}" if self.warnings else "")
            )
        if plugin_type and plugin.plugin_type != plugin_type:
            raise TypeError(
                f"插件 {name!r} 的类型是 {plugin.plugin_type!r}，但节点声明为 {plugin_type!r}"
            )
        return plugin

    def names(self) -> List[str]:
        return sorted(self._plugins)

    def items(self) -> Iterator[tuple]:
        return iter(sorted(self._plugins.items()))

    def __len__(self) -> int:
        return len(self._plugins)

    # ---------- 发现 ----------

    @classmethod
    def discover(cls, plugins_root: str | Path) -> "PluginRegistry":
        """扫描插件目录并实例化所有插件。"""
        registry = cls()
        root = Path(plugins_root)
        project_root = root.parent

        # 插件内 `from plugin_base import ...` 依赖项目根在 sys.path 上
        for p in (str(project_root), str(root)):
            if p not in sys.path:
                sys.path.insert(0, p)

        if not root.exists():
            registry.warnings.append(f"插件目录不存在：{root}")
            return registry

        for entry in sorted(root.iterdir()):
            if entry.name.startswith((".", "_")):
                continue
            if entry.is_dir():
                module_path = entry / "plugin.py"
                if not module_path.exists():
                    registry.warnings.append(f"{entry.name}/: 未找到 plugin.py（已跳过）")
                    continue
            elif entry.is_file() and entry.suffix == ".py":
                module_path = entry
            else:
                continue

            registry._load_module(module_path, entry.name)
        return registry

    def _load_module(self, module_path: Path, source: str) -> None:
        module_name = f"ai_framework.plugins.{module_path.parent.name}"
        spec = importlib.util.spec_from_file_location(module_name, str(module_path))
        if spec is None or spec.loader is None:
            self.warnings.append(f"{source}: 无法构造 import spec（已跳过）")
            return
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)  # type: ignore[union-attr]
        except Exception as exc:  # noqa: BLE001 - 插件是外部代码，坏插件不应拖垮框架
            self.warnings.append(f"{source}: 导入失败 {exc!r}（已跳过）")
            return

        found = 0
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if obj is BasePlugin or not issubclass(obj, BasePlugin):
                continue
            if obj.__module__ != module.__name__:  # 排除 import 进来的类
                continue
            if inspect.isabstract(obj):
                continue
            if not obj.plugin_name:
                self.warnings.append(f"{source}: 类 {obj.__name__} 未声明 plugin_name（已跳过）")
                continue
            self._register_soft(obj(), source)
            found += 1

        if found == 0:
            self.warnings.append(f"{source}: 未发现任何可注册的插件类（已跳过）")
