"""
可视化图片去重工具 - 后端

风险提示：/api/execute 会真正删除或移动磁盘上的文件。
默认 DRY_RUN=1（只返回将要执行的操作清单，不动真格）。
确认无误后，设置环境变量 DRY_RUN=0 再启动，才会真正删除/移动。
前端页面本身也有一次「确认执行」弹窗，两层确认都过了才会改动磁盘。
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import hashlib
import shutil
from collections import defaultdict

app = Flask(__name__)
CORS(app)

DRY_RUN = os.environ.get("DRY_RUN", "1") != "0"


def get_file_hash(filepath, chunk_size=8192):
    hasher = hashlib.md5()
    try:
        with open(filepath, 'rb') as f:
            while chunk := f.read(chunk_size):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception:
        return None

@app.route('/api/scan', methods=['POST'])
def scan_directory():
    data = request.json
    source_dir = data.get('source', '.')
    source_dir = os.path.abspath(source_dir)
    is_flat = data.get('flat', False)

    if not os.path.isdir(source_dir):
        return jsonify({"error": "Invalid directory"}), 400

    size_map = defaultdict(list)
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
    for root, _, files in os.walk(source_dir):
        for name in files:
            ext = os.path.splitext(name)[1].lower()
            if ext not in image_extensions:
                continue
            path = os.path.join(root, name)
            try:
                size = os.path.getsize(path)
                size_map[size].append(path)
            except OSError:
                continue

    hash_groups = defaultdict(list)
    for size, paths in size_map.items():
        if len(paths) > 1:
            for path in paths:
                h = get_file_hash(path)
                if h:
                    hash_groups[h].append(path)

    duplicates = []
    unique_delegates = []

    for h, paths in hash_groups.items():
        if len(paths) > 1:
            duplicates.append({
                "hash": h,
                "size": os.path.getsize(paths[0]),
                "files": [
                    {"path": p, "name": os.path.basename(p), "dir": os.path.dirname(p)}
                    for p in paths
                ]
            })
            unique_delegates.append(paths[0])
        else:
            unique_delegates.append(paths[0])

    for size, paths in size_map.items():
        if len(paths) == 1:
            unique_delegates.append(paths[0])

    flattening_plan = []
    if is_flat:
        import datetime
        used_targets = set()
        for path in unique_delegates:
            try:
                mtime = os.path.getmtime(path)
                dt = datetime.datetime.fromtimestamp(mtime)
                year_month_dir = dt.strftime('%Y/%m')
            except Exception:
                year_month_dir = "unknown"

            filename = os.path.basename(path)
            name, ext = os.path.splitext(filename)
            target_rel_path = os.path.join(year_month_dir, filename)

            counter = 1
            while target_rel_path in used_targets:
                target_rel_path = os.path.join(year_month_dir, f"{name}_{counter}{ext}")
                counter += 1

            used_targets.add(target_rel_path)
            flattening_plan.append({
                "source": path,
                "target_name": target_rel_path,
                "original_name": filename,
                "date": year_month_dir
            })

    return jsonify({
        "source": source_dir,
        "duplicates": duplicates,
        "flattening_plan": flattening_plan,
        "dry_run": DRY_RUN
    })

@app.route('/api/execute', methods=['POST'])
def execute_operations():
    data = request.json
    actions = data.get('actions', [])

    if DRY_RUN:
        # 只列清单，不真的删除/移动。想让它真的动手，启动前设 DRY_RUN=0。
        return jsonify({
            "dry_run": True,
            "message": "当前是 DRY_RUN 模式，以下操作没有真的执行。确认无误后设 DRY_RUN=0 重新启动再执行。",
            "results": [
                {"path": a.get("source"), "status": "would_" + a.get("type", "?"),
                 "to": a.get("target")}
                for a in actions
            ]
        })

    results = []
    for action in actions:
        try:
            if action['type'] == 'delete':
                if os.path.exists(action['source']):
                    os.remove(action['source'])
                    results.append({"path": action['source'], "status": "deleted"})
            elif action['type'] == 'move':
                target_path = action['target']
                target_dir = os.path.dirname(target_path)
                if not os.path.exists(target_dir):
                    os.makedirs(target_dir, exist_ok=True)
                shutil.move(action['source'], target_path)
                results.append({"path": action['source'], "status": "moved", "to": target_path})
        except Exception as e:
            results.append({"path": action.get('source'), "status": "error", "message": str(e)})

    return jsonify({"dry_run": False, "results": results})

@app.route('/api/preview')
def get_preview():
    path = request.args.get('path')
    if not path or not os.path.exists(path):
        return "Not found", 404
    directory = os.path.dirname(path)
    filename = os.path.basename(path)
    return send_from_directory(directory, filename)

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('.', path)

if __name__ == '__main__':
    if DRY_RUN:
        print("DRY_RUN 模式：/api/execute 只会列清单，不会真的删除/移动文件。")
        print("确认没问题后，用 DRY_RUN=0 python app.py 重新启动才会真正执行。")
    app.run(port=5001, debug=True)
