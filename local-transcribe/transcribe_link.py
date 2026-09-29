#!/usr/bin/env python3
"""丢一条链接（或本地音视频），出一份本地转写稿。全程本机、免费。

    python3 transcribe_link.py <小宇宙单集链接 | B站/YouTube 链接 | 音频直链 | 本地文件>
        [--context "热词 空格分隔"] [--out ./transcripts] [--keep-audio] [--max-seconds N]

链路：取音频 → ffmpeg 转 16k 单声道 → mlx-qwen3-asr（Qwen3-ASR-1.7B）→ 带出处头的 markdown。
只依赖标准库 + 本机已装的 ffmpeg / yt-dlp / mlx-qwen3-asr。
"""
import argparse
import datetime
import html
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ASR_BIN = os.environ.get("QWEN_ASR_BIN") or shutil.which("mlx-qwen3-asr") or "mlx-qwen3-asr"
MODEL = os.environ.get("QWEN_ASR_MODEL", "Qwen/Qwen3-ASR-1.7B")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126 Safari/537.36"
AUDIO_EXT = (".mp3", ".m4a", ".wav", ".aac", ".flac", ".ogg", ".mp4", ".mov", ".mkv", ".webm")


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def download(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f, length=1 << 20)


def slugify(s: str, n: int = 40) -> str:
    s = re.sub(r"[^\w\u4e00-\u9fff]+", "-", s).strip("-")
    return s[:n].strip("-") or "untitled"


def resolve_xiaoyuzhou(url: str) -> dict:
    """小宇宙单集页源码里的 __NEXT_DATA__ 自带音频直链和 show notes，不用播放、不用插件。"""
    page = fetch(url.split("?")[0]).decode("utf-8", "ignore")
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', page, re.S)
    if not m:
        raise SystemExit("小宇宙页面里没找到 __NEXT_DATA__，页面结构可能改了")
    ep = json.loads(m.group(1))["props"]["pageProps"]["episode"]
    audio = (ep.get("enclosure") or {}).get("url") or (ep.get("media") or {}).get("source", {}).get("url")
    if not audio:
        hit = re.search(r'https://media\.xyzcdn\.net/[^"\\]+\.(?:mp3|m4a)', page)
        audio = hit.group(0) if hit else None
    if not audio:
        raise SystemExit("没拿到音频直链（付费单集？）")
    notes = re.sub(r"<[^>]+>", "\n", ep.get("shownotes") or ep.get("description") or "")
    notes = html.unescape(re.sub(r"\n\s*\n+", "\n", notes)).strip()
    return {
        "title": ep.get("title") or "untitled",
        "podcast": (ep.get("podcast") or {}).get("title", ""),
        "pub_date": (ep.get("pubDate") or "")[:10],
        "audio_url": audio,
        "notes": notes,
    }


