# NVIDIA AI 视频工具套件

基于 NVIDIA GPU 加速的 AI 视频处理桌面应用。

## 功能

| 功能 | 说明 | 核心技术 |
|------|------|----------|
| 🎥 **视频画质增强** | 将低分辨率视频超分为高清（2x / 4x） | Real-ESRGAN + CUDA + NVENC |
| 🎬 **单图生成视频** | 从一张静态图片生成动态短视频 | Stable Video Diffusion (SVD) |
| 📁 **图片序列合成** | 将多张图片合成为视频（支持过渡效果） | FFmpeg + NVENC |

## 系统要求

| 组件 | 最低要求 | 推荐 |
|------|----------|------|
| 操作系统 | Windows 10 / 11 | Windows 11 |
| GPU | NVIDIA RTX 2060 (6 GB VRAM) | RTX 4070+ (12 GB VRAM) |
| CUDA | 11.8+ | 12.1+ |
| Python | 3.10+ | 3.11 |
| FFmpeg | 4.4+ (PATH 中可访问) | 6.0+ |
| 内存 | 16 GB RAM | 32 GB RAM |

## 安装

### 🚀 一键沙箱安装（推荐）

项目自带虚拟环境沙箱，无需手动配置 Python 依赖：

```batch
:: 第一步：双击运行安装脚本（仅需一次）
setup.bat

:: 第二步：双击运行启动脚本
run.bat
```

`setup.bat` 会自动：
1. 创建独立 Python 虚拟环境（`venv/`）
2. 安装 CUDA 版 PyTorch
3. 安装全部依赖（PySide6、Real-ESRGAN、diffusers 等）
4. 检查 FFmpeg 是否可用

> 沙箱环境与系统 Python 完全隔离，不会污染系统环境。

### 手动安装（高级用户）

```bash
# 创建虚拟环境（可选）
python -m venv venv
venv\Scripts\activate

# 先安装 PyTorch (CUDA 版)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# 再安装其余依赖
pip install -r requirements.txt
```

### 2. 安装 FFmpeg

- 从 [ffmpeg.org](https://ffmpeg.org/download.html) 下载 Windows 版本
- 将 `ffmpeg.exe` 所在目录加入系统 PATH
- 或在应用「设置」页中手动指定 FFmpeg 路径

### 3. 下载 AI 模型（可选，首次运行自动下载）

| 模型 | 用途 | 大小 |
|------|------|------|
| RealESRGAN_x4plus | 视频超分 | ~67 MB |
| stable-video-diffusion-img2vid-xt | 图生视频 | ~5 GB |

模型自动下载到 `models/` 目录，也可手动放入。

## 使用

### 启动 GUI

```bash
# 沙箱方式（推荐 — 双击即可）
run.bat

# 或手动方式
venv\Scripts\activate
python main.py
```

### 快速打包为独立 exe 文件夹

```bash
pip install pyinstaller
pyinstaller build.spec
# 输出在 dist\NVIDIA_AI_Video_Toolkit\
```

### 命令行查看 GPU 状态

```bash
python main.py --info
```

### 界面说明

1. **视频画质增强** — 拖入视频 → 选择模型和放大倍数 → 点击"开始增强"
2. **图片生视频** — 两个子页：
   - *单图生成视频*: 拖入图片 → 设置帧数/动态幅度 → 生成 AI 短视频
   - *图片序列合成*: 拖入图片文件夹 → 设置帧率/分辨率 → 合成视频
3. **设置** — 配置模型路径、输出目录、GPU 和精度

## 项目结构

```
nvidia-video-toolkit/
├── setup.bat                  # 沙箱一键安装脚本
├── run.bat                    # 沙箱一键启动脚本
├── main.py                    # 应用入口
├── requirements.txt           # Python 依赖
├── core/
│   ├── gpu_utils.py           # GPU 检测与工具
│   ├── enhance.py             # 视频超分引擎 (Real-ESRGAN)
│   ├── img2video_svd.py       # 单图生视频 (Stable Video Diffusion)
│   └── sequence.py            # 图片序列合成 (FFmpeg)
├── gui/
│   ├── main_window.py         # 主窗口
│   ├── enhance_tab.py         # 视频增强 Tab
│   ├── img2video_tab.py       # 图片生视频 Tab
│   ├── settings_tab.py        # 设置 Tab
│   └── widgets/               # UI 组件
│       ├── drop_zone.py       # 拖放区域
│       ├── progress.py        # 进度面板
│       └── preview.py         # 预览组件
├── models/                    # AI 模型存放
├── output/                    # 默认输出目录
└── assets/                    # 图标资源
```

## 打包为 exe

```bash
pip install pyinstaller
pyinstaller build.spec
```

输出在 `dist/NVIDIA_AI_Video_Toolkit/` 目录。

## 常见问题

**Q: 提示 "CUDA 不可用"**
- 确保已安装 NVIDIA 显卡驱动
- 安装 CUDA 版 PyTorch：`pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121`

**Q: 图生视频时 VRAM 不足**
- 使用 `svd`（基础版 14 帧）代替 `svd_xt` (25 帧)
- 关闭其他占用 GPU 的程序
- 在设置中将精度改为 FP16

**Q: FFmpeg 编码失败**
- 确保 FFmpeg 在 PATH 中：`ffmpeg -version`
- 或在设置中手动指定 FFmpeg 路径
- NVENC 不可用时，应用会自动回退到 CPU 编码 (libx264)

## License

MIT
