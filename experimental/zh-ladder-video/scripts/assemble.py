#!/usr/bin/env python3
"""把渲染好的动画、配音和字幕合成为成片。

用法：python3 assemble.py --video 动画.mp4 --build build/ --out 成片.mp4 [--burn]

做的事：
  1. 按 build/timings.json 把各镜头配音拼成一条音轨，镜头之间插入停顿
  2. 动画比配音短时，用最后一帧补齐；比配音长时保留动画原长
  3. 把 build/subtitles.srt 作为可开关的字幕轨嵌进 MP4；加 --burn 则把字幕直接烧进画面
依赖：ffmpeg、ffprobe。
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

RATE = 48000


def run(cmd):
    subprocess.run(cmd, check=True)


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=nw=1:nk=1", str(path)], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def build_narration(build, tmp):
    t = json.loads((build / "timings.json").read_text(encoding="utf-8"))
    parts, cursor = [], 0.0
    for i, s in enumerate(t["scenes"]):
        if s["start"] > cursor + 0.01:  # 镜头之间的停顿
            sil = tmp / f"sil{i}.wav"
            run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"anullsrc=r={RATE}:cl=mono",
                 "-t", f"{s['start'] - cursor:.3f}", str(sil)])
            parts.append(sil)
        wav = tmp / f"seg{i}.wav"
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(build / s["audio"]), "-ar", str(RATE), "-ac", "1", str(wav)])
        parts.append(wav)
        cursor = s["start"] + duration(wav)
    lst = tmp / "list.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
    narration = tmp / "narration.wav"
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(narration)])
    return narration


def main():
    ap = argparse.ArgumentParser(description="合成动画、配音和字幕")
    ap.add_argument("--video", required=True)
    ap.add_argument("--build", default="build")
    ap.add_argument("--out", default="成片.mp4")
    ap.add_argument("--burn", action="store_true", help="把字幕烧进画面（需要 ffmpeg 带 libass）")
    ap.add_argument("--font", default="PingFang SC", help="烧字幕用的字体，Linux 上可用 Noto Sans CJK SC")
    args = ap.parse_args()
    build, video, out = Path(args.build), Path(args.video), Path(args.out)
    srt = build / "subtitles.srt"

    with tempfile.TemporaryDirectory() as d:
        narration = build_narration(build, Path(d))
        va, aa = duration(video), duration(narration)
        vf = []
        if aa > va + 0.05:
            vf.append(f"tpad=stop_mode=clone:stop_duration={aa - va + 0.05:.2f}")
            print(f"动画 {va:.1f} 秒，比配音 {aa:.1f} 秒短，已用最后一帧补齐。动画最好按 timings.json 重新对齐。")
        elif va > aa + 1:
            print(f"动画 {va:.1f} 秒，比配音 {aa:.1f} 秒长 {va - aa:.1f} 秒，结尾会是无声画面。")
        if args.burn:
            style = f"FontName={args.font},FontSize=18,Outline=1,MarginV=28"
            vf.append(f"subtitles={srt.as_posix()}:force_style='{style}'")
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-i", str(narration)]
        if not args.burn:
            cmd += ["-i", str(srt)]
        cmd += ["-map", "0:v:0", "-map", "1:a:0"]
        if not args.burn:
            cmd += ["-map", "2:s:0", "-c:s", "mov_text", "-metadata:s:s:0", "language=chi"]
        if vf:
            cmd += ["-vf", ",".join(vf)]
        cmd += ["-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
                "-movflags", "+faststart", str(out)]
        run(cmd)
    print(f"已合成 {out}（{duration(out):.1f} 秒）。下一步运行 verify_video.py 核验。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
