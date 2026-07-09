"""
单图生成动态视频引擎
基于 Stability AI 的 Stable Video Diffusion (SVD) 模型

用法:
  from core.img2video_svd import ImageToVideoGenerator
  gen = ImageToVideoGenerator()
  gen.generate("input.jpg", "output.mp4", num_frames=25)

依赖：
  - diffusers, transformers, accelerate
  - torch (CUDA)
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional, Callable

import numpy as np

logger = logging.getLogger("NvidiaVideoToolkit.Img2Video")

# 延迟导入重型库
_torch = None
_diffusers = None
_PIL_Image = None


def _get_torch():
    global _torch
    if _torch is None:
        import torch
        _torch = torch
    return _torch


def _get_diffusers():
    global _diffusers
    if _diffusers is None:
        import diffusers
        _diffusers = diffusers
    return _diffusers


def _get_Image():
    global _PIL_Image
    if _PIL_Image is None:
        from PIL import Image
        _PIL_Image = Image
    return _PIL_Image


# ---------------------------------------------------------------------------
# 可用模型
# ---------------------------------------------------------------------------

MODEL_VARIANTS = {
    "svd": {
        "name": "stabilityai/stable-video-diffusion-img2vid",
        "desc": "SVD 基础版 — 14 帧生成，速度较快",
        "default_frames": 14,
    },
    "svd_xt": {
        "name": "stabilityai/stable-video-diffusion-img2vid-xt",
        "desc": "SVD XT 增强版 — 25 帧生成，质量更高",
        "default_frames": 25,
    },
    "svd_xt_1.1": {
        "name": "stabilityai/stable-video-diffusion-img2vid-xt-1-1",
        "desc": "SVD XT 1.1 — 最新 25 帧版本",
        "default_frames": 25,
    },
}


# ---------------------------------------------------------------------------
# 生成器
# ---------------------------------------------------------------------------

class ImageToVideoGenerator:
    """SVD 图生视频生成器"""

    def __init__(
        self,
        model_id: str = "svd_xt",
        device: str = "cuda",
        dtype: str = "auto",     # "fp16" / "fp32" / "auto"
        gpu_id: int = 0,
    ):
        self.model_id = model_id
        self.device = device
        self.dtype = dtype
        self.gpu_id = gpu_id
        self._pipe = None
        self._loaded = False

    @property
    def model_info(self) -> dict:
        return MODEL_VARIANTS.get(self.model_id, MODEL_VARIANTS["svd_xt"])

    def load(self) -> None:
        """加载 SVD pipeline"""
        if self._loaded:
            return

        torch = _get_torch()
        diffusers = _get_diffusers()

        model_cfg = self.model_info
        model_name = model_cfg["name"]
        logger.info("正在加载 SVD 模型: %s", model_name)

        # 决定精度
        if self.dtype == "auto":
            use_fp16 = (self.device == "cuda" and torch.cuda.is_available())
            torch_dtype = torch.float16 if use_fp16 else torch.float32
        elif self.dtype == "fp16":
            torch_dtype = torch.float16
        else:
            torch_dtype = torch.float32

        try:
            self._pipe = diffusers.StableVideoDiffusionPipeline.from_pretrained(
                model_name,
                torch_dtype=torch_dtype,
                variant="fp16" if torch_dtype == torch.float16 else None,
            )
            self._pipe.enable_model_cpu_offload()
            # 尝试启用内存高效注意力
            try:
                self._pipe.enable_vae_slicing()
                self._pipe.enable_vae_tiling()
            except Exception:
                pass

            self._loaded = True
            logger.info("SVD 模型加载完成 (精度: %s)", "fp16" if torch_dtype == torch.float16 else "fp32")

        except Exception as e:
            logger.error("SVD 模型加载失败: %s", e)
            raise

    def generate(
        self,
        image_path: str,
        output_path: str,
        num_frames: Optional[int] = None,
        fps: int = 7,
        decode_chunk_size: int = 8,
        motion_bucket_id: int = 127,
        noise_aug_strength: float = 0.02,
        seed: int = 42,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> dict:
        """
        从单张图片生成短视频

        参数:
            image_path:          输入图片路径
            output_path:         输出视频路径 (.mp4)
            num_frames:          生成帧数 (None=使用模型默认值)
            fps:                 输出视频帧率
            decode_chunk_size:   解码块大小（VRAM 不足时减小）
            motion_bucket_id:    动态幅度 (1-255，越大越剧烈)
            noise_aug_strength:  噪声增强强度 (0.0-1.0)
            seed:                随机种子
            progress_callback:   进度回调 (current, total, status)

        返回:
            dict: {"output": ..., "num_frames": ..., "time_seconds": ...}
        """
        import time
        start_time = time.time()

        torch = _get_torch()

        if not self._loaded:
            if progress_callback:
                progress_callback(0, 1, "加载 SVD 模型...")
            self.load()

        model_cfg = self.model_info
        if num_frames is None:
            num_frames = model_cfg["default_frames"]

        # 加载图片
        Image = _get_Image()
        image = Image.open(image_path).convert("RGB")

        # 调整图片尺寸为 SVD 推荐值
        image = self._resize_for_svd(image)

        logger.info(
            "开始生成: %d 帧, motion=%d, seed=%d",
            num_frames, motion_bucket_id, seed
        )

        if progress_callback:
            progress_callback(0, 1, f"生成 {num_frames} 帧中...")

        # 设置随机种子
        generator = torch.Generator(device=self.device).manual_seed(seed)

        with torch.inference_mode():
            frames = self._pipe(
                image,
                decode_chunk_size=decode_chunk_size,
                num_frames=num_frames,
                motion_bucket_id=motion_bucket_id,
                noise_aug_strength=noise_aug_strength,
                generator=generator,
            ).frames[0]

        if progress_callback:
            progress_callback(1, 1, f"合成视频 ({len(frames)} 帧)...")

        # 导出为视频
        self._frames_to_video(frames, output_path, fps=fps)

        elapsed = time.time() - start_time
        logger.info("视频生成完成: %s (%.1f 秒)", output_path, elapsed)

        if progress_callback:
            progress_callback(1, 1, f"完成！耗时 {elapsed:.1f} 秒")

        return {
            "output": output_path,
            "num_frames": len(frames),
            "time_seconds": elapsed,
            "output_width": frames[0].width,
            "output_height": frames[0].height,
        }

    def _resize_for_svd(self, image) -> object:
        """将图片尺寸调整为 SVD 友好的大小（宽高为 64 的倍数）"""
        w, h = image.size

        # SVD 最佳输入尺寸
        target_max = 1024
        if max(w, h) > target_max:
            scale = target_max / max(w, h)
            w, h = int(w * scale), int(h * scale)

        # 对齐到 64 的倍数
        w = (w // 64) * 64
        h = (h // 64) * 64
        w = max(w, 256)
        h = max(h, 256)

        if (w, h) != image.size:
            image = image.resize((w, h), _get_Image().LANCZOS)
            logger.info("图片已调整为 SVD 推荐尺寸: %dx%d", w, h)

        return image

    def _frames_to_video(
        self,
        frames: list,
        output_path: str,
        fps: int = 7,
    ) -> None:
        """将 PIL Image 帧列表导出为 MP4 视频"""
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        # 先保存帧到临时目录，再用 FFmpeg 合成
        tmpdir = tempfile.mkdtemp(prefix="nvt_svd_")
        try:
            for i, frame in enumerate(frames):
                frame_path = os.path.join(tmpdir, f"frame_{i:06d}.png")
                frame.save(frame_path)

            cmd = [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "warning",
                "-framerate", str(fps),
                "-i", os.path.join(tmpdir, "frame_%06d.png"),
                "-c:v", "libx264",    # SVD 输出通常不长，CPU 编码足够
                "-preset", "medium",
                "-crf", "18",
                "-pix_fmt", "yuv420p",
                output_path,
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"FFmpeg 合成失败: {result.stderr}")

        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def unload(self) -> None:
        """释放模型显存"""
        self._pipe = None
        self._loaded = False
        import gc
        gc.collect()
        try:
            _get_torch().cuda.empty_cache()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# 便捷函数
# ---------------------------------------------------------------------------

def generate_video_from_image(
    image_path: str,
    output_path: str = "output/svd_output.mp4",
    model_id: str = "svd_xt",
    num_frames: int = 25,
    fps: int = 7,
    motion_bucket_id: int = 127,
    seed: int = 42,
    gpu_id: int = 0,
) -> dict:
    """一键生成：图片 → 视频"""
    gen = ImageToVideoGenerator(
        model_id=model_id,
        device="cuda",
        gpu_id=gpu_id,
    )
    try:
        return gen.generate(
            image_path=image_path,
            output_path=output_path,
            num_frames=num_frames,
            fps=fps,
            motion_bucket_id=motion_bucket_id,
            seed=seed,
        )
    finally:
        gen.unload()


# ---------------------------------------------------------------------------
# 自检
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("SVD 可用模型变体:")
    for key, cfg in MODEL_VARIANTS.items():
        print(f"  {key:<12s} — {cfg['desc']}")
        print(f"              HuggingFace: {cfg['name']}")
        print(f"              默认帧数: {cfg['default_frames']}")
