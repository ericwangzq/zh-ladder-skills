#!/usr/bin/env python3
"""检查 skill 有没有写回「只对某个 agent 有效」的东西。

用法：
  python3 tools/portability_check.py            检查 skills/ 和 experimental/
  python3 tools/portability_check.py --strict   有提醒也当失败

查的是跨 agent 兼容性，不是内容质量：
  1. frontmatter 只用 Agent Skills 规范允许的字段
  2. 没有产品专用变量（${CLAUDE_SKILL_DIR} 之类）和写死的安装目录
  3. 跑脚本的命令用 $SKILL_DIR，不假设工作目录就是 skill 目录
  4. SKILL.md 提到的 references/ scripts/ assets/ 文件真的存在
  5. Python 版本说法一致（SKILL.md 的 compatibility、脚本文档、README）
  6. shared/ 的副本和各 skill 里的 references/ 一致

退出码：0 通过，1 有错，--strict 时有提醒也算 1。
"""
import argparse
import filecmp
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SPEC_FIELDS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
# 各产品自己加的字段：能用，但只在那家生效，而且会挡住 claude.ai 上传和规范打包
HOST_FIELDS = {
    "disable-model-invocation": "Claude Code / pi",
    "user-invocable": "Claude Code",
    "context": "Claude Code",
    "agent": "Claude Code",
    "model": "Claude Code",
    "effort": "Claude Code",
    "paths": "Claude Code",
    "hooks": "Claude Code",
    "argument-hint": "Claude Code",
    "arguments": "Claude Code",
    "when_to_use": "Claude Code",
    "shell": "Claude Code",
    "background": "Claude Code",
    "disallowed-tools": "Claude Code",
}
NAME_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])$")
# 产品专用变量：出现即错（README 和 tools/ 里可以提，那是给人看的说明）
PRODUCT_VARS = re.compile(r"\$\{?(CLAUDE_[A-Z_]+|CODEX_[A-Z_]+|OPENAI_[A-Z_]+)\}?")
# 写死的安装目录：出现在 skill 正文里即错
HARD_PATHS = re.compile(r"~/\.(claude|pi|codex|gemini)\b|\.cursor/|\$CODEX_HOME")
BARE_SCRIPT = re.compile(r"python3\s+(?:-I\s+)?scripts/")
PY_VER_RE = re.compile(r"Python\s+3\.(\d+)")
REF_RE = re.compile(r"(references|scripts|assets)/([\w.\u4e00-\u9fff-]+\.(?:md|py|json|svg|html|txt|png))")

errors: list = []
warnings: list = []


def err(skill, msg):
    errors.append(f"{skill}: {msg}")


def warn(skill, msg):
    warnings.append(f"{skill}: {msg}")


def frontmatter(text):
    """返回 (字段名集合, 原始 frontmatter 文本)；开头不对时返回 (None, '')。"""
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        return None, ""
    head = text[4:].split("\n---\n", 1)[0]
    keys = set()
    cur = None
    for line in head.split("\n"):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[0] in " \t":
            continue  # 缩进的续行 / 嵌套（metadata 的子键）
        m = re.match(r"^([\w-]+):", line)
        if m:
            cur = m.group(1)
            keys.add(cur)
    return keys, head


def field_of(head, name):
    m = re.search(rf"^{name}:[ \t]*(.*)$", head, re.M)
    return m.group(1).strip().strip('"') if m else None


