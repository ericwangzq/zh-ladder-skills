"""Manim 中文讲解视频的辅助模块。把本文件复制到 scene.py 旁边，然后 from zh_manim import *。

提供：
  FONT                自动挑一个本机有的中文字体
  颜色常量             BG、INK、INK2、ACCENT、BAD、GOOD，和讲解图、交互页同一套
  zh(...)             中文文字，统一字体和颜色
  TimedScene          按 build/timings.json 对齐配音的场景基类
    self.begin(id)    开始一个镜头（落后于配音时会先等到镜头起点）
    self.finish()     结束一个镜头（动画比配音短就补等待；比配音长会打印提醒）
    self.title_card(id, 标题, 副标题=None)
    self.recap_card(id, 要点列表, 备注=None)
"""
import json
from pathlib import Path

import manimpango
from manim import (BOLD, DOWN, LEFT, UP, FadeIn, FadeOut, Scene, Text, VGroup, Write, config, logger)

CANDIDATE_FONTS = ["PingFang SC", "Noto Sans CJK SC", "Source Han Sans SC", "思源黑体",
                   "Microsoft YaHei", "WenQuanYi Zen Hei"]


def pick_font():
    available = set(manimpango.list_fonts())
    for f in CANDIDATE_FONTS:
        if f in available:
            return f
    raise RuntimeError("没有找到中文字体。Mac 自带苹方（PingFang SC）；Linux 请安装 fonts-noto-cjk。")


FONT = pick_font()

BG, INK, INK2 = "#17181a", "#e8e9eb", "#a3a6ad"
ACCENT, BAD, GOOD = "#5b8cff", "#f06a62", "#4cc35a"

config.background_color = BG


def zh(text, size=36, color=INK, bold=False):
    """中文文字。不要用 Tex 写中文：要装整套 LaTeX 中文环境，又重又慢。"""
    return Text(text, font=FONT, font_size=size, color=color, weight=BOLD if bold else "NORMAL")


def load_timings(path="build/timings.json"):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data, {s["id"]: s for s in data["scenes"]}


class TimedScene(Scene):
    """动画按配音的真实时长对齐。每个镜头写成：self.begin("s02") …动画… self.finish()。"""

    timings_path = "build/timings.json"

    def setup(self):
        self.camera.background_color = BG
        self._data, self._by_id = load_timings(self.timings_path)
        self._ids = [s["id"] for s in self._data["scenes"]]
        self._current = None

    def _now(self):
        return self.renderer.time

    def begin(self, sid):
        if sid not in self._by_id:
            raise KeyError(f"timings.json 里没有镜头 {sid}")
        self._current = sid
        lag = self._by_id[sid]["start"] - self._now()
        if lag > 0.01:
            self.wait(lag)

    def finish(self):
        s = self._by_id[self._current]
        idx = self._ids.index(self._current)
        end = (self._by_id[self._ids[idx + 1]]["start"] if idx + 1 < len(self._ids)
               else s["start"] + s["duration"] + 0.8)
        remain = end - self._now()
        if remain > 0.01:
            self.wait(remain)
        elif remain < -0.3:
            logger.warning(f"镜头 {self._current} 的动画比配音长 {-remain:.1f} 秒，后面的镜头会整体后移，请缩短动画")

    def title_card(self, sid, title, subtitle=None):
        self.begin(sid)
        group = VGroup(zh(title, 48, bold=True))
        if subtitle:
            group.add(zh(subtitle, 28, INK2))
        group.arrange(DOWN, buff=0.4)
        self.play(Write(group[0]), run_time=1.2)
        if subtitle:
            self.play(FadeIn(group[1], shift=UP * 0.2), run_time=0.6)
        self.finish()
        self.play(FadeOut(group), run_time=0.4)

    def recap_card(self, sid, points, note=None):
        self.begin(sid)
        head = zh("记住这几点", 36, bold=True).to_edge(UP, buff=0.8)
        items = VGroup(*[zh(p, 32) for p in points]).arrange(DOWN, aligned_edge=LEFT, buff=0.45)
        items.next_to(head, DOWN, buff=0.7)
        self.play(FadeIn(head), run_time=0.5)
        for it in items:
            self.play(FadeIn(it, shift=LEFT * 0.2), run_time=0.6)
        if note:
            n = zh(note, 24, INK2).to_edge(DOWN, buff=0.6)
            self.play(FadeIn(n), run_time=0.4)
        self.finish()
