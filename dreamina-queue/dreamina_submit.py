#!/usr/bin/env python3
"""
dreamina_submit.py — 可靠的 Dreamina 批量提交工具

解决 dreamina CLI 的三个生产缺陷：
1. 提交后不验证任务是否真正进入服务端队列
2. query_result 对幽灵任务返回 "querying" 而非 "not found"
3. list_task 读本地缓存，不反映服务端真实状态

用法：
  python dreamina_submit.py config.json

config.json 格式：
[
  {
    "image": "path/to/image.png",
    "prompt": "generation prompt",
    "model_version": "seedance2.0",    # 可选，默认 seedance2.0
    "duration": 5                       # 可选，默认 5
  },
  ...
]

每条任务提交后会：
1. 等待 3 秒让服务端注册
2. query_result 检查是否真正进入队列（queue_idx > 0 或已完成）
3. 如果检测到幽灵任务（querying 但无 queue_info），自动重试最多 2 次
4. 输出汇总报告
"""

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, List


DREAMINA = "dreamina"
MAX_RETRIES = 2
VERIFY_DELAY = 3  # 提交后等待验证的秒数


def run_dreamina(args: List[str]) -> Optional[dict]:
    """执行 dreamina CLI 命令，返回解析后的 JSON 或 None。"""
    cmd = [DREAMINA] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    output = result.stdout.strip()
    if not output:
        return None
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        print(f"  [WARN] 非 JSON 输出: {output[:200]}", file=sys.stderr)
        return None


def submit_one(image: str, prompt: str, model_version: str = "seedance2.0",
               duration: int = 5) -> Optional[str]:
    """提交单条 image2video 任务，返回 submit_id 或 None。"""
    args = [
        "image2video",
        f"--image={image}",
        f"--prompt={prompt}",
        f"--model_version={model_version}",
        f"--duration={duration}",
    ]
    result = run_dreamina(args)
    if result and "submit_id" in result:
        return result["submit_id"]
    print(f"  [FAIL] 提交失败: {result}", file=sys.stderr)
    return None


def verify_task(submit_id: str) -> dict:
    """查询任务状态，返回结构化结果。"""
    result = run_dreamina(["query_result", f"--submit_id={submit_id}"])
    if not result:
        return {"status": "no_response", "verified": False}

    status = result.get("gen_status", "unknown")
    queue_info = result.get("queue_info", {})
    queue_idx = queue_info.get("queue_idx", -1)
    queue_status = queue_info.get("queue_status", "")

    # 判断是否为幽灵任务
    if status == "querying" and not queue_info:
        return {"status": "ghost", "verified": False, "raw": result}

    if status == "querying" and queue_idx == 0 and queue_status == "":
        return {"status": "ghost", "verified": False, "raw": result}

    if status == "success":
        return {"status": "success", "verified": True, "raw": result}

    if status == "fail":
        reason = result.get("fail_reason", "unknown")
        return {"status": "fail", "verified": True, "reason": reason, "raw": result}

    if status == "querying" and (queue_idx > 0 or queue_status == "Queueing"):
        return {
            "status": "queued",
            "verified": True,
            "queue_idx": queue_idx,
            "queue_length": queue_info.get("queue_length", 0),
            "raw": result,
        }

    # 其他情况保守判断
    return {"status": status, "verified": bool(queue_info), "raw": result}


def submit_and_verify(shot: dict, shot_num: int) -> dict:
    """提交 + 验证，失败自动重试。"""
    image = shot["image"]
    prompt = shot["prompt"]
    model_version = shot.get("model_version", "seedance2.0")
    duration = shot.get("duration", 5)

    for attempt in range(1, MAX_RETRIES + 2):  # 1 次初始 + MAX_RETRIES 次重试
        prefix = f"  Shot {shot_num}" + (f" (重试 {attempt-1})" if attempt > 1 else "")

        # 提交
        print(f"{prefix}: 提交中...")
        submit_id = submit_one(image, prompt, model_version, duration)
        if not submit_id:
            print(f"{prefix}: 提交无返回，跳过")
            if attempt <= MAX_RETRIES:
                continue
            return {"shot": shot_num, "status": "submit_failed"}

        print(f"{prefix}: submit_id={submit_id}，等待 {VERIFY_DELAY}s 验证...")
        time.sleep(VERIFY_DELAY)

        # 验证
        check = verify_task(submit_id)
        print(f"{prefix}: 验证结果={check['status']} verified={check['verified']}")

        if check["verified"]:
            return {
                "shot": shot_num,
                "submit_id": submit_id,
                "status": check["status"],
                "detail": check,
            }

        # 幽灵任务，重试
        if attempt <= MAX_RETRIES:
            print(f"{prefix}: 检测到幽灵任务，将重试")
        else:
            print(f"{prefix}: 重试 {MAX_RETRIES} 次后仍为幽灵任务")
            return {
                "shot": shot_num,
                "submit_id": submit_id,
                "status": "ghost",
                "detail": check,
            }

    return {"shot": shot_num, "status": "unknown"}


def main():
    if len(sys.argv) < 2:
        print("用法: python dreamina_submit.py config.json")
        sys.exit(1)

    config_path = Path(sys.argv[1])
    shots = json.loads(config_path.read_text())

    print(f"共 {len(shots)} 条任务\n")

    results = []
    for i, shot in enumerate(shots, 1):
        result = submit_and_verify(shot, i)
        results.append(result)
        print()

    # 汇总
    print("=" * 60)
    print("汇总报告")
    print("=" * 60)

    success = [r for r in results if r["status"] in ("success", "queued")]
    failed = [r for r in results if r["status"] == "fail"]
    ghosts = [r for r in results if r["status"] == "ghost"]
    errors = [r for r in results if r["status"] in ("submit_failed", "unknown")]

    print(f"  成功/排队: {len(success)}")
    print(f"  审核失败:  {len(failed)}")
    print(f"  幽灵任务:  {len(ghosts)}")
    print(f"  提交错误:  {len(errors)}")

    for r in results:
        sid = r.get("submit_id", "N/A")[:12]
        print(f"  Shot {r['shot']}: {r['status']:15} | {sid}")

    # 写出结果
    output_path = config_path.with_suffix(".result.json")
    output_path.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\n结果已写入: {output_path}")


if __name__ == "__main__":
    main()
