"""
GPU 检测与 NVIDIA 加速基础工具
- 检测 NVIDIA GPU（型号、VRAM、CUDA 版本）
- 检查 NVENC 可用性（用于 FFmpeg 硬件编码）
- 根据 VRAM 自动选择模型精度（fp16 / fp32）
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass
class GPUInfo:
    """单块 GPU 的信息"""
    index: int = 0
    name: str = ""
    vram_mb: int = 0
    cuda_version: str = ""
    compute_capability: str = ""

    @property
    def vram_gb(self) -> float:
        return self.vram_mb / 1024.0

    @property
    def is_nvidia(self) -> bool:
        return "nvidia" in self.name.lower() or self.cuda_version != ""


@dataclass
class SystemInfo:
    """系统 GPU 综合信息"""
    gpus: list[GPUInfo] = field(default_factory=list)
    cuda_available: bool = False
    cuda_version: str = ""
    nvenc_available: bool = False
    ffmpeg_available: bool = False
    ffmpeg_path: str = ""

    @property
    def has_gpu(self) -> bool:
        return len(self.gpus) > 0

    @property
    def best_gpu(self) -> Optional[GPUInfo]:
        """返回 VRAM 最大的 GPU"""
        if not self.gpus:
            return None
        return max(self.gpus, key=lambda g: g.vram_mb)

    @property
    def can_use_fp16(self) -> bool:
        """VRAM >= 8 GB 时建议使用 fp16"""
        best = self.best_gpu
        return best is not None and best.vram_gb >= 8.0


# ---------------------------------------------------------------------------
# 检测函数
# ---------------------------------------------------------------------------

def _run(cmd: list[str]) -> tuple[int, str, str]:
    """运行命令，返回 (returncode, stdout, stderr)"""
    try:
        p = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except FileNotFoundError:
        return -1, "", "command not found"
    except Exception as e:
        return -1, "", str(e)


def detect_gpu_info() -> SystemInfo:
    """全面检测 GPU、CUDA 和 NVENC 状态"""
    info = SystemInfo()

    # ---- 1. 通过 PyTorch 检测 CUDA ----
    try:
        import torch
        info.cuda_available = torch.cuda.is_available()
        if info.cuda_available:
            info.cuda_version = torch.version.cuda or ""
            for i in range(torch.cuda.device_count()):
                props = torch.cuda.get_device_properties(i)
                g = GPUInfo(
                    index=i,
                    name=props.name,
                    vram_mb=props.total_memory // (1024 * 1024),
                    cuda_version=info.cuda_version,
                    compute_capability=f"{props.major}.{props.minor}",
                )
                info.gpus.append(g)
    except ImportError:
        pass

    # ---- 2. 回退：通过 nvidia-smi 检测 GPU ----
    if not info.gpus:
        rc, out, _ = _run(["nvidia-smi", "--query-gpu=index,name,memory.total", "--format=csv,noheader,nounits"])
        if rc == 0:
            for line in out.splitlines():
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 3:
                    try:
                        g = GPUInfo(
                            index=int(parts[0]),
                            name=parts[1],
                            vram_mb=int(parts[2]),
                        )
                        info.gpus.append(g)
                    except ValueError:
                        continue

    # ---- 3. 检测 NVENC 编码器 ----
    if info.has_gpu:
        rc, out, _ = _run(["ffmpeg", "-hide_banner", "-encoders"])
        if rc == 0:
            info.nvenc_available = "h264_nvenc" in out or "hevc_nvenc" in out

    # ---- 4. 检测 FFmpeg 可用性 ----
    rc, out, _ = _run(["ffmpeg", "-version"])
    if rc == 0:
        info.ffmpeg_available = True
        info.ffmpeg_path = "ffmpeg"  # PATH 中的 ffmpeg

    return info


def get_recommended_precision(info: SystemInfo) -> str:
    """根据 GPU 返回推荐的推理精度"""
    if not info.cuda_available:
        return "fp32"               # CPU fallback
    best = info.best_gpu
    if best is None:
        return "fp32"
    if best.vram_gb >= 12:
        return "fp16"
    if best.vram_gb >= 6:
        return "fp16"               # SVD 需要较大 VRAM，但 6-8G 可尝试
    return "fp32"


def check_nvenc_presets() -> list[str]:
    """返回可用的 NVENC 编码器预设列表"""
    presets = []
    rc, out, _ = _run(["ffmpeg", "-hide_banner", "-encoders"])
    if rc != 0:
        return presets
    for codec in ["h264_nvenc", "hevc_nvenc", "av1_nvenc"]:
        if codec in out:
            presets.append(codec)
    return presets


# ---------------------------------------------------------------------------
# 便捷函数
# ---------------------------------------------------------------------------

def gpu_summary(info: Optional[SystemInfo] = None) -> str:
    """返回 GPU 状态的可读摘要"""
    if info is None:
        info = detect_gpu_info()

    lines = []
    lines.append("=" * 50)
    lines.append("  NVIDIA GPU / CUDA 状态")
    lines.append("=" * 50)

    if not info.has_gpu:
        lines.append("  [警告] 未检测到 NVIDIA GPU")
    else:
        for g in info.gpus:
            lines.append(f"  GPU #{g.index}: {g.name}")
            lines.append(f"        VRAM: {g.vram_mb} MB ({g.vram_gb:.1f} GB)")
            if g.compute_capability:
                lines.append(f"        Compute Capability: {g.compute_capability}")

    lines.append(f"  CUDA 可用: {info.cuda_available}")
    if info.cuda_version:
        lines.append(f"  CUDA 版本: {info.cuda_version}")
    lines.append(f"  NVENC 可用: {info.nvenc_available}")
    lines.append(f"  FFmpeg 可用: {info.ffmpeg_available}")
    lines.append(f"  推荐精度: {get_recommended_precision(info)}")
    lines.append("=" * 50)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 自检入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    info = detect_gpu_info()
    print(gpu_summary(info))
