# 实验区

这里的 skill 不随插件加载，`npx skills add` 也不会装到它们。

| skill | 状态 | 为什么放在这里 |
| --- | --- | --- |
| `zh-ladder-video` 讲解视频 | 配音、合成、核验脚本已冒烟测试；**Manim 动画部分从未运行过** | 没有完整跑通过一条流程；默认配音 edge-tts 调用的是非官方接口，可能随时失效；渲染耗时，付费配音还要花钱。投入产出比要单独评估。 |

要试用：把目录拷到对应 agent 扫描的位置。

```bash
cp -r experimental/zh-ladder-video ~/.claude/skills/    # Claude Code
cp -r experimental/zh-ladder-video ~/.agents/skills/    # Codex、pi 都读这里
```

依赖：`brew install ffmpeg cairo pango pkg-config && pip install manim edge-tts`；可选 `pip install faster-whisper` 做配音转写核对。

移回 `skills/` 之前要满足：至少一份真实材料从分镜走到成片，并通过 `verify_video.py` 的核验和人工观看。
