#!/usr/bin/env python3
"""让另一个模型对照原文复核测验的标准答案，列出它认为有问题的题，供人工审。

用法：python3 check_quiz.py [quiz 文件，默认 hard/quiz.draft.json] [--model 模型]
"""
import json
import sys

from common import HARD, call_json, cases, models, pmap

MODEL = None  # 环境变量 ZH_LADDER_QUIZ_CHECKER
SYSTEM = "你是严谨的事实核查员。只依据原文判断。只输出 JSON。"
PROMPT = """下面是一份原文和一组测验题（含标准答案、得分要点、常见错答）。逐题对照原文核查：

- 标准答案和得分要点是否完全符合原文？有没有漏掉原文里会改变答案的条件、例外或矛盾？有没有加原文没有的东西？
- 题目是否有歧义、或在题面里暗示了答案？
- 「常见错答」是否真的是错的？

输出：{{"issues": [{{"id": "q4", "problem": "……", "fix": "建议的改法"}}]}}。没问题的题不要列。

== 测验 ==
{quiz}

== 原文 ==
{source}
"""


def check(args):
    case, qs = args
    obj = call_json(MODEL, SYSTEM, PROMPT.format(quiz=json.dumps(qs, ensure_ascii=False, indent=1),
                                                 source=case["source"]))
    return case["id"], obj.get("issues", [])


def main():
    global MODEL
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--model" in sys.argv:
        MODEL = sys.argv[sys.argv.index("--model") + 1]
        args = [a for a in args if a != MODEL]
    if MODEL is None:
        MODEL = models("ZH_LADDER_QUIZ_CHECKER")[0]
    path = args[0] if args else HARD / "quiz.draft.json"
    quiz = json.loads(open(path, encoding="utf-8").read())
    by_id = {c["id"]: c for c in cases()}
    res = pmap(check, [(by_id[k], v) for k, v in quiz.items()], workers=5)
    out = HARD / "quiz.check.json"
    out.write_text(json.dumps(dict(res), ensure_ascii=False, indent=1), encoding="utf-8")
    for cid, issues in res:
        for i in issues:
            print(f"{cid} {i['id']}: {i['problem']}\n    → {i.get('fix', '')}")
    print("写入", out)


if __name__ == "__main__":
    main()
