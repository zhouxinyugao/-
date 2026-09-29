# GitHub 同步规范（通用）

> 目标：**本地仓库与远端保持同源**，随时可换机、随时可开源。
> 本文只写**通用规范**，不含任何本机专属信息（账号、真实远端地址、密钥路径等
> 一律用占位符 `<USER>` / `<REPO>` 表示）。本机实际值记在 `docs/本机同步备忘.md`，
> 该文件已加入 `.gitignore`，永不入库。

---

## 1. 仓库与可见性

| 项 | 约定 |
|---|---|
| 远端 | `git@github.com:<USER>/<REPO>.git` |
| 默认分支 | `master`（单人开发直接提交主干；决定开源后再评估切 `develop` + PR 流程） |
| 可见性 | 未开源前建议 **private**；仓库 Settings → Danger Zone → Change visibility 可切换 |
| 转 public 的前提 | `docs/决策与评审记录.md` 里的"差异化论证"补齐（为什么比 Ollama + Talos 组合更好用） |

理由：开源定位未定。private 既能拿云端备份与跨设备同步的好处，又不用提前承诺 API 稳定性。

## 2. 认证方式

推荐 **SSH 密钥**：凭据不落盘、不进仓库、无需每次输密码。

```bash
ssh-keygen -t ed25519 -C "<任意备注>" -f ~/.ssh/id_ed25519  # 生成
ssh -T git@github.com                                                            # 验证
```

把 `.pub` 内容整行贴进 GitHub → Settings → SSH and GPG keys → New SSH key。
若本机有多个密钥，在 `~/.ssh/config` 为 `Host github.com` 指定 `IdentityFile` 并开 `IdentitiesOnly yes`。

```bash
git remote add origin git@github.com:<USER>/<REPO>.git
git push -u origin master
```

### 备选：gh CLI / PAT

需要无人值守地建仓、改可见性时可用 PAT（classic，勾 `repo`；改 Actions 再加 `workflow`），
存进系统凭据管理器，**不要写进任何文件、不要提交**。
PAT 是具备写权限的长期凭据，泄漏等于交出仓库控制权，务必只在本机保管。

## 3. 每日同步流程（手敲版）

```bash
git status                 # 1. 看改了什么
git add -A                 # 2. 全部暂存（.gitignore 已排除密钥/产物）
git commit -m "feat: xxx"  # 3. 提交
git pull --rebase origin master   # 4. 先拉后推，避免冲突
git push                   # 5. 推送
```

若配了自动同步，规则应保守：无改动不动；有改动先跑单测、不过不提交；
冲突或推送失败停手报告，**禁止 `--force`**。

## 4. 提交粒度与信息规范

- **一次提交 = 一个可独立回滚的小改动**。宁可一天三次，不要三天一次大包。
- 提交信息前缀：`feat` / `fix` / `docs` / `refactor` / `test` / `chore`，后跟简短中文描述。
  例：`feat: 引擎支持 stop_at 分段执行`、`fix: unload 未放进 finally`
- **每个可运行的能力点都配最小验证**（dummy 插件或单测），避免攒大招。
- **提交前自查**：改动里不应出现账号、绝对路径、密钥、个人备注。

## 5. 绝不入库清单（换机/开源的安全底线）

| 类别 | 位置 | 保障 |
|---|---|---|
| 密钥 / token | `.env` | `.gitignore` 排除；仓库里只有 `.env.example` |
| **本机专属信息** | `docs/本机同步备忘.md` | `.gitignore` 排除（账号、真实远端、密钥路径、本机命令） |
| 运行产物 | `outputs/*`、`runs/*` | `.gitignore` 排除（保留 `.gitkeep`） |
| 大文件（模型/素材/MP4） | 不进仓库 | 未来如需模型权重，用 Git LFS，不要直接 commit |
| 绝对路径 | 代码里 | 统一 `pathlib` 相对项目根 |

推送前自检：`git status --short` 里不应出现 `.env`、`outputs/`、`runs/`、`本机同步备忘.md`。

> ⚠️ **已推送的历史改不掉**：git 历史永久保留。一旦密钥或私钥被提交，
> 删文件也没用，必须立刻吊销（GitHub 上删除 SSH key / revoke token）后重新生成。

## 6. 换机恢复

```bash
git clone <repo-url>        # 或拷贝整个目录（含 .git）
pip install -r requirements.txt
cp .env.example .env        # 按需填密钥
python main.py list-plugins
```

新机器需自备 SSH 密钥（密钥不随仓库走），并把远端地址按新账号改掉。

## 7. 状态与待办

已完成：
- [x] SSH 认证打通
- [x] 首次 push
- [x] 每日自动同步（无改动不动 / 单测不过不提交 / 禁 `--force`）
- [x] 本机专属信息从入库文档中剥离（2026-09-30）

待办：
- [ ] 仓库可见性按需调整（需账号本人在网页操作）
- [ ] 视情况启用 PAT，实现完全无人值守（含建仓、改可见性）
- [ ] 决定开源时机（补差异化论证后再转 public）
