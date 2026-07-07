"""Install/check the optional runtime dependency (mediapipe) inside
Blender's bundled Python."""
from __future__ import annotations

import importlib
import importlib.util
import os
import subprocess
import sys


def python_binary() -> str:
    # Blender >= 2.92 exposes its interpreter as sys.executable
    return sys.executable


def have_deps() -> bool:
    for mod in ("mediapipe", "cv2", "numpy"):
        if importlib.util.find_spec(mod) is None:
            return False
    return True


def install_deps(progress=None) -> str:
    """Blocking pip install.  Returns '' on success, else an error string."""
    py = python_binary()
    env = dict(os.environ)
    env.setdefault("PYTHONNOUSERSITE", "0")
    cmds = [
        [py, "-m", "ensurepip", "--upgrade"],
        [py, "-m", "pip", "install", "--upgrade", "pip", "wheel"],
        [py, "-m", "pip", "install", "mediapipe"],
    ]
    for i, cmd in enumerate(cmds):
        if progress:
            progress(i / len(cmds), " ".join(cmd[2:4]))
        try:
            r = subprocess.run(cmd, capture_output=True, text=True,
                               timeout=1200, env=env)
        except Exception as e:  # noqa: BLE001
            return f"Failed to run {' '.join(cmd)}: {e}"
        if r.returncode != 0 and "ensurepip" not in cmd[2]:
            tail = (r.stderr or r.stdout or "").strip().splitlines()[-6:]
            return ("pip failed:\n" + "\n".join(tail)
                    + "\n\nIf Blender is installed in a protected location, "
                      "run Blender as administrator once, or install into "
                      "a user site: add --user to the pip command.")
    importlib.invalidate_caches()
    if not have_deps():
        return ("Installation finished but 'mediapipe' still cannot be "
                "imported. Restart Blender and try again.")
    return ""
