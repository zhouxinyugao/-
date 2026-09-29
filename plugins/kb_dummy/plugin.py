"""最小示例 KB 插件：内存字典模拟向量库分区。

KB 是**资源**而非可调度节点：只能由 llm/api 节点通过 kb_plugin_name / kb_collection 挂载，
框架在 infer 前检索，结果写入 payload["kb_result"]。
"""

from __future__ import annotations

from typing import Any, Dict, List

from plugin_base import BaseKBPlugin


class KbDummyPlugin(BaseKBPlugin):
    plugin_name = "kb_dummy"
    plugin_version = "0.1.0"
    plugin_description = "最小示例：内存知识库（多分区）"

    def __init__(self) -> None:
        super().__init__()
        self._store: Dict[str, Dict[str, str]] = {}

    def query(self, collection_id: str, search_text: str) -> List[Dict[str, Any]]:
        docs = self._store.get(collection_id, {})
        hits = [
            {"id": doc_id, "text": text, "score": 1.0}
            for doc_id, text in docs.items()
            if search_text and search_text in text
        ]
        print(f"[kb_dummy] query({collection_id!r}, {search_text!r}) -> {len(hits)} 条")
        return hits

    def add_docs(self, collection_id: str, docs: list) -> None:
        bucket = self._store.setdefault(collection_id, {})
        for i, doc in enumerate(docs):
            doc_id = doc.get("id") if isinstance(doc, dict) else None
            doc_id = doc_id or f"doc_{len(bucket) + i + 1}"
            bucket[doc_id] = doc.get("text", "") if isinstance(doc, dict) else str(doc)

    def delete_docs(self, collection_id: str, doc_ids: list) -> None:
        bucket = self._store.get(collection_id, {})
        for doc_id in doc_ids:
            bucket.pop(doc_id, None)
