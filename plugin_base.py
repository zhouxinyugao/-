"""插件抽象层。

框架不绑定任何模型、技能、知识库；插件只要继承对应基类、实现抽象方法即可被自动发现。

四类插件：

===========  =============  ==========================================================
plugin_type  基类            语义
===========  =============  ==========================================================
llm          BaseLLMPlugin  本地模型，框架强制 load() -> infer() -> unload() 生命周期
api          BaseAPIPlugin  远程 API，沿用同一生命周期，但 load/unload 为空操作
skill        BaseSkillPlugin 工具函数，无显存操作，只实现 run()
kb           BaseKBPlugin   知识库资源，**不是可调度节点**，只能挂在 llm/api 节点上
===========  =============  ==========================================================

约定（由框架保证）：
1. ``params`` 通道：节点在 YAML 里声明的 ``params``，由框架在调用前通过 :meth:`bind_params`
   注入，插件内用 ``self.params`` 读取（同时会镜像到 ``meta["node_params"]`` 供 trace 排查）。
2. 输出键前缀：插件写入 payload 的新键建议用 ``self.output_key(workflow_data, "xxx")``，
   即 ``<node_id>.xxx``，避免跨节点覆盖。框架会做前缀校验（见 core/engine.py）。
3. 插件只能读写 ``payload``，``meta`` 顶层字段由框架维护，改动会被框架回滚。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict


class PluginError(Exception):
    """插件层基础异常。"""


class BasePlugin(ABC):
    """所有插件的根基类。

    子类必须声明 ``plugin_name``（注册表内的唯一标识）；
    ``plugin_type`` 由具体子类给定，不要手动覆盖。
    """

    plugin_name: str = ""
    plugin_type: str = ""
    plugin_version: str = "0.1.0"
    plugin_description: str = ""

    def __init__(self) -> None:
        # 由框架在执行前通过 bind_params() 注入，插件只读
        self.params: Dict[str, Any] = {}

    def bind_params(self, params: Dict[str, Any] | None) -> None:
        """注入节点级参数（YAML 中的 params）。框架调用，插件不要重写。"""
        self.params = dict(params or {})

    def output_key(self, workflow_data: Dict[str, Any], name: str) -> str:
        """生成符合约定的输出键：<当前node_id>.<name>。

        插件不知道自己在哪个节点里，所以从 meta 里取；这样天然满足前缀校验。
        """
        node_id = workflow_data.get("meta", {}).get("current_node_id", "unknown")
        return f"{node_id}.{name}"

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.plugin_name!r} type={self.plugin_type!r}>"


class BaseLLMPlugin(BasePlugin):
    """本地模型插件。生命周期由框架强制管理：load -> infer -> unload。"""

    plugin_type = "llm"

    #: 为 True 时框架不在节点结束后立即卸载，而是延迟到整条 workflow 跑完再卸载。
    #: 多 LLM 节点复用同一模型时可显著降低重复加载开销（代价是显存占用时间变长）。
    keep_alive: bool = False

    @abstractmethod
    def load(self) -> Dict[str, Any]:
        """加载模型到显存，返回 {"status": "ok"}。"""

    @abstractmethod
    def infer(self, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        """推理。接收完整 workflow_data，返回更新后的 workflow_data（也可原地改后返回 None）。"""

    @abstractmethod
    def unload(self) -> Dict[str, Any]:
        """卸载模型、释放显存。框架保证在 infer 抛异常时同样被调用。"""


class BaseAPIPlugin(BaseLLMPlugin):
    """远程 API 插件。

    与 LLM 插件共用生命周期，语义一致，因此可以直接替换本地模型插件；
    load/unload 默认为空操作（远程没有本地显存可释放）。
    """

    plugin_type = "api"

    def load(self) -> Dict[str, Any]:
        return {"status": "ok", "remote": True}

    def unload(self) -> Dict[str, Any]:
        return {"status": "ok", "remote": True}


class BaseSkillPlugin(BasePlugin):
    """工具插件：检索、导出、校验等，无显存操作。"""

    plugin_type = "skill"

    @abstractmethod
    def run(self, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行工具逻辑，返回更新后的 workflow_data（也可原地改后返回 None）。"""


class BaseKBPlugin(BasePlugin):
    """知识库插件：向量库封装，支持多隔离分区。

    定位：**资源，不是可调度节点**。只能通过节点的 ``kb_plugin_name`` / ``kb_collection``
    挂在 llm/api 节点上，由框架在 infer 前检索并把结果写入 ``payload["kb_result"]``。
    """

    plugin_type = "kb"

    @abstractmethod
    def query(self, collection_id: str, search_text: str) -> list:
        """在指定分区检索，返回结果列表。"""

    @abstractmethod
    def add_docs(self, collection_id: str, docs: list) -> None:
        """向指定分区新增文档。"""

    @abstractmethod
    def delete_docs(self, collection_id: str, doc_ids: list) -> None:
        """删除指定分区文档。"""
