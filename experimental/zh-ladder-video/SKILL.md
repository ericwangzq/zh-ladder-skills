---
name: zh-ladder-video
description: 做中文讲解视频：3Blue1Brown 风格动画加中文配音和字幕，讲清按步骤展开的过程。先出分镜表，确认后才渲染。实验性 skill，完整流程未跑通，默认不安装。
license: MIT
compatibility: 需要 Python 3.9+、ffmpeg、Manim、配音来源（默认 edge-tts，走非官方接口，可能随时失效；macOS 可离线用自带的 say）；核验脚本可选 faster-whisper。依赖缺失时明说降级，不冒充成片。
allowed-tools: Read Grep Glob Write Edit Bash(python3 */scripts/*.py) Bash(manim *)
metadata:
  author: Eric Wang
  version: "0.5.0"
---

# 中文讲解视频

目标：读者看完一遍，就能用自己的话复述这个过程；而且视频里的每句话、每个数字都对得上原文。

视频最难核对：画面、声音、动画同时争夺注意力，一个错误裹在精美的动画里，比写在文字里更有说服力。所以本 skill 有两道关：渲染之前先确认分镜，渲染之后逐项核验。

先读底线规则：`references/底线.md`。

## 用法

输入：命令后面的文字就是任务；要讲解的材料（文件路径或粘贴的文字）没给就先问一句，不要自己找。

输出：分镜表、配音、成片、字幕，都落在本地（底线第 6 条），不上传、不发布。

**路径约定**：本文里 `references/…`、`scripts/…`、`assets/…` 都相对于**本 SKILL.md 所在的目录**（下称 skill 目录）。你的工作目录不是 skill 目录，跑脚本必须用绝对路径：命令里的 `$SKILL_DIR` 指 skill 目录的绝对路径，**运行前换成实际路径**（加载本 skill 时已经给过你 SKILL.md 的位置）。shell 不会自动展开这个变量。

## 1. 先出分镜表，等确认

视频费时间，可能还费钱（付费配音）。所以第一步只交分镜表，不渲染：

1. 按 `references/分镜.md` 写分镜表：标题卡、三到六个正文镜头、总结卡；每个镜头写旁白、画面和屏幕文字。
2. 同时给出：预计时长、用哪个配音（见 `references/配音.md`）、会不会产生费用、需要装哪些工具。
3. **等用户确认再往下做。** 用户已经明确说过「直接做成片」时可以跳过等待，但分镜表仍然要写。

内容其实用一张图或一个交互页就能讲清时，在这一步直说，并提议改用 `zh-ladder-diagram` 或 `zh-ladder-page`。

## 2. 配音和字幕

配音先做，动画按配音的真实时长来排，这样不会音画错位。

```bash
python3 "$SKILL_DIR/scripts/tts.py" 分镜.json --out build/
```

脚本按分镜逐镜头生成音频，写出每个镜头的时长（`timings.json`）和字幕（`subtitles.srt`）。配音来源可以替换，默认是 edge-tts，Mac 上可以离线用系统自带的 `say`，见 `references/配音.md`。

## 3. 动画

用 Manim 写动画，中文写法和常见坑见 `references/manim中文.md`。`assets/zh_manim.py` 提供中文字体选择、标题卡、总结卡和「按配音时长补齐」的辅助函数，直接导入使用。

几条最容易错的：

- 中文一律用 `Text`，不用 `Tex`。`Tex` 处理中文要装整套 LaTeX 中文环境，又重又慢。
- 每个镜头的动画时长对齐 `timings.json` 里的配音时长，不要按英文模板的「每秒几个词」估。
- 屏幕上的文字和旁白说的是同一件事，数字一致。旁白里有「预计」「约」，屏幕上也要有。

渲染：

```bash
manim -qh scene.py Explainer
```

## 4. 合成和核验

```bash
python3 "$SKILL_DIR/scripts/assemble.py" --video <渲染出的 mp4> --build build/ --out 成片.mp4
python3 "$SKILL_DIR/scripts/verify_video.py" 成片.mp4 --storyboard 分镜.json --out check/
```

核验脚本会报：音视频时长是否一致、有没有异常长的静音、字幕是否覆盖全片；每两秒抽一帧拼成一张总览图；装了 faster-whisper 的话，把配音转回文字和旁白稿对比。

然后**打开总览图看**：标题卡和总结卡在不在、中文是不是方块、文字有没有出画、画面是否跟上旁白。具体要看什么见 `references/核验.md`。

## 5. 诚实降级

工具缺了就明说降级成了什么，不要冒充成片：

- 没有 Manim 或渲染失败：交付分镜表和配音，说明「未渲染视频」。
- 没有配音：交付无声视频加字幕，说明「无配音」。
- 用 HTML 动画代替：说明「这是网页动画，不是 MP4」。
- 没做核验：说明「未核验」，不要说「检查过了」。

## 交付

交付成片（MP4，内嵌可开关的字幕）、字幕文件、分镜表。附一句话：视频多长、讲的是什么、哪些内容是推算或未确认的。
