#!/usr/bin/env python3
"""按分镜生成中文配音、每个镜头的时长和字幕。

用法：python3 tts.py 分镜.json [--out build/] [--provider edge|say|command] [--voice 音色]
           [--command '模板'] [--lint-only]

输出（都在 --out 目录下）：
  audio/<镜头id>.mp3   每个镜头一段配音
  timings.json         每个镜头的起点和时长（秒），动画按它对齐
  subtitles.srt        字幕，按句切分

配音来源（分镜 JSON 的 tts.provider，或命令行 --provider）：
  edge     默认。用 edge-tts（pip install edge-tts），需要联网。调用的是微软 Edge 的非官方接口，只适合个人使用。
  say      Mac 自带的 say 命令，离线可用。中文音色：Tingting、Meijia 等（say -v '?' 查看）。需要 ffmpeg 转码。
  command  任意命令行工具。用 --command 或 tts.command 给模板，{text_file} 和 {out} 会被替换，
           例如：'my-tts --in {text_file} --out {out}'。换成付费接口时用这个，不用改本脚本。

生成前会先做一遍分镜检查：屏幕文字里的数字旁白里有没有、旁白里的「约」「预计」屏幕上丢没丢。
依赖：ffmpeg / ffprobe（用来读时长、转码）。
"""
import argparse
import asyncio
import json
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HEDGES = ("约", "大约", "预计", "估算", "推算", "初步", "可能", "未实测", "未验证", "尚未", "未确认")
NUM_RE = re.compile(r"\d+(?:[.,]\d+)*")


# ---------- 分镜检查 ----------
CN_DIGIT = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
CN_UNIT = {"十": 10, "百": 100, "千": 1000}
CN_BIG = {"万": 10 ** 4, "亿": 10 ** 8}
CN_RE = re.compile(r"[零〇一二两三四五六七八九十百千万亿]+(?:点[零〇一二三四五六七八九]+)?")


def cn_to_num(s):
    """把「九千」「二十六」「一点五」这类汉字数字换成数字字符串；不像数字的返回 None。"""
    if "点" in s:
        a, b = s.split("点", 1)
        head = cn_to_num(a) if a else "0"
        tail = "".join(str(CN_DIGIT[c]) for c in b if c in CN_DIGIT)
        return f"{head}.{tail}" if head is not None and tail else None
    total, section, num = 0, 0, None
    for c in s:
        if c in CN_DIGIT:
            num = CN_DIGIT[c]
        elif c in CN_UNIT:
            section += (num if num is not None else 1) * CN_UNIT[c]
            num = None
        elif c in CN_BIG:
            section += num or 0
            total += section * CN_BIG[c]
            section, num = 0, None
    value = total + section + (num or 0)
    if value == 0 and not any(c in "零〇" for c in s):
        return None
    return str(value)


def numbers_in(text):
    found = {n.replace(",", "") for n in NUM_RE.findall(text)}
    found |= {v for v in (cn_to_num(m) for m in CN_RE.findall(text)) if v}
    return found


def lint(storyboard):
    warnings = []
    ids = [s.get("id") for s in storyboard["scenes"]]
    if len(ids) != len(set(ids)) or None in ids:
        warnings.append("镜头 id 缺失或重复")
    kinds = [s.get("kind") for s in storyboard["scenes"]]
    if kinds[:1] != ["title"]:
        warnings.append("第一个镜头不是标题卡（kind: title）")
    if kinds[-1:] != ["recap"]:
        warnings.append("最后一个镜头不是总结卡（kind: recap）")
    for s in storyboard["scenes"]:
        nar = s.get("narration", "")
        screen = " ".join(s.get("on_screen", []))
        nar_nums = numbers_in(nar) | numbers_in(s.get("basis", ""))
        for n in NUM_RE.findall(screen):
            if n.replace(",", "") not in nar_nums:
                warnings.append(f"{s['id']}：屏幕上的数字 {n} 旁白里没有说")
        for h in HEDGES:
            if h in nar and screen and h not in screen and not any(x in screen for x in ("推算", "未实测", "约", "≈", "预计")):
                warnings.append(f"{s['id']}：旁白有「{h}」，屏幕文字没有任何限定，可能被说成了确定的事")
                break
        for line in s.get("on_screen", []):
            cjk = len(re.findall(r"[一-鿿]", line))
            if cjk > 14:
                warnings.append(f"{s['id']}：屏幕文字「{line}」超过 14 个汉字，建议断行")
    return warnings


# ---------- 配音来源 ----------
def ffprobe_duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=nw=1:nk=1", str(path)], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


async def edge_synth(text, out, voice, rate):
    import edge_tts
    try:
        comm = edge_tts.Communicate(text, voice, rate=rate, boundary="SentenceBoundary")
    except TypeError:  # 旧版本没有 boundary 参数
        comm = edge_tts.Communicate(text, voice, rate=rate)
    marks = []
    with open(out, "wb") as f:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"].endswith("Boundary"):
                marks.append({"start": chunk["offset"] / 1e7, "end": (chunk["offset"] + chunk["duration"]) / 1e7,
                              "text": chunk["text"], "kind": chunk["type"]})
    return marks


