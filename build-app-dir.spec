# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for building RPE_Detection.app on macOS.

Build from the project root on macOS with:
    pyinstaller --clean --noconfirm build-macos-tf2-app.spec

Notes:
- This spec is meant for macOS only.
- Do not reuse the Windows TensorFlow DLL runtime hook here.
- Build on the same CPU family you intend to distribute to, or build separate
  Intel and Apple Silicon apps. PyInstaller is not a cross-compiler.
"""

from pathlib import Path
import importlib.util

from PyInstaller.utils.hooks import (
    collect_submodules,
    collect_data_files,
    collect_dynamic_libs,
    copy_metadata,
)

block_cipher = None


def package_root(package_name):
    spec = importlib.util.find_spec(package_name)
    if spec is None or spec.origin is None:
        raise RuntimeError(f"Cannot find package: {package_name}")
    return Path(spec.origin).resolve().parent


def collect_package_binary_tree(package_name, suffixes=(".so", ".dylib")):
    """
    Preserve package-relative locations for native libraries inside packages.
    TensorFlow wheels contain many extension/shared-library files that may not
    all be detected by import scanning.
    """
    root = package_root(package_name)
    out = []
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in suffixes:
            rel_parent = path.parent.relative_to(root.parent)
            out.append((str(path), str(rel_parent)))
    return out


def safe_extend(func, package_name):
    try:
        return func(package_name)
    except Exception:
        return []


hiddenimports = []
datas = []
binaries = []

# Main scientific/ML stack.
for pkg in (
    "tensorflow",
    "keras",
    "h5py",
    "numpy",
    "scipy",
    "skimage",
    "SimpleITK",
    "vtkmodules",
    "PyQt5",
):
    hiddenimports += safe_extend(collect_submodules, pkg)
    datas += safe_extend(collect_data_files, pkg)
    binaries += safe_extend(collect_dynamic_libs, pkg)

# TensorFlow: preserve native shared objects in their package-relative paths.
binaries += collect_package_binary_tree("tensorflow")

# Runtime package metadata used by TensorFlow/Keras and friends.
for dist_name in (
    "tensorflow",
    "keras",
    "h5py",
    "numpy",
    "scipy",
    "scikit-image",
    "SimpleITK",
    "PyQt5",
    "vtk",
):
    try:
        datas += copy_metadata(dist_name)
    except Exception:
        pass

# Remove duplicates while preserving order.
def dedupe(seq):
    seen = set()
    out = []
    for item in seq:
        key = tuple(item) if isinstance(item, (tuple, list)) else item
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


binaries = dedupe(binaries)
datas = dedupe(datas)
hiddenimports = sorted(set(hiddenimports + [
    "vtkmodules",
    "vtkmodules.all",
    "vtkmodules.qt.QVTKRenderWindowInteractor",
    "vtkmodules.util",
    "vtkmodules.util.numpy_support",
]))


a = Analysis(
    ["__main__.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas + [
        ("./model_weights", "./model_weights"),
        ("./Icons/*", "./Icons"),
        ("./Help/*", "./Help"),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "matplotlib",
        "matplotlib.tests",
        "PyQt4",
        "PySide",
        "_tkinter",
        "PyQt5.QtPrintSupport",
        "PyQt5.QtMultimedia",
        "PyQt5.QtBluetooth",
    ],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="RPE_Detection",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="RPE_Detection",
)

app = BUNDLE(
    coll,
    name="RPE_Detection.app",
    icon="Icons/RPE_Detection256x256.icns",
    bundle_identifier="org.local.RPE_Detection",
    info_plist={
        "CFBundleName": "RPE_Detection",
        "CFBundleDisplayName": "RPE_Detection",
        "CFBundleExecutable": "RPE_Detection",
        "CFBundlePackageType": "APPL",
        "NSHighResolutionCapable": "True",
    },
)
