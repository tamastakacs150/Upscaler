# process.py
import os
import re
import subprocess
import shutil
from datetime import datetime

try:
    from PIL import Image
except Exception:
    Image = None  # ha nincs Pillow, továbbra is fut, csak nem normalizál

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- Binárisok helye ---
REALDIR = os.path.join(BASE_DIR, "realesrgan")
REALBIN = os.path.join(REALDIR, "realesrgan-ncnn-vulkan.exe")
REALMODELS = os.path.join(REALDIR, "models")
GFPDIR  = os.path.join(BASE_DIR, "gfpgan")
GFPBIN  = os.path.join(GFPDIR, "gfpgan-ncnn-vulkan.exe")
GFPMODELS = os.path.join(GFPDIR, "models")

CREATE_FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)
LOGFILE = os.path.join(BASE_DIR, "upscale.log")


def _log(msg: str):
    try:
        with open(LOGFILE, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass


def _subprocess_env():
    """
    A binarisok mellett levo DLL-eket (opencv_world*.dll, vcomp140.dll) a Windows
    csak akkor talalja meg, ha az exe mappaja vagy a PATH tartalmazza oket.
    A GFPGAN exe kulon mappaban van, DLL nelkul, ezert a realesrgan mappat is
    beletesszuk a PATH-ba - onnan tolti be az opencv DLL-t.
    """
    env = os.environ.copy()
    extra = [d for d in (REALDIR, GFPDIR, os.environ.get("OPENCV_BIN", "")) if d and os.path.isdir(d)]
    if extra:
        env["PATH"] = os.pathsep.join(extra) + os.pathsep + env.get("PATH", "")
    return env


def _short_error(output: str, fallback: str) -> str:
    """A process kimenetéből az utolsó értelmes sor, hogy a kliensnek ne a teljes zajt küldjük."""
    for line in reversed((output or "").splitlines()):
        line = line.strip()
        if line:
            return line[:300]
    return fallback


def _run(cmd, cwd=None, timeout=None):
    try:
        cp = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout,
            env=_subprocess_env(),
            creationflags=CREATE_FLAGS
        )
        out = (cp.stdout or "") + (cp.stderr or "")
        _log(f"OK: {' '.join(cmd)}\n{out}")
        return True, out
    except subprocess.CalledProcessError as e:
        out = ((e.stdout or "") + (e.stderr or "")) or str(e)
        _log(f"ERR: {' '.join(cmd)}\n{out}")
        return False, out
    except Exception as e:
        _log(f"EXC: {' '.join(cmd)}\n{e}")
        return False, str(e)


def normalize_image(src_path: str) -> str:
    """
    Bármilyen képet garantáltan RGB PNG-vé alakít.
    Ha nincs Pillow, visszaadja az eredetit.
    """
    if Image is None:
        _log("Pillow not available; skipping normalize")
        return src_path

    try:
        with Image.open(src_path) as im:
            # CMYK/LA/P stb. -> RGB
            if im.mode not in ("RGB", "RGBA"):
                im = im.convert("RGB")
            base = os.path.splitext(os.path.basename(src_path))[0]
            dst_path = os.path.join(os.path.dirname(src_path), f"__norm__{base}.png")
            im.save(dst_path, format="PNG")
            _log(f"Normalized {src_path} -> {dst_path} ({im.mode})")
            return dst_path
    except Exception as e:
        _log(f"Normalize failed for {src_path}: {e}")
        return src_path


MODEL_ALIAS = {
    "realesr-animevideov3": "realesr-animevideov3-x4",
    "realesrgan-x4plus-anime": "realesrgan-x4plus-anime",
    "realesrgan-x4plus": "realesrgan-x4plus",
    "realesrnet-x4plus": "realesrnet-x4plus",
}


def available_models():
    """A models mappaban tenylegesen meglevo modellek nevei."""
    try:
        return sorted({
            os.path.splitext(f)[0]
            for f in os.listdir(REALMODELS)
            if f.endswith(".param")
        })
    except OSError:
        return []


def native_scale(model_name: str) -> int:
    """
    A modell sajat nagyitasi aranya a nevebol: realesrgan-x4plus -> 4,
    realesr-animevideov3-x2 -> 2. Ez fontos, mert a binaris CSAK a sajat
    aranyaval ad helyes eredmenyt; mas ertekkel osszekevert csempeket general.
    """
    m = re.search(r"x(\d)", model_name)
    return int(m.group(1)) if m else 4


