from flask import Flask, request, send_from_directory, jsonify
from werkzeug.utils import secure_filename
import os, uuid
from process import upscale_batch

_OPENCV_BIN = os.environ.get("OPENCV_BIN", r"C:\Users\takit\Desktop\opencv\build\x64\vc16\bin")
if _OPENCV_BIN and os.path.isdir(_OPENCV_BIN):
    os.environ["PATH"] = _OPENCV_BIN + os.pathsep + os.environ.get("PATH", "")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 1024  # 1GB

ALLOWED = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

# ---------- API ----------
@app.post("/api/upscale")
def api_upscale():
    scale = int(request.form.get("scale", "4"))
    model = request.form.get("model", "realesrgan-x4plus")
    # frontend "face" mezője "true"/"false" string, alakítsuk bool-lá:
    face_enhance = str(request.form.get("face", "false")).lower() in ("1", "true", "on", "yes")

    files = request.files.getlist("images")
    if not files:
        return jsonify({"ok": False, "error": "No files uploaded"}), 400

    batch_id = str(uuid.uuid4())[:8]
    up_dir = os.path.join(UPLOAD_DIR, batch_id)
    out_dir = os.path.join(OUTPUT_DIR, batch_id)
    os.makedirs(up_dir, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)

    paths = []
    for f in files:
        name = secure_filename(f.filename)
        ext = os.path.splitext(name)[1].lower()
        if ext not in ALLOWED:
            continue
        p = os.path.join(up_dir, name)
        f.save(p)
        paths.append(p)

    if not paths:
        return jsonify({"ok": False, "error": "No valid images"}), 400

    outs = upscale_batch(
        input_paths=paths,
        output_dir=out_dir,
        scale=scale,
        model_name=model,
        face_enhance=face_enhance
    )

    payload = [{
        "url": f"/outputs/{batch_id}/{os.path.basename(x)}",
        "filename": os.path.basename(x)
    } for x in outs]

    return jsonify({"ok": True, "results": payload})

@app.get("/outputs/<path:path>")
def serve_outputs(path):
    return send_from_directory(OUTPUT_DIR, path, as_attachment=False)

# ---------- React build (SPA) ----------
@app.get("/")
def root():
    return send_from_directory("static/app", "index.html")

@app.get("/assets/<path:path>")
def assets(path):
    return send_from_directory("static/app/assets", path)

# SPA catch-all: minden egyéb útvonal menjen az index.html-re
@app.errorhandler(404)
def spa_fallback(e):
    try:
        return send_from_directory("static/app", "index.html")
    except Exception:
        return "Not Found", 404

if __name__ == "__main__":
    from waitress import serve
    serve(app, host="0.0.0.0", port=7860)
