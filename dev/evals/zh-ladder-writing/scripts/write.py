#!/usr/bin/env python3
"""用 Claude Code 生成改写稿。

每条用例在独立的临时目录里跑，目录里只有 原文.md，写作者看不到 cases.json 和标注。
带 skill 的组通过 --plugin-dir 加载本仓库，和真实使用时一样，也会运行 skill 里的对比脚本。

用法：python3 write.py 输出组别 --model opus|haiku [--skill [--repo 插件目录]] [--only h01,h07] [--workers 4]
  例：python3 write.py run3/opus_skill_v3 --model opus --skill
      python3 write.py run3/opus_skill_v2 --model opus --skill --repo /tmp/zh-ladder-v2   # 旧版 skill 做对照
输出：results/<组别>/<用例>.md，以及 results/<组别>/_meta.json（耗时、费用）
"""
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from common import REPO, RESULTS, cases, pmap

_lock = threading.Lock()


def prompt_for(case, skill):
    limit = f"（{case['word_limit']} 字以内）" if case.get("word_limit") else ""
    # skill 设了 disable-model-invocation，只能用斜杠命令调用；插件里的命令带插件名前缀
    cmd = "/zh-ladder:zh-ladder-writing " if skill else ""
    return (f"{cmd}任务：{case['task']}{limit}\n\n原文在当前目录的 原文.md。"
            "把最终交付的文字写入当前目录的 新稿.md，只写交付内容。")


def run_one(job):
    arm, case, model, skill, repo = job
    out = RESULTS / arm / f"{case['id']}.md"
    if out.exists():
        return 0
    work = Path(tempfile.mkdtemp(prefix="zhw-"))
    try:
        (work / "原文.md").write_text(case["source"], encoding="utf-8")
        cmd = ["claude", "-p", "--model", model, "--output-format", "json",
               "--permission-mode", "acceptEdits",
               "--allowedTools", "Read,Write,Edit,Glob,Grep,Skill,Bash(python3:*),Bash(mktemp:*),Bash(cat:*)"]
        if skill:
            cmd += ["--plugin-dir", str(repo)]
        t0 = time.time()
        # 提示走 stdin：--allowedTools 是可变参数，放在命令行末尾会把提示吞掉
        r = subprocess.run(cmd, input=prompt_for(case, skill), cwd=work, capture_output=True, text=True, timeout=1800)
        draft = work / "新稿.md"
        if not draft.exists():
            print(f"失败 {arm} {case['id']}：没有写出 新稿.md；{(r.stdout or r.stderr)[-300:]}", flush=True)
            return 1
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(draft, out)
        try:
            info = json.loads(r.stdout)
        except json.JSONDecodeError:
            info = {}
        meta = {"seconds": round(time.time() - t0), "cost_usd": info.get("total_cost_usd"),
                "turns": info.get("num_turns"), "model": model, "skill": skill,
                "repo": str(repo) if skill else None}
        with _lock:
            mp = RESULTS / arm / "_meta.json"
            data = json.loads(mp.read_text(encoding="utf-8")) if mp.exists() else {}
            data[case["id"]] = meta
            mp.write_text(json.dumps(dict(sorted(data.items())), ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"完成 {arm} {case['id']}  {meta['seconds']}s  ${meta['cost_usd']}", flush=True)
        return 0
    except subprocess.TimeoutExpired:
        print(f"超时 {arm} {case['id']}", flush=True)
        return 1
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main():
    argv = sys.argv[1:]
    if not argv or "--model" not in argv:
        print(__doc__)
        sys.exit(2)
    arm = argv[0]
    model = argv[argv.index("--model") + 1]
    skill = "--skill" in argv
    only = argv[argv.index("--only") + 1].split(",") if "--only" in argv else None
    repo = Path(argv[argv.index("--repo") + 1]).resolve() if "--repo" in argv else REPO
    workers = int(argv[argv.index("--workers") + 1]) if "--workers" in argv else 4
    cs = [c for c in cases() if not only or c["id"][:3] in only]
    fails = sum(pmap(run_one, [(arm, c, model, skill, repo) for c in cs], workers))
    if fails:
        print(f"有 {fails} 条失败，重跑同一命令会只补缺的")


if __name__ == "__main__":
    main()
