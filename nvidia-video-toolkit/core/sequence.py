"""
图片序列合成视频模块
基于 FFmpeg 将图片序列合成为视频文件

功能:
  - 支持 glob 模式匹配图片序列
  - 自动排序（按文件名数字或自然顺序）
  - NVIDIA NVENC 硬件编码
  - 可选缩放、帧率、过渡效果

依赖:
  - ffmpeg (系统 PATH)
"""

from __future__ import annotations

import glob as glob_mod
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional, Callable

logger = logging.getLogger("NvidiaVideoToolkit.Sequence")


# ---------------------------------------------------------------------------
# 图片发现与排序
# ---------------------------------------------------------------------------

def _natural_sort_key(name: str) -> list:
    """自然排序 key：将字符串中的数字按数值排序"""
    import re as _re
    return [
        int(part) if part.isdigit() else part.lower()
        for part in _re.split(r"(\d+)", name)
    ]


def discover_images(
    source: str,
    patterns: tuple = ("*.png", "*.jpg", "*.jpeg", "*.bmp", "*.tiff", "*.webp"),
    sort: str = "natural",    # "natural" | "name" | "mtime"
) -> list[str]:
    """
    发现并排序图片文件

    参数:
        source:   目录路径 或 glob 模式（如 "frames/*.png"）
        patterns: 当 source 是目录时，匹配的扩展名模式
        sort:     排序方式

    返回:
        排序后的图片路径列表
    """
    source_path = Path(source)

    if source_path.is_dir():
        # 目录模式：收集所有匹配的图片
        images = []
        for pattern in patterns:
            images.extend(str(p) for p in source_path.glob(pattern))
    else:
        # glob 模式
        if any(c in source for c in "*?["):
            images = [str(p) for p in Path().glob(source)]
        else:
            # 可能是文件列表
            images = [source] if source_path.is_file() else []

    if not images:
        raise FileNotFoundError(f"未找到图片文件: {source}")

    # 排序
    if sort == "natural":
        images.sort(key=lambda p: _natural_sort_key(os.path.basename(p)))
    elif sort == "mtime":
        images.sort(key=lambda p: os.path.getmtime(p))
    else:
        images.sort()

    logger.info("发现 %d 张图片 (排序: %s)", len(images), sort)
    return images


# ---------------------------------------------------------------------------
# 图片序列预处理
# ---------------------------------------------------------------------------

