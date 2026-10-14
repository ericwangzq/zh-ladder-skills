#!/usr/bin/env python3
"""保真评分：评委对照原文和用例标注，给每份改写稿单独打分（不做两两比较，避免位置偏差）。

每份稿子评：
  必须保留的事实  逐条判 kept / weakened（还在但条件、确定程度或范围走样）/ lost
  不能出现的歪曲  逐条判有没有出现
  陷阱            逐条判有没有处理好
  无依据添加      原文没有的事实、原因、日期、建议
  可读性          1–5

有字数上限的摘要用例，只按「摘要必须保留的核心事实」评保留。

用法：python3 judge.py 组别... [--judge 模型,模型]
结果缓存在 results/<组别>/_judge/ 下，重跑只补缺的。
"""
import json
import sys
import threading

from common import RESULTS, call_json, cases, char_count, models, output_path, pmap, safe

JUDGES = None  # 环境变量 ZH_LADDER_JUDGES，逗号分隔两位评委

SYSTEM = "你是严格、公正的中文改写质量评委。只依据原文和标注判断。只输出 JSON。"
PROMPT = """下面是原文、改写任务、评测标注，以及一份改写稿。请给这份改写稿打分。

- "preserve"：对「必须保留的事实」逐条判断，值为 "kept"（意思完整保留）、"weakened"（还在，但条件、确定程度、范围、归属或状态走样了）、"lost"（没有了）。按标注顺序给一个数组。
- "must_not"：对「不能出现的歪曲」逐条判断改写稿是否出现了（true/false），按顺序给数组。
- "traps"：对「陷阱」逐条判断改写稿是否处理好了（true/false），按顺序给数组。与改写任务无关、无需处理的陷阱（例如摘要里本来就可以省略的细节）算 true。
- "fabrications"：改写稿里原文没有依据的事实、原因、日期、数字、建议，每条一句话；按原文条件做的、标明了是推算的计算不算。没有就给空数组。
- "readability"：1–5，读者读一遍能否抓住要点、是否简洁；5 最好。
- "notes"：一两句话说明主要扣分点。

输出：{{"preserve": [...], "must_not": [...], "traps": [...], "fabrications": [...], "readability": 4, "notes": "……"}}

== 改写任务 ==
{task}{limit}

== 必须保留的事实 ==
{preserve}

== 不能出现的歪曲 ==
{must_not}

== 陷阱 ==
{traps}

== 原文 ==
{source}

== 改写稿（{n} 字）==
{output}
"""

_lock = threading.Lock()


def rubric(case):
    keep = case.get("must_preserve_core") or case["must_preserve"]
    return keep, case["must_not"], case["traps"]


def path_for(arm, judge):
    d = RESULTS / arm / "_judge"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{safe(judge)}.json"


def load(p):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def judge_one(job):
    arm, case, judge = job
    p = path_for(arm, judge)
    if case["id"] in load(p):
        return 0
    try:
        keep, must_not, traps = rubric(case)
        out = output_path(arm, case["id"]).read_text(encoding="utf-8")
        num = lambda xs: "\n".join(f"{i}. {x}" for i, x in enumerate(xs, 1))
        res = call_json(judge, SYSTEM, PROMPT.format(
            task=case["task"], limit=f"（{case['word_limit']} 字以内）" if case.get("word_limit") else "",
            preserve=num(keep), must_not=num(must_not), traps=num(traps),
            source=case["source"], output=out, n=char_count(out)))
        for k, xs in (("preserve", keep), ("must_not", must_not), ("traps", traps)):
            if len(res.get(k, [])) != len(xs):
                raise RuntimeError(f"{k} 条数不对：{len(res.get(k, []))} ≠ {len(xs)}")
        with _lock:
            data = load(p)
            data[case["id"]] = res
            p.write_text(json.dumps(dict(sorted(data.items())), ensure_ascii=False, indent=1), encoding="utf-8")
        return 0
    except Exception as e:
        print(f"失败 {arm} {case['id']} {judge}：{str(e)[:160]}", flush=True)
        return 1


def summarize(arm, judges):
    """每位评委一行汇总，返回 [(judge, dict)]。"""
    rows = []
    for j in judges:
        data = load(path_for(arm, j))
        s = dict(n=len(data), kept=0, weakened=0, lost=0, must_not=0, traps=0, traps_total=0, fab=0, read=0.0)
        for r in data.values():
            for v in r["preserve"]:
                s[v if v in ("kept", "weakened", "lost") else "lost"] += 1
            s["must_not"] += sum(bool(x) for x in r["must_not"])
            s["traps"] += sum(bool(x) for x in r["traps"])
            s["traps_total"] += len(r["traps"])
            s["fab"] += len(r["fabrications"])
            s["read"] += r["readability"]
        if data:
            s["read"] /= len(data)
        rows.append((j, s))
    return rows


def main():
    argv = sys.argv[1:]
    arms = [a for i, a in enumerate(argv) if not a.startswith("--") and (i == 0 or argv[i - 1] != "--judge")]
    judges = sys.argv[sys.argv.index("--judge") + 1].split(",") if "--judge" in sys.argv else models("ZH_LADDER_JUDGES")
    if not arms:
        print(__doc__)
        sys.exit(2)
    if "--report" not in sys.argv:
        jobs = [(a, c, j) for a in arms for c in cases() for j in judges]
        fails = sum(pmap(judge_one, jobs, workers=10))
        if fails:
            print(f"有 {fails} 份失败，重跑同一命令会只补缺的")
    print("| 组别 | 评委 | 弱化 | 丢失 | 歪曲 | 陷阱 | 无依据添加 | 可读性 |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for a in arms:
        for j, s in summarize(a, judges):
            short = j.split("/")[-1].split(":")[0]
            print(f"| {a} | {short} | {s['weakened']} | {s['lost']} | {s['must_not']} | "
                  f"{s['traps']}/{s['traps_total']} | {s['fab']} | {s['read']:.1f} |")


if __name__ == "__main__":
    main()
