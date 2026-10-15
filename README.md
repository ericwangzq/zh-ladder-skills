# zh-ladder-skills：中文理解阶梯

把模型的输出变成中文读者容易看懂、也容易核对的形式。思路来自 Andrej Karpathy 2026 年 10 月 2 日关于「理解模型输出」的帖子：文字 → 图 → 交互页 → 视频，按需要逐级升级。

| skill | 做什么 | 产出 |
| --- | --- | --- |
| `zh-ladder-writing` 中文受控写作 | 改写、摘要、汇报、讲给外行，意思不走样 | Markdown 文字 |
| `zh-ladder-diagram` 讲解图 | 流程、架构、时间线、因果链、方案对比等 | 可编辑的 SVG + PNG |
| `zh-ladder-page` 交互讲解页 | 读者拖滑块、切选项、先猜后看，自己看出参数怎么影响结果 | 单文件 HTML |

三个 skill 共用一套底线：答案先行、意思不变、不加原文没有的事实、不虚报、不硬升级形式、交付物留在本地。比起「更好看」，它们更在意「每一句、每条线、每个数字都能对回原文」：都带检查脚本，交付前要跑。

讲解视频（`zh-ladder-video`）还没跑通完整流程，放在 [`experimental/`](experimental/README.md)，默认不安装。

## 谁决定用不用

