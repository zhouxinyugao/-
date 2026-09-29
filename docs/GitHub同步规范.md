# GitHub 同步规范

> 目标：**本地仓库与 GitHub 保持同源**，每天同步一点，随时可换机、随时可开源。
> 制定时间：2026-09-30

---

## 1. 仓库与可见性

| 项 | 当前约定 |
|---|---|
| 仓库地址 | `git@github.com:zhouxinyugao/-.git`（**已完成首次推送**，2026-09-30） |
| 默认分支 | `master`（单人开发，日常直接提交主干；决定开源后再评估切 `develop` + PR 流程） |
| 可见性 | **当前是 public**（建仓时未选 private）。若不想公开：仓库 Settings → Danger Zone → Change visibility → Private |
| 转 public 的前提 | `docs/决策与评审记录.md` 第四节里的"差异化论证"补齐（为什么比 Ollama+Talos 组合更好用） |

理由：开源定位未定。先 private 既能拿云端备份与跨设备同步的好处，又不用提前承诺 API 稳定性。

## 2. 认证方式（当前：SSH）

**SSH 密钥**（2026-09-30 已配置完成）：

- 密钥：`~/.ssh/id_ed25519_ai_framework`
- `~/.ssh/config` 已为 `Host github.com` 绑定该密钥并开启 `IdentitiesOnly yes`
- 验证：`ssh -T git@github.com` → `Hi zhouxinyugao!`

```bash
ssh-keygen -t ed25519 -C "ai_framework@local" -f ~/.ssh/id_ed25519_ai_framework   # 生成（已做）
ssh -T git@github.com                                                             # 验证
```

远端已在用：

```bash
git remote add origin git@github.com:zhouxinyugao/-.git    # 已配好
git push -u origin master                                  # 已完成首次推送
```

### 备选：gh CLI / PAT（未启用）

`gh auth login --web` 曾两次 `Bad Gateway`（当时未开代理）。若日后需要无人值守地建仓库、
改可见性，可启用 PAT（classic + `repo` 权限）存进 Windows 凭据管理器。
**用户表示先了解 PAT 后再决定，暂不启用。**

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

## 7. 状态与待办

已完成：
- [x] SSH 认证打通（`ssh -T git@github.com` 通过）
- [x] 首次 push（6 次提交已上行）
- [x] 每日 22:00 自动同步（无改动不动 / 单测不过不提交 / 禁 `--force`）

待办：
- [ ] 仓库由 public 转 private（需用户在网页操作）
- [ ] 视情况启用 PAT，实现完全无人值守（含建仓、改可见性）
- [ ] 决定开源时机（补差异化论证后再转 public）