def say_synth(text, out, voice, rate):
    with tempfile.TemporaryDirectory() as d:
        txt, aiff = Path(d) / "t.txt", Path(d) / "t.aiff"
        txt.write_text(text, encoding="utf-8")
        cmd = ["say", "-v", voice or "Tingting", "-o", str(aiff), "-f", str(txt)]
        if rate:
            cmd[1:1] = ["-r", str(rate)]
        subprocess.run(cmd, check=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(aiff), "-codec:a", "libmp3lame", "-q:a", "3", str(out)], check=True)
    return []


def command_synth(text, out, template):
    with tempfile.TemporaryDirectory() as d:
        txt = Path(d) / "t.txt"
        txt.write_text(text, encoding="utf-8")
        cmd = template.replace("{text_file}", shlex.quote(str(txt))).replace("{out}", shlex.quote(str(out)))
        subprocess.run(cmd, shell=True, check=True)
    return []


# ---------- 字幕 ----------
def split_sentences(text):
    parts = [p for p in re.split(r"(?<=[。！？；])", text) if p.strip()]
    out = []
    for p in parts:  # 太长的句子在逗号处再切，一条字幕不超过约 24 个字
        while len(p) > 24 and "，" in p[8:24]:
            k = p.index("，", 8) + 1
            out.append(p[:k])
            p = p[k:]
        out.append(p)
    return [x.strip() for x in out if x.strip()]


def srt_time(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def cues_for_scene(narration, start, duration, marks):
    sents = split_sentences(narration)
    sentence_marks = [m for m in marks if m["kind"] == "SentenceBoundary"]
    if sentence_marks and len(sentence_marks) == len(sents):
        return [(start + m["start"], start + m["end"], s) for m, s in zip(sentence_marks, sents)]
    # 没有句子边界时，按字数比例分配时长
    total = sum(len(s) for s in sents) or 1
    cues, t = [], start
    for s in sents:
        d = duration * len(s) / total
        cues.append((t, t + d, s))
        t += d
    return cues


def main():
    ap = argparse.ArgumentParser(description="按分镜生成中文配音和字幕")
    ap.add_argument("storyboard")
    ap.add_argument("--out", default="build")
    ap.add_argument("--provider")
    ap.add_argument("--voice")
    ap.add_argument("--rate")
    ap.add_argument("--command")
    ap.add_argument("--lint-only", action="store_true", help="只检查分镜，不生成配音")
    args = ap.parse_args()

    sb = json.loads(Path(args.storyboard).read_text(encoding="utf-8"))
    warnings = lint(sb)
    print(f"分镜检查：{len(warnings)} 条提醒")
    for w in warnings:
        print("  -", w)
    if args.lint_only:
        return 0

    cfg = sb.get("tts", {})
    provider = args.provider or cfg.get("provider", "edge")
    voice = args.voice or cfg.get("voice") or ("zh-CN-XiaoxiaoNeural" if provider == "edge" else None)
    rate = args.rate or cfg.get("rate") or ("+0%" if provider == "edge" else None)
    template = args.command or cfg.get("command")
    gap = float(sb.get("gap_seconds", 0.6))
    for tool in ("ffprobe",) + (("ffmpeg",) if provider == "say" else ()):
        if not shutil.which(tool):
            print(f"缺少 {tool}。Mac：brew install ffmpeg；Linux：apt install ffmpeg")
            return 2
    if provider == "edge":
        try:
            import edge_tts  # noqa: F401
        except ImportError:
            print("缺少 edge-tts。请运行：pip install edge-tts；或改用 --provider say（Mac 离线）")
            return 2
    if provider == "command" and not template:
        print("provider 为 command 时，需要用 --command 或 tts.command 给出命令模板")
        return 2

    out = Path(args.out)
    (out / "audio").mkdir(parents=True, exist_ok=True)
    timings, cues, t = [], [], 0.0
    for s in sb["scenes"]:
        path = out / "audio" / f"{s['id']}.mp3"
        text = s["narration"]
        if provider == "edge":
            marks = asyncio.run(edge_synth(text, path, voice, rate))
        elif provider == "say":
            marks = say_synth(text, path, voice, rate)
        else:
            marks = command_synth(text, path, template)
        dur = ffprobe_duration(path)
        timings.append({"id": s["id"], "kind": s.get("kind"), "start": round(t, 3), "duration": round(dur, 3),
                        "audio": str(path.relative_to(out))})
        cues += cues_for_scene(text, t, dur, marks)
        print(f"  {s['id']}：{dur:.1f} 秒，{len(text)} 字（{len(text) / dur:.1f} 字/秒）")
        t += dur + gap

    total = round(t - gap, 3)
    (out / "timings.json").write_text(json.dumps({"provider": provider, "voice": voice, "gap": gap, "total": total,
                                                  "scenes": timings}, ensure_ascii=False, indent=2), encoding="utf-8")
    with open(out / "subtitles.srt", "w", encoding="utf-8") as f:
        for i, (a, b, s) in enumerate(cues, 1):
            f.write(f"{i}\n{srt_time(a)} --> {srt_time(b)}\n{s}\n\n")
    print(f"总时长约 {total:.1f} 秒。已写出 {out}/timings.json 和 {out}/subtitles.srt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
