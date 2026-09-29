#!/usr/bin/env python3
"""把 Markdown 长文灌进 MultiPost 桌面端的各平台编辑器。

依赖 MultiPost 桌面客户端（一个开源的多平台发布工具）在跑，且「设置 → 外部 API」已打开。
token 从 MultiPost 客户端的本机配置目录（~/Library/Application Support/multipost-desktop/
app-settings.json）读，也可以用 MULTIPOST_TOKEN 环境变量覆盖。

默认只灌草稿不发布（autoSubmit=false）。要真发得显式加 --submit。

各平台走不同内容通道，这是实测的结论：
    公众号  htmlContent      传 markdown 会得到零样式裸文章，所以先内联样式
    知乎    markdownContent  编辑器自己会渲染，样式反正也会被它吃掉

实测已知的坑（MultiPost 文档没写），本脚本都绕过了：
    - 公众号必须有封面否则直接 failed；知乎不要 → 缺封面时自动用 make_cover.py 生成
    - digest 参数对公众号不生效，摘要会被自动从正文开头截 64 字
      → 填完用 MCP 的 execute_script 直接写 DOM 补上
    - 「阅读原文」(source_url) MultiPost 的 API 不碰
      → 同样用 execute_script 补，见 --read-original

依赖两个相邻工具文件夹（同一个 daniel-tools 仓库下）：
    ../md-to-wechat-html/md_to_wechat_html.py   公众号 HTML 内联样式转换
    ../wechat-text-cover/make_cover.py          自动生成封面

Usage:
    python multipost_publish.py article.md --platforms zhihu,wechat
    python multipost_publish.py article.md --digest "一句话摘要" \
        --read-original https://example.com/xxx.html --brand "示例公众号"
    python multipost_publish.py article.md --platforms zhihu --dry-run
    python multipost_publish.py --list-accounts
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

TOOLS_DIR = Path(__file__).resolve().parent
SIBLING_MD_TO_WECHAT = TOOLS_DIR.parent / "md-to-wechat-html"
SIBLING_COVER_SCRIPT = TOOLS_DIR.parent / "wechat-text-cover" / "make_cover.py"

sys.path.insert(0, str(SIBLING_MD_TO_WECHAT))
try:
    from md_to_wechat_html import convert  # noqa: E402
except ImportError as e:
    print(f"缺少依赖: {e}\n"
          f"multipost-draft-filler 依赖相邻文件夹 md-to-wechat-html/md_to_wechat_html.py，"
          f"确认两个文件夹在同一层级（都在 daniel-tools/ 下）。", file=sys.stderr)
    sys.exit(1)

DEFAULT_BASE_URL = "http://127.0.0.1:19528"
SETTINGS_PATH = Path.home() / "Library/Application Support/multipost-desktop/app-settings.json"
TERMINAL_STATES = ("ready", "success", "failed", "cancelled")

# 哪些平台吃 HTML、哪些吃 markdown
HTML_PLATFORMS = {"wechat"}
COVER_REQUIRED = {"wechat"}
# 这些字段 MultiPost 的 API 管不了，只能填完再用脚本补
PATCHABLE = {"wechat"}
DYNAMIC_ONLY = {"xiaohongshu", "douyin", "shipinhao"}  # 仅作兜底，实际以 /v1/platforms 实时能力为准


def platform_capabilities(base: str, token: str) -> dict[str, list[str]]:
    """平台 → 支持的 contentType。实时查，别信写死的表（平台支持范围会变）。"""
    try:
        data = api(base, token, "/v1/platforms")
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️  查不到平台能力（{exc}），跳过校验", file=sys.stderr)
        return {}
    items = data if isinstance(data, list) else (data.get("data") or data.get("platforms") or [])
    if isinstance(items, dict):
        items = list(items.values())
    return {str(it.get("id")): list(it.get("supportedContentTypes") or [])
            for it in items if isinstance(it, dict) and it.get("id")}


def assert_supported(base: str, token: str, platforms: list[str], content_type: str) -> None:
    caps = platform_capabilities(base, token)
    if not caps:
        return
    bad = [p for p in platforms if p in caps and content_type not in caps[p]]
    if bad:
        detail = "; ".join(f"{p} 只支持 {'/'.join(caps[p]) or '(无)'}" for p in bad)
        raise SystemExit(f"{', '.join(bad)} 不支持 {content_type}。{detail}")


def load_token() -> str:
    token = os.environ.get("MULTIPOST_TOKEN")
    if token:
        return token
    if not SETTINGS_PATH.exists():
        raise SystemExit(f"找不到 {SETTINGS_PATH}，MultiPost 桌面端装了吗？")
    cfg = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    token = (cfg.get("externalApi") or {}).get("token")
    if not token:
        raise SystemExit("app-settings.json 里没有 externalApi.token，先在设置里打开外部 API")
    return token


def api(base: str, token: str, path: str, method: str = "GET",
        payload: dict[str, Any] | None = None) -> Any:
    headers = {"Authorization": f"Bearer {token}"}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body.strip() else None
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        raise SystemExit(f"API {method} {path} 失败 [{e.code}]: {detail}") from e
    except urllib.error.URLError as e:
        raise SystemExit(f"连不上 {base}，MultiPost 桌面端在跑吗？({e.reason})") from e


class McpClient:
    """MultiPost 的 execute_script 只在 MCP 上有，REST 没有这条路（实测 404）。
    所以补字段得走 MCP 的 Streamable HTTP。"""

    def __init__(self, base: str, token: str) -> None:
        self.url = f"{base}/mcp"
        self.token = token
        self.session_id: str | None = None

    def _post(self, body: dict[str, Any], notify: bool = False) -> Any:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.session_id:
            headers["mcp-session-id"] = self.session_id
        req = urllib.request.Request(self.url, data=json.dumps(body).encode("utf-8"),
                                     headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            if self.session_id is None:
                self.session_id = resp.headers.get("mcp-session-id")
            raw = resp.read().decode("utf-8")
        if notify or not raw.strip():
            return None
        for line in raw.splitlines():          # Streamable HTTP 会包成 SSE
            if line.startswith("data: "):
                raw = line[6:]
                break
        return json.loads(raw)

    def connect(self) -> None:
        self._post({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                               "clientInfo": {"name": "multipost_publish", "version": "1"}}})
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"}, notify=True)

    def call(self, name: str, args: dict[str, Any]) -> str:
        r = self._post({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                        "params": {"name": name, "arguments": args}})
        if "error" in r:
            raise RuntimeError(f"MCP {name} 失败: {r['error']}")
        parts = [c["text"] for c in r.get("result", {}).get("content", [])
                 if c.get("type") == "text"]
        return "\n".join(parts)


# 公众号的摘要和阅读原文是 React 受控组件，得用原生 setter 再派发事件，
# 直接改 .value 会被框架冲掉。
PATCH_JS = r"""
(() => {
  const setNative = (el, val) => {
    const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype
                                            : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, val);
    el.dispatchEvent(new Event('input', {bubbles: true}));
    el.dispatchEvent(new Event('change', {bubbles: true}));
    el.dispatchEvent(new Event('blur', {bubbles: true}));
  };
  const out = {};
  const DIGEST = __DIGEST__;
  const SRC = __SRC__;

  if (DIGEST !== null) {
    const dg = document.querySelector('#js_description');
    if (dg) { setNative(dg, DIGEST); out.digest = dg.value; }
    else out.digest = '(没找到摘要框)';
  }
  if (SRC !== null) {
    const s = document.querySelector('input[name="source_url"]');
    if (s) { setNative(s, SRC); out.sourceUrl = s.value; }
    else out.sourceUrl = '(没找到阅读原文框)';
  }
  return JSON.stringify(out);
})()
"""


def patch_wechat_fields(mcp: McpClient, group_id: str, account_id: str,
                        digest: str | None, read_original: str | None) -> dict[str, Any]:
    js = (PATCH_JS
          .replace("__DIGEST__", json.dumps(digest, ensure_ascii=False) if digest else "null")
          .replace("__SRC__", json.dumps(read_original) if read_original else "null"))
    raw = mcp.call("execute_group_script",
                   {"groupId": group_id, "accountId": account_id, "script": js})
    try:
        return json.loads(json.loads(raw) if raw.startswith('"') else raw)
    except (json.JSONDecodeError, TypeError):
        return {"raw": raw[:200]}


def generate_cover(title: str, kicker: str, brand: str, theme: str, out: Path) -> Path:
    if not SIBLING_COVER_SCRIPT.exists():
        raise SystemExit(
            f"找不到 {SIBLING_COVER_SCRIPT}。multipost-draft-filler 依赖相邻文件夹 "
            f"wechat-text-cover/make_cover.py 自动生成封面，确认两个文件夹在同一层级，"
            f"或用 --cover 自己传一张、--no-auto-cover 跳过自动生成。"
        )
    cmd = [sys.executable, str(SIBLING_COVER_SCRIPT), "--title", title,
           "--theme", theme, "-o", str(out)]
    if kicker:
        cmd += ["--kicker", kicker]
    if brand:
        cmd += ["--brand", brand]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"封面生成失败:\n{proc.stderr}")
    return out


def list_accounts(base: str, token: str) -> list[dict[str, Any]]:
    data = api(base, token, "/v1/accounts")
    return data.get("accounts", []) if isinstance(data, dict) else (data or [])


def resolve_accounts(base: str, token: str, platforms: list[str]) -> dict[str, dict[str, Any]]:
    """平台名 → 账号。只认已登录且 active 的。"""
    accounts = list_accounts(base, token)
    by_platform = {a["platform"]: a for a in accounts
                    if a.get("isLoggedIn") or (a.get("health") or {}).get("state") == "active"}
    resolved: dict[str, dict[str, Any]] = {}
    for p in platforms:
        acc = by_platform.get(p)
        if acc is None:
            avail = ", ".join(sorted(by_platform)) or "(一个都没登录)"
            raise SystemExit(f"平台 {p} 没有已登录账号。当前可用: {avail}")
        state = (acc.get("health") or {}).get("state")
        if state and state != "active":
            print(f"⚠️  {p} 账号状态是 {state}，可能要重新登录", file=sys.stderr)
        resolved[p] = acc
    return resolved


def split_title_body(md_text: str) -> tuple[str, str]:
    text = md_text.strip()
    fm_title = ""
    m = re.match(r"^---\s*\n.*?\n---\s*\n", text, re.DOTALL)
    if m:
        tm = re.search(r"^title:\s*[\"']?(.+?)[\"']?\s*$", m.group(0), re.MULTILINE)
        if tm:
            fm_title = tm.group(1).strip()
        text = text[m.end():].strip()
    lines = text.split("\n")
    if lines and lines[0].startswith("# "):
        return lines[0][2:].strip(), "\n".join(lines[1:]).strip()
    return fm_title, text


def extract_tags(text: str) -> list[str]:
    return re.findall(r"#([\w一-鿿]+)", text)


TAG_LINE_RE = re.compile(r"^\s*(#[\w一-鿿]+\s*)+$")
# 这些平台的话题由专门脚本做成真正的话题标签，不在本仓库范围内（自己按平台补一个）；
# 把 tags 交给适配器只会多出一份纯文本。
TOPICS_BY_SCRIPT = {"douyin": "mp_douyin_topics.py"}


def split_tag_lines(text: str) -> tuple[str, list[str]]:
    """把只含 #标签 的行从正文里拿掉，标签单独返回。

    正文里留着标签行、同时又把标签交给适配器，平台上会出现两份重复标签。
    """
    kept, tags = [], []
    for line in text.split("\n"):
        if TAG_LINE_RE.match(line):
            tags += [t for t in extract_tags(line) if t not in tags]
        else:
            kept.append(line)
    return "\n".join(kept).strip(), tags


def prepare_text(args: argparse.Namespace, body: str,
                 platforms: list[str]) -> tuple[str, list[str], list[str]]:
    """返回 (正文, 交给适配器的 tags, 全部标签)。标签在平台上只出现一次。"""
    _, tags = split_tag_lines(body)
    raw = args.content if args.content else md_to_plaintext(body)
    content, extra = split_tag_lines(raw)
    tags += [t for t in extra if t not in tags]

    scripted = [p for p in platforms if p in TOPICS_BY_SCRIPT]
    if scripted and len(platforms) > 1:
        raise SystemExit(f"{', '.join(scripted)} 的话题要单独加，请把它单独放一组发")
    payload_tags = [] if scripted else tags
    return content, payload_tags, tags


def print_tags(platforms: list[str], payload_tags: list[str], all_tags: list[str]) -> None:
    if not all_tags:
        return
    shown = " ".join("#" + t for t in all_tags)
    if payload_tags:
        print(f"标签: {shown}（正文里已去掉标签行，只交给平台一次）")
        return
    script = TOPICS_BY_SCRIPT[platforms[0]]
    print(f"标签: {shown}（不交给适配器，正文里也没有）")
    print(f"  ⚠️  灌完需要自己找一个 {script} 之类的脚本另外加话题（不在本仓库里）")


def md_to_plaintext(md: str) -> str:
    lines = []
    for line in md.split("\n"):
        s = line.strip()
        s = re.sub(r"^#{1,6}\s+", "", s)
        s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
        s = re.sub(r"\*(.+?)\*", r"\1", s)
        s = re.sub(r"`(.+?)`", r"\1", s)
        s = re.sub(r"^[-*]\s+", "", s)
        s = re.sub(r"^\d+\.\s+", "", s)
        s = re.sub(r"^>\s+", "", s)
        if re.match(r"^---+$", s):
            continue
        lines.append(s)
    return "\n".join(lines).strip()


def build_payload(platform: str, md_body: str, title: str, digest: str,
                  cover: str | None, theme: str, link_mode: str,
                  tags: list[str]) -> dict[str, Any]:
    data: dict[str, Any] = {"title": title, "digest": digest, "tags": tags}
    if cover:
        data["cover"] = cover
    if platform in HTML_PLATFORMS:
        data["htmlContent"] = convert(md_body, theme_name=theme, link_mode=link_mode)["html"]
    else:
        data["markdownContent"] = md_body
    return data


def build_dynamic_payload(title: str, content: str, images: list[str],
                          tags: list[str]) -> dict[str, Any]:
    data: dict[str, Any] = {"content": content}
    if title:
        data["title"] = title
    if images:
        data["images"] = images
    if tags:
        data["tags"] = tags
    return data


def build_video_payload(title: str, content: str, video: str,
                        cover: str | None, tags: list[str]) -> dict[str, Any]:
    """VIDEO 通道。MultiPost 校验（app.asar zod）：title 必填非空，video 必填，content/cover/tags 可选。"""
    data: dict[str, Any] = {"title": title, "video": video}
    if content:
        data["content"] = content
    if cover:
        data["cover"] = cover
    if tags:
        data["tags"] = tags
    return data


def poll(base: str, token: str, group_id: str, timeout_s: int = 120) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    last: dict[str, Any] = {}
    while time.time() < deadline:
        last = api(base, token, f"/v1/publish/{group_id}")
        targets = last.get("targets", [])
        line = "  ".join(
            f"{t['platform']}={t['status']}" + (f" ({t['error']})" if t.get("error") else "")
            for t in targets
        )
        print(f"  [{last.get('status')}] {line}", flush=True)
        if targets and all(t["status"] in TERMINAL_STATES for t in targets):
            return last
        time.sleep(5)
    print("  ⚠️  轮询超时", file=sys.stderr)
    return last


def cmd_publish_dynamic(args: argparse.Namespace) -> int:
    base, token = args.base_url, load_token()
    platforms = [p.strip() for p in args.platforms.split(",") if p.strip()]

    md_text = Path(args.md).read_text(encoding="utf-8")
    h1_title, body = split_title_body(md_text)
    title = args.title or h1_title or ""

    content, tags, all_tags = prepare_text(args, body, platforms)

    images: list[str] = []
    if args.images:
        for img in args.images.split(","):
            p = Path(img.strip()).resolve()
            if not p.exists():
                raise SystemExit(f"图片不存在: {p}")
            images.append(str(p))

    accounts = resolve_accounts(base, token, platforms)
    data = build_dynamic_payload(title, content, images, tags)

    print(f"类型: DYNAMIC")
    print(f"标题: {title or '(无)'}")
    print(f"正文: {len(content)} 字符")
    print(f"图片: {len(images)} 张")
    print_tags(platforms, tags, all_tags)
    targets = ", ".join(f"{p} → {accounts[p].get('displayName')}" for p in platforms)
    print(f"目标: {targets}")
    submit_label = "是 (--submit)" if args.submit else "否，只灌草稿"
    print(f"提交: {submit_label}")
    print()

    if args.dry_run:
        print("--- DYNAMIC 预览 ---")
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    req = {
        "contentType": "DYNAMIC",
        "accountIds": [accounts[p]["id"] for p in platforms],
        "data": data,
        "autoSubmit": bool(args.submit),
    }
    resp = api(base, token, "/v1/publish", "POST", req)
    gid = resp["groupId"]
    print(f"groupId: {gid}")
    final = poll(base, token, gid, args.timeout)

    failed = any(t["status"] == "failed" for t in final.get("targets", []))

    if not args.submit:
        print("草稿已灌好，没有发布。去 MultiPost 里核对，确认无误再发。")
    return 1 if failed else 0


def cmd_publish_video(args: argparse.Namespace) -> int:
    base, token = args.base_url, load_token()
    platforms = [p.strip() for p in args.platforms.split(",") if p.strip()]
    assert_supported(base, token, platforms, "VIDEO")

    md_text = Path(args.md).read_text(encoding="utf-8")
    h1_title, body = split_title_body(md_text)
    title = args.title or h1_title or ""
    if not title.strip():
        raise SystemExit("VIDEO 模式必须有标题：给 --title，或在 md 里写 H1")

    content, tags, all_tags = prepare_text(args, body, platforms)

    if not args.video:
        raise SystemExit("VIDEO 模式要 --video <视频路径>")
    vp = Path(args.video).expanduser().resolve()
    if not vp.exists():
        raise SystemExit(f"视频不存在: {vp}")
    video = str(vp)

    cover = None
    if args.cover:
        cp = Path(args.cover).expanduser().resolve()
        if not cp.exists():
            raise SystemExit(f"封面不存在: {cp}")
        cover = str(cp)

    accounts = resolve_accounts(base, token, platforms)
    data = build_video_payload(title, content, video, cover, tags)

    size_mb = vp.stat().st_size / 1024 / 1024
    print("类型: VIDEO")
    print(f"标题: {title}  ({len(title)} 字)")
    print(f"正文: {len(content)} 字符")
    print(f"视频: {video}  ({size_mb:.1f} MB)")
    print(f"封面: {cover or '(不传，用视频首帧)'}")
    print_tags(platforms, tags, all_tags)
    targets = ", ".join(f"{p} → {accounts[p].get('displayName')}" for p in platforms)
    print(f"目标: {targets}")
    print(f"提交: {'是 (--submit)' if args.submit else '否，只灌草稿'}")
    print()

    if args.dry_run:
        print("--- VIDEO 预览 ---")
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    req = {
        "contentType": "VIDEO",
        "accountIds": [accounts[p]["id"] for p in platforms],
        "data": data,
        "autoSubmit": bool(args.submit),
    }
    resp = api(base, token, "/v1/publish", "POST", req)
    gid = resp["groupId"]
    print(f"groupId: {gid}")
    final = poll(base, token, gid, args.timeout)

    failed = any(t["status"] == "failed" for t in final.get("targets", []))
    if not args.submit:
        print("草稿已灌好，没有发布。去 MultiPost 里核对视频、标题、正文，确认无误再发。")
    return 1 if failed else 0


def cmd_publish(args: argparse.Namespace) -> int:
    base, token = args.base_url, load_token()
    platforms = [p.strip() for p in args.platforms.split(",") if p.strip()]

    if args.content_type == "ARTICLE":
        bad = [p for p in platforms if p in DYNAMIC_ONLY]
        if bad:
            raise SystemExit(
                f"{', '.join(bad)} 不支持 ARTICLE，用 --content-type DYNAMIC")

    if args.content_type == "VIDEO":
        return cmd_publish_video(args)

    if args.content_type == "DYNAMIC":
        return cmd_publish_dynamic(args)

    md_text = Path(args.md).read_text(encoding="utf-8")
    h1_title, body = split_title_body(md_text)
    title = args.title or h1_title
    if not title:
        raise SystemExit("没有标题：文件首行不是 # 标题，也没给 --title")
    cover_title = args.cover_title or title

    digest = args.digest or ""
    cover = str(Path(args.cover).resolve()) if args.cover else None

    # 公众号缺封面会直接 failed，没给就自己画一张，省得来回
    needs_cover = any(p in COVER_REQUIRED for p in platforms)
    if needs_cover and not cover and not args.no_auto_cover:
        out = Path(args.cover_out) if args.cover_out else \
            Path(tempfile.gettempdir()) / f"mp_cover_{abs(hash(cover_title)) % 10**8}.png"
        cover = str(generate_cover(cover_title, args.kicker, args.brand, args.cover_theme, out).resolve())
        print(f"自动生成封面: {cover}")

    missing_cover = [p for p in platforms if p in COVER_REQUIRED and not cover]
    if missing_cover:
        raise SystemExit(f"{', '.join(missing_cover)} 必须有封面，给 --cover 或别用 --no-auto-cover")

    accounts = resolve_accounts(base, token, platforms)

    # 内容通道不同的平台不能塞进同一个发布组，按通道分开建
    groups: dict[str, list[str]] = {}
    for p in platforms:
        groups.setdefault("html" if p in HTML_PLATFORMS else "markdown", []).append(p)

    print(f"平台标题: {title}")
    if cover_title != title:
        print(f"封面标题: {cover_title}")
    print(f"正文: {len(body)} 字符")
    print(f"封面: {cover or '(无)'}")
    print(f"目标: {', '.join(f'{p} → {accounts[p].get('displayName')}' for p in platforms)}")
    print(f"提交: {'是 (--submit)' if args.submit else '否，只灌草稿'}")
    print()

    if args.dry_run:
        for channel, ps in groups.items():
            data = build_payload(ps[0], body, title, digest, cover, args.theme, args.link_mode, [])
            key = "htmlContent" if channel == "html" else "markdownContent"
            print(f"--- {channel} 通道 ({', '.join(ps)}) ---")
            print(f"{key}: {len(data[key])} 字符")
            print(data[key][:400] + ("..." if len(data[key]) > 400 else ""))
            print()
        return 0

    failed = False
    for channel, ps in groups.items():
        data = build_payload(ps[0], body, title, digest, cover, args.theme, args.link_mode, [])
        req = {
            "contentType": "ARTICLE",
            "accountIds": [accounts[p]["id"] for p in ps],
            "data": data,
            "autoSubmit": bool(args.submit),
        }
        print(f"=== {channel} 通道: {', '.join(ps)} ===")
        resp = api(base, token, "/v1/publish", "POST", req)
        gid = resp["groupId"]
        print(f"  groupId: {gid}")
        final = poll(base, token, gid, args.timeout)
        for t in final.get("targets", []):
            if t["status"] == "failed":
                failed = True

        # API 管不到的字段，等填充完再用脚本补
        if digest or args.read_original:
            for p in ps:
                if p not in PATCHABLE:
                    continue
                ready = any(t["status"] == "ready" and t["accountId"] == accounts[p]["id"]
                            for t in final.get("targets", []))
                if not ready:
                    print(f"  ⚠️  {p} 没到 ready，跳过补字段")
                    continue
                mcp = McpClient(base, token)
                mcp.connect()
                got = patch_wechat_fields(mcp, gid, accounts[p]["id"],
                                          digest or None, args.read_original)
                for k, v in got.items():
                    print(f"  已补 {k}: {str(v)[:60]}")
        print()

    if not args.submit:
        print("草稿已灌好，没有发布。去 MultiPost 里核对，确认无误再发。")
    return 1 if failed else 0


def cmd_list_accounts(args: argparse.Namespace) -> int:
    accounts = list_accounts(args.base_url, load_token())
    if not accounts:
        print("一个账号都没登录。打开 MultiPost 桌面端登录。")
        return 1
    print(f"{'平台':<16} {'昵称':<20} {'状态':<10} id")
    for a in accounts:
        state = (a.get("health") or {}).get("state", "?")
        print(f"{a['platform']:<16} {str(a.get('displayName') or ''):<20} {state:<10} {a['id']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="把 Markdown 灌进 MultiPost 各平台编辑器")
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL)
    ap.add_argument("--list-accounts", action="store_true", help="列出已登录账号后退出")
    ap.add_argument("md", nargs="?", help="Markdown 文件")
    ap.add_argument("--content-type", default="ARTICLE", choices=("ARTICLE", "DYNAMIC", "VIDEO"),
                    help="内容类型。图文动态用 DYNAMIC，发视频用 VIDEO")
    ap.add_argument("--platforms", default="zhihu,wechat", help="逗号分隔，默认 zhihu,wechat")
    ap.add_argument("--title", help="平台文章标题，默认取正文首个 H1")
    ap.add_argument("--images",
                    help="DYNAMIC 模式的图片路径，逗号分隔（绝对路径）")
    ap.add_argument("--content",
                    help="DYNAMIC/VIDEO 模式的正文文本。不给则从 md 文件提取纯文本")
    ap.add_argument("--video", help="VIDEO 模式的视频文件路径（绝对路径）")
    ap.add_argument("--cover-title", help="封面标题，默认与 --title 相同；想让封面短一点而平台标题保留完整时给它")
    ap.add_argument("--digest", default="",
                    help="摘要。公众号的 API 参数不生效，脚本会填完再用 DOM 补上")
    ap.add_argument("--read-original", help="公众号「阅读原文」链接，同样靠 DOM 补")
    ap.add_argument("--cover", help="封面图路径。VIDEO 模式不给则用视频首帧；目标含公众号时自动生成")
    ap.add_argument("--no-auto-cover", action="store_true", help="不自动生成封面")
    ap.add_argument("--cover-out", help="自动生成的封面存哪，默认扔临时目录")
    ap.add_argument("--cover-theme", default="plain", choices=("plain", "dark"), help="封面主题")
    ap.add_argument("--kicker", default="", help="封面上方小字，比如栏目名")
    ap.add_argument("--brand", default="", help="封面落款，比如公众号名")
    ap.add_argument("--theme", default="plain", help="公众号正文样式主题")
    ap.add_argument("--link-mode", default="footnote", choices=("footnote", "inline", "keep"),
                    help="公众号链接处理，默认转脚注")
    ap.add_argument("--timeout", type=int, default=120, help="每组轮询超时秒数")
    ap.add_argument("--dry-run", action="store_true", help="只打印将要发送的内容，不调接口")
    ap.add_argument("--submit", action="store_true",
                    help="灌完直接发布。默认关闭，别轻易开")
    args = ap.parse_args()

    if args.list_accounts:
        return cmd_list_accounts(args)
    if not args.md:
        ap.error("要么给 Markdown 文件，要么用 --list-accounts")
    return cmd_publish(args)


if __name__ == "__main__":
    raise SystemExit(main())
