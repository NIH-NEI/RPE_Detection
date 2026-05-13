"""
PyInstaller runtime hook for TensorFlow on Windows.

This version is intentionally old-fashioned: in addition to os.add_dll_directory(),
it prepends TensorFlow's frozen native-binary directories to PATH and calls
SetDllDirectoryW(). Some TensorFlow native loading paths still use a bare DLL
name, so relying only on os.add_dll_directory() may not be enough.
"""
import ctypes
import os
import sys
from pathlib import Path


def _unique_existing(paths):
    out = []
    seen = set()
    for p in paths:
        try:
            p = Path(p).resolve()
        except Exception:
            p = Path(p)
        if p.is_dir() and str(p).lower() not in seen:
            seen.add(str(p).lower())
            out.append(p)
    return out


if sys.platform.startswith("win"):
    exe_dir = Path(sys.executable).resolve().parent
    internal = exe_dir / "_internal"
    meipass = Path(getattr(sys, "_MEIPASS", internal)).resolve()

    candidates = [
        exe_dir,
        internal,
        meipass,
        internal / "tensorflow",
        internal / "tensorflow" / "python",
        meipass / "tensorflow",
        meipass / "tensorflow" / "python",
    ]

    # Also add any directory under _internal/tensorflow that contains native files.
    for base in (internal / "tensorflow", meipass / "tensorflow"):
        if base.is_dir():
            for root, _dirs, files in os.walk(base):
                if any(f.lower().endswith((".dll", ".pyd")) for f in files):
                    candidates.append(Path(root))

    dirs = _unique_existing(candidates)

    # 1. Prepend to PATH. This is still necessary for libraries loaded by bare name.
    old_path = os.environ.get("PATH", "")
    prefix = os.pathsep.join(str(p) for p in dirs)
    os.environ["PATH"] = prefix + os.pathsep + old_path if old_path else prefix

    # 2. Use add_dll_directory for Python 3.8+ extension loading semantics.
    for p in dirs:
        try:
            os.add_dll_directory(str(p))
        except Exception:
            pass

    # 3. SetDllDirectory is global/process-wide and helps old-style LoadLibrary calls.
    # Use tensorflow/python as the most important directory.
    tf_python_dirs = [p for p in dirs if str(p).lower().replace("/", "\\").endswith("tensorflow\\python")]
    for p in tf_python_dirs[:1]:
        try:
            ctypes.windll.kernel32.SetDllDirectoryW(str(p))
        except Exception:
            pass

    # 4. Try preloading from the exact path and print result.
    common = None
    for p in dirs:
        q = p / "_pywrap_tensorflow_common.dll"
        if q.exists():
            common = q
            break

    if common is not None:
        try:
            ctypes.WinDLL(str(common))
            print(f"[TF runtime hook] preloaded {common}")
        except OSError as e:
            print(f"[TF runtime hook] found but could not preload {common}")
            print(f"[TF runtime hook] preload error: {e!r}")
    else:
        print("[TF runtime hook] _pywrap_tensorflow_common.dll not found in candidate dirs")
        for p in dirs:
            print(f"[TF runtime hook] dir: {p}")
