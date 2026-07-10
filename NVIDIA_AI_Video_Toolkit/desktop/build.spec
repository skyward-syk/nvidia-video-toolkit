# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 打包配置 — 生成自包含文件夹
用法:
  1. 先安装依赖: pip install -r requirements.txt
  2. 执行打包:   pyinstaller build.spec
  3. 输出目录:   dist/NVIDIA_AI_Video_Toolkit/
"""

import os
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.abspath(SPECPATH))

# 隐藏导入
hidden_imports = [
    "realesrgan", "realesrgan.archs", "realesrgan.archs.srvgg_arch",
    "realesrgan.data", "realesrgan.utils",
    "basicsr", "basicsr.archs", "basicsr.archs.rrdbnet_arch", "basicsr.utils",
    "diffusers", "diffusers.pipelines", "diffusers.pipelines.stable_video_diffusion",
    "transformers", "transformers.models",
    "accelerate", "safetensors",
    "torch", "torchvision",
    "cv2", "numpy", "PIL",
    "tqdm", "psutil", "ffmpeg_python",
]

# 收集数据文件 + 启动脚本
datas = [
    (os.path.join(PROJECT_ROOT, "run.bat"), "."),
    (os.path.join(PROJECT_ROOT, "README.md"), "."),
]

# 排除不必要的模块以减小体积
excluded_modules = [
    "matplotlib", "scipy", "pandas",
    "IPython", "jupyter", "notebook",
    "tkinter", "test", "unittest",
]

a = Analysis(
    [os.path.join(PROJECT_ROOT, "main.py")],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excluded_modules,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="NVIDIA_AI_Video_Toolkit",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(PROJECT_ROOT, "assets", "icon.ico") if os.path.exists(os.path.join(PROJECT_ROOT, "assets", "icon.ico")) else None,
)

# 收集到文件夹
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="NVIDIA_AI_Video_Toolkit",
)
