"""
视频画质增强引擎
基于 Real-ESRGAN + FFmpeg 的完整流水线：
  1. FFmpeg 拆帧（同时提取音频）
  2. Real-ESRGAN 逐帧超分辨率
  3. FFmpeg 合成增强后的帧 + 原始音频
  4. 支持 NVIDIA NVENC 硬件编码加速

依赖：
  - realesrgan  (pip install realesrgan)
  - ffmpeg       (系统 PATH 或指定路径)
  - opencv-python, numpy, Pillow
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional, Callable

import numpy as np

# cv2 和 PIL 在需要时才导入，避免模块级导入失败阻塞其他功能
_cv2 = None
_PIL_Image = None

def _get_cv2():
    global _cv2
    if _cv2 is None:
        import cv2 as _cv2_module
        _cv2 = _cv2_module
    return _cv2

def _get_Image():
    global _PIL_Image
    if _PIL_Image is None:
        from PIL import Image as _PIL_Image_module
        _PIL_Image = _PIL_Image_module
    return _PIL_Image

logger = logging.getLogger("NvidiaVideoToolkit.Enhance")


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

# Real-ESRGAN 可用模型（名称 → 描述）
AVAILABLE_MODELS: dict[str, str] = {
    "RealESRGAN_x4plus":       "通用 4x 超分（推荐）",
    "RealESRGAN_x2plus":       "通用 2x 超分",
    "RealESRNet_x4plus":       "4x 超分（仅提升分辨率，不降噪）",
    "RealESRGAN_x4plus_anime": "动漫专用 4x 超分",
    "realesr-animevideov3":    "动漫视频 4x 超分 v3",
}

# NVENC 编码器预设
NVENC_ENCODERS = {
    "h264": "h264_nvenc",
    "hevc": "hevc_nvenc",
    "av1":  "av1_nvenc",
}


# ---------------------------------------------------------------------------
# 视频信息
# ---------------------------------------------------------------------------

def get_video_info(video_path: str) -> dict:
    """获取视频基本参数"""
    cv2 = _get_cv2()
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"无法打开视频文件: {video_path}")

    info = {
        "width":       int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height":      int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        "fps":         cap.get(cv2.CAP_PROP_FPS),
        "frame_count": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        "duration":    cap.get(cv2.CAP_PROP_FRAME_COUNT) / max(cap.get(cv2.CAP_PROP_FPS), 1),
    }
    cap.release()
    return info


# ---------------------------------------------------------------------------
# FFmpeg 拆帧
# ---------------------------------------------------------------------------

def _extract_frames(
    video_path: str,
    output_dir: str,
    quality: int = 2,    # PNG 质量：0-9，越低越好
) -> list[str]:
    """用 FFmpeg 将视频拆为 PNG 帧序列，返回帧文件路径列表"""
    os.makedirs(output_dir, exist_ok=True)
    pattern = os.path.join(output_dir, "frame_%06d.png")

    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", video_path,
        "-q:v", str(quality),
        pattern,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg 拆帧失败: {result.stderr}")

    frames = sorted(Path(output_dir).glob("frame_*.png"))
    return [str(f) for f in frames]


def _extract_audio(video_path: str, output_path: str) -> bool:
    """从视频中提取音频为 AAC，成功返回 True"""
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", video_path,
        "-vn", "-acodec", "aac",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


# ---------------------------------------------------------------------------
# Real-ESRGAN 超分
# ---------------------------------------------------------------------------

class RealESRGANEnhancer:
    """Real-ESRGAN 增强器封装"""

    def __init__(
        self,
        model_name: str = "RealESRGAN_x4plus",
        outscale: float = 4.0,
        tile_size: int = 400,
        tile_pad: int = 10,
        pre_pad: int = 0,
        fp32: bool = False,
        gpu_id: int = 0,
    ):
        self.model_name = model_name
        self.outscale = outscale
        self.tile_size = tile_size
        self.tile_pad = tile_pad
        self.pre_pad = pre_pad
        self.fp32 = fp32
        self.gpu_id = gpu_id
        self._upsampler = None

    def load(self) -> None:
        """加载 Real-ESRGAN 模型"""
        if self._upsampler is not None:
            return

        logger.info("正在加载 Real-ESRGAN 模型: %s", self.model_name)
        try:
            from realesrgan import RealESRGANer
            from basicsr.archs.rrdbnet_arch import RRDBNet

            # 根据模型名选择架构
            if "anime" in self.model_name.lower():
                # 动漫模型使用不同的架构和 tile 策略
                model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=6, num_grow_ch=32, scale=4)
                netscale = 4
            else:
                model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
                netscale = 4

            # 推断模型路径
            model_path = self._find_model_path(self.model_name)

            self._upsampler = RealESRGANer(
                scale=netscale,
                model_path=model_path,
                model=model,
                tile=self.tile_size,
                tile_pad=self.tile_pad,
                pre_pad=self.pre_pad,
                half=not self.fp32,
                gpu_id=self.gpu_id,
            )
            logger.info("Real-ESRGAN 模型加载完成")
        except Exception as e:
            logger.error("加载 Real-ESRGAN 失败: %s", e)
            raise

    def _find_model_path(self, model_name: str) -> Optional[str]:
        """查找模型文件路径（先查本地 models/，再查 realesrgan 包自带）"""
        # 1) 项目本地 models/ 目录
        local = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "models", f"{model_name}.pth"
        )
        if os.path.isfile(local):
            return local

        # 2) realesrgan 包自带的 weights 目录
        try:
            import realesrgan
            pkg_dir = os.path.dirname(realesrgan.__file__)
            weights_dir = os.path.join(pkg_dir, "weights")
            for f in os.listdir(weights_dir):
                if model_name in f and f.endswith(".pth"):
                    return os.path.join(weights_dir, f)
        except Exception:
            pass

        # 3) 回退：让 RealESRGANer 自动下载
        return None

    def enhance_image(self, image: np.ndarray) -> np.ndarray:
        """对单张图片（BGR numpy array）进行超分"""
        if self._upsampler is None:
            self.load()

        output, _ = self._upsampler.enhance(image, outscale=self.outscale)
        return output

    def enhance_frame_file(self, input_path: str, output_path: str) -> None:
        """增强单帧并保存"""
        cv2 = _get_cv2()
        img = cv2.imread(input_path, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError(f"无法读取图片: {input_path}")
        enhanced = self.enhance_image(img)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        _get_cv2().imwrite(output_path, enhanced)

    def unload(self) -> None:
        """释放模型显存"""
        self._upsampler = None
        import gc
        gc.collect()
        try:
            import torch
            torch.cuda.empty_cache()
        except ImportError:
            pass


# ---------------------------------------------------------------------------
# 增强后合成视频
# ---------------------------------------------------------------------------

def _compose_video(
    frames_dir: str,
    output_path: str,
    fps: float,
    width: int,
    height: int,
    audio_path: Optional[str] = None,
    encoder: str = "h264_nvenc",
    crf: int = 18,
    preset: str = "p4",
) -> None:
    """用 FFmpeg 将帧序列合成为视频，可选合入音频"""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "warning",
        "-framerate", str(fps),
        "-i", os.path.join(frames_dir, "enhanced_%06d.png"),
    ]

    # 音频
    if audio_path and os.path.isfile(audio_path):
        cmd += ["-i", audio_path]

    # 视频编码
    cmd += [
        "-c:v", encoder,
        "-preset", preset,
        "-crf", str(crf),
        "-pix_fmt", "yuv420p",
        "-vf", f"scale={width}:{height}:flags=lanczos",
    ]

    if audio_path and os.path.isfile(audio_path):
        cmd += ["-c:a", "aac", "-b:a", "192k", "-shortest"]

    cmd.append(output_path)

    logger.info("正在合成视频: %s", output_path)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg 合成视频失败: {result.stderr}")


# ---------------------------------------------------------------------------
# 完整流水线
# ---------------------------------------------------------------------------

def enhance_video(
    input_path: str,
    output_path: str,
    model_name: str = "RealESRGAN_x4plus",
    outscale: float = 2.0,
    encoder: str = "h264_nvenc",
    crf: int = 18,
    keep_audio: bool = True,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    fp32: bool = False,
    gpu_id: int = 0,
    tile_size: int = 400,
) -> dict:
    """
    完整视频增强流水线

    参数:
        input_path:        输入视频路径
        output_path:       输出视频路径
        model_name:        Real-ESRGAN 模型名
        outscale:          放大倍数（2.0 或 4.0）
        encoder:           FFmpeg 视频编码器（h264_nvenc / hevc_nvenc / libx264）
        crf:               CRF 质量（越小越好，NVENC 推荐 18-23）
        keep_audio:        是否保留原始音频
        progress_callback: 进度回调 (current, total, status_text)
        fp32:              强制 fp32（否则默认 fp16）
        gpu_id:            CUDA 设备 ID
        tile_size:         Real-ESRGAN tile 大小（VRAM 不足时减小）

    返回:
        dict: {"output": output_path, "time_seconds": ..., "total_frames": ...}
    """
    start_time = time.time()

    # --- 1. 获取视频信息 ---
    info = get_video_info(input_path)
    logger.info(
        "视频信息: %dx%d @ %.2f fps, %d 帧",
        info["width"], info["height"], info["fps"], info["frame_count"]
    )
    if progress_callback:
        progress_callback(0, info["frame_count"], "分析视频信息...")

    # --- 2. 创建临时目录 ---
    tmpdir = tempfile.mkdtemp(prefix="nvt_enhance_")
    frames_raw_dir = os.path.join(tmpdir, "raw")
    frames_enhanced_dir = os.path.join(tmpdir, "enhanced")
    audio_path = os.path.join(tmpdir, "audio.aac")

    try:
        # --- 3. 拆帧 ---
        if progress_callback:
            progress_callback(0, info["frame_count"], "正在拆帧...")
        raw_frames = _extract_frames(input_path, frames_raw_dir)
        logger.info("拆帧完成: %d 帧", len(raw_frames))

        # --- 4. 提取音频 ---
        has_audio = False
        if keep_audio:
            has_audio = _extract_audio(input_path, audio_path)
            if has_audio:
                logger.info("音频提取成功")
            else:
                logger.warning("未提取到音频（可能视频本无音频轨）")

        # --- 5. 加载模型 ---
        if progress_callback:
            progress_callback(0, info["frame_count"], "加载 Real-ESRGAN 模型...")
        enhancer = RealESRGANEnhancer(
            model_name=model_name,
            outscale=outscale,
            tile_size=tile_size,
            fp32=fp32,
            gpu_id=gpu_id,
        )
        enhancer.load()

        # --- 6. 逐帧超分 ---
        os.makedirs(frames_enhanced_dir, exist_ok=True)
        total = len(raw_frames)

        for idx, frame_path in enumerate(raw_frames):
            basename = os.path.basename(frame_path)
            out_frame = os.path.join(frames_enhanced_dir, basename)

            enhancer.enhance_frame_file(frame_path, out_frame)

            if progress_callback and (idx % 5 == 0 or idx == total - 1):
                eta = (time.time() - start_time) / (idx + 1) * (total - idx - 1) if idx > 0 else 0
                status = f"超分处理中... {idx + 1}/{total} | 预计剩余 {eta:.0f}s"
                progress_callback(idx + 1, total, status)

        enhancer.unload()

        # --- 7. 获取增强后的分辨率 ---
        if raw_frames:
            cv2 = _get_cv2()
            sample = cv2.imread(os.path.join(frames_enhanced_dir, os.path.basename(raw_frames[0])))
            out_h, out_w = sample.shape[:2]
        else:
            out_w, out_h = int(info["width"] * outscale), int(info["height"] * outscale)

        # --- 8. 合成视频 ---
        if progress_callback:
            progress_callback(total, total, "正在合成视频...")
        _compose_video(
            frames_dir=frames_enhanced_dir,
            output_path=output_path,
            fps=info["fps"],
            width=out_w,
            height=out_h,
            audio_path=audio_path if has_audio else None,
            encoder=encoder,
            crf=crf,
        )

        elapsed = time.time() - start_time
        logger.info("视频增强完成: %s (%.1f 秒)", output_path, elapsed)

        if progress_callback:
            progress_callback(total, total, f"完成！耗时 {elapsed:.1f} 秒")

        return {
            "output": output_path,
            "time_seconds": elapsed,
            "total_frames": total,
            "output_width": out_w,
            "output_height": out_h,
        }

    finally:
        # 清理临时目录
        shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# 自检
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Real-ESRGAN 可用模型:")
    for name, desc in AVAILABLE_MODELS.items():
        print(f"  {name:<30s} — {desc}")

    print("\nNVENC 编码器:")
    for name, enc in NVENC_ENCODERS.items():
        print(f"  {name:<10s} — {enc}")
