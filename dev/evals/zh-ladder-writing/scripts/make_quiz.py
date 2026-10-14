#!/usr/bin/env python3
"""为每条难用例生成读者测验的草稿：问题、标准答案、得分要点、常见错答。

草稿必须人工逐条审过再用：标准答案错了，整个测验就测歪了。

用法：
  python3 make_quiz.py [--model 模型] [--only h01,h02]   出草稿
  python3 check_quiz.py                                   另一个模型复核，写 quiz.check.json
  python3 make_quiz.py --revise                           按复核意见修订草稿
输出：hard/quiz.draft.json（审完改名为 hard/quiz.json）
"""
import json
import sys

from common import HARD, call_json, cases, models, pmap

MODEL = None  # 环境变量 ZH_LADDER_QUIZ_MAKER

SYSTEM = "你是严谨的中文评测设计者。只依据给你的原文出题和写答案，不加原文没有的信息。只输出 JSON。"

PROMPT = """下面是一份原文，以及评测设计者事先标注的「必须保留的事实」「陷阱」「不能出现的歪曲」和三个读者问题。

我们要做一个「读者测验」：读者只读别人改写后的稿子（看不到原文），然后回答问题。答得对不对，反映改写稿有没有让读者正确理解原文。

请出 7 道题：
- 第 1–3 题：原样使用给出的三个读者问题（role 写 "reader"）。
- 第 4–7 题：针对陷阱和歪曲各出一道（role 写 "probe"）。像一个真实读者会问的那样提问，语气中性，不要在题目里暗示答案（不要问「X 是不是估算」，要问「X 这个数是怎么来的」）。挑最可能在改写中走样、且走样后会影响读者判断的点。

每道题给：
- "q"：问题
- "answer"：标准答案，一到三句，严格依据原文；原文自己有矛盾的，答案要写明矛盾
- "key_points"：答对必须包含的要点，2–4 条，每条一句短话
- "wrong_if"：常见错答，即改写稿走样后读者会给出的错误理解，1–3 条
- "role"："reader" 或 "probe"

输出格式：{{"questions": [...]}}

== 任务 ==
{task}

== 必须保留的事实 ==
{must_preserve}

== 陷阱 ==
{traps}

== 不能出现的歪曲 ==
{must_not}

== 读者问题 ==
{reader_questions}

== 原文 ==
{source}
"""


def make(case):
    lines = lambda xs: "\n".join(f"- {x}" for x in xs)
    prompt = PROMPT.format(
        task=case["task"], must_preserve=lines(case["must_preserve"]), traps=lines(case["traps"]),
        must_not=lines(case["must_not"]), reader_questions=lines(case["reader_questions"]),
        source=case["source"])
    obj = call_json(MODEL, SYSTEM, prompt)
    qs = obj["questions"]
    assert len(qs) == 7, f"{case['id']} 出了 {len(qs)} 道题"
    for i, q in enumerate(qs, 1):
        q["id"] = f"q{i}"
    print("出题完成", case["id"], flush=True)
    return case["id"], qs


REVISE = """下面是一组读者测验题，以及核查员对照原文提出的问题。请对照原文逐条判断核查意见：成立的就改，不成立的保留原样。

修改原则：
- 标准答案和得分要点必须严格符合原文；原文没有的不加，原文有矛盾就写明矛盾，不替原文判断哪处对。
- 得分要点是评分依据，只放读者理解这道题必须知道的 2–4 点，不求穷尽。
- 题面要中性、不暗示答案；范围太宽的题可以收窄。
- 第 1–3 题题面是给定的读者问题，不改题面，只改答案和要点。

输出完整的 7 道题，格式同输入：{{"questions": [...]}}

== 核查意见 ==
{issues}

== 当前测验 ==
{quiz}

== 原文 ==
{source}
"""


def revise(args):
    case, qs, issues = args
    if not issues:
        return case["id"], qs
    obj = call_json(MODEL, SYSTEM, REVISE.format(
        issues=json.dumps(issues, ensure_ascii=False, indent=1),
        quiz=json.dumps(qs, ensure_ascii=False, indent=1), source=case["source"]))
    new = obj["questions"]
    assert len(new) == 7, f"{case['id']} 改后有 {len(new)} 道题"
    for i, q in enumerate(new, 1):
        q["id"] = f"q{i}"
    print("修订完成", case["id"], flush=True)
    return case["id"], new


def main_revise():
    draft = json.loads((HARD / "quiz.draft.json").read_text(encoding="utf-8"))
    checks = json.loads((HARD / "quiz.check.json").read_text(encoding="utf-8"))
    by_id = {c["id"]: c for c in cases()}
    res = pmap(revise, [(by_id[k], v, checks.get(k, [])) for k, v in draft.items()], workers=5)
    (HARD / "quiz.draft.json").write_text(json.dumps(dict(sorted(res)), ensure_ascii=False, indent=1), encoding="utf-8")
    print("已按核查意见修订 quiz.draft.json")


def main():
    global MODEL
    if "--model" in sys.argv:
        MODEL = sys.argv[sys.argv.index("--model") + 1]
    if MODEL is None:
        MODEL = models("ZH_LADDER_QUIZ_MAKER")[0]
    if "--revise" in sys.argv:
        return main_revise()
    only = None
    if "--only" in sys.argv:
        only = sys.argv[sys.argv.index("--only") + 1].split(",")
    cs = [c for c in cases() if not only or c["id"][:3] in only]
    out = HARD / "quiz.draft.json"
    draft = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    for cid, qs in pmap(make, cs, workers=5):
        draft[cid] = qs
    out.write_text(json.dumps(dict(sorted(draft.items())), ensure_ascii=False, indent=1), encoding="utf-8")
    print("写入", out)


if __name__ == "__main__":
    main()
