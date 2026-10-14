#!/usr/bin/env python3
"""核验讲解视频成片。

用法：python3 verify_video.py 成片.mp4 [--storyboard 分镜.json] [--out check/] [--every 2]

报告：
  1. 有没有视频、音频、字幕三条轨；音视频时长差多少
  2. 超过 1.5 秒的静音段（片尾除外）
  3. 每隔 N 秒抽一帧（默认 2 秒），拼成一张总览图 check/总览.png，单帧在 check/frames/
  4. 装了 faster-whisper 时，把配音转回文字，和分镜旁白逐字对比（相似度低于 0.85 时提醒）
脚本查不出画面内容对不对：总览图一定要打开看。
依赖：ffmpeg、ffprobe；可选 pip install faster-whisper。
"""
import argparse
import difflib
import json
import math
import re
import subprocess
import sys
from pathlib import Path


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def silences(path, min_len=1.5):
    p = subprocess.run(["ffmpeg", "-i", str(path), "-af", f"silencedetect=noise=-40dB:d={min_len}", "-f", "null", "-"],
                       capture_output=True, text=True)
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", p.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", p.stderr)]
    return list(zip(starts, ends + [None] * (len(starts) - len(ends))))


def strip(s):
    return re.sub(r"[\s，。！？；：、,.!?;:\"'“”‘’（）()《》「」【】\-—…]", "", s)


def main():
    ap = argparse.ArgumentParser(description="核验讲解视频")
    ap.add_argument("video")
    ap.add_argument("--storyboard")
    ap.add_argument("--out", default="check")
    ap.add_argument("--every", type=float, default=2.0, help="抽帧间隔（秒）")
    args = ap.parse_args()
    video, out = Path(args.video), Path(args.out)
    (out / "frames").mkdir(parents=True, exist_ok=True)
    problems = []

    info = probe(video)
    kinds = {s["codec_type"]: s for s in info["streams"]}
    total = float(info["format"]["duration"])
    print(f"时长 {total:.1f} 秒；轨道：{'、'.join(sorted(kinds))}")
    for k, name in (("video", "视频"), ("audio", "音频"), ("subtitle", "字幕")):
        if k not in kinds:
            problems.append(f"没有{name}轨" + ("（若字幕已烧进画面可忽略）" if k == "subtitle" else ""))
    if "video" in kinds and "audio" in kinds:
        vd = float(kinds["video"].get("duration", total))
        ad = float(kinds["audio"].get("duration", total))
        if abs(vd - ad) > 0.5:
            problems.append(f"音视频时长相差 {abs(vd - ad):.1f} 秒（视频 {vd:.1f}，音频 {ad:.1f}）")

    if "audio" in kinds:
        for a, b in silences(video):
            if b is None or b > total - 0.3:
                continue
            problems.append(f"{a:.1f}–{b:.1f} 秒静音 {b - a:.1f} 秒")

    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-vf", f"fps=1/{args.every},scale=480:-1",
                    str(out / "frames" / "%03d.png")], check=True)
    n = len(list((out / "frames").glob("*.png")))
    cols = 5
    rows = max(1, math.ceil(n / cols))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-vf",
                    f"fps=1/{args.every},scale=320:-1,tile={cols}x{rows}:padding=4:color=white",
                    "-frames:v", "1", str(out / "总览.png")], check=True)
    print(f"抽了 {n} 帧，总览图：{out / '总览.png'}")

    if args.storyboard and "audio" in kinds:
        script = "".join(s["narration"] for s in json.loads(Path(args.storyboard).read_text(encoding="utf-8"))["scenes"])
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            print("未装 faster-whisper，跳过配音转写对比（pip install faster-whisper 后可用）")
        else:
            model = WhisperModel("small", compute_type="int8")
            segs, _ = model.transcribe(str(video), language="zh")
            heard = "".join(s.text for s in segs)
            ratio = difflib.SequenceMatcher(None, strip(script), strip(heard)).ratio()
            print(f"配音转写与旁白稿的相似度：{ratio:.2f}")
            if ratio < 0.85:
                problems.append(f"配音转写与旁白稿相似度只有 {ratio:.2f}，可能有读错、漏读或多音字问题")
            (out / "转写.txt").write_text(heard, encoding="utf-8")

    if problems:
        print(f"发现 {len(problems)} 个问题：")
        for p in problems:
            print("  -", p)
    else:
        print("轨道、时长、静音检查都正常。")
    print("请打开总览图看：标题卡和总结卡在不在、中文是不是方块、文字有没有出画、画面是否跟上旁白。")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
