#!/usr/bin/env python3
"""在 Chromium 里检查交互讲解页，并截图供人看。

用法：python3 check_page.py 页面.html [--out 截图目录]

做的事：
  1. 在 5 个宽度（390 手机、768 平板、1024、1280、1440）下打开页面，各截一张整页图
  2. 在桌面宽度下，把每个滑块拨到最小值和最大值、把每组分段按钮逐个点一遍，各截一张图；点一次「先猜」按钮
  3. 报告：控制台报错、页面脚本异常、对外网络请求、横向滚动、文字溢出、图中文字被截或太小、
     首屏有没有 h1 结论、手机上结论句是否超过 3 行、手机上可点区域是否太小
有问题时退出码为 1。截图要打开看：脚本只能查出机械问题，查不出数字算错和读者看不懂。

依赖：pip install playwright，然后 python3 -m playwright install chromium
"""
import argparse
import json
import sys
from pathlib import Path

WIDTHS = [390, 768, 1024, 1280, 1440]

OVERFLOW_JS = r"""
() => {
  const out = [];
  const doc = document.documentElement;
  if (doc.scrollWidth > window.innerWidth + 1) out.push({type: '页面横向滚动', 宽: doc.scrollWidth, 视口: window.innerWidth});
  document.querySelectorAll('body *').forEach(el => {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') return;
    if (['SVG', 'svg', 'INPUT', 'SELECT', 'TEXTAREA', 'HTML', 'BODY'].includes(el.tagName)) return;
    if (el.closest('svg')) return;
    const scrollable = /(auto|scroll)/.test(cs.overflowX);
    if (!scrollable && el.scrollWidth > el.clientWidth + 2 && el.clientWidth > 0 && el.children.length === 0)
      out.push({type: '文字溢出', text: el.textContent.trim().slice(0, 40), 内容宽: el.scrollWidth, 容器宽: el.clientWidth});
  });
  document.querySelectorAll('svg').forEach(svg => {
    const sb = svg.getBoundingClientRect();
    if (sb.width === 0) return;
    svg.querySelectorAll('text').forEach(t => {
      const b = t.getBoundingClientRect(), s = t.textContent.trim();
      if (!s) return;
      if (b.left < sb.left - 1 || b.right > sb.right + 1 || b.top < sb.top - 1 || b.bottom > sb.bottom + 1)
        out.push({type: '图中文字被截掉', text: s.slice(0, 30)});
      if (b.height < 11) out.push({type: '图中文字太小', text: s.slice(0, 30), 实际高度px: Math.round(b.height)});
    });
  });
  const h1 = document.querySelector('h1');
  if (!h1) out.push({type: '缺少 h1 结论'});
  else if (h1.getBoundingClientRect().top > window.innerHeight) out.push({type: 'h1 结论不在第一屏'});
  return out;
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


def main():
    ap = argparse.ArgumentParser(description="检查交互讲解页")
    ap.add_argument("file")
    ap.add_argument("--out", default="page-check", help="截图目录")
    args = ap.parse_args()
    page_path = Path(args.file).resolve()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    url = page_path.as_uri()

    problems, shots = [], []
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = launch(p)
        for w in WIDTHS:
            ctx = browser.new_context(viewport={"width": w, "height": 900}, device_scale_factor=1)
            page = ctx.new_page()
            console, external = [], []
            page.on("console", lambda m: console.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: console.append(f"脚本异常：{e}"))
            page.on("request", lambda r: external.append(r.url) if not r.url.startswith(("file:", "data:", "blob:", "about:")) else None)
            page.goto(url)
            page.wait_for_load_state("networkidle")
            for x in page.evaluate(OVERFLOW_JS):
                problems.append({**x, "宽度": w})
            if w == 390:
                small = page.evaluate("""() => [...document.querySelectorAll('button,input,select,a')]
                  .filter(e => { const b = e.getBoundingClientRect(); return b.width > 0 && b.height < 32; })
                  .map(e => (e.textContent || e.getAttribute('aria-label') || e.type || '').trim().slice(0, 20))""")
                if small:
                    problems.append({"type": "手机上可点区域太小（高度不足 32px）", "控件": small[:6]})
                h1_lines = page.evaluate("""() => { const h = document.querySelector('h1'); if (!h) return 0;
                  return Math.round(h.getBoundingClientRect().height / parseFloat(getComputedStyle(h).lineHeight)); }""")
                if h1_lines > 3:
                    problems.append({"type": "手机上结论句超过 3 行", "行数": h1_lines})
            shot = out / f"w{w}.png"
            page.screenshot(path=str(shot), full_page=True)
            shots.append(shot.name)

            if w == 1280:
                ranges = page.locator('input[type="range"]')
                for i in range(ranges.count()):
                    r = ranges.nth(i)
                    rid = r.get_attribute("id") or f"range{i}"
                    for end in ("min", "max"):
                        v = r.get_attribute(end) or ("0" if end == "min" else "100")
                        r.evaluate("(el, v) => { el.value = v; el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); }", v)
                        page.wait_for_timeout(150)
                        for x in page.evaluate(OVERFLOW_JS):
                            problems.append({**x, "宽度": w, "状态": f"{rid}={v}"})
                        shot = out / f"w{w}_{rid}_{end}.png"
                        page.screenshot(path=str(shot), full_page=True)
                        shots.append(shot.name)
                # 分段按钮组：逐个点一遍，各截一张
                groups = page.locator('[role="group"]')
                for gi in range(groups.count()):
                    btns = groups.nth(gi).locator("button")
                    gid = groups.nth(gi).get_attribute("id") or f"group{gi}"
                    for bi in range(btns.count()):
                        btns.nth(bi).click()
                        page.wait_for_timeout(150)
                        for x in page.evaluate(OVERFLOW_JS):
                            problems.append({**x, "宽度": w, "状态": f"{gid} 第{bi + 1}项"})
                        shot = out / f"w{w}_{gid}_{bi + 1}.png"
                        page.screenshot(path=str(shot), full_page=True)
                        shots.append(shot.name)
                    if btns.count():
                        btns.first.click()
                guesses = page.locator("[data-guess]")
                if guesses.count():
                    guesses.first.click()
                    page.wait_for_timeout(150)
                    shot = out / f"w{w}_guess.png"
                    page.screenshot(path=str(shot), full_page=True)
                    shots.append(shot.name)
                else:
                    problems.append({"type": "没有「先猜后看」（找不到 data-guess 按钮）"})
            if console:
                problems.append({"type": "控制台报错", "宽度": w, "内容": console[:5]})
            if external:
                problems.append({"type": "对外网络请求", "宽度": w, "地址": sorted(set(external))[:5]})
            ctx.close()
        browser.close()

    print(f"截图 {len(shots)} 张，在 {out}")
    print("  " + "、".join(shots))
    if problems:
        print(f"发现 {len(problems)} 个问题：")
        for x in problems:
            print("  -", json.dumps(x, ensure_ascii=False))
    else:
        print("没有发现报错、外部请求、横向滚动或文字溢出。")
    print("请打开 w390.png、w1280.png 和滑块拨到两端的截图看一遍，并手算两组输入核对结果。")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
