from flask import Flask, request, send_from_directory, jsonify
from werkzeug.utils import secure_filename
import os, uuid
from process import upscale_batch, available_models, gfpgan_available, native_scale
from storage import cleanup_old_batches

_OPENCV_BIN = os.environ.get("OPENCV_BIN", r"C:\Users\takit\Desktop\opencv\build\x64\vc16\bin")
if _OPENCV_BIN and os.path.isdir(_OPENCV_BIN):
    os.environ["PATH"] = _OPENCV_BIN + os.pathsep + os.environ.get("PATH", "")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Indulaskor takaritunk, hogy a regi batchek ne gyuljenek a vegtelensegig
cleanup_old_batches([UPLOAD_DIR, OUTPUT_DIR])

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 1024  # 1GB

ALLOWED = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

# ---------- API ----------
# A sorrend a legordulot is meghatarozza: eloszor a fotokhoz valo modellek.
MODEL_LABELS = {
    "realesrgan-x4plus": "General Purpose — photos (4x)",
    "realesrgan-x4plus-anime": "Anime & Art — illustration (4x)",
    "realesr-animevideov3-x4": "Anime Video — fast, less detail (4x)",
    "realesr-animevideov3-x3": "Anime Video — fast, less detail (3x)",
    "realesr-animevideov3-x2": "Anime Video — fast, less detail (2x)",
}
MODEL_ORDER = list(MODEL_LABELS)


@app.get("/api/models")
def api_models():
    """Csak azokat a modelleket kinaljuk fel, amiknek a fajljai tenyleg megvannak."""
    face_ok, face_why = gfpgan_available()
    return jsonify({
        "models": [
            {"id": m, "label": MODEL_LABELS.get(m, m), "nativeScale": native_scale(m)}
            for m in sorted(available_models(),
                            key=lambda m: (MODEL_ORDER.index(m) if m in MODEL_ORDER else 99, m))
        ],
        "faceEnhanceAvailable": face_ok,
        "faceEnhanceReason": face_why,
    })



@app.post("/api/upscale")
def api_upscale():
    scale = int(request.form.get("scale", "4"))
    model = request.form.get("model", "realesrgan-x4plus")
    # frontend "face" mezője "true"/"false" string, alakítsuk bool-lá:
    face_enhance = str(request.form.get("face", "false")).lower() in ("1", "true", "on", "yes")
    # csempeméret: 0 = a bináris dönt. Kisebb érték kevesebb GPU-memóriát használ.
    try:
        tile = max(0, int(request.form.get("tile", "0")))
    except ValueError:
        tile = 0

    files = request.files.getlist("images")
    if not files:
        return jsonify({"ok": False, "error": "No files uploaded"}), 400

    # Minden keresnel takaritunk egyet, igy a mappak nem nonek korlatlanul
    cleanup_old_batches([UPLOAD_DIR, OUTPUT_DIR])

    batch_id = str(uuid.uuid4())[:8]
    up_dir = os.path.join(UPLOAD_DIR, batch_id)
    out_dir = os.path.join(OUTPUT_DIR, batch_id)
    os.makedirs(up_dir, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)

    paths = []
    skipped = []
    for f in files:
        name = secure_filename(f.filename)
        ext = os.path.splitext(name)[1].lower()
        if ext not in ALLOWED:
            skipped.append({"source": f.filename, "ok": False,
                            "error": f"Nem tamogatott formatum: {ext or 'ismeretlen'}"})
            continue
        p = os.path.join(up_dir, name)
        f.save(p)
        paths.append(p)

    if not paths:
        return jsonify({"ok": False, "error": "No valid images", "results": skipped}), 400

    outs = upscale_batch(
        input_paths=paths,
        output_dir=out_dir,
        scale=scale,
        model_name=model,
        face_enhance=face_enhance,
        tile=tile
    )

    results = list(skipped)
    for r in outs:
        item = {
            "source": r["source"],
            "ok": r["ok"],
            "error": r["error"],
            "faceEnhanced": r["face_enhanced"],
        }
        if r["ok"] and r["path"]:
            item["filename"] = os.path.basename(r["path"])
            item["url"] = f"/outputs/{batch_id}/{os.path.basename(r['path'])}"
        results.append(item)

    succeeded = sum(1 for r in results if r["ok"])
    return jsonify({
        "ok": succeeded > 0,
        "succeeded": succeeded,
        "failed": len(results) - succeeded,
        "results": results,
    })

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
