# 版本记录

版本号同时写在 `.claude-plugin/plugin.json` 和各 SKILL.md 的 `metadata.version`，git tag 打 `v<版本号>`。

## 0.5.1（2026-10-14）

- 修 `zh-ladder-writing/references/严格模式.md` 里套错的代码围栏：上一轮把 `${CLAUDE_SKILL_DIR}` 换成 `$SKILL_DIR` 时多开了一个 ```bash，命令跑到了围栏外面。
- `tools/portability_check.py` 从「只查 SKILL.md」扩到查整个 skill：references/ 里的产品专用变量、裸相对脚本路径、引用文件是否存在都在范围内。新增三项交叉核对——「底线第 N 条」在 `references/底线.md` 里数得到、README/NOTICE 写的仓库路径真的存在、代码围栏配对。
- 逐字收录的 `references/stc/` 不参与内容检查：那是 CC BY 4.0 原文，检查器逼着人去改它反而是问题。
- 跑脚本的命令只在 shell 代码块和正文里查，```json 配置示例里的 `python3 xxx.py` 不算命令。
- `dev/evals/*/README.md` 不再声称中间产物「在 git 历史里」：那条历史只在作者本机，公开仓库的 main 只有两个提交，别人按 commit 号找只会拿到 `not a valid object name`。
- `tools/sync_local.sh` 部署前多跑一次 `portability_check.py --strict`。

## 0.5.0（2026-10-14）

从「Claude Code 的 skill」改成「Agent Skills 的 skill」。

- frontmatter 只保留规范的 6 个字段（`name`、`description`、`license`、`compatibility`、`metadata`、`allowed-tools`），删掉 `disable-model-invocation`：是否自动挂载交回用户，README 给出各家的关法（Claude Code/pi 加字段、Codex 用 `agents/openai.yaml` 的 `policy.allow_implicit_invocation: false`）。
- `${CLAUDE_SKILL_DIR}` 全部换成 `$SKILL_DIR` 占位，每个 SKILL.md 加「路径约定」，写明必须由 agent 替换成绝对路径，shell 不会自动展开。
- `allowed-tools` 补上 `Write Edit`（写 SVG、HTML 和新稿要用），并写明它只是免审批清单，不是权限隔离。
- `shared/底线.md` 新增第 6 条「交付物留在本地」；`zh-ladder-page` 的交付不再默认「有发布工具就发布」。
- 三个 skill 各写清检查脚本能查什么、查不了什么；`check_page.py` 的外部请求只记录不阻断，`svg_check.py` 缺字体时会静默回退。
- Python 版本统一按 3.9+ 说，实际要求改由规范字段 `compatibility` 声明。
- README 补齐各 agent 的调用写法和安装位置（`.agents/skills/`）、「不同 agent 上的差异」、「检查脚本能查出什么、查不出什么」、「效果证据」。
- 新增 `tools/portability_check.py`；`experimental/zh-ladder-video` 按同一套模板同步，并修掉它 frontmatter 缺少的闭合 `---`。

## 0.4.0（2026-10-14）

首个公开版本：三个正式 skill（受控写作、讲解图、交互页）加实验版讲解视频，共用一套底线和交付前检查。
