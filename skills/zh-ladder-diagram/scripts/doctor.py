#!/usr/bin/env python3
"""检查这台机器能不能正确渲染中文图。第一次使用时运行一次。

用法：python3 doctor.py [输出 PNG 路径，默认写到系统临时目录]

做三件事：
  1. 启动 Chromium（或系统 Chrome）
  2. 渲染一行中英混排的测试文字，读出浏览器实际用到的字体
  3. 导出一张 PNG，供你打开确认没有方块
"""
import sys
import tempfile
from pathlib import Path

SAMPLE = "中文讲解图：API 网关（QPS 1200）≤ 0.1%"
HTML = f"""<!doctype html><meta charset="utf-8">
<body style="margin:0;background:#fff">
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 80" width="640" height="80"
     font-family="'PingFang SC','Noto Sans CJK SC','Microsoft YaHei',sans-serif">
  <rect width="100%" height="100%" fill="#fff"/>
  <text id="t" x="24" y="48" font-size="22" fill="#1f2329">{SAMPLE}</text>
</svg></body>"""

CJK_FONT_HINTS = ("PingFang", "Noto Sans CJK", "Noto Sans SC", "Source Han", "思源", "苹方",
                  "Microsoft YaHei", "微软雅黑", "WenQuanYi", "Hiragino Sans GB", "Heiti", "黑体")


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else Path(tempfile.gettempdir()) / "zh-ladder-diagram-doctor.png").resolve()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("缺少 playwright。请运行：pip install playwright && python3 -m playwright install chromium")
        return 2
    tmp = out.with_suffix(".html")
    tmp.write_text(HTML, encoding="utf-8")
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
            which = "Playwright Chromium"
        except Exception:
            try:
                browser = p.chromium.launch(channel="chrome")
                which = "系统 Chrome"
            except Exception as e:
                print(f"无法启动浏览器：{e}\n请运行：python3 -m playwright install chromium")
                return 2
        page = browser.new_page(device_scale_factor=2)
        page.goto(tmp.as_uri())
        page.evaluate("document.fonts.ready")
        cdp = page.context.new_cdp_session(page)
        cdp.send("DOM.enable")
        cdp.send("CSS.enable")
        root = cdp.send("DOM.getDocument")["root"]["nodeId"]
        node = cdp.send("DOM.querySelector", {"nodeId": root, "selector": "#t"})["nodeId"]
        fonts = cdp.send("CSS.getPlatformFontsForNode", {"nodeId": node})["fonts"]
        page.locator("svg").screenshot(path=str(out))
        browser.close()
    tmp.unlink(missing_ok=True)

    print(f"浏览器：{which}")
    used = [f"{f['familyName']}（{f['glyphCount']} 个字）" for f in fonts]
    print("实际用到的字体：" + "、".join(used))
    has_cjk = any(any(h.lower() in f["familyName"].lower() for h in CJK_FONT_HINTS) for f in fonts)
    if has_cjk:
        print("中文字体：正常。")
    else:
        print("中文字体：没有找到常见的中文字体，图里的中文可能显示成方块。"
              "Mac 自带苹方；Linux 请安装 fonts-noto-cjk；Windows 自带微软雅黑。")
    print(f"测试图：{out}（请打开确认没有方块）")
    return 0 if has_cjk else 1


if __name__ == "__main__":
    sys.exit(main())
