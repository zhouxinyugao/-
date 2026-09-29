# 贡献指南

> 项目处于 0.x 早期阶段，API 不承诺兼容。当前以自用为主，开源计划见
> [`docs/决策与评审记录.md`](docs/决策与评审记录.md) 第五节。

## 开发前置

```bash
pip install -r requirements.txt   # 运行时依赖：pyyaml
python -m unittest discover -s tests -v   # 单测（标准库 unittest，无需额外依赖）
```

## 提交规范

- 一次提交 = 一个可独立回滚的小改动
- 提交信息前缀：`feat` / `fix` / `docs` / `refactor` / `test` / `chore`
- 每日至少同步一次到远端，见 [`docs/GitHub同步规范.md`](docs/GitHub同步规范.md)

## 写一个插件

1. 在 `plugins/<你的插件名>/plugin.py` 里写类，继承对应基类
   （`BaseLLMPlugin` / `BaseAPIPlugin` / `BaseSkillPlugin` / `BaseKBPlugin`）
2. 类里声明 `plugin_name`（注册表唯一标识，不能重名）
3. 用 `self.params` 读节点参数，用 `self.output_key(workflow_data, "xxx")` 写 payload
4. 跑 `python main.py list-plugins` 确认被发现

约定：
- **只读写 `payload`**，`meta` 归框架管（改了会被回滚并告警）
- 输出键必须带 `<node_id>.` 前缀，避免跨节点覆盖
- LLM/API 插件不要自己管显存释放——框架保证在 `finally` 里调 `unload()`

## 加一个工作流

在 `workflow/` 下写 YAML，`nodes` 从上到下即执行顺序：

```yaml
workflow_id: my_flow
nodes:
  - node_id: step_1
    type: llm            # llm / api / skill
    plugin_name: llm_dummy
    params: {}
```

跑：`python main.py run -w my_flow.yaml -i "输入" -v`

## 不做什么（保持克制）

框架不内置任何模型、提示词、业务逻辑。想加能力就写插件，不要把业务塞进内核。
追求"通用"会掉进配置地狱——目标是刚好接住自己的几条流程。
