# NVIDIA AI 视频工具套件

基于 NVIDIA GPU 加速的 AI 视频处理桌面应用。支持视频超分辨率增强、单图生成动态视频、图片序列合成视频。

---

## 功能一览

| 功能 | 说明 | 核心技术 |
|------|------|----------|
| 🎥 **视频画质增强** | 低分辨率视频 → 2x/4x 超分高清输出，保留原始音频 | Real-ESRGAN + CUDA + FFmpeg NVENC |
| 🎬 **单图生成视频** | 一张静态图片 → AI 生成动态短视频 | Stable Video Diffusion (SVD) |
| 📁 **图片序列合成** | 多张图片 → 视频文件，支持交叉淡入淡出过渡 | FFmpeg + NVENC |

---

## 项目结构

```
NVIDIA_AI_Video_Toolkit/
├── desktop/                    PySide6 桌面版
│   ├── start.bat               一键启动
│   ├── setup.bat               一键安装全部依赖
│   ├── check.bat               环境诊断
│   ├── download_models.py      AI 模型下载器
│   ├── main.py                 应用入口
│   ├── core/                   核心引擎
│   │   ├── gpu_utils.py        GPU / CUDA / 显存检测
│   │   ├── enhance.py          Real-ESRGAN 视频超分流水线
│   │   ├── img2video_svd.py    Stable Video Diffusion 图生视频
│   │   └── sequence.py         FFmpeg 序列合成
│   └── gui/                    界面层
│       ├── main_window.py      主窗口 + 暗色主题
│       ├── enhance_tab.py      视频增强页
│       ├── img2video_tab.py    图片生视频页
│       └── settings_tab.py     设置页
│
└── web/                        FastAPI Web 版
    ├── start.bat               一键启动 (自动打开浏览器)
    ├── setup.bat               一键安装
    ├── download_models.py      AI 模型下载器
    ├── server.py               后端 (REST API + WebSocket)
    ├── core/                   核心引擎 (同桌面版)
    └── static/                 前端 SPA
        ├── index.html          单页应用入口
        ├── css/style.css       暗色主题
        └── js/app.js           拖放上传 + WebSocket 实时进度
```

---

## 系统要求

| 组件 | 最低 | 推荐 |
|------|------|------|
| 操作系统 | Windows 10 | Windows 11 |
| GPU | NVIDIA RTX 2060 (6 GB) | RTX 4070+ (12 GB) |
| CUDA | 12.1+ | 12.8+ |
| Python | 3.10+ | 3.11 |
| FFmpeg | 4.4+ | 6.0+ |
| 内存 | 16 GB | 32 GB |
| 磁盘 | 30 GB (含模型) | SSD 50 GB+ |

> RTX 50 系列 (Blackwell) 需 PyTorch ≥ 2.11 + CUDA 12.8，setup.bat 已自动处理。

---

## 快速开始

### 桌面版

```batch
cd desktop
setup.bat            # 首次运行：一键安装全部依赖 (~10 分钟)
start.bat            # 启动 GUI
```

### Web 版

```batch
cd web
setup.bat            # 首次运行：一键安装
start.bat            # 启动服务器 → 自动打开浏览器 http://127.0.0.1:8765
```

### 下载 AI 模型

```bash
python download_models.py realesrgan    # 超分模型 (~67 MB)
python download_models.py svd           # SVD 图生视频模型 (~5 GB)
python download_models.py all           # 全部
```

> 模型支持断点续传；Real-ESRGAN 也可在首次使用时自动下载。

---

## 使用说明

### 视频画质增强

1. 拖入视频文件 (mp4/avi/mkv/mov)
2. 选择超分模型和放大倍数 (2x / 4x)
3. 调整参数：CRF 质量 (越小越好)、分块大小 (显存不足时减小)
4. 点击「开始增强」→ 自动拆帧 → 逐帧超分 → 合成输出
5. 处理中可点击红色停止按钮取消

### 单图生成 AI 视频

1. 拖入图片 (jpg/png/webp)
2. 选择模型 (svd 基础版 14 帧 / svd_xt 增强版 25 帧)
3. 调节动态幅度 (1 静止 ~ 255 剧烈)
4. 点击「开始生成」→ SVD 推理 → 合成视频

### 图片序列合成

1. 拖入图片文件夹
2. 设置输出帧率和分辨率
3. 点击「开始合成」→ FFmpeg 视频编码

---

## 界面截图

桌面版暗色主题，三 Tab 布局：

- 🎥 视频画质增强 — 文件拖放 + 参数面板 + 实时进度条
- 🖼️ 图片生视频 — SVD AI 生成 / 序列合成 两个子页
- ⚙️ 设置 — GPU 状态 + 路径配置 + 推理精度选择

Web 版同功能，浏览器运行，无需安装 PySide6。

---

## 打包为 exe

```bash
pip install pyinstaller
pyinstaller build.spec
# 输出: dist/NVIDIA_AI_Video_Toolkit.exe
```

---

## 常见问题

**Q: CUDA 不可用 / CUDA error: unknown error**
- 运行 `check.bat` 诊断
- RTX 50 系列需 PyTorch ≥ 2.11 + CUDA 12.8 (setup.bat 已处理)
- CUDA 错误后会自动重置上下文，重试即可

**Q: 显存不足 (8 GB 及以下)**
- 视频增强：减小分块大小到 128-200
- SVD：使用 svd 基础版 (14 帧) 而非 svd_xt
- 关闭其他 GPU 程序

**Q: SVD 模型下载失败 (HuggingFace 连接问题)**
- 运行 `python download_models.py svd` 使用自动镜像
- 手动：`set HF_ENDPOINT=https://hf-mirror.com`
- 手动下载放入 `models/svd_cache/`

**Q: 点启动没反应**
- 先运行 `setup.bat` 安装依赖
- 检查 `check.bat` 诊断结果
- FFmpeg 需要单独下载并加入 PATH

---

## 技术栈

| 层 | 桌面版 | Web 版 |
|----|--------|--------|
| GUI | PySide6 (Qt) | HTML5 + CSS3 + Vanilla JS |
| 后端 | 内置 | FastAPI + uvicorn |
| 实时通信 | Qt Signals 跨线程 | WebSocket |
| AI 推理 | PyTorch CUDA | PyTorch CUDA (同一套 core/) |
| 视频处理 | FFmpeg subprocess | FFmpeg subprocess |
| 打包 | PyInstaller 单文件 EXE | PyInstaller 单文件 EXE |