def _looks_blank(path) -> bool:
    """
    Igaz, ha a kep gyakorlatilag teljesen fekete. A ncnn binaris NEM hibazik,
    ha elfogy a GPU-memoria (pl. tul nagy csempemeret): nulla kilepesi koddal
    fut le, es fekete kepet ir ki. Ezt csak a kimenet megnezesevel lehet elkapni.
    """
    if Image is None:
        return False
    try:
        with Image.open(path) as im:
            extrema = im.convert("RGB").getextrema()
        return all(hi <= 2 for _lo, hi in extrema)
    except Exception:
        return False


def run_realesrgan(input_path, output_path, scale=4, model_name="realesrgan-x4plus", tile=0):
    """
    Felnagyítja a képet. Visszaadja: (ok: bool, error: str | None).

    A modellt mindig a sajat aranyaval futtatjuk, es ha a kert nagyitas ettol
    elter, Pillow-val kicsinyitunk a vegen. Ha a binarisnak nem a sajat aranyat
    adjuk at, csempekre darabolt, osszekevert kepet ad vissza.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    model = MODEL_ALIAS.get(model_name, model_name)

    have = available_models()
    if have and model not in have:
        return False, (f"A(z) '{model}' modell fajljai hianyoznak a realesrgan/models mappabol. "
                       f"Elerheto: {', '.join(have)}")

    native = native_scale(model)
    run_scale = native

    # 1) Normalizáljuk az inputot "tuti" formátumra
    norm_input = normalize_image(input_path)

    # 2) Ha nincs Pillow, nem tudunk utolag kicsinyiteni - ilyenkor marad a kert arany
    if Image is None and scale != native:
        run_scale = scale
        _log(f"Pillow missing; running the binary at the requested scale {scale} "
             f"instead of the model's native {native}")

    cmd = [
        REALBIN,
        "-i", norm_input,
        "-o", output_path,
        "-s", str(run_scale),
        "-n", model,
        "-f", "png"
    ]
    # A -t a csempeméret: kisebb érték kevesebb GPU-memóriát használ.
    # 0 = a bináris maga választ.
    if tile and int(tile) > 0:
        cmd += ["-t", str(int(tile))]

    ok, out = _run(cmd, cwd=REALDIR)

    if not ok:
        return False, _short_error(out, "Az upscaler folyamat hibával lépett ki.")
    if not os.path.exists(output_path):
        _log(f"realesrgan reported success but produced no file: {output_path}")
        return False, "Az upscaler lefutott, de nem jött létre kimeneti fájl."

    # Fekete kimenet: a binaris sikert jelez, de elfogyott a GPU-memoria.
    # Csak akkor hiba, ha a bemenet maga nem fekete.
    if _looks_blank(output_path) and not _looks_blank(input_path):
        _log(f"blank output detected for {output_path} (tile={tile}) - likely out of GPU memory")
        hint = (f"csempemeret {tile}" if tile else "az automatikus csempemeret")
        return False, (f"A kimenet ures lett - valoszinuleg elfogyott a GPU-memoria "
                       f"({hint}). Probald kisebb csempemerettel, vagy allitsd Auto-ra.")

    # 3) Ha a kert arany kisebb a modell sajat aranyanal, kicsinyitunk ra
    if Image is not None and scale != run_scale:
        try:
            with Image.open(input_path) as src:
                sw, sh = src.size
            target = (max(1, round(sw * scale)), max(1, round(sh * scale)))
            with Image.open(output_path) as up:
                up.convert("RGB").resize(target, Image.LANCZOS).save(output_path, format="PNG")
            _log(f"Resized {output_path} from x{run_scale} down to x{scale} -> {target}")
        except Exception as e:
            _log(f"Downscale to x{scale} failed: {e}")
            return False, f"A felnagyitas sikerult, de az atmeretezes x{scale}-re nem: {e}"

    return True, None


def _newest_created_file(dir_before, dir_after, search_dir):
    created = list(set(dir_after) - set(dir_before))
    candidates = [f for f in created if os.path.isfile(os.path.join(search_dir, f))]
    if candidates:
        full = [os.path.join(search_dir, f) for f in candidates]
        return max(full, key=os.path.getmtime)
    return None


def gfpgan_available():
    """(ok, hiba) - megvan-e minden a GFPGAN futtatasahoz."""
    if not os.path.exists(GFPBIN):
        return False, "A GFPGAN binaris nem talalhato a gfpgan/ mappaban."
    if not os.path.isdir(GFPMODELS) or not os.listdir(GFPMODELS):
        return False, ("A GFPGAN modellfajljai hianyoznak (gfpgan/models). "
                       "Toltsd le a GFPGAN-ncnn-vulkan kiadasat, es masold be a models mappat.")
    return True, None


def run_gfpgan(input_path, output_path):
    """
    Arc-helyreállítás. Visszaadja: (ok: bool, error: str | None).
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    ready, why = gfpgan_available()
    if not ready:
        return False, why

    out_dir = os.path.dirname(output_path)
    before = os.listdir(out_dir)

    param_cmd = [GFPBIN, "-i", input_path, "-o", output_path, "-m", GFPMODELS]

    ok, out = _run(param_cmd, cwd=GFPDIR)

    if ok and os.path.exists(output_path):
        return True, None

    # A bináris verziójától függ, milyen argumentumokat fogad el.
    usage_markers = ("usage", "unrecognized", "unknown option", "invalid option")
    if (not ok) and any(token in out.lower() for token in usage_markers):
        simple_cmd = [GFPBIN, input_path]
        ok2, out2 = _run(simple_cmd, cwd=GFPDIR)
        if ok2:
            after = os.listdir(out_dir)
            newest = _newest_created_file(before, after, out_dir)
            if newest and os.path.exists(newest):
                if os.path.abspath(newest) != os.path.abspath(output_path):
                    try:
                        shutil.copy2(newest, output_path)
                    except Exception as e:
                        _log(f"gfpgan copy newest failed: {e}")
                        return False, f"Nem sikerult a helyreallitott fajl masolasa: {e}"
                return True, None

            in_dir = os.path.dirname(input_path)
            try:
                newest_any = max(
                    (os.path.join(in_dir, f) for f in os.listdir(in_dir)),
                    key=os.path.getmtime
                )
                if os.path.isfile(newest_any):
                    shutil.copy2(newest_any, output_path)
                    return True, None
            except Exception as e:
                _log(f"gfpgan search any failed: {e}")
        out = out2 or out

    # A hianyzo DLL-t a Windows parbeszedablakban jelzi, a kimenet ilyenkor ures
    if not (out or "").strip():
        return False, ("A GFPGAN nem indult el. Valoszinuleg hianyzik egy DLL "
                       "(pl. opencv_world4120.dll) a gfpgan mappa mellol.")

    return False, _short_error(out, "Az arc-helyreallitas nem sikerult.")


