"""节点内并发工具。

框架层面是**串行**的（V0.1 不做并行节点），但单个节点内部经常要并发——
比如素片生成要并发 3 路调 API。这类并发由插件自己发起，框架只提供统一的工具与约定，
避免每个插件各写一套线程池。

约定：
- 并发结果**与输入同序**返回，调用方不必自己对齐索引；
- 默认 fail-fast（一个失败立即取消剩余任务并抛错），符合框架的整体失败策略；
- 进度/错误通过回调抛出，方便插件把进度写进 payload 或 trace。
"""

from __future__ import annotations

from concurrent.futures import FIRST_EXCEPTION, ThreadPoolExecutor, wait
from typing import Any, Callable, Iterable, List, Optional, Sequence


class ConcurrentError(RuntimeError):
    """并发任务中有失败。"""

    def __init__(self, message: str, index: int, cause: BaseException) -> None:
        super().__init__(message)
        self.index = index
        self.cause = cause


def map_parallel(
    fn: Callable[[Any], Any],
    items: Sequence[Any] | Iterable[Any],
    max_workers: int = 3,
    fail_fast: bool = True,
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> List[Any]:
    """并发执行 ``fn(item)``，返回与 items 同序的结果列表。

    :param max_workers: 并发度（老项目素片生成的默认值就是 3）
    :param fail_fast: True=任一任务失败立即取消剩余并抛 ConcurrentError；
                      False=失败位置填 None，其余照常返回
    :param on_progress: 进度回调 ``(已完成数, 总数)``
    """
    items = list(items)
    total = len(items)
    if total == 0:
        return []

    workers = max(1, min(int(max_workers), total))
    results: List[Any] = [None] * total
    done_count = 0

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fn, item): idx for idx, item in enumerate(items)}
        pending = set(futures)

        while pending:
            done, pending = wait(pending, return_when=FIRST_EXCEPTION)
            for fut in done:
                idx = futures[fut]
                exc = fut.exception()
                if exc is not None:
                    if fail_fast:
                        for f in pending:
                            f.cancel()
                        raise ConcurrentError(f"第 {idx} 个并发任务失败", idx, exc) from exc
                    results[idx] = None
                else:
                    results[idx] = fut.result()
                done_count += 1
                if on_progress:
                    on_progress(done_count, total)

            if fail_fast and pending:
                # FIRST_EXCEPTION 返回说明有任务抛了异常，上面的循环里已抛出；
                # 这里只是兜底，防止极端情况下空转
                break

    return results
