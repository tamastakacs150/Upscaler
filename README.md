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
    names, runs the binary, and returns `(ok, error)`.
  - `run_gfpgan()` handles the fact that the GFPGAN build accepts different argument styles
    depending on version: it tries `-i/-o/-m` first, and if the binary answers with a usage
    message, it falls back to positional arguments and then locates the newest created file.
  - `upscale_batch()` reports each image separately, so one failure does not abort the batch.
- **`storage.py`** — deletes batch directories older than the retention window, so `uploads/`
  and `outputs/` do not grow without bound.

The model list in the UI comes from `GET /api/models`, which reports the `.param` files actually
present in `realesrgan/models/`. The upstream ncnn release ships `realesrgan-x4plus`,
`realesrgan-x4plus-anime` and the `realesr-animevideov3-x2/x3/x4` set. **`realesrnet-x4plus` is not
part of it** — it exists only as a PyTorch weight in the main Real-ESRGAN repo, so it cannot be
offered here.

Every model has a native ratio (`realesrgan-x4plus` is 4x). The binary is always run at that ratio
and the result is resized down when a smaller one is requested, because passing a ratio the model
was not trained for returns the image split into squares and reassembled wrong.

### Errors are reported, not hidden

Every image in a batch comes back with its own `ok` flag and, when it failed, the last useful
line of the binary's output:

```json
{
  "ok": true, "succeeded": 2, "failed": 1,
  "results": [
    { "source": "a.jpg", "ok": true,  "url": "/outputs/1a2b3c4d/a_x4.png", "faceEnhanced": false },
    { "source": "b.tif", "ok": false, "error": "Nem tamogatott formatum: .tif" },
    { "source": "c.png", "ok": true,  "url": "/outputs/1a2b3c4d/c_x4_face.png", "faceEnhanced": true }
  ]
}
```

If the upscale succeeds but the optional face pass does not, the upscaled image is still
returned with a warning rather than being thrown away. The UI lists whatever failed underneath
the results; the full process output goes to `upscale.log`.

## Running it

Requires Python 3.10+, Node 18+, and a Vulkan-capable GPU.

On Windows, `AI Upscaler.bat` does all of this for you — it checks the virtual environment,
rebuilds it from `requirements.txt` if it is missing or broken (for example after a Python
upgrade), starts the server and opens the browser.

Manually:

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt

cd frontend
npm install
npm run build                    # type-checks, then writes straight to static/app
cd ..

python app.py                    # serves on http://localhost:7860
```

The Real-ESRGAN and GFPGAN binaries and their model weights are **not** in this repository
(they are large and not mine to redistribute). Download them from the upstream projects and
place them in `realesrgan/` and `gfpgan/`:

- Real-ESRGAN ncnn Vulkan — https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan
- GFPGAN ncnn Vulkan — https://github.com/onuralpszr/GFPGAN-ncnn-vulkan
  (the weights are a separate download: the `GFPGAN-ncnn-models.zip` asset on the
  `v0.0.1-models` release, extracted into `gfpgan/models/`)

The GFPGAN executable ships without the DLLs it needs. Rather than duplicating them, the backend
puts both binary directories on `PATH` when it starts a subprocess, so the exe in `gfpgan/` finds
`opencv_world4120.dll` next to the Real-ESRGAN binary. Face enhancement is disabled in the UI, with
the reason on hover, whenever the weights are missing.

If OpenCV DLLs live outside the project, point `OPENCV_BIN` at the directory containing them
before starting the server.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `OPENCV_BIN` | a local path | Directory holding the OpenCV DLLs |
| `UPSCALER_RETENTION_HOURS` | `24` | Batches older than this are deleted; `0` disables cleanup |
| `UPSCALER_KEEP_LAST` | `5` | This many newest batches are always kept, whatever their age |

The **Tile Size** control in the UI maps to the binary's `-t` flag. Large images can exhaust GPU
memory at once; a smaller tile processes the image in pieces, which is slower but fits.

## Known limitations

- **The served UI is a build artifact.** `static/app/` is what Flask serves and is not tracked
  in git, so after changing anything under `frontend/src` you have to run `npm run build` again
  or the running app keeps showing the previous build.
- **Requests are handled synchronously.** A large batch blocks the worker until it finishes, and
  there is no job queue or progress reporting. This is the next thing worth rewriting — the
  start/poll split I used for video generation in another project would fit here.
- Cleanup runs at startup and once per request, so a long-idle instance keeps its files until
  the next request arrives.
- Tested on Windows only.

## Credits

The upscaling itself is done by [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) (Xintao
Wang et al.) and [GFPGAN](https://github.com/TencentARC/GFPGAN), via their ncnn/Vulkan builds.
This repository is the web application around them, not an implementation of the models.
