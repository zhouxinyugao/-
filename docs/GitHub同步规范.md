# GitHub 同步规范

> 目标：**本地仓库与 GitHub 保持同源**，每天同步一点，随时可换机、随时可开源。
> 制定时间：2026-09-30

---

## 1. 仓库与可见性

| 项 | 当前约定 |
|---|---|
| 仓库名 | `ai_framework` |
| 默认分支 | `master`（单人开发，日常直接提交主干；决定开源后再评估切 `develop` + PR 流程） |
| 可见性 | **先 private** |
| 转 public 的前提 | `docs/决策与评审记录.md` 第四节里的"差异化论证"补齐（为什么比 Ollama+Talos 组合更好用） |

理由：开源定位未定。先 private 既能拿云端备份与跨设备同步的好处，又不用提前承诺 API 稳定性。

## 2. 认证方式

**GitHub CLI（`gh`）浏览器登录**——凭据由系统托管，token 不落盘、不进仓库、不经手任何人。

```bash
gh auth login --web --git-protocol https   # 只需做一次
gh auth status                             # 验证
```

首次建立远端：

```bash
gh repo create ai_framework --private --source=. --remote=origin --push
```

## 3. 每日同步流程（手敲版）

```bash
git status                 # 1. 看改了什么
git add -A                 # 2. 全部暂存（.gitignore 已排除密钥/产物）
git commit -m "feat: xxx"  # 3. 提交
git pull --rebase origin master   # 4. 先拉后推，避免冲突
git push                   # 5. 推送
```

## 4. 提交粒度与信息规范

- **一次提交 = 一个可独立回滚的小改动**。宁可一天三次，不要三天一次大包。
- 提交信息前缀：`feat` / `fix` / `docs` / `refactor` / `test` / `chore`，后跟简短中文描述。
  例：`feat: 引擎支持 stop_at 分段执行`、`fix: unload 未放进 finally`
- **每个可运行的能力点都配最小验证**（dummy 插件或单测），避免攒大招。

## 5. 绝不入库清单（换机/开源的安全底线）

| 类别 | 位置 | 保障 |
|---|---|---|
| 密钥 / token | `.env` | `.gitignore` 排除；仓库里只有 `.env.example` |
| 运行产物 | `outputs/*`、`runs/*` | `.gitignore` 排除（保留 `.gitkeep`） |
| 大文件（模型/素材/MP4） | 不进仓库 | 未来如需模型权重，用 Git LFS，不要直接 commit |
| 绝对路径 | 代码里 | 统一 `pathlib` 相对项目根 |

推送前自检：`git status --short` 里不应出现 `.env`、`outputs/`、`runs/`。

## 6. 换机恢复

```bash
git clone <repo-url>        # 或拷贝整个目录（含 .git）
pip install -r requirements.txt
cp .env.example .env        # 按需填密钥
python main.py list-plugins
```

## 7. 待办

- [ ] 完成 `gh auth login` 与首次 push
- [ ] 确认是否启用「每日自动同步」（定时 commit + push）
- [ ] 决定开源时机（补差异化论证后再转 public）
