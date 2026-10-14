# zh-ladder-writing 评测

## 用例

- `hard/cases.json`：10 条长文难用例（每条 2,700–3,600 字），主评测集。每条标注了任务、必须保留的事实、摘要必须保留的核心事实、不能出现的歪曲、读者问题，以及原文里埋的陷阱（6 条有故意的内部矛盾）。全部是虚构材料。`hard/inputs/` 是同样的原文，单独成文件方便阅读。
- `hard/quiz.json`：读者测验，每条用例 7 题（3 道读者问题 + 4 道陷阱题），两个模型出题互审后人工改过。
- `easy/`：10 条短用例（280–420 字）。强模型不加 skill 也不丢事实，只留作回归测试。

## 脚本

在 `scripts/` 下运行。生成用 Claude Code（`claude -p`），评分和测验通过 [pi](https://github.com/earendil-works/pi) 的非交互模式调用模型（`common.py` 里的 `call`）。评分模型用环境变量指定，写法同 `pi --model`：

```bash
export ZH_LADDER_JUDGES=<评委1>,<评委2>        # judge.py
export ZH_LADDER_READER=<读者模型>              # quiz.py、report.py
export ZH_LADDER_GRADERS=<阅卷1>,<阅卷2>        # quiz.py、report.py
export ZH_LADDER_QUIZ_MAKER=<出题模型>          # make_quiz.py
export ZH_LADDER_QUIZ_CHECKER=<复核模型>        # check_quiz.py
```

评委最好和写作模型不是同一家，避免自评偏好。第 3 轮用的是 deepseek-v4-pro 和 qwen3.8-max 当评委，qwen3.8-flash 当读者。

| 脚本 | 做什么 |
| --- | --- |
| `write.py` | 每条用例在独立临时目录里生成改写稿；`--skill` 时用 `--plugin-dir` 加载本仓库并以斜杠命令调用 skill，`--repo` 可指向旧版本做对照 |
| `judge.py` | 保真评分：两位评委对照原文和标注，逐份独立打分（保留 / 弱化 / 丢失、歪曲、陷阱、无依据添加、可读性） |
| `quiz.py` | 读者测验：读者模型只读改写稿回答问题，两位评委按得分要点阅卷；分读全文和只读开头 300 字两种 |
| `report.py` | 汇总篇幅和读者测验 |
| `make_quiz.py`、`check_quiz.py` | 生成和复核读者测验（已生成好，一般不用再跑） |

```bash
cd scripts
python3 write.py run/opus_base --model opus
python3 write.py run/opus_skill --model opus --skill      # Opus 每条约 $0.2–0.6
python3 judge.py run/opus_base run/opus_skill
python3 quiz.py run/opus_base run/opus_skill              # 调用多，慢
python3 report.py source run/opus_base run/opus_skill     # source = 读者直接读原文，作参照
```

结果写在 `results/`（不进仓库），各组的评分缓存在 `_judge/`、`_quiz/` 下，中断后重跑只补缺的。

## 结论

**第 2 轮（v2，2026-10-12）**，Opus 和 Sonnet 两位评委两两盲评：在 Opus 上 skill 明显减少走样和编造，可读性略低（4.3–4.4 对 4.6–4.9）；在 Haiku 上胜负接近。

**第 3 轮（v3，2026-10-14，未跑完）**，换成非 Claude 评委并加了读者测验：

| | Opus 基线 | Opus v2 | Opus v3 | Haiku 基线 | Haiku v2 | Haiku v3 |
| --- | --- | --- | --- | --- | --- | --- |
| 篇幅（无字数上限的 8 条，占原文） | 85% | 99% | 77% | 91% | 91% | 77% |
| 生成费用（10 条合计） | $2.2 | $3.8 | $5.1 | $0.07 | $0.11 | $0.15 |

- v3 加的篇幅目标有效，篇幅明显缩短。
- 读者测验读全文时，各组得分都在 61%–66%，分不出高下（同组重测会差约 4 个百分点；直接读原文 69%–73%）。只读开头 300 字时 skill 稳定领先，21%–22% 对 16%–17%。
- 非 Claude 评委下基线几乎不编造，第 2 轮「skill 大幅减少编造」没能复现；Opus 上 skill 的优势只剩更少的弱化。

模型读者分辨不出组间差异，继续跑性价比低，之后以真实使用的体感为准。

历次改写稿和评分缓存没有放进仓库，在 git 历史里（提交 `489603e` 及之前的 `dev/evals/*/results/`）。

## 局限

只有 10 条用例，材料是合成的；单条用例的结果波动大。
