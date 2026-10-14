#!/usr/bin/env python3
"""读者测验：读者只读改写稿（看不到原文），回答 hard/quiz.json 里的问题，再由评委对照标准答案打分。

两种读法：
  full  读全文，答 7 道题（3 道读者问题 + 4 道陷阱题）
  skim  只读开头 300 字（字数口径同 fidelity_check.py），答 3 道读者问题——模拟领导只看开头

每道题，评委逐条判断得分要点是否答到，并判断读者有没有被误导（答出了与原文相反或走样的理解）。
「被误导」比「不知道」更糟：读者以为自己懂了。

用法：
  python3 quiz.py 组别... [--reader 模型] [--grader 模型,模型] [--modes full,skim] [--rep 2]
  组别是 results/ 下的子目录，如 opus_base it2/opus_skill；source 表示直接读原文（参照上限）

结果缓存在 results/<组别>/_quiz/ 下，重跑只补缺的。
"""
import json
import sys
import threading

from common import RESULTS, call_json, cases, char_count, models, output_path, pmap, safe

READER = None   # 环境变量 ZH_LADDER_READER
GRADERS = None  # 环境变量 ZH_LADDER_GRADERS，逗号分隔
SKIM_CHARS = 300
REP = ""  # 重复实验时的文件名后缀，如 "_r2"

READER_SYSTEM = "你是一位忙碌的读者。只依据给你的稿子回答问题，不用自己的常识补充。只输出 JSON。"
READER_PROMPT = """下面是同事交给你的一份稿子{skim_note}。读完后回答问题。

规则：
- 只依据稿子。稿子里没写的，就回答「稿子没说」，不要猜。
- 稿子里写了不确定、有矛盾、或有前提条件的，照实说出来。
- 每题一到三句。

输出：{{"answers": {{"q1": "……", "q2": "……"}}}}

== 问题 ==
{questions}

== 稿子 ==
{text}
"""

GRADER_SYSTEM = "你是严格、公正的阅卷人。只依据标准答案和得分要点判断。只输出 JSON。"
GRADER_PROMPT = """读者读了一份改写稿（不是原文）后回答了下面的问题。请对照标准答案逐题阅卷。

每道题：
- "points"：对每条得分要点，读者的回答是否表达了这个意思（true/false）。意思对就算，不要求措辞一致；只说了一半的算 false。
- "misled"：读者的回答里有没有与标准答案相反、或属于「常见错答」的理解（true/false）。回答「稿子没说」不算 misled。
- "note"：一句话说明扣分或 misled 的原因；全对就写空字符串。

输出：{{"q1": {{"points": [true, false], "misled": false, "note": ""}}, ...}}

== 题目、标准答案和读者回答 ==
{items}
"""

_lock = threading.Lock()


def skim(text: str, n: int = SKIM_CHARS) -> str:
    """取开头，直到计数口径下满 n 字。"""
    for i in range(len(text)):
        if char_count(text[: i + 1]) >= n:
            return text[: i + 1]
    return text


def arm_text(arm: str, case: dict) -> str:
    if arm == "source":
        return case["source"]
    return output_path(arm, case["id"]).read_text(encoding="utf-8")


def store(arm: str, name: str) -> "Path":
    d = RESULTS / arm / "_quiz"
    d.mkdir(parents=True, exist_ok=True)
    return d / name


def load(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save(path, cid, value):
    with _lock:
        data = load(path)
        data[cid] = value
        path.write_text(json.dumps(dict(sorted(data.items())), ensure_ascii=False, indent=1), encoding="utf-8")


def questions_for(qs, mode):
    return [q for q in qs if mode == "full" or q["role"] == "reader"]


def read_one(job):
    arm, case, qs, mode, reader = job
    path = store(arm, f"answers_{mode}_{safe(reader)}{REP}.json")
    if case["id"] in load(path):
        return
    text = arm_text(arm, case)
    if mode == "skim":
        text = skim(text)
    qlist = questions_for(qs, mode)
    prompt = READER_PROMPT.format(
        skim_note="（你只读了开头这一段）" if mode == "skim" else "",
        questions="\n".join(f"{q['id']}. {q['q']}" for q in qlist), text=text)
    ans = call_json(reader, READER_SYSTEM, prompt)["answers"]
    save(path, case["id"], ans)


def grade_one(job):
    arm, case, qs, mode, reader, grader = job
    path = store(arm, f"grades_{mode}_{safe(reader)}__{safe(grader)}{REP}.json")
    if case["id"] in load(path):
        return
    answers = load(store(arm, f"answers_{mode}_{safe(reader)}{REP}.json"))[case["id"]]
    items = []
    for q in questions_for(qs, mode):
        items.append({"id": q["id"], "题目": q["q"], "标准答案": q["answer"],
                      "得分要点": q["key_points"], "常见错答": q["wrong_if"],
                      "读者回答": answers.get(q["id"], "（未作答）")})
    res = call_json(grader, GRADER_SYSTEM, GRADER_PROMPT.format(items=json.dumps(items, ensure_ascii=False, indent=1)))
    for q in questions_for(qs, mode):
        r = res.get(q["id"])
        if not r or len(r.get("points", [])) != len(q["key_points"]):
            raise RuntimeError(f"{arm} {case['id']} {q['id']} 阅卷结果不完整：{r}")
    save(path, case["id"], res)


def guarded(fn):
    def wrap(job):
        try:
            fn(job)
        except Exception as e:  # 单份失败不影响其他，重跑会补上
            print(f"失败 {job[0]} {job[1]['id']} {job[3]}：{str(e)[:160]}", flush=True)
            return 1
        return 0
    return wrap


def run(arms, reader, graders, modes, workers=10):
    quiz = json.loads((RESULTS.parent / "hard" / "quiz.json").read_text(encoding="utf-8"))
    cs = [c for c in cases() if c["id"] in quiz]
    jobs = [(a, c, quiz[c["id"]], m, reader) for a in arms for c in cs for m in modes]
    print(f"读者作答 {len(jobs)} 份……", flush=True)
    fails = sum(pmap(guarded(read_one), jobs, workers))
    gjobs = [j + (g,) for j in jobs for g in graders]
    print(f"阅卷 {len(gjobs)} 份……", flush=True)
    fails += sum(pmap(guarded(grade_one), gjobs, workers))
    if fails:
        print(f"有 {fails} 份失败，重跑同一命令会只补缺的")


def opt(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


if __name__ == "__main__":
    flags = {"--reader", "--grader", "--modes", "--rep"}
    argv = sys.argv[1:]
    arms = [a for i, a in enumerate(argv) if not a.startswith("--") and (i == 0 or argv[i - 1] not in flags)]
    if not arms:
        print(__doc__)
        sys.exit(2)
    if "--rep" in sys.argv:
        REP = "_r" + opt("--rep", "2")
    reader = opt("--reader", None) or models("ZH_LADDER_READER")[0]
    graders = opt("--grader", None)
    graders = graders.split(",") if graders else models("ZH_LADDER_GRADERS")
    run(arms, reader, graders,
        opt("--modes", "full,skim").split(","))
    print("完成")
