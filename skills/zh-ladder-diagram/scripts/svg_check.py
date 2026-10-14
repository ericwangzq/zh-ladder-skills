#!/usr/bin/env python3
"""在 Chromium 里按真实字体检查中文 SVG 图，并可导出 PNG。

用法：
  python3 svg_check.py 图.svg [--png 图.png] [--scale 2]
  python3 svg_check.py 页面.html  （检查页面里的第一张 SVG）

检查：
  1. 文字超出它所在的框（按文字中心落在哪个框里判断归属）
  2. 文字超出画布
  3. 两段文字互相压住
  4. 用省略号截断的文字
  5. Mermaid 图（foreignObject 里的文字）溢出
有问题时退出码为 1。PNG 用 Chromium 截图，不用 CairoSVG 或 rsvg：
前者遇到中文会出方块，后者会让 Mermaid 的文字消失。

依赖：pip install playwright，然后 python3 -m playwright install chromium
（Mac 上已装 Chrome 时，脚本会退而使用系统 Chrome。）
"""
import argparse
import json
import re
import sys
from pathlib import Path

JS = r"""
() => {
  const svg = document.querySelector('svg');
  if (!svg) return {error: '没有找到 <svg>'};
  const canvas = svg.getBoundingClientRect();
  const r = el => { const b = el.getBoundingClientRect(); return {x: b.left, y: b.top, w: b.width, h: b.height}; };
  const area = b => Math.max(0, b.w) * Math.max(0, b.h);
  const inter = (a, b) => {
    const w = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
    const h = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
    return (w > 0 && h > 0) ? w * h : 0;
  };
  // 框：rect / polygon / circle / ellipse，去掉铺满画布的背景
  const boxes = [...svg.querySelectorAll('rect,polygon,circle,ellipse')]
    .filter(e => !e.closest('defs,marker,pattern,clipPath,mask'))
    .map(e => ({el: e, b: r(e), tag: e.tagName}))
    .filter(o => o.b.w > 4 && o.b.h > 4 && !(o.b.w >= canvas.width * 0.95 && o.b.h >= canvas.height * 0.95));
  // 文字行：有 tspan 的按 tspan 量，否则按 text 量
  const lines = [];
  svg.querySelectorAll('text').forEach(t => {
    if (t.closest('defs')) return;
    const spans = [...t.querySelectorAll('tspan')].filter(s => s.textContent.trim());
    (spans.length ? spans : [t]).forEach(el => {
      const s = el.textContent.trim();
      if (s) lines.push({text: s, b: r(el)});
    });
  });
  const problems = [];
  const PAD = 2;
  for (const L of lines) {
    const b = L.b, cx = b.x + b.w / 2, cy = b.y + b.h / 2;
    if (b.x < canvas.left - PAD || b.y < canvas.top - PAD || b.x + b.w > canvas.right + PAD || b.y + b.h > canvas.bottom + PAD)
      problems.push({type: '超出画布', text: L.text});
    const holders = boxes.filter(o => cx >= o.b.x && cx <= o.b.x + o.b.w && cy >= o.b.y && cy <= o.b.y + o.b.h)
                         .sort((a, c) => area(a.b) - area(c.b));
    if (holders.length) {
      const h = holders[0].b;
      const over = Math.max(h.x - b.x, (b.x + b.w) - (h.x + h.w), 0);
      if (over > PAD) problems.push({type: '超出所在的框', text: L.text, 超出px: Math.round(over), 框宽: Math.round(h.w), 文字宽: Math.round(b.w)});
    }
    if (/(…|\.\.\.)$/.test(L.text)) problems.push({type: '省略号截断', text: L.text});
  }
  for (let i = 0; i < lines.length; i++) for (let j = i + 1; j < lines.length; j++) {
    const a = lines[i].b, c = lines[j].b, k = inter(a, c);
    if (k > 0.15 * Math.min(area(a), area(c))) problems.push({type: '文字互相压住', text: lines[i].text + ' ⟷ ' + lines[j].text});
  }
  svg.querySelectorAll('foreignObject').forEach(fo => {
    fo.querySelectorAll('div,span,p').forEach(d => {
      if (d.scrollWidth > d.clientWidth + 1 && d.clientWidth > 0)
        problems.push({type: 'Mermaid 文字溢出', text: d.textContent.trim().slice(0, 40)});
    });
  });
  return {lines: lines.length, fo: svg.querySelectorAll('foreignObject').length, boxes: boxes.length, width: canvas.width, height: canvas.height, problems};
}
"""


def launch(p):
    try:
        return p.chromium.launch()
    except Exception as first:
        try:
            return p.chromium.launch(channel="chrome")
        except Exception:
            raise SystemExit(f"无法启动浏览器：{first}\n请运行：python3 -m playwright install chromium")


def view_box(svg_text):
    m = re.search(r'viewBox\s*=\s*"\s*[-\d.]+[\s,]+[-\d.]+[\s,]+([\d.]+)[\s,]+([\d.]+)', svg_text)
    return (float(m.group(1)), float(m.group(2))) if m else (960.0, 600.0)


def main():
    ap = argparse.ArgumentParser(description="检查中文 SVG 图并导出 PNG")
    ap.add_argument("file")
    ap.add_argument("--png", help="导出 PNG 的路径")
    ap.add_argument("--scale", type=float, default=2.0, help="PNG 放大倍数，默认 2")
    args = ap.parse_args()
    path = Path(args.file).resolve()
    text = path.read_text(encoding="utf-8")
    w, h = view_box(text) if path.suffix.lower() == ".svg" else (1280, 900)

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = launch(p)
        page = browser.new_page(viewport={"width": int(w), "height": int(h)}, device_scale_factor=args.scale)
        page.goto(path.as_uri())
        page.evaluate("document.fonts.ready")
        result = page.evaluate(JS)
        if args.png and "error" not in result:
            target = page.locator("svg").first
            target.screenshot(path=args.png)
        browser.close()

    if "error" in result:
        print(result["error"])
        return 2
    probs = result["problems"]
    fo = f"、{result['fo']} 个 Mermaid 标签" if result["fo"] else ""
    print(f"检查了 {result['lines']} 行文字{fo}、{result['boxes']} 个框，画布 {int(result['width'])}×{int(result['height'])}")
    if probs:
        print(f"发现 {len(probs)} 个问题：")
        for x in probs:
            print("  -", json.dumps(x, ensure_ascii=False))
    else:
        print("没有发现溢出、重叠或截断。")
    if args.png:
        print(f"已导出 {args.png}。请打开看一遍：中文是否变成方块、箭头是否穿过了框、是否太挤。")
    return 1 if probs else 0


if __name__ == "__main__":
    sys.exit(main())
