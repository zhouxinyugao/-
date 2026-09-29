# ai_framework · 轻量插件式 AI 工作流调度框架

> **状态：V0.1 骨架已跑通（本地仓库，尚未推送远端）**
> 目标：纯骨架框架，无内置业务逻辑；插件插拔、YAML 定义工作流、串行执行节点、
> LLM 插件生命周期由框架强制管理、全局统一数据流转；适配单 GPU 显存有限场景。

## 这是什么

- 插件遵守统一接口即可接入，框架自动扫描 `plugins/`
- 工作流顺序由 YAML 定义，V0.1 线性串行
- LLM/API 插件生命周期 `load() → infer() → unload()`，**异常时也保证卸载**
- 全局单一 `workflow_data{payload, meta}` 在节点间流转
- 每节点落 checkpoint：支持断点续跑、定点重跑、分段执行（人机确认的基础）

## 快速开始

```bash
pip install -r requirements.txt

python main.py list-plugins                                   # 看已发现的插件
python main.py run -w workflow/demo.yaml -i "西瓜，夏天解暑" -v  # 跑一条工作流
python main.py run -w demo_parallel.yaml -v                    # 节点内并发 + 资产只放引用
python main.py run -w demo.yaml -i "..." --stop-at step_2     # 跑到某节点暂停
python main.py run -w demo.yaml --resume <run_id>             # 断点续跑
python main.py runs                                           # 历史运行记录

python -m unittest discover -s tests -v                       # 单测（22 项）
```

## 目录结构

```
ai_framework/
├─ main.py                 # CLI 入口（list-plugins / run / runs）
├─ plugin_base.py          # 插件抽象基类：llm / api / skill / kb
├─ core/
│  ├─ engine.py            # 调度内核：串行驱动、生命周期、守卫、trace
│  ├─ registry.py          # 插件注册与自动发现
│  ├─ checkpoint.py        # 每节点落盘，支持 resume
│  ├─ concurrency.py       # 节点内并发工具（同序返回、fail-fast 可切、进度回调）
│  └─ assets.py            # 资产落盘约定：payload 只放引用，实体落 outputs/
├─ plugins/                # 插件目录（自动扫描，一个插件一个子目录）
├─ workflow/               # YAML 工作流配置
├─ utils/schema_check.py   # 工作流结构校验
├─ tests/                  # unittest（零额外依赖）
├─ outputs/                # 运行产物（不入库）
├─ runs/                   # checkpoint / 运行记录（不入库）
├─ docs/                   # 决策与评审记录、GitHub 同步规范
├─ .env.example            # 密钥模板；真密钥放 .env 且永不入库
├─ CHANGELOG.md / CONTRIBUTING.md / LICENSE
└─ requirements.txt
```

## 插件类型

| type | 基类 | 语义 |
|---|---|---|
| `llm` | `BaseLLMPlugin` | 本地模型，框架强制 load/infer/unload（异常也卸载） |
| `api` | `BaseAPIPlugin` | 远程 API，同一生命周期，load/unload 为空操作 |
| `skill` | `BaseSkillPlugin` | 工具函数，无显存操作，只实现 `run()` |
| `kb` | `BaseKBPlugin` | 知识库**资源**，不是可调度节点，只能挂在 llm/api 节点上 |

## 全局数据结构

```python
workflow_data = {
    "payload": {},   # 业务数据，插件读写；输出键约定 <node_id>.xxx
    "meta": {
        "workflow_id": "", "current_node_id": "", "node_params": {}, "trace": []
    }
}
```

框架守卫：插件改 `meta` 会被回滚并告警；写入非 `<node_id>.` 前缀的 payload 键会告警，
`--strict-payload` 下直接报错。`trace` 为结构化事件（时间 / 级别 / node_id / 事件 / 耗时）。

## 环境可复制性（换机 / 协作必读）

1. **Python**：3.10+（写在 `requirements.txt` 顶部）
2. **依赖**：`pip install -r requirements.txt`；新增依赖必须登记并注明用途
3. **密钥**：复制 `.env.example` → `.env` 后填写；`.env` 已在 `.gitignore`，永不入库
4. **路径**：禁止硬编码绝对路径，统一 `pathlib` 相对项目根
5. **产物**：`outputs/`、`runs/` 不入库
6. **记录**：所有设计决策写入 `docs/`，与代码同仓保存
7. **同步**：见 [`docs/GitHub同步规范.md`](docs/GitHub同步规范.md)

## 文档

- [`docs/决策与评审记录.md`](docs/决策与评审记录.md) —— 本项目的"记忆"：
  设计评审（3 个 critical）、与既有项目融合分析、验收清单、GitHub 竞品调研、开源岔路
- [`docs/GitHub同步规范.md`](docs/GitHub同步规范.md) —— 认证、提交粒度、不入库清单、换机恢复
- [`CONTRIBUTING.md`](CONTRIBUTING.md) —— 如何写插件 / 工作流
- [`CHANGELOG.md`](CHANGELOG.md) —— 变更日志

## 开源计划

先以 private 仓库每日同步，等差异化论证（为什么比「Ollama + Talos」这类组合更好用）
写进决策记录后再转 public。见决策记录第四、五节。
