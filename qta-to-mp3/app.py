import os
import subprocess
import threading
import json
import webbrowser
import tempfile
import shutil
import zipfile
import io
from flask import Flask, request, jsonify, render_template, send_file

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024 * 1024  # 8 GiB

# 单用户本地工具，内存状态足够
app_state = {
    "files": [],           # 当前文件列表（每项含 path/status/output_path/message）
    "converting": False,   # 是否正在转换
    "upload_temp_dir": None,
}
state_lock = threading.Lock()


# ── 工具函数 ──────────────────────────────────────────────

def cleanup_upload_session():
    """删除上次上传的临时目录。"""
    with state_lock:
        d = app_state.get("upload_temp_dir")
        if d and os.path.isdir(d):
            shutil.rmtree(d, ignore_errors=True)
        app_state["upload_temp_dir"] = None


def scan_directory(path):
    results = []
    if not os.path.isdir(path):
        return results
    for root, _dirs, files in os.walk(path):
        for name in files:
            if name.lower().endswith(".qta"):
                full = os.path.join(root, name)
                results.append({
                    "path": full,
                    "name": name,
                    "display_path": full,
                    "status": "pending",
                    "output_path": "",
                    "message": "",
                })
    return results


def get_unique_output_path(source_path):
    base, _ = os.path.splitext(source_path)
    output = base + ".mp3"
    if not os.path.exists(output):
        return output
    counter = 1
    while True:
        output = f"{base}_copy{counter}.mp3"
        if not os.path.exists(output):
            return output
        counter += 1


def run_conversion(file_item):
    source = file_item["path"]
    try:
        output = get_unique_output_path(source)
        cmd = [
            "ffmpeg", "-y",
            "-i", source,
            "-vn",
            "-map", "0:a:0",   # 明确选第一条音频轨（AAC），跳过 apac
            "-ac", "2",
            "-b:a", "192k",
            output,
        ]
        with state_lock:
            file_item["status"] = "converting"

        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace").strip()
            print(f"FFmpeg failed for {source}:\n{stderr}")
            raise RuntimeError(stderr[-300:] if len(stderr) > 300 else stderr)

        if not os.path.isfile(output) or os.path.getsize(output) == 0:
            raise RuntimeError("输出文件为空或不存在")

        with state_lock:
            file_item["status"] = "done"
            file_item["output_path"] = output
            file_item["message"] = os.path.basename(output)

    except Exception as e:
        print(f"Error converting {source}: {e}")
        with state_lock:
            file_item["status"] = "error"
            file_item["message"] = str(e)


def conversion_worker(files):
    for f in files:
        run_conversion(f)
    with state_lock:
        app_state["converting"] = False


def _safe_path_segment(name):
    if not name:
        return ""
    s = str(name).replace("\x00", "").strip()
    s = s.replace("/", "_").replace("\\", "_")
    if s in ("", ".", ".."):
        return ""
    for bad in ':*?"<>|':
        s = s.replace(bad, "_")
    return s


def sanitize_upload_relative_path(filename):
    if not filename or not str(filename).strip():
        return "uploaded.qta"
    raw = str(filename).replace("\\", "/").strip().lstrip("/")
    parts = []
    for p in raw.split("/"):
        if p in ("", ".", ".."):
            continue
        seg = _safe_path_segment(p)
        if seg:
            parts.append(seg)
    return os.path.join(*parts) if parts else "uploaded.qta"


# ── 路由 ──────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/scan", methods=["POST"])
def api_scan():
    """手动路径扫描。"""
    data = request.json or {}
    directory = data.get("path", "").strip()
    if not directory:
        return jsonify({"error": "请输入路径"}), 400
    if not os.path.isdir(directory):
        return jsonify({"error": f"目录不存在: {directory}"}), 400

    cleanup_upload_session()
    files = scan_directory(directory)
    with state_lock:
        app_state["files"] = files
        app_state["converting"] = False
    return jsonify({"files": files})


@app.route("/api/upload", methods=["POST"])
@app.route("/api/scan-upload", methods=["POST"])
def api_upload():
    """浏览器上传文件。"""
    uploaded = request.files.getlist("files")
    if not uploaded:
        return jsonify({"error": "未收到文件"}), 400

    qta_parts = []
    for f in uploaded:
        if not f or not f.filename:
            continue
        rel = sanitize_upload_relative_path(f.filename)
        if rel.lower().endswith(".qta"):
            qta_parts.append((f, rel))

    if not qta_parts:
        return jsonify({"error": "没有找到 .qta 文件"}), 400

    cleanup_upload_session()
    upload_root = tempfile.mkdtemp(prefix="qta_upload_")

    results = []
    try:
        for f, rel in qta_parts:
            dest = os.path.join(upload_root, rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            f.save(dest)
            results.append({
                "path": dest,
                "name": os.path.basename(dest),
                "display_path": rel.replace("\\", "/"),
                "status": "pending",
                "output_path": "",
                "message": "",
            })
    except Exception as e:
        shutil.rmtree(upload_root, ignore_errors=True)
        return jsonify({"error": f"保存失败: {e}"}), 500

    with state_lock:
        app_state["files"] = results
        app_state["upload_temp_dir"] = upload_root
        app_state["converting"] = False
    return jsonify({"files": results})


@app.route("/api/convert", methods=["POST"])
def api_convert():
    """启动后台转换线程。"""
    with state_lock:
        if app_state["converting"]:
            return jsonify({"error": "转换正在进行中"}), 409
        to_convert = [f for f in app_state["files"] if f["status"] == "pending"]
        if not to_convert:
            return jsonify({"message": "没有待转换的文件"}), 200
        app_state["converting"] = True

    thread = threading.Thread(target=conversion_worker, args=(to_convert,), daemon=True)
    thread.start()
    return jsonify({"message": "started", "count": len(to_convert)})


@app.route("/api/status")
def api_status():
    """轮询接口：返回所有文件的当前状态。"""
    with state_lock:
        return jsonify({
            "converting": app_state["converting"],
            "files": [
                {
                    "path": f["path"],
                    "name": f["name"],
                    "display_path": f.get("display_path", f["path"]),
                    "status": f["status"],
                    "output_path": f.get("output_path", ""),
                    "message": f.get("message", ""),
                }
                for f in app_state["files"]
            ],
        })


@app.route("/api/download")
def api_download():
    path = request.args.get("path", "")
    if not path or not os.path.isfile(path) or not path.endswith(".mp3"):
        return jsonify({"error": "文件不存在"}), 404
    with state_lock:
        allowed = any(f.get("output_path") == path for f in app_state["files"])
    if not allowed:
        return jsonify({"error": "无权下载"}), 403
    return send_file(path, as_attachment=True, download_name=os.path.basename(path))


@app.route("/api/download-all")
def api_download_all():
    with state_lock:
        done = [
            f for f in app_state["files"]
            if f.get("status") == "done"
            and f.get("output_path")
            and os.path.isfile(f["output_path"])
        ]
    if not done:
        return jsonify({"error": "没有已完成的文件"}), 404

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in done:
            zf.write(f["output_path"], os.path.basename(f["output_path"]))
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name="converted_mp3.zip",
                     mimetype="application/zip")


if __name__ == "__main__":
    webbrowser.open("http://127.0.0.1:5001")
    app.run(debug=True, port=5001, use_reloader=False)
