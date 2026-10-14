# zh-ladder-skills：中文理解阶梯

把模型的输出变成中文读者容易看懂、也容易核对的形式。思路来自 Andrej Karpathy 2026 年 10 月 2 日关于「理解模型输出」的帖子：文字 → 图 → 交互页 → 视频，按需要逐级升级。

| skill | 做什么 | 产出 |
| --- | --- | --- |
| `zh-ladder-writing` 中文受控写作 | 改写、摘要、汇报、讲给外行，意思不走样 | Markdown 文字 |
| `zh-ladder-diagram` 讲解图 | 流程、架构、时间线、因果链、方案对比等 | 可编辑的 SVG + PNG |
| `zh-ladder-page` 交互讲解页 | 读者拖滑块、切选项、先猜后看，自己看出参数怎么影响结果 | 单文件 HTML |

三个 skill 共用一套底线：答案先行、意思不变、不加原文没有的事实、不虚报、不硬升级形式。比起「更好看」，它们更在意「每一句、每条线、每个数字都能对回原文」：都带检查脚本，交付前要跑。

讲解视频（`zh-ladder-video`）还没跑通完整流程，放在 [`experimental/`](experimental/README.md)，默认不安装。

## 用法

三个 skill 都**只能手动调用**（`disable-model-invocation: true`），模型不会自己挑它们。命令后面写任务：

| Claude Code | pi | 例子 |
| --- | --- | --- |
| `/zh-ladder-writing` | `/skill:zh-ladder-writing` | `/zh-ladder-writing 把 周报.md 整理成给领导的汇报` |
| `/zh-ladder-diagram` | `/skill:zh-ladder-diagram` | `/zh-ladder-diagram 把 方案.md 的审批流程画出来` |
| `/zh-ladder-page` | `/skill:zh-ladder-page` | `/zh-ladder-page 把 补贴政策.md 做成能算补贴的页面` |

作为 Claude Code 插件安装时，命令带插件名前缀：`/zh-ladder:zh-ladder-writing`。

一个 skill 觉得换种形式更合适时，会建议你调用另一个，不会自己切换。

## 安装

每个 `skills/<名字>/` 目录都是自包含的，拷走就能用。

**任意支持 Agent Skills 的 agent**（Claude Code、Codex、Cursor……）：

```bash
npx skills add ericwangzq/zh-ladder-skills
```

**Claude Code 插件**：

```text
/plugin marketplace add ericwangzq/zh-ladder-skills
/plugin install zh-ladder@zh-ladder-skills
```

**手动**：

```bash
git clone git@github.com:ericwangzq/zh-ladder-skills.git
cp -r zh-ladder-skills/skills/* ~/.claude/skills/      # pi 用 ~/.pi/agent/skills/
```

同一个 agent 里只用一种方式，否则同名 skill 会出现两份。

## 依赖

| skill | 需要 |
| --- | --- |
| 写作 | Python 3.8+，无第三方包 |
| 讲解图、交互页 | `pip install playwright`。本机装了 Chrome 时直接用它；没有就再运行 `python3 -m playwright install chromium`。第一次画图前运行 `python3 skills/zh-ladder-diagram/scripts/doctor.py`，确认中文字体可用 |

没有浏览器时，讲解图和交互页仍能产出，但会注明「未渲染检查」。

## 仓库结构

```
skills/                    三个正式 skill，每个目录自包含
  zh-ladder-writing/         SKILL.md、references/（底线、汇报模板、空话清单、严格模式、STC 规范）、scripts/（保真对比、STC 检查）
  zh-ladder-diagram/         SKILL.md、references/（底线、选图、中文 SVG 规范、Mermaid）、assets/（模板）、scripts/（检查、自检）
  zh-ladder-page/            SKILL.md、references/（底线、页面结构、交互模式）、assets/（模板）、scripts/（多宽度检查）
experimental/              未跑通的 skill，不随插件加载
shared/底线.md             共用底线的唯一源头，各 skill 的 references/底线.md 是它的副本
tools/sync_shared.py       把 shared/ 同步进各 skill；--check 只检查
tools/sync_local.sh        作者本机用：同步到 Skills Manager
dev/evals/                 写作 skill 的评测用例、读者测验、脚本和结论
dev/examples/              讲解图和交互页的实测产出，以及所用的原始材料（虚构）
.claude-plugin/            Claude Code 插件和 marketplace 信息
```

## 开发

- 改 `shared/底线.md` 后运行 `python3 tools/sync_shared.py`，再提交。
- 脚本路径在 SKILL.md 里写成 `${CLAUDE_SKILL_DIR}/scripts/…`。Claude Code 会替换这个变量；其他 agent 读到的是 SKILL.md 开头的说明：它指 SKILL.md 所在目录。
- 提交前检查：

  ```bash
  python3 tools/sync_shared.py --check
  claude plugin validate .
  ```

## 借鉴与许可

本项目以 MIT 许可发布，见 [LICENSE](LICENSE)。收录的简明技术中文（STC）规范和词表是 CC BY 4.0，借鉴来源见 [NOTICE.md](NOTICE.md)。
