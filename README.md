# Local AI Image Upscaler

A small web application that upscales images 2x/3x/4x on your own machine, with an optional
face-restoration pass. Nothing is uploaded to a third-party service: the models run locally on
the GPU through Vulkan.

Built as a personal project to learn how to wrap an existing model into a usable application.

## How it works

```
React + TypeScript frontend
        |  multipart POST /api/upscale
        v
Flask backend (app.py)
        |  subprocess call
        v
realesrgan-ncnn-vulkan.exe   <- Real-ESRGAN, ncnn/Vulkan build
        |  optional second pass
        v
gfpgan-ncnn-vulkan.exe       <- GFPGAN face restoration
```

I use the **ncnn/Vulkan builds** of Real-ESRGAN and GFPGAN rather than the PyTorch versions.
The backend calls them as command-line processes instead of loading the models in Python. The
trade-off: no PyTorch/CUDA install is needed and it runs on any Vulkan-capable GPU, but the
process boundary means each image pays a start-up cost and errors have to be parsed out of the
process output.

### What the backend does

- **`app.py`** — Flask API. Accepts a batch of images, assigns each batch a short UUID, writes
  the inputs to `uploads/<batch>/`, and serves results from `outputs/<batch>/`. Also serves the
  built React SPA with a catch-all 404 fallback so client-side routes work.
- **`process.py`** — the actual work.
  - `normalize_image()` converts anything (CMYK, palette, LA) to RGB PNG first. Without this,
    the ncnn binary fails on some inputs with an unhelpful error.
  - `run_realesrgan()` builds the CLI arguments, maps friendly model names to the real model
    names, and runs the binary.
  - `run_gfpgan()` handles the fact that the GFPGAN build accepts different argument styles
    depending on version: it tries `-i/-o/-m` first, and if the binary answers with a usage
    message, it falls back to positional arguments and then locates the newest created file.

Supported models: `realesrgan-x4plus`, `realesrgan-x4plus-anime`, `realesrnet-x4plus`.

## Running it

Requires Python 3.10+, Node 18+, and a Vulkan-capable GPU.

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt

cd frontend
npm install
npm run build                    # output goes to static/app
cd ..

python app.py                    # serves on http://localhost:7860
```

The Real-ESRGAN and GFPGAN binaries and their model weights are **not** in this repository
(they are large and not mine to redistribute). Download them from the upstream projects and
place them in `realesrgan/` and `gfpgan/`:

- Real-ESRGAN ncnn Vulkan — https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan
- GFPGAN ncnn Vulkan — https://github.com/onuralpszr/GFPGAN-ncnn-vulkan

If OpenCV DLLs live outside the project, point `OPENCV_BIN` at the directory containing them
before starting the server.

## Known limitations

- **Failures are silent.** If the upscaler binary fails, `process.py` copies the input to the
  output path so the request still returns an image. This keeps the UI from breaking, but it
  means a failed upscale looks like a successful one. Surfacing the error to the client instead
  is the next thing to fix.
- Requests are handled synchronously — a large batch blocks the worker until it finishes. There
  is no job queue or progress reporting.
- Memory use scales with image size; very large inputs can exhaust GPU memory. The ncnn binary
  supports tiling (`-t`), which is not exposed in the UI yet.
- Tested on Windows only.

## Credits

The upscaling itself is done by [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) (Xintao
Wang et al.) and [GFPGAN](https://github.com/TencentARC/GFPGAN), via their ncnn/Vulkan builds.
This repository is the web application around them, not an implementation of the models.
