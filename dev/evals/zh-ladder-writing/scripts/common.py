"""评测脚本共用的路径、模型调用和计数函数。

模型调用走 pi 的非交互模式：不带工具、skill、扩展和上下文文件，只给系统提示和一条消息，
保证评委和读者只看到我们给它的东西。
"""
import json
import os
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

EVAL = Path(__file__).resolve().parent.parent          # dev/evals/zh-ladder-writing
REPO = EVAL.parents[2]                                 # 仓库根目录
HARD = EVAL / "hard"
RESULTS = EVAL / "results"
SKILL = REPO / "skills" / "zh-ladder-writing"


def char_count(text: str) -> int:
    """与 fidelity_check.py 同一口径：空白和 Markdown 符号不算。"""
    return len(re.sub(r"[\s#*|`>_~\-]", "", text))


def cases() -> list:
    return json.loads((HARD / "cases.json").read_text(encoding="utf-8"))


def source_text(case: dict) -> str:
    """原文正文（不含「任务：」那一行）。"""
    return case["source"]


def output_path(arm: str, case_id: str) -> Path:
    return RESULTS / arm / f"{case_id}.md"


def models(var: str) -> list:
    """从环境变量读模型名（pi 的 provider/model[:thinking] 写法），逗号分隔多个。"""
    v = os.environ.get(var, "").strip()
    if not v:
        raise SystemExit(f"请先设置环境变量 {var}，例如：export {var}=anthropic/claude-sonnet-4-6:low"
                         "（模型名用 `pi --list-models` 查，多个用逗号分隔）")
    return [x.strip() for x in v.split(",") if x.strip()]


def call(model: str, system: str, prompt: str, retries: int = 4, timeout: int = 600) -> str:
    cmd = ["pi", "-p", "--no-session", "--no-tools", "--no-skills", "--no-extensions",
           "--no-context-files", "--no-prompt-templates", "--offline",
           "--system-prompt", system, "--model", model]
    err = ""
    for i in range(retries):
        try:
            r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=timeout)
            out = r.stdout.strip()
            if r.returncode == 0 and out and not re.match(r"^\d{3}: ", out):
                return out
            err = (out or r.stderr)[-300:]
        except subprocess.TimeoutExpired:
            err = "timeout"
        time.sleep(5 * (i + 1))
    raise RuntimeError(f"{model} 调用失败：{err}")


def parse_json(text: str):
    """从模型输出里取出第一个 JSON 对象或数组。"""
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        text = m.group(1)
    start = min([i for i in (text.find("{"), text.find("[")) if i >= 0], default=-1)
    if start < 0:
        raise ValueError(f"没有 JSON：{text[:200]}")
    obj, _ = json.JSONDecoder().raw_decode(text[start:])
    return obj


def call_json(model: str, system: str, prompt: str, tries: int = 3):
    last = None
    for _ in range(tries):
        try:
            return parse_json(call(model, system, prompt))
        except (ValueError, json.JSONDecodeError) as e:
            last = e
    raise RuntimeError(f"{model} 没有返回可解析的 JSON：{last}")


def pmap(fn, items, workers: int = 6):
    with ThreadPoolExecutor(workers) as ex:
        return list(ex.map(fn, items))


def safe(name: str) -> str:
    """模型名里的 / 和 : 换成文件名可用的字符。"""
    return re.sub(r"[/:]", "_", name)