def check_skill(d: Path):
    f = d / "SKILL.md"
    text = f.read_text(encoding="utf-8")
    rel = d.relative_to(ROOT)
    keys, head = frontmatter(text)
    if keys is None:
        err(rel, "SKILL.md 的 YAML frontmatter 没有正确闭合（第一行是 ---，closing --- 单独占一行）")
        return
    unknown = keys - SPEC_FIELDS
    for k in sorted(unknown):
        where = HOST_FIELDS.get(k)
        if where:
            warn(rel, f"`{k}` 是 {where} 专用字段，别的 agent 会忽略；上传 claude.ai 或规范打包会硬报错")
        else:
            err(rel, f"`{k}` 不在 Agent Skills 规范的 6 个字段里")

    # 值：name / description / compatibility
    name, desc = field_of(head, "name"), field_of(head, "description")
    if not name:
        err(rel, "缺 name")
    elif name != d.name:
        err(rel, f"name={name} 和目录名 {d.name} 不一致")
    elif not NAME_RE.match(name) or "--" in name:
        err(rel, f"name「{name}」不符合规范（只能小写字母、数字、单个连字符，首尾不能是 -）")
    if not desc:
        err(rel, "缺 description")
    elif len(desc) > 1024:
        err(rel, f"description 长 {len(desc)}，超过 1024")
    compat = field_of(head, "compatibility")

    # 正文里不能有产品专用变量和写死的安装目录
    for lineno, line in enumerate(text.split("\n"), 1):
        for pat, label in ((PRODUCT_VARS, "产品专用环境变量"), (HARD_PATHS, "写死的安装目录")):
            for m in pat.finditer(line):
                err(rel, f"第 {lineno} 行出现{label} `{m.group(0)}`")

    # 命令必须显式给出 skill 目录，不能假设工作目录
    body = text[4:].split("\n---\n", 1)[1]
    for lineno, line in enumerate(body.split("\n"), 1):
        if "python3" in line and ".py" in line:
            if BARE_SCRIPT.search(line):
                err(rel, f"第 {lineno} 行用了裸的 `python3 scripts/…`，工作目录不是 skill 目录时会找不到文件")
            elif "$SKILL_DIR" not in line:
                err(rel, f"第 {lineno} 行跑脚本没有写明目录：{line.strip()[:60]}")

    # 引用的文件要存在
    for m in REF_RE.finditer(text):
        target = d / m.group(0)
        if not target.exists():
            err(rel, f"引用了不存在的文件 {m.group(0)}")

    # skill 目录约定要在正文里说明过
    if "$SKILL_DIR" in body and "路径约定" not in body:
        warn(rel, "用了 $SKILL_DIR 但没写「路径约定」说明它是什么")

    # 行数
    if len(text.split("\n")) > 500:
        err(rel, "SKILL.md 超过 500 行，规范建议拆分")

    # Python 版本说法一致
    claims = set()
    where = {}
    sources = [f] + sorted((d / "references").rglob("*.md")) + sorted((d / "scripts").glob("*.py"))
    for src in sources:
        for m in PY_VER_RE.finditer(src.read_text(encoding="utf-8")):
            claims.add(int(m.group(1)))
            where.setdefault(int(m.group(1)), set()).add(str(src.relative_to(ROOT)))
    if len(claims) > 1:
        e = f"{rel}: Python 版本说法不一致：" + "；".join(
            f"3.{c} 见 {', '.join(sorted(v))}" for c, v in sorted(where.items())
        )
        errors.append(e)
    elif claims and compat and str(list(claims)[0]) not in compat:
        warn(rel, f"脚本写的是 Python 3.{list(claims)[0]}+，compatibility 字段没对上")

    # 有脚本依赖 playwright，compatibility 必须提到
    scripts = d / "scripts"
    if scripts.is_dir():
        needs_pw = any("playwright" in f.read_text(encoding="utf-8") for f in scripts.glob("*.py"))
        if needs_pw and (not compat or "playwright" not in compat.lower()):
            err(rel, "脚本需要 playwright，但 compatibility 没写")


def check_versions():
    """全仓库对 Python 版本的说法只能有一个数，别 README 说 3.8、脚本文档说 3.9。"""
    seen = {}
    targets = [ROOT / "README.md"]
    for base in ("skills", "experimental"):
        root = ROOT / base
        if not root.exists():
            continue
        for d in sorted(root.iterdir()):
            targets += [d / "SKILL.md"]
            for sub in ("references", "scripts", "assets"):
                if (d / sub).is_dir():
                    targets += sorted((d / sub).rglob("*.md")) + sorted((d / sub).glob("*.py"))
    for f in targets:
        if not f.exists():
            continue
        for m in PY_VER_RE.finditer(f.read_text(encoding="utf-8")):
            seen.setdefault(int(m.group(1)), set()).add(str(f.relative_to(ROOT)))
    if len(seen) > 1:
        errors.append("Python 版本说法不一致：" + "；".join(
            f"3.{v} 见 {', '.join(sorted(fs))}" for v, fs in sorted(seen.items())
        ))


def check_shared():
    for base in ("skills", "experimental"):
        for d in sorted((ROOT / base).iterdir()):
            if not (d / "SKILL.md").exists():
                continue
            for src in sorted((ROOT / "shared").iterdir()):
                dst = d / "references" / src.name
                if dst.exists() and not filecmp.cmp(src, dst, shallow=False):
                    err(d.relative_to(ROOT), f"references/{src.name} 和 shared/ 不一致，运行 tools/sync_shared.py")


def main():
    ap = argparse.ArgumentParser(description="跨 agent 兼容性自查")
    ap.add_argument("--strict", action="store_true", help="有提醒也当失败")
    args = ap.parse_args()

    dirs = []
    for base in ("skills", "experimental"):
        root = ROOT / base
        if root.exists():
            dirs += [d for d in sorted(root.iterdir()) if (d / "SKILL.md").exists()]
    for d in dirs:
        check_skill(d)
    check_versions()
    check_shared()

    for e in errors:
        print(f"错  {e}")
    for w in warnings:
        print(f"提醒 {w}")
    if not errors and not warnings:
        print(f"checked: {len(dirs)} 个 skill，没发现问题")
        return 0
    print(f"\n{len(errors)} 个错，{len(warnings)} 个提醒（{len(dirs)} 个 skill）")
    return 1 if errors or (args.strict and warnings) else 0


if __name__ == "__main__":
    sys.exit(main())
