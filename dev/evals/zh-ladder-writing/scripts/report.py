#!/usr/bin/env python3
"""汇总读者测验和篇幅，打印 Markdown 表格。

用法：python3 report.py 组别... [--reader 模型] [--grader 模型,模型] [--by-case] [--rep 2]

指标：
  篇幅      改写稿字数 ÷ 原文字数（有字数上限的摘要用例单列，不计入平均）
  全文得分  读全文后，7 道题的得分要点答到的比例（两位评委平均）
  误导      读者被误导的题数（10 条用例 × 7 题 = 70 题，两位评委平均）
  开头得分  只读开头 300 字，3 道读者问题的得分要点答到的比例
  评委差    两位评委全文得分之差，用来看评分稳不稳
"""
import json
import sys

from common import RESULTS, cases, char_count, output_path, safe
import quiz
from common import models
from quiz import arm_text


def load(arm, mode, reader, grader):
    REP = quiz.REP
    p = RESULTS / arm / "_quiz" / f"grades_{mode}_{safe(reader)}__{safe(grader)}{REP}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def score(grades):
    got = tot = misled = 0
    for case in grades.values():
        for q in case.values():
            got += sum(bool(x) for x in q["points"])
            tot += len(q["points"])
            misled += bool(q.get("misled"))
    return (got / tot if tot else float("nan")), misled, len(grades)


def main():
    flags = {"--reader", "--grader", "--rep"}
    argv = sys.argv[1:]
    arms = [a for i, a in enumerate(argv) if not a.startswith("--") and (i == 0 or argv[i - 1] not in flags)]
    reader = sys.argv[sys.argv.index("--reader") + 1] if "--reader" in sys.argv else models("ZH_LADDER_READER")[0]
    graders = (sys.argv[sys.argv.index("--grader") + 1].split(",") if "--grader" in sys.argv else models("ZH_LADDER_GRADERS"))
    if "--rep" in sys.argv:
        quiz.REP = "_r" + sys.argv[sys.argv.index("--rep") + 1]
    cs = cases()
    unlimited = [c for c in cs if not c.get("word_limit")]

    print("| 组别 | 篇幅（无字数上限的 8 条） | 全文得分 | 误导（/70） | 开头得分 | 开头误导（/30） | 评委差 |")
    print("| --- | --- | --- | --- | --- | --- | --- |")
    for arm in arms:
        ratios = [char_count(arm_text(arm, c)) / char_count(c["source"]) for c in unlimited]
        full = [score(load(arm, "full", reader, g)) for g in graders]
        sk = [score(load(arm, "skim", reader, g)) for g in graders]
        n = min(x[2] for x in full + sk)
        fs = sum(x[0] for x in full) / len(full)
        fm = sum(x[1] for x in full) / len(full)
        ss = sum(x[0] for x in sk) / len(sk)
        sm = sum(x[1] for x in sk) / len(sk)
        gap = abs(full[0][0] - full[-1][0])
        note = "" if n == len(cs) else f"（只有 {n} 条）"
        print(f"| {arm}{note} | {sum(ratios) / len(ratios):.0%} | {fs:.0%} | {fm:.1f} | {ss:.0%} | {sm:.1f} | {gap:.0%} |")

    if "--by-case" in sys.argv:
        print("\n全文得分（按用例，两位评委平均）\n")
        print("| 用例 | " + " | ".join(arms) + " |")
        print("| --- |" + " --- |" * len(arms))
        for c in cs:
            row = []
            for arm in arms:
                vals = []
                for g in graders:
                    gr = load(arm, "full", reader, g)
                    if c["id"] in gr:
                        vals.append(score({c["id"]: gr[c["id"]]})[0])
                row.append(f"{sum(vals) / len(vals):.0%}" if vals else "—")
            print(f"| {c['id']} | " + " | ".join(row) + " |")


if __name__ == "__main__":
    main()
