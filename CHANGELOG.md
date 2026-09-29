# 变更日志

本项目采用 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 风格，
版本遵循语义化版本（MAJOR.MINOR.PATCH）。**决定开源前的版本号一律为 0.x，API 不承诺兼容。**

## [Unreleased]

### Added
- 插件抽象层 `plugin_base.py`：`llm` / `api` / `skill` / `kb` 四类插件基类
- 调度内核 `main.py` + `core/engine.py`：串行驱动、finally unload、params 通道、
  payload 前缀校验、meta 保护、结构化 trace、checkpoint
- `core/registry.py`：插件自动发现（导入失败跳过、重名告警）
- `core/checkpoint.py`：每节点落盘，支持 `resume` / `--from-node` 定点重跑 / `--stop-at` 分段执行
- `utils/schema_check.py`：工作流 YAML 结构校验
- 4 个 dummy 插件（`llm_dummy` / `api_dummy` / `skill_print_payload` / `kb_dummy`）与 `workflow/demo.yaml`
- `tests/test_engine.py`：unittest 覆盖生命周期、守卫、checkpoint、schema
- `docs/GitHub同步规范.md`、`docs/决策与评审记录.md`

### Added（第二批：融合层骨头）
- `core/concurrency.py`：节点内并发工具（结果同序、fail-fast 可切、进度回调）
- `core/assets.py`：资产落盘约定——实体落 `outputs/<wf>/<run>/assets/`，payload 只放引用
- `plugins/skill_parallel_demo` + `workflow/demo_parallel.yaml`：并发与资产引用的可参考写法
- `tests/test_core_utils.py`：并发与资产单测（合计 22 项）

### 待办（融合层剩余骨头，见决策记录第三节）
- [x] 节点内并发（素片生成并发 3）
- [x] 资产引用约定（payload 只放路径，大件落 `outputs/`）
- [ ] 子流程 / 嵌套节点
- [ ] headless API + 进度回传给 UI

---

## [0.0.1] - 2026-09-30
### Added
- 工程骨架与规范：README、.gitignore、.gitattributes、requirements.txt、.env.example
- 决策与评审记录（V0.1 设计评审、融合分析、竞品调研、开源岔路）
