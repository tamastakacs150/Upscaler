# storage.py
"""
A feltoltott es a generalt kepek batch-mappakban gyulnek (uploads/<id>, outputs/<id>),
es eddig semmi nem takaritotta oket. Ez a modul a regi batcheket torli.

Beallitas kornyezeti valtozokkal:
    UPSCALER_RETENTION_HOURS  hany oranal regebbi batch torolheto (alap: 24, 0 = kikapcsolva)
    UPSCALER_KEEP_LAST        ennyi legfrissebb batch mindig megmarad (alap: 5)
"""
import os
import shutil
import time
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGFILE = os.path.join(BASE_DIR, "upscale.log")


def _log(msg: str):
    try:
        with open(LOGFILE, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass


def _retention_hours() -> float:
    try:
        return float(os.environ.get("UPSCALER_RETENTION_HOURS", "24"))
    except ValueError:
        return 24.0


def _keep_last() -> int:
    try:
        return max(0, int(os.environ.get("UPSCALER_KEEP_LAST", "5")))
    except ValueError:
        return 5


def _dir_size(path: str) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def cleanup_old_batches(directories, retention_hours=None, keep_last=None) -> dict:
    """
    Torli a megadott konyvtarak alatti regi batch-almappakat.

    A legfrissebb `keep_last` darabot mindig megtartja, meg akkor is, ha regiek -
    igy egy hosszabb szunet utan sem tunik el az utolso eredmeny a felulet alol.

    Visszaad: { "removed": <db>, "freed_bytes": <byte> }
    """
    hours = _retention_hours() if retention_hours is None else float(retention_hours)
    keep = _keep_last() if keep_last is None else int(keep_last)

    if hours <= 0:
        return {"removed": 0, "freed_bytes": 0}

    cutoff = time.time() - hours * 3600
    removed = 0
    freed = 0

    for d in directories:
        if not os.path.isdir(d):
            continue

        entries = []
        for name in os.listdir(d):
            p = os.path.join(d, name)
            if not os.path.isdir(p):
                continue
            try:
                entries.append((os.path.getmtime(p), p))
            except OSError:
                pass

        # a legfrissebbek elol, hogy a megtartandokat konnyen levaghassuk
        entries.sort(reverse=True)
        for mtime, p in entries[keep:]:
            if mtime >= cutoff:
                continue
            try:
                size = _dir_size(p)
                shutil.rmtree(p)
                removed += 1
                freed += size
            except Exception as e:
                _log(f"cleanup failed for {p}: {e}")

    if removed:
        _log(f"cleanup: {removed} batch torolve, {freed / 1_048_576:.1f} MB felszabaditva")

    return {"removed": removed, "freed_bytes": freed}
