"""
app.py — Flask API server for the Photo Sorter.

Endpoints:
  GET  /status          — server health + model loaded status
  GET  /pick-folder     — open native macOS folder picker dialog
  GET  /image           — serve a local image file by path
  POST /classify        — classify all images in a folder (SSE streaming)
  POST /sort            — copy classified images into portrait/landscape subfolders
"""

import os
import sys
import json
import shutil
import subprocess
import threading
import time
from pathlib import Path
from flask import Flask, request, jsonify, Response, send_file
from flask_cors import CORS

from classifier import classifier

app = Flask(__name__)
CORS(app)

# Thread-safe progress store
_progress: dict = {}
_progress_lock = threading.Lock()

# ─────────────────────────────────────────────────────────────────────────────
# Startup: load CLIP model
# ─────────────────────────────────────────────────────────────────────────────

@app.before_request
def ensure_model_loaded():
    if classifier.model is None:
        classifier.load()


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/status")
def status():
    return jsonify({"ok": True, "model_loaded": classifier.model is not None})


@app.get("/pick-folder")
def pick_folder():
    """Open a native folder chooser dialog via tkinter (cross-platform).
    Returns the selected absolute POSIX path, or null if cancelled."""
    try:
        picker = os.path.join(os.path.dirname(__file__), "picker.py")
        result = subprocess.run(
            [sys.executable, picker],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode != 0:
            return jsonify({"path": None, "cancelled": True})
        posix = result.stdout.strip()
        return jsonify({"path": posix, "cancelled": False})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.get("/image")
def serve_image():
    """Serve a local image file so the browser can display it."""
    path = request.args.get("path", "")
    if not path or not os.path.isfile(path):
        return jsonify({"error": "File not found"}), 404
    return send_file(path)


@app.post("/classify")
def classify_folder():
    """
    Classify all images in a folder.
    Body: { "folder": "/absolute/path/to/photos" }

    Returns a streaming SSE response.
    Each event is a JSON object:
      { "type": "progress", "index": N, "total": M, "path": "...", "result": {...} }
      { "type": "done", "results": [...] }
      { "type": "error", "message": "..." }
    """
    data = request.get_json(silent=True) or {}
    folder = data.get("folder", "").strip()

    if not folder:
        return jsonify({"error": "Missing 'folder' parameter"}), 400
    if not os.path.isdir(folder):
        return jsonify({"error": f"Not a directory: {folder}"}), 400

    def generate():
        images = classifier.find_images(folder)
        total = len(images)

        if total == 0:
            yield f"data: {json.dumps({'type': 'error', 'message': 'No images found in folder'})}\n\n"
            return

        yield f"data: {json.dumps({'type': 'start', 'total': total})}\n\n"

        results = []
        for i, img_path in enumerate(images):
            result = classifier.classify_image(img_path)
            entry = {
                "path": img_path,
                "filename": os.path.basename(img_path),
                **result,
            }
            results.append(entry)

            yield f"data: {json.dumps({'type': 'progress', 'index': i + 1, 'total': total, 'entry': entry})}\n\n"

        yield f"data: {json.dumps({'type': 'done', 'results': results})}\n\n"

    return Response(generate(), mimetype="text/event-stream",
                    headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})


@app.post("/sort")
def sort_files():
    """
    Copy classified images into sorted subfolders.
    Body: {
        "folder": "/path/to/photos",
        "results": [ { "path": "...", "label": "portrait"|"landscape", ... } ]
    }
    Creates:
        <folder>/sorted/portraits/
        <folder>/sorted/landscapes/
        <folder>/sorted/uncertain/   (confidence < threshold)
    """
    data = request.get_json(silent=True) or {}
    folder = data.get("folder", "").strip()
    results = data.get("results", [])
    threshold = float(data.get("threshold", 0.65))

    if not folder or not os.path.isdir(folder):
        return jsonify({"error": "Invalid folder"}), 400
    if not results:
        return jsonify({"error": "No results provided"}), 400

    sorted_dir = os.path.join(folder, "sorted")
    portraits_dir = os.path.join(sorted_dir, "portraits")
    landscapes_dir = os.path.join(sorted_dir, "landscapes")
    uncertain_dir = os.path.join(sorted_dir, "uncertain")

    os.makedirs(portraits_dir, exist_ok=True)
    os.makedirs(landscapes_dir, exist_ok=True)
    os.makedirs(uncertain_dir, exist_ok=True)

    counts = {"portraits": 0, "landscapes": 0, "uncertain": 0, "errors": 0}

    for entry in results:
        src = entry.get("path", "")
        label = entry.get("label", "unknown")
        confidence = float(entry.get("confidence", 0))

        if not os.path.isfile(src):
            counts["errors"] += 1
            continue

        filename = os.path.basename(src)

        if confidence < threshold:
            dest_dir = uncertain_dir
            counts["uncertain"] += 1
        elif label == "portrait":
            dest_dir = portraits_dir
            counts["portraits"] += 1
        else:
            dest_dir = landscapes_dir
            counts["landscapes"] += 1

        # Handle filename collisions
        dest = os.path.join(dest_dir, filename)
        if os.path.exists(dest):
            stem = Path(filename).stem
            suffix = Path(filename).suffix
            dest = os.path.join(dest_dir, f"{stem}_{int(time.time())}{suffix}")

        shutil.copy2(src, dest)

    return jsonify({
        "ok": True,
        "sorted_dir": sorted_dir,
        "counts": counts,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("🚀 Starting Photo Sorter server…")
    print("📷 Loading AI model (first run downloads ~350MB)…")
    classifier.load()
    print("🌐 Server running at http://localhost:5050")
    app.run(host="0.0.0.0", port=5050, debug=False, threaded=True)
