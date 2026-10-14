#!/usr/bin/env python3
"""shared/ 是共用规则的唯一源头。每个 skill 的 references/ 里放一份副本，让 skill 目录自包含。

用法：
  python3 tools/sync_shared.py          把 shared/ 复制进每个 skill 的 references/
  python3 tools/sync_shared.py --check  只检查副本是否和源头一致，不一致时退出码为 1

改了 shared/ 里的文件，先运行一次不带参数的版本再提交。
"""
import filecmp
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def skill_dirs():
    for base in ("skills", "experimental"):
        for d in sorted((ROOT / base).iterdir()):
            if (d / "SKILL.md").exists():
                yield d


def main():
    check = "--check" in sys.argv
    stale = []
    for d in skill_dirs():
        for src in sorted((ROOT / "shared").iterdir()):
            dst = d / "references" / src.name
            if dst.exists() and filecmp.cmp(src, dst, shallow=False):
                continue
            if check:
                stale.append(dst.relative_to(ROOT))
            else:
                dst.parent.mkdir(exist_ok=True)
                shutil.copy(src, dst)
                print(f"已更新 {dst.relative_to(ROOT)}")
    if stale:
        print("这些副本和 shared/ 不一致，运行 python3 tools/sync_shared.py：")
        for s in stale:
            print("  ", s)
        return 1
    if check:
        print("shared/ 的副本都一致。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