def _prepare_frames(
    images: list[str],
    output_dir: str,
    target_size: Optional[tuple[int, int]] = None,
    pad_to_size: bool = False,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> tuple[list[str], int, int]:
    """
    将图片序列复制/调整到统一命名格式，返回 (帧路径列表, width, height)

    如果 target_size 指定，会统一缩放；否则保持原始尺寸（最大尺寸对齐）
    """
    import shutil

    os.makedirs(output_dir, exist_ok=True)
    frames = []

    # 延迟导入 cv2
    try:
        import cv2
        has_cv2 = True
    except ImportError:
        has_cv2 = False

    total = len(images)
    max_w, max_h = 0, 0

    for idx, img_path in enumerate(images):
        out_name = f"seq_{idx:06d}.png"
        out_path = os.path.join(output_dir, out_name)

        if target_size or not has_cv2:
            # 简单复制（后续由 FFmpeg 做缩放）
            shutil.copy2(img_path, out_path)
            frames.append(out_path)
        else:
            # 用 OpenCV 统一处理
            img = cv2.imread(img_path)
            if img is None:
                shutil.copy2(img_path, out_path)
                frames.append(out_path)
                continue
            h, w = img.shape[:2]
            max_w = max(max_w, w)
            max_h = max(max_h, h)

            if target_size:
                tw, th = target_size
                if (w, h) != (tw, th):
                    img = cv2.resize(img, (tw, th), interpolation=cv2.INTER_LANCZOS4)
            cv2.imwrite(out_path, img)
            frames.append(out_path)

        if progress_callback and idx % 10 == 0:
            progress_callback(idx + 1, total, f"准备帧... {idx + 1}/{total}")

    # 确定输出尺寸
    if target_size:
        out_w, out_h = target_size
    elif has_cv2 and max_w > 0:
        out_w, out_h = max_w, max_h
    else:
        # 读取第一帧获取尺寸
        try:
            from PIL import Image
            with Image.open(frames[0]) as im:
                out_w, out_h = im.size
        except Exception:
            out_w, out_h = 1920, 1080

    return frames, out_w, out_h


# ---------------------------------------------------------------------------
# 视频合成
# ---------------------------------------------------------------------------

def _compose_from_frames(
    frames_dir: str,
    output_path: str,
    fps: float = 30.0,
    width: int = 1920,
    height: int = 1080,
    encoder: str = "h264_nvenc",
    crf: int = 20,
    preset: str = "p4",
    extra_ffmpeg_args: Optional[list[str]] = None,
) -> None:
    """内部函数：从帧目录合成视频"""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "warning",
        "-framerate", str(fps),
        "-i", os.path.join(frames_dir, "seq_%06d.png"),
        "-c:v", encoder,
        "-preset", preset,
        "-crf", str(crf),
        "-pix_fmt", "yuv420p",
        "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
    ]

    if extra_ffmpeg_args:
        cmd.extend(extra_ffmpeg_args)

    cmd.append(output_path)

    logger.info("合成视频: %dx%d @ %.2f fps → %s", width, height, fps, output_path)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg 合成失败: {result.stderr}")


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def images_to_video(
    source: str,
    output_path: str = "output/sequence.mp4",
    fps: float = 30.0,
    width: int = 1920,
    height: int = 1080,
    encoder: str = "h264_nvenc",
    crf: int = 20,
    sort: str = "natural",
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> dict:
    """
    将图片序列合成为视频

    参数:
        source:            图片目录 或 glob 模式（如 "frames/*.png"）
        output_path:       输出视频路径
        fps:               帧率
        width/height:      输出分辨率
        encoder:           FFmpeg 编码器
        crf:               CRF 质量值
        sort:              排序方式 ("natural" / "name" / "mtime")
        progress_callback: 进度回调

    返回:
        dict: {"output": ..., "total_frames": ..., "fps": ...}
    """
    import time
    start_time = time.time()

    # 1. 发现图片
    if progress_callback:
        progress_callback(0, 1, "扫描图片文件...")
    images = discover_images(source, sort=sort)
    total = len(images)

    if total == 0:
        raise ValueError("未找到任何图片文件")
    if total == 1:
        logger.warning("只有一张图片，将生成长度为 1 帧的视频")

    # 2. 准备帧
    tmpdir = os.path.join(
        tempfile := __import__("tempfile").mkdtemp(prefix="nvt_seq_"),
        "frames"
    )
    try:
        if progress_callback:
            progress_callback(0, total, "准备帧...")
        frames, detected_w, detected_h = _prepare_frames(
            images, tmpdir,
            progress_callback=progress_callback,
        )

        # 使用自动检测的尺寸（如果未指定）
        use_w = width if width > 0 else detected_w
        use_h = height if height > 0 else detected_h

        # 3. 合成视频
        if progress_callback:
            progress_callback(total, total, "合成视频...")
        _compose_from_frames(
            frames_dir=tmpdir,
            output_path=output_path,
            fps=fps,
            width=use_w,
            height=use_h,
            encoder=encoder,
            crf=crf,
        )

        elapsed = time.time() - start_time
        logger.info("序列合成完成: %s (%.1f 秒, %d 帧)", output_path, elapsed, total)

        if progress_callback:
            progress_callback(total, total, f"完成！{total} 帧，耗时 {elapsed:.1f}s")

        return {
            "output": output_path,
            "total_frames": total,
            "fps": fps,
            "width": use_w,
            "height": use_h,
            "time_seconds": elapsed,
        }

    finally:
        import shutil
        shutil.rmtree(os.path.dirname(tmpdir), ignore_errors=True)


# ---------------------------------------------------------------------------
# 便捷变体：带交叉淡入淡出
# ---------------------------------------------------------------------------

def images_to_video_with_transition(
    source: str,
    output_path: str = "output/sequence_trans.mp4",
    fps: float = 30.0,
    crossfade_frames: int = 15,
    encoder: str = "h264_nvenc",
    crf: int = 20,
    width: int = 1920,
    height: int = 1080,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> dict:
    """
    带交叉淡入淡出过渡的图片序列合成视频

    每两张相邻图片之间插入 crossfade_frames 帧的渐变过渡
    """
    import time
    import tempfile as _tmp
    import shutil as _shutil

    start_time = time.time()

    images = discover_images(source)
    total_images = len(images)

    if total_images < 2:
        # 图片不足，回退到普通合成
        return images_to_video(
            source, output_path, fps=fps, encoder=encoder, crf=crf,
            width=width, height=height,
            progress_callback=progress_callback,
        )

    tmpdir = _tmp.mkdtemp(prefix="nvt_seq_xfade_")
    try:
        # 制作每张图的"静止帧"片段（每段持续 1 秒）
        segments = []
        for i, img in enumerate(images):
            seg_path = os.path.join(tmpdir, f"seg_{i:04d}.mp4")
            _compose_single_image_video(img, seg_path, fps=fps, duration=1.0, encoder=encoder, crf=crf)
            segments.append(seg_path)

        # 用 xfade 串联
        _concat_with_xfade(segments, output_path, fps=fps, crossfade_frames=crossfade_frames)

        elapsed = time.time() - start_time
        logger.info("过渡视频合成完成: %s (%.1f 秒)", output_path, elapsed)

        return {
            "output": output_path,
            "total_images": total_images,
            "fps": fps,
            "width": width,
            "height": height,
            "time_seconds": elapsed,
        }

    finally:
        _shutil.rmtree(tmpdir, ignore_errors=True)


def _compose_single_image_video(
    image_path: str, output_path: str,
    fps: float, duration: float,
    encoder: str, crf: int,
) -> None:
    """将单张图片做成固定时长的小视频片段"""
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-loop", "1",
        "-i", image_path,
        "-t", str(duration),
        "-c:v", encoder,
        "-preset", "p4",
        "-crf", str(crf),
        "-pix_fmt", "yuv420p",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg 单图片段生成失败: {result.stderr}")


def _concat_with_xfade(
    segments: list[str],
    output_path: str,
    fps: float,
    crossfade_frames: int = 15,
) -> None:
    """使用 FFmpeg xfade 滤镜串联片段"""
    if len(segments) == 1:
        import shutil
        shutil.copy2(segments[0], output_path)
        return

    # 构建 filter_complex
    # xfade 需要先把每个 segment 作为输入
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "warning"]
    for seg in segments:
        cmd += ["-i", seg]

    # 构建 filter 链
    fade_duration = crossfade_frames / fps
    filter_parts = []
    last = "[0:v]"

    for i in range(1, len(segments)):
        out_label = f"[v{i}]" if i < len(segments) - 1 else "[vout]"
        offset = i * (1.0 - fade_duration)   # 每段 1 秒，减去重叠
        filter_parts.append(
            f"{last}[{i}:v]xfade=transition=fade:duration={fade_duration}:offset={offset}{out_label}"
        )
        last = out_label

    filter_complex = ";".join(filter_parts)

    cmd += [
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-c:v", "h264_nvenc",
        "-preset", "p4",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg xfade 串联失败: {result.stderr}")


# ---------------------------------------------------------------------------
# 自检
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    print("图片序列合成模块")
    print("用法: python sequence.py <图片目录|glob> [输出.mp4]")
    if len(sys.argv) > 1:
        src = sys.argv[1]
        out = sys.argv[2] if len(sys.argv) > 2 else "output/sequence.mp4"
        result = images_to_video(src, out)
        print(f"完成: {result}")
    else:
        print("示例: python sequence.py ./frames/ output/demo.mp4")