def resolve(src: str, work: Path) -> dict:
    """返回 {title, audio_path, source, notes...}；音频落在 work/ 下。"""
    if os.path.exists(src):
        p = Path(src)
        return {"title": p.stem, "audio_path": p, "source": str(p), "notes": "", "local": True}
    if "xiaoyuzhoufm.com/episode/" in src:
        meta = resolve_xiaoyuzhou(src)
        ext = os.path.splitext(meta["audio_url"].split("?")[0])[1] or ".mp3"
        meta["audio_path"] = work / f"source{ext}"
        download(meta["audio_url"], meta["audio_path"])
        meta["source"] = src.split("?")[0]
        return meta
    if src.split("?")[0].lower().endswith(AUDIO_EXT):
        ext = os.path.splitext(src.split("?")[0])[1]
        dest = work / f"source{ext}"
        download(src, dest)
        return {"title": Path(src.split("?")[0]).stem, "audio_path": dest, "source": src, "notes": ""}
    # 其余交给 yt-dlp（B站 / YouTube 等）
    ytdlp = shutil.which("yt-dlp") or "yt-dlp"
    info = json.loads(subprocess.run([ytdlp, "-J", "--no-playlist", src], check=True, capture_output=True, text=True).stdout)
    subprocess.run([ytdlp, "-f", "bestaudio/best", "--no-playlist", "-o", str(work / "source.%(ext)s"), src], check=True)
    audio = next(p for p in work.iterdir() if p.name.startswith("source."))
    return {
        "title": info.get("title") or "untitled",
        "podcast": info.get("uploader") or "",
        "pub_date": (info.get("upload_date") or "")[:8],
        "audio_path": audio,
        "source": info.get("webpage_url") or src,
        "notes": (info.get("description") or "").strip(),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", help="小宇宙/B站/YouTube 链接、音频直链或本地文件")
    ap.add_argument("--context", default="", help="热词，空格分隔。写完整搭配（如「超线性学院」「具身智能」），是软偏置不是硬词表")
    ap.add_argument("--out", default=str(BASE_DIR / "transcripts"), help="成稿目录（默认 ./transcripts，建议加进 .gitignore）")
    ap.add_argument("--keep-audio", action="store_true", help="保留下载的音频和中间文件")
    ap.add_argument("--max-seconds", type=int, default=0, help="只转前 N 秒（试跑用）")
    a = ap.parse_args()

    if not shutil.which(ASR_BIN) and not os.path.exists(ASR_BIN):
        raise SystemExit(f"找不到 mlx-qwen3-asr：{ASR_BIN}\n用环境变量 QWEN_ASR_BIN 指到装了它的 venv，或确保它在 PATH 里。")

    today = datetime.date.today().isoformat()
    work = BASE_DIR / "tmp" / "transcribe_work" / f"{today}_{int(time.time())}"
    work.mkdir(parents=True, exist_ok=True)

    print("① 取音频 …", flush=True)
    meta = resolve(a.src, work)
    print(f"   {meta['title']}")

    print("② 转 16k 单声道 …", flush=True)
    wav = work / "audio_16k.wav"
    cmd = ["ffmpeg", "-loglevel", "error", "-y", "-i", str(meta["audio_path"])]
    if a.max_seconds:
        cmd += ["-t", str(a.max_seconds)]
    subprocess.run(cmd + ["-ac", "1", "-ar", "16000", str(wav)], check=True)
    dur = float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(wav)],
        check=True, capture_output=True, text=True).stdout.strip())

    print(f"③ 转写（{MODEL}，音频 {dur/60:.0f} 分钟；M1 上约 3–5 倍实时）…", flush=True)
    t0 = time.time()
    asr = [ASR_BIN, "--model", MODEL, "--language", "Chinese", "-f", "txt", "-o", str(work), str(wav)]
    if a.context.strip():
        asr[1:1] = ["--context", a.context.strip()]
    subprocess.run(asr, check=True, stdout=subprocess.DEVNULL)  # 正文只落盘，不刷屏
    took = time.time() - t0
    text = (work / "audio_16k.txt").read_text(encoding="utf-8").strip()

    out_dir = Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{today}_{slugify(meta['title'])}.md"
    head = [
        f"# {meta['title']}",
        "",
        f"- 来源：{meta['source']}",
    ]
    if meta.get("podcast"):
        head.append(f"- 节目/作者：{meta['podcast']}")
    if meta.get("pub_date"):
        head.append(f"- 发布日期：{meta['pub_date']}")
    head += [
        f"- 时长：{dur/60:.1f} 分钟" + ("（只转了开头一段）" if a.max_seconds else ""),
        f"- 转写：{MODEL}（本机 MLX），{today}，用时 {took/60:.1f} 分钟",
        f"- 热词：{a.context.strip() or '无'}",
        "- 这是机器稿：不分说话人；专名可能听错成同音字；引用原话前回听音频核对。仅自用，不外发全文。",
        "",
    ]
    if meta.get("notes"):
        head += ["## 节目方 show notes（人写的，专名以这里为准）", "", meta["notes"], ""]
    head += ["## 转写正文", "", text, ""]
    out.write_text("\n".join(head), encoding="utf-8")

    if not a.keep_audio:
        shutil.rmtree(work, ignore_errors=True)
    print(f"④ 完成：{out}  （{len(text)} 字，{took/60:.1f} 分钟，{dur/took:.1f} 倍实时）")


if __name__ == "__main__":
    sys.exit(main())
