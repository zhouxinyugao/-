# ai_framework · 轻量插件式 AI 工作流调度框架

> **状态：设计中 / 骨架未实现**
> 本目录当前只固化「工程规范 + 决策记录」，为后续实现与可能的开源/换机做准备。
> 骨架代码（`main.py` / `plugin_base.py`）尚未编写。

## 这是什么

纯骨架调度框架，不绑定任何模型、技能、知识库：

- 插件遵守统一接口即可接入，框架自动扫描
- 工作流顺序由 YAML 定义，V0.1 线性串行
- LLM 插件生命周期 `load() / infer() / unload()` 由框架强制管理
- 全局单一 `workflow_data{payload, meta}` 在节点间流转
- 面向单 GPU 显存受限场景

## 目录规范

```
ai_framework/
├─ main.py              # 调度内核（待实现）
├─ plugin_base.py       # 插件抽象基类（待实现）
├─ plugins/             # 插件目录，自动扫描；每插件一个子目录 + plugin.py
├─ workflow/            # YAML 工作流配置
├─ utils/               # 工具（schema 校验等）
├─ outputs/             # 运行产物（不入库）
├─ runs/                # checkpoint / 运行记录（不入库，待实现）
├─ docs/                # 设计文档与决策记录
├─ .env.example         # 密钥模板；真密钥放 .env 且永不入库
├─ requirements.txt
└─ README.md
```

## 环境可复制性（换机 / 协作必读）

1. **Python**：3.10+（版本要求写在 `requirements.txt` 顶部）
2. **依赖**：`pip install -r requirements.txt`。新增依赖必须登记并注明用途
3. **密钥**：复制 `.env.example` → `.env` 后填写；`.env` 已在 `.gitignore`，永不入库
4. **路径**：代码中禁止硬编码绝对路径，统一用 `pathlib` 相对项目根解析
5. **产物**：`outputs/`、`runs/` 不入库，换机可安全丢弃
6. **记录**：所有设计决策与评审意见写入 `docs/`，与代码同仓保存

## 快速开始（待骨架实现后启用）

```bash
pip install -r requirements.txt
python main.py --workflow workflow/demo.yaml   # CLI 形式待定
```

## 决策记录

见 [`docs/决策与评审记录.md`](docs/决策与评审记录.md)，包含：
设计评审（3 个 critical 缺陷）、与既有项目的融合分析（5 条摩擦）、
框架验收清单、GitHub 竞品调研、开源岔路判断。

## 开源计划

待定。开源前必须先明确差异化定位——见决策记录第五节。
