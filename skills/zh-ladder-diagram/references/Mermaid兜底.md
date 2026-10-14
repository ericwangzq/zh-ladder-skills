# Mermaid 兜底

什么时候用：用户点名要 Mermaid；或者图很大、结构还会反复改，手写 SVG 的坐标不值得维护。其他时候用手写 SVG，因为 Mermaid 的自动布局经常把关键的那条线放在不显眼的地方，而且你无法控制强调色以外的细节。

## 渲染

用 mermaid-cli，必须带上本目录的配置文件，否则中文标点会显示成半宽、带空隙：

```bash
npx -y @mermaid-js/mermaid-cli -i 图.mmd -o 图.svg -c <本 skill 目录>/assets/mermaid-config.json
```

已经装了 Chromium 但 mermaid-cli 自己下载浏览器失败时，设置 `PUPPETEER_SKIP_DOWNLOAD=1` 安装，再用 `-p` 指定一个 puppeteer 配置文件，在里面写 `executablePath` 指向已有的 Chrome 或 Chromium。

出 PNG 时，用 `python3 ${CLAUDE_SKILL_DIR}/scripts/svg_check.py 图.svg --png 图.png`，不要用 CairoSVG 或 rsvg 转：Mermaid 的文字放在 foreignObject 里，这两个工具会让文字整段消失。

## 写法

- 第一行写方向：`flowchart LR`（从左到右）或 `flowchart TD`（从上到下）。
- 长标签在合适的位置用 `<br/>` 手动断行，不要指望自动换行。
- 连线标签：`A -->|调用接口| B`。
- 不确定的关系用虚线：`A -.->|回滚？| B`，并在图下说明。
- 强调一个节点：`style B stroke:#3370ff,stroke-width:2px,fill:#eef3ff`。只强调一个。
- 标题不放进 Mermaid 里，写在图上方的正文里（一句结论）。
