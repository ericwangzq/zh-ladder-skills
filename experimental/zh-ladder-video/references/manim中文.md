# Manim 中文写法

## 安装（Mac）

```bash
brew install ffmpeg cairo pango pkg-config
pip install manim edge-tts
```

不需要装 MacTeX，除非要写数学公式。验证：`manim --version`。

## 骨架

把 `assets/zh_manim.py` 复制到 `scene.py` 旁边。每个分镜镜头对应一段 `begin` … `finish`，动画会自动对齐配音时长：

```python
from manim import *
from zh_manim import *

class Explainer(TimedScene):
    def construct(self):
        self.title_card("s01", "并发一高为什么会排队")

        self.begin("s02")
        gpu = RoundedRectangle(width=6, height=3, corner_radius=0.2, color=INK2)
        label = zh("1 张显卡", 28, INK2).next_to(gpu, UP)
        self.play(Create(gpu), FadeIn(label))
        slots = VGroup(*[Square(0.4, fill_opacity=0.8, fill_color=ACCENT, stroke_width=0)
                         for _ in range(18)]).arrange_in_grid(3, 6, buff=0.15).move_to(gpu)
        self.play(LaggedStart(*[FadeIn(s) for s in slots], lag_ratio=0.1))
        note = zh("≈ 同时 18 个请求（推算）", 28).next_to(gpu, DOWN)
        self.play(Write(note))
        self.finish()
        self.play(FadeOut(VGroup(gpu, label, slots, note)))

        # … 其余镜头 …

        self.recap_card("s04", ["① 超过容量才排队", "② 加卡约翻倍（推算，未实测）"])
```

渲染：`manim -qh scene.py Explainer`（1080p）。调试时用 `-ql` 快速出低清版。

## 中文文字

- 一律用 `zh(...)`（内部是 `Text` 加中文字体），不用 `Tex`、`MathTex` 写中文。
- 公式单独用 `MathTex`，里面不放中文；中文说明放在公式旁边的 `zh(...)` 里。用公式就要装 LaTeX。
- 一行不超过 14 个汉字；字号正文 28–36，标题 48，注释 24。低于 24 在手机上看不清。
- 屏幕文字和旁白说同一件事。旁白里的「约」「预计」「推算」，屏幕上也要有。

## 画面风格

- 深色背景（`BG`），浅色文字（`INK`），次要信息用 `INK2`。
- 一个镜头只用一种强调色（`ACCENT`）；红（`BAD`）只表示问题或排队、失败。
- 一个镜头只讲一件事。新内容出现时，上一个镜头的内容淡出，不要越堆越满。
- 动作要慢：读者要跟着旁白看。单个动画 0.6–1.5 秒，关键的变化前后留半秒。

## 常见报错

| 现象 | 原因和办法 |
| --- | --- |
| `RuntimeError: 没有找到中文字体` | Mac 应该有苹方；Linux 装 `fonts-noto-cjk`，然后重开终端 |
| 中文显示成方块 | 用了 `Tex`，或 `Text` 没指定 `font`。改用 `zh(...)` |
| `LaTeX error` | 写了 `Tex`/`MathTex` 但没装 LaTeX。中文改用 `zh`；公式要么装 MacTeX，要么改用文字 |
| 日志提示「动画比配音长」 | 这个镜头的动画总时长超过了配音，缩短 `run_time` 或删掉一些动作 |
| 找不到 `build/timings.json` | 先运行 `scripts/tts.py` 生成配音；或在 `scene.py` 所在目录运行 manim |