def upscale_batch(input_paths, output_dir, scale=4, model_name="realesrgan-x4plus",
                  face_enhance=False, tile=0):
    """
    Feldolgozza a képeket, és képenként visszaadja az eredményt:

        [{ "source": <bemeneti fajlnev>,
           "path":   <kimeneti fajl utvonala vagy None>,
           "ok":     bool,
           "error":  str | None,
           "face_enhanced": bool }, ...]

    Egy kép hibája nem szakítja meg a batch többi részét.
    """
    os.makedirs(output_dir, exist_ok=True)
    results = []

    # Ha az arcjavitast kertek, de nem all keszen, egyszer jelezzuk - nem kepenkent
    face_ready, face_why = (True, None)
    if face_enhance:
        face_ready, face_why = gfpgan_available()

    for p in input_paths:
        source = os.path.basename(p)
        base = os.path.splitext(source)[0]
        upscaled = os.path.join(output_dir, f"{base}_x{scale}.png")

        ok, err = run_realesrgan(p, upscaled, scale=scale, model_name=model_name, tile=tile)
        if not ok:
            results.append({"source": source, "path": None, "ok": False,
                            "error": err, "face_enhanced": False})
            continue

        if not face_enhance:
            results.append({"source": source, "path": upscaled, "ok": True,
                            "error": None, "face_enhanced": False})
            continue

        if not face_ready:
            results.append({"source": source, "path": upscaled, "ok": True,
                            "error": f"A felnagyitas sikerult, de az arc-helyreallitas kimaradt: {face_why}",
                            "face_enhanced": False})
            continue

        face_base = os.path.splitext(os.path.basename(upscaled))[0]
        facefixed = os.path.join(output_dir, f"{face_base}_face.png")
        f_ok, f_err = run_gfpgan(upscaled, facefixed)

        if f_ok and os.path.exists(facefixed):
            results.append({"source": source, "path": facefixed, "ok": True,
                            "error": None, "face_enhanced": True})
        else:
            results.append({"source": source, "path": upscaled, "ok": True,
                            "error": f"A felnagyitas sikerult, de az arc-helyreallitas nem: {f_err}",
                            "face_enhanced": False})

    return results