只按 [Agent Skills 开放规范](https://agentskills.io) 各家都认的字段写，**没有内置「默认不自动挂载」的逻辑**：agent 可以按 `description` 自己挑，你也可以自己点名。想让它只在点名时生效，见下面[只想手动调用](#只想手动调用)。

| agent | 手动调用的写法 |
| --- | --- |
| Claude Code | `/zh-ladder-writing`（装成插件时是 `/zh-ladder:zh-ladder-writing`） |
| Codex CLI / IDE 扩展 | `$zh-ladder-writing`，或先 `/skills` 看列表 |
| ChatGPT 桌面版 | 输入 `@` 选 skill |
| pi | `/skill:zh-ladder-writing` |
| 其他支持 Agent Skills 的产品 | 用 skill 名调用，具体写法见各家文档 |

一个 skill 觉得换种形式更合适时，会建议你调用另一个，不会自己切换。

## 安装

每个 `skills/<名字>/` 目录都是自包含的，拷走就能用。

**任意支持 Agent Skills 的 agent**：

```bash
npx skills add ericwangzq/zh-ladder-skills
```

**手动**：放到对应 agent 会扫描的目录里，整目录拷走即可。

```bash
git clone git@github.com:ericwangzq/zh-ladder-skills.git

mkdir -p ~/.agents/skills && cp -r zh-ladder-skills/skills/* ~/.agents/skills/   # Codex 和 pi 都读这个位置
cp -r zh-ladder-skills/skills/* ~/.claude/skills/                                 # Claude Code
cp -r zh-ladder-skills/skills/* ~/.pi/agent/skills/                               # pi 的用户级目录
```

项目级同理，把 `~` 换成仓库根目录即可（`.agents/skills/` 会被 Codex 和 pi 一起看到）。

**Claude Code 插件**：

```text
/plugin marketplace add ericwangzq/zh-ladder-skills
/plugin install zh-ladder@zh-ladder-skills
```

同一个 agent 里只用一种方式，否则同名 skill 会出现两份。

## 只想手动调用

各家机制不一样，没有跨产品的统一开关。按需加，本项目默认不加：

| agent | 怎么关掉自动挂载 |
| --- | --- |
| Claude Code、pi | SKILL.md 开头加 `disable-model-invocation: true` |
| Codex、ChatGPT | skill 目录下建 `agents/openai.yaml`，写 `policy: {allow_implicit_invocation: false}`；或在 `~/.codex/config.toml` 里 `[[skills.config]]` 标 `enabled = false` |
| 其他 | 大多只能靠 `description` 写窄一点，或宿主自己的开关 |

注意 `disable-model-invocation` 不是规范字段：加了它的 SKILL.md 上传 claude.ai、走 Skills API 或用 `package_skill.py` 打包会直接报错。要在那些路径上用，就别加这一行。

## 依赖

| skill | 需要 |
| --- | --- |
| 写作 | Python 3.9+，无第三方包 |
| 讲解图、交互页 | `pip install playwright`。本机装了 Chrome 时直接用它；没有就再运行 `python3 -m playwright install chromium`。第一次画图前运行 `python3 skills/zh-ladder-diagram/scripts/doctor.py`，确认中文字体可用 |

没有浏览器时，讲解图和交互页仍能产出，但会注明「未渲染检查」。各 skill 开头 `compatibility` 字段写的就是实际要求；更低版本没验证过，跑不起来算正常。

## 不同 agent 上的差异

这些差异是真实的，别指望三个 skill 在每个宿主上表现一致：

- **frontmatter 字段**：只有 `name`、`description`、`license`、`compatibility`、`metadata`、`allowed-tools` 属于规范，各家都读得懂、不会报错。`allowed-tools` 在规范里标为实验性：Claude Code 用它做「本回合免审批」清单，别的 agent 大多只当元数据放着，有的直接忽略。
- **`allowed-tools` 不是权限隔离**。它只是「这些工具不用再问一遍」，不是「只能用这些工具」，更不是沙箱；组织托管设置还能让 Claude Code 整个忽略它。真正的边界在宿主自己的权限设置里，装第三方 skill 前该读的还是脚本和正文。
- **路径**：SKILL.md 里用 `$SKILL_DIR` 占位表示 skill 目录，需要 agent 自己替换成绝对路径。规范推荐的是相对 skill 根目录的路径（`scripts/foo.py`），但工作目录通常是用户的项目目录，直接跑会找不到文件，所以每个 SKILL.md 开头都写了这条约定。
- **渲染**：讲解图和交互页需要本机有 Chromium。没有就降级成「未渲染检查」，skill 会明说。

## 检查脚本能查出什么、查不出什么

三个脚本都是字面和几何层面的提醒，不是正确性证明：

| 脚本 | 查得出 | 查不出 |
| --- | --- | --- |
| `fidelity_check.py` | 数字和单位丢了或变了、限定词（预计/约/尚未）掉了、条件和否定词不见了、新稿冒出原文没有的数字 | 归属互换（「张三认为」写成「已决定」）、例外挂到别的条件上、口径从「含税」变「金额」、定义被删、结论依赖矛盾数字 |
| `svg_check.py` | 文字溢出、互相压住、超出画布、字号太小 | 箭头关系对不对、节点归属、强调色选错、中文渲染成方块（缺字体时会静默回退） |
| `check_page.py` | 控制台报错、横向滚动、文字溢出、按钮太小、结论不在首屏、页面发了外部请求 | 算错、读者看不看得懂、「先猜后看」的结论和公式不一致 |

`check_page.py` 只是**记录**外部请求，不阻断，也不是沙箱。`svg_check.py` 和 `check_page.py` 会启动真实浏览器，页面的任何脚本都会执行。

跑脚本前请当作「有提醒就要逐条看」，退出码 0 不等于意思没变——这是三个 skill 里都写进流程的原因。

## 效果证据

`dev/evals/` 里有 10 条合成长文用例、读者测验和三轮评测记录。已知局限写在那里：**样本只有 10 条、材料是虚构的、单条波动大**；第 3 轮换非 Claude 评委后，第 2 轮「skill 大幅减少编造」的结论没能复现，剩下的稳定收益是篇幅更短、只看开头时读者答对率更高。

也就是说：这套 skill 的价值主要来自规则本身和交付前检查，不来自跑分。在 Codex 或其他 agent 上会好多少，我们没有测过。

## 仓库结构

```
skills/                    三个正式 skill，每个目录自包含
  zh-ladder-writing/         SKILL.md、references/（底线、汇报模板、空话清单、严格模式、STC 规范）、scripts/（保真对比、STC 检查）
  zh-ladder-diagram/         SKILL.md、references/（底线、选图、中文 SVG 规范、Mermaid）、assets/（模板）、scripts/（检查、自检）
  zh-ladder-page/            SKILL.md、references/（底线、页面结构、交互模式）、assets/（模板）、scripts/（多宽度检查）
experimental/              未跑通的 skill，不随插件加载
shared/底线.md             共用底线的唯一源头，各 skill 的 references/底线.md 是它的副本
tools/sync_shared.py       把 shared/ 同步进各 skill；--check 只检查
tools/portability_check.py 检查 skill 是否还残留某个 agent 专用的写法
tools/sync_local.sh        作者本机用：同步到 Skills Manager
CHANGELOG.md               版本记录，和 git tag v<版本号> 对上
dev/examples/              讲解图和交互页的实测产出，以及所用的原始材料（虚构）
.claude-plugin/            Claude Code 插件和 marketplace 信息
```

## 开发

- 每次改动记进 [CHANGELOG.md](CHANGELOG.md)，版本号同时对齐 `.claude-plugin/plugin.json`、各 SKILL.md 的 `metadata.version` 和 git tag。
- 改 `shared/底线.md` 后运行 `python3 tools/sync_shared.py`，再提交。
- 脚本路径写成 `"$SKILL_DIR/scripts/…"`，并在每个 SKILL.md 的「路径约定」里说明 `$SKILL_DIR` 是什么。不要写回 `${CLAUDE_SKILL_DIR}`，那是 Claude Code 专用变量，别的 agent 只会当成一串字面字符。
- 提交前检查：

  ```bash
  python3 tools/sync_shared.py --check
  python3 tools/portability_check.py --strict   # 跨 agent 兼容性自查
  skills-ref validate skills/zh-ladder-writing   # 规范校验，可选
  claude plugin validate .                # 只在维护 Claude 插件时需要
  ```

## 借鉴与许可

本项目以 MIT 许可发布，见 [LICENSE](LICENSE)。收录的简明技术中文（STC）规范和词表是 CC BY 4.0，借鉴来源见 [NOTICE.md](NOTICE.md)。
