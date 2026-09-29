#!/usr/bin/env python3
"""
dreamina_queue.py — 鲁棒的串行 image2video 生产工具

特性（2026-04-19 重构）：
- 串行提交（绕过并发限制=1）
- **幽灵任务检测**：提交后 8 秒内验证 queue_info，空则重提
- **审核失败识别**：区分内容审核 fail vs 网络 / 并发错误
- **状态持久化**：每步写 `.i2v_state.json`，脚本挂了可 `--resume` 接着跑
- **中途停滞检测**：连续 2.5 分钟无队列进度判定为幽灵，放弃
- 完成后自动下载到关键帧同目录

用法：
  # 首次运行（从 i2v_queue.json 生成状态文件并执行）
  python tools/dreamina_queue.py assets/proj/i2v_queue.json

  # 从状态文件恢复（只跑 pending/failed/ghost 的 shot）
  python tools/dreamina_queue.py --resume assets/proj/

  # 多项目串行（AC-5 → AC-6）
  python tools/dreamina_queue.py assets/einstein-selfie/i2v_queue.json assets/davinci-ipad/i2v_queue.json

  # 只看计划不执行
  python tools/dreamina_queue.py --dry-run assets/proj/i2v_queue.json

状态文件格式（项目目录下 `.i2v_state.json`）：
{
  "version": 1,
  "shots": [
    {"idx": 1, "label": "S01", "image": "...", "prompt": "...",
     "video_resolution": "1080p",
     "status": "success|pending|failed|ghost|submitted",
     "submit_id": "...", "video_file": "...",
     "attempts": N, "last_error": "...",
     "started_at": "...", "completed_at": "..."},
    ...
  ]
}
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# --- 配置 ---
DREAMINA = "dreamina"
POLL_INTERVAL = 25              # 每 25 秒 poll 一次任务状态
SUBMIT_VERIFY_DELAY = 8         # 提交后等 8 秒验证非幽灵
MAX_SUBMIT_RETRIES = 5          # 提交重试次数（幽灵 / ExceedConcurrencyLimit）
CONCURRENCY_WAIT = 90           # 撞到并发限制时等多久（秒）
NO_QUEUE_TIMEOUT_POLLS = 6      # 连续 N 次无 queue_info 判定为幽灵（6*25s = 2.5min）
STATE_FILE_NAME = ".i2v_state.json"


# ================= 底层 CLI =================

def run_dreamina(args: list, timeout: int = 60) -> Optional[dict]:
    """执行 dreamina CLI。返回解析 JSON 或 None。使用 LARK_CLI_NO_PROXY=1 避免代理超时。"""
    env = {**os.environ, "LARK_CLI_NO_PROXY": "1"}
    try:
        r = subprocess.run([DREAMINA] + args, capture_output=True,
                           text=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return None
    output = r.stdout.strip()
    if not output:
        return None
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return None


# ================= 幽灵检测 =================

def is_ghost(query_result: dict) -> bool:
    """判断一个 querying 状态是否是幽灵任务。"""
    if query_result.get("gen_status") != "querying":
        return False
    qi = query_result.get("queue_info") or {}
    # 真实任务：queue_idx > 0 或 queue_status in ["Queueing","Generating","Finish"]
    idx = qi.get("queue_idx", -1)
    status = qi.get("queue_status", "")
    if idx > 0 or status in ("Queueing", "Generating", "Finish"):
        return False
    # 无任何队列信息 = 幽灵
    return True


# ================= 提交 =================

def submit_i2v(shot: dict, verbose: bool = True) -> tuple[Optional[str], str]:
    """提交 image2video，含幽灵检测 + 并发重试。

    Returns (submit_id, status_code):
      - ("xxx", "submitted")  成功提交且非幽灵
      - (None, "censored")    内容审核 fail
      - (None, "concurrency_exhausted") 多次并发限制
      - (None, "no_response") 网络问题
      - (None, "ghost_exhausted") 多次幽灵
    """
    image = shot["image"]
    prompt = shot["prompt"]
    model = shot.get("model_version", "seedance2.0")
    duration = shot.get("duration", 5)
    video_resolution = shot.get("video_resolution", "")
    label = shot.get("_label", Path(image).stem)

    for attempt in range(1, MAX_SUBMIT_RETRIES + 1):
        if verbose:
            print(f"    [{label}] 提交 (尝试 {attempt}/{MAX_SUBMIT_RETRIES})", flush=True)

        args = ["image2video", f"--image={image}", f"--prompt={prompt}",
                f"--model_version={model}", f"--duration={duration}"]
        if video_resolution:
            args.append(f"--video_resolution={video_resolution}")
        r = run_dreamina(args)
        if not r:
            if verbose:
                print(f"    [{label}] 无响应，15s 后重试", flush=True)
            time.sleep(15)
            continue

        # 直接失败（审核 / 并发限制 / 网络）
        if r.get("gen_status") == "fail":
            fr = r.get("fail_reason", "")
            if "ExceedConcurrencyLimit" in fr:
                if verbose:
                    print(f"    [{label}] [LIMIT] 并发已满，等 {CONCURRENCY_WAIT}s", flush=True)
                time.sleep(CONCURRENCY_WAIT)
                continue
            # 网络/上游超时：重试而不是标记为 censored
            transient_markers = ["context deadline exceeded", "TLS handshake timeout",
                                  "connection reset", "no route to host", "i/o timeout",
                                  "upload image", "ApplyImageUpload"]
            if any(m in fr for m in transient_markers):
                if verbose:
                    print(f"    [{label}] [NET] 网络/上游错误，20s 后重试: {fr[:100]}", flush=True)
                time.sleep(20)
                continue
            # 其他 fail = 审核拒绝（确认性失败，不重试）
            return None, f"censored: {fr}"

        # 有 submit_id
        sid = r.get("submit_id")
        if not sid:
            if verbose:
                print(f"    [{label}] 无 submit_id 返回：{r}", flush=True)
            time.sleep(15)
            continue

        # 幽灵检测
        time.sleep(SUBMIT_VERIFY_DELAY)
        v = run_dreamina(["query_result", f"--submit_id={sid}"])
        if v and is_ghost(v):
            if verbose:
                print(f"    [{label}] [GHOST] {sid[:12]} 服务端未注册，重提", flush=True)
            time.sleep(10)
            continue
        # 非幽灵（已进队列或已完成）
        return sid, "submitted"

    return None, "exhausted"


# ================= 轮询等待 =================

def wait_for_result(sid: str, dl_dir: str, label: str = "", verbose: bool = True) -> tuple[str, str]:
    """轮询直到任务完成。返回 (status, detail)：
      - ("success", video_path)
      - ("failed", fail_reason)
      - ("ghost_midflight", "no queue info for N polls")
    """
    start = time.time()
    no_queue_count = 0

    while True:
        r = run_dreamina(["query_result", f"--submit_id={sid}"])
        if not r:
            time.sleep(POLL_INTERVAL)
            continue

        st = r.get("gen_status", "")
        elapsed = int(time.time() - start)

        if st == "success":
            # 下载
            run_dreamina(["query_result", f"--submit_id={sid}", f"--download_dir={dl_dir}"])
            videos = r.get("result_json", {}).get("videos", [])
            video_path = videos[0].get("path", "") if videos else ""
            # download 之后再 query 一次才能拿到 path
            r2 = run_dreamina(["query_result", f"--submit_id={sid}", f"--download_dir={dl_dir}"])
            if r2:
                vs = r2.get("result_json", {}).get("videos", [])
                if vs and "path" in vs[0]:
                    video_path = vs[0]["path"]
            if verbose:
                print(f"    ✅ {label} 完成 ({elapsed}s) → {Path(video_path).name if video_path else '?'}", flush=True)
            return "success", video_path

        if st == "fail":
            fr = r.get("fail_reason", "")
            if verbose:
                print(f"    ❌ {label} 失败: {fr} ({elapsed}s)", flush=True)
            return "failed", fr

        # 中途幽灵（提交时非幽灵，但跑着跑着队列信息消失）
        qi = r.get("queue_info") or {}
        idx = qi.get("queue_idx", -1)
        qs = qi.get("queue_status", "")
        if (not qi) or (idx < 1 and qs == ""):
            no_queue_count += 1
            if no_queue_count >= NO_QUEUE_TIMEOUT_POLLS:
                if verbose:
                    print(f"    [GHOST MID] {label} 连续 {no_queue_count} 次无队列信息，放弃 ({elapsed}s)", flush=True)
                return "ghost_midflight", f"no queue info for {no_queue_count} polls"
        else:
            no_queue_count = 0
            if verbose:
                if idx > 0:
                    print(f"    {label} 排队 idx={idx} ({elapsed}s)", flush=True)
                elif qs == "Generating":
                    print(f"    {label} 生成中 ({elapsed}s)", flush=True)

        time.sleep(POLL_INTERVAL)


# ================= 状态管理 =================

def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def shots_from_config(config_path: str) -> list:
    """从 i2v_queue.json 读取 shot 列表。"""
    shots = json.loads(Path(config_path).read_text())
    out = []
    for i, s in enumerate(shots):
        out.append({
            "idx": i + 1,
            "label": f"S{i+1:02d}",
            "image": s["image"],
            "prompt": s["prompt"],
            "model_version": s.get("model_version", "seedance2.0"),
            "duration": s.get("duration", 5),
            "video_resolution": s.get("video_resolution", ""),
            "status": "pending",
            "submit_id": "",
            "video_file": "",
            "attempts": 0,
            "last_error": "",
            "started_at": "",
            "completed_at": "",
        })
    return out


def state_path_for(config_or_dir: str) -> Path:
    """找到项目目录下的 .i2v_state.json。"""
    p = Path(config_or_dir)
    if p.is_file():
        return p.parent / STATE_FILE_NAME
    return p / STATE_FILE_NAME


def load_state(state_file: Path) -> Optional[dict]:
    if not state_file.exists():
        return None
    return json.loads(state_file.read_text())


def save_state(state_file: Path, state: dict):
    state["updated_at"] = now_iso()
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def ensure_state(config_path: str, resume: bool = False) -> tuple[Path, dict]:
    """返回 (state_file, state_dict)。resume=True 时要求状态文件存在。"""
    sp = state_path_for(config_path)
    existing = load_state(sp)
    if resume:
        if not existing:
            print(f"❌ --resume 模式但状态文件不存在: {sp}")
            sys.exit(1)
        return sp, existing
    # 非 resume：如果存在已完成状态，直接使用；否则从 config 初始化
    if existing:
        return sp, existing
    shots = shots_from_config(config_path)
    state = {
        "version": 1,
        "config_path": str(config_path),
        "created_at": now_iso(),
        "shots": shots,
    }
    save_state(sp, state)
    return sp, state


# ================= 主执行 =================

def needs_work(shot: dict) -> bool:
    """哪些状态需要（重新）执行。"""
    return shot["status"] in ("pending", "failed", "ghost_midflight", "ghost_exhausted", "submit_fail", "submitted")
    # 注：submitted 也要重跑——上次可能没等到结果（脚本挂了）


def process_one(shot: dict, state_file: Path, state: dict, dry_run: bool = False) -> str:
    """处理一个 shot。返回最终 status。"""
    label = f"{Path(shot['image']).parent.name} {shot['label']}"
    shot["_label"] = label

    if dry_run:
        print(f"    [DRY] 将处理: {label} status={shot['status']}", flush=True)
        return shot["status"]

    # 已经 submitted 但没 success：先 check 下之前的 sid
    if shot["status"] == "submitted" and shot["submit_id"]:
        print(f"    [{label}] 有现存 submit_id {shot['submit_id'][:12]}，先查询", flush=True)
        r = run_dreamina(["query_result", f"--submit_id={shot['submit_id']}"])
        if r:
            if r.get("gen_status") == "success":
                dl_dir = str(Path(shot["image"]).parent)
                run_dreamina(["query_result", f"--submit_id={shot['submit_id']}", f"--download_dir={dl_dir}"])
                shot["status"] = "success"
                shot["completed_at"] = now_iso()
                save_state(state_file, state)
                print(f"    ✅ {label} 原任务已完成，跳过", flush=True)
                return "success"
            if r.get("gen_status") == "fail":
                print(f"    [{label}] 原 sid 失败: {r.get('fail_reason','')[:80]}，重新提交", flush=True)
                # fall through to resubmit
            elif is_ghost(r):
                print(f"    [{label}] 原 sid 是幽灵，重提", flush=True)
                # fall through to resubmit
            else:
                # 正常在队列中 → 直接等待，不要重提
                print(f"    [{label}] 原 sid 仍在队列中，直接等待", flush=True)
                dl_dir = str(Path(shot["image"]).parent)
                final_status, detail = wait_for_result(shot["submit_id"], dl_dir, label=label)
                shot["status"] = "success" if final_status == "success" else final_status
                shot["completed_at"] = now_iso()
                if final_status == "success":
                    shot["video_file"] = detail
                else:
                    shot["last_error"] = detail
                save_state(state_file, state)
                return shot["status"]

    shot["attempts"] = shot.get("attempts", 0) + 1
    shot["started_at"] = now_iso()
    save_state(state_file, state)

    # 提交
    sid, submit_status = submit_i2v(shot)
    if not sid:
        shot["status"] = "submit_fail" if "exhausted" in submit_status else "censored"
        shot["last_error"] = submit_status
        shot["completed_at"] = now_iso()
        save_state(state_file, state)
        print(f"    ❌ {label} 提交失败: {submit_status}", flush=True)
        return shot["status"]

    shot["submit_id"] = sid
    shot["status"] = "submitted"
    save_state(state_file, state)

    # 等待
    dl_dir = str(Path(shot["image"]).parent)
    final_status, detail = wait_for_result(sid, dl_dir, label=label)
    shot["status"] = "success" if final_status == "success" else final_status
    shot["completed_at"] = now_iso()
    if final_status == "success":
        shot["video_file"] = detail
    else:
        shot["last_error"] = detail
    save_state(state_file, state)
    return shot["status"]


def run_project(config_path: str, resume: bool = False, dry_run: bool = False):
    """处理一个项目（一个 i2v_queue.json 或含 state 的目录）。"""
    state_file, state = ensure_state(config_path, resume=resume)
    print(f"\n=== 项目 {Path(config_path).parent.name if Path(config_path).is_file() else Path(config_path).name} ===")
    print(f"状态文件: {state_file}")

    # 统计
    by_status = {}
    for s in state["shots"]:
        by_status[s["status"]] = by_status.get(s["status"], 0) + 1
    print(f"现状态: {by_status}")

    for shot in state["shots"]:
        if shot["status"] == "success":
            print(f"  ✓ {shot['label']} 已成功，跳过")
            continue
        if not needs_work(shot):
            print(f"  - {shot['label']} status={shot['status']} 不需处理，跳过")
            continue
        print(f"\n  → 处理 {shot['label']}")
        process_one(shot, state_file, state, dry_run=dry_run)

    # 汇总
    print(f"\n=== 项目汇总 ===")
    final_counts = {}
    for s in state["shots"]:
        final_counts[s["status"]] = final_counts.get(s["status"], 0) + 1
    print(f"  {final_counts}")
    return state


def main():
    args = sys.argv[1:]
    if not args or "-h" in args or "--help" in args:
        print(__doc__)
        sys.exit(0)

    resume = "--resume" in args
    dry_run = "--dry-run" in args
    args = [a for a in args if not a.startswith("--")]

    for config in args:
        run_project(config, resume=resume, dry_run=dry_run)


if __name__ == "__main__":
    main()
