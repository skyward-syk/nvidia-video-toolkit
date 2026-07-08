"""
视频画质增强 Tab
"""
from __future__ import annotations

import os
import threading
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QPushButton, QComboBox, QDoubleSpinBox,
    QSpinBox, QCheckBox, QFileDialog, QLineEdit,
    QMessageBox,
)
from PySide6.QtCore import Qt, Signal

from gui.widgets.preview import PreviewLabel
from gui.widgets.progress import ProgressPanel
from gui.widgets.drop_zone import DropZone
from core.enhance import AVAILABLE_MODELS, NVENC_ENCODERS, enhance_video, get_video_info
from core.gpu_utils import SystemInfo


class EnhanceTab(QWidget):
    """视频画质增强页面"""

    # 跨线程进度信号
    progress_signal = Signal(int, int, str)
    done_signal = Signal(dict)

    def __init__(self, gpu_info: SystemInfo, logger, parent=None):
        super().__init__(parent)
        self.gpu_info = gpu_info
        self.logger = logger
        self._input_path: Optional[str] = None
        self._running = False

        self._setup_ui()

        # 连接信号
        self.progress_signal.connect(self._on_progress)
        self.done_signal.connect(self._on_done)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # === 输入区 ===
        input_group = QGroupBox("1. 输入视频")
        input_layout = QVBoxLayout(input_group)

        self.drop_zone = DropZone("拖放视频文件到此处\n或点击选择 (mp4 / avi / mkv / mov)")
        self.drop_zone.file_dropped.connect(self._on_file_selected)
        input_layout.addWidget(self.drop_zone)

        file_row = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        self.path_edit.setPlaceholderText("未选择文件...")
        file_row.addWidget(self.path_edit)

        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self._browse_file)
        file_row.addWidget(browse_btn)
        input_layout.addLayout(file_row)

        # 视频信息
        self.info_label = QLabel("")
        self.info_label.setStyleSheet("color: #888; font-size: 12px;")
        input_layout.addWidget(self.info_label)

        layout.addWidget(input_group)

        # === 参数区 ===
        param_group = QGroupBox("2. 增强参数")
        param_layout = QVBoxLayout(param_group)

        # 模型选择
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("超分模型:"))
        self.model_combo = QComboBox()
        for name, desc in AVAILABLE_MODELS.items():
            self.model_combo.addItem(f"{name} — {desc}", name)
        self.model_combo.setCurrentIndex(0)
        row1.addWidget(self.model_combo, 1)
        param_layout.addLayout(row1)

        # 放大倍数 + 编码器
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("放大倍数:"))
        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(1.0, 4.0)
        self.scale_spin.setValue(4.0)
        self.scale_spin.setSingleStep(1.0)
        row2.addWidget(self.scale_spin)

        row2.addSpacing(20)
        row2.addWidget(QLabel("编码器:"))
        self.encoder_combo = QComboBox()
        for label, enc in NVENC_ENCODERS.items():
            self.encoder_combo.addItem(f"{label} ({enc})", enc)
        # 如果 NVENC 不可用，增加 CPU 回退
        if not self.gpu_info.nvenc_available:
            self.encoder_combo.addItem("CPU (libx264)", "libx264")
        self.encoder_combo.setCurrentIndex(0)
        row2.addWidget(self.encoder_combo, 1)
        param_layout.addLayout(row2)

        # CRF + Tile
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("CRF 质量:"))
        self.crf_spin = QSpinBox()
        self.crf_spin.setRange(1, 51)
        self.crf_spin.setValue(18)
        self.crf_spin.setToolTip("越小质量越好，NVENC 建议 18-23")
        row3.addWidget(self.crf_spin)

        row3.addSpacing(20)
        row3.addWidget(QLabel("分块大小:"))
        self.tile_spin = QSpinBox()
        self.tile_spin.setRange(100, 1000)
        self.tile_spin.setValue(400)
        self.tile_spin.setToolTip("VRAM 不足时减小此值")
        row3.addWidget(self.tile_spin)
        param_layout.addLayout(row3)

        # 选项
        row4 = QHBoxLayout()
        self.keep_audio_cb = QCheckBox("保留原始音频")
        self.keep_audio_cb.setChecked(True)
        row4.addWidget(self.keep_audio_cb)

        self.fp32_cb = QCheckBox("强制 FP32（默认 FP16）")
        self.fp32_cb.setChecked(False)
        row4.addWidget(self.fp32_cb)
        row4.addStretch()
        param_layout.addLayout(row4)

        layout.addWidget(param_group)

        # === 输出区 ===
        out_group = QGroupBox("3. 输出")
        out_layout = QHBoxLayout(out_group)
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("自动生成输出路径...")
        out_layout.addWidget(self.output_edit)

        out_browse = QPushButton("选择...")
        out_browse.clicked.connect(self._browse_output)
        out_layout.addWidget(out_browse)
        layout.addWidget(out_group)

        # === 执行按钮 ===
        self.run_btn = QPushButton("▶  开始增强")
        self.run_btn.setMinimumHeight(40)
        self.run_btn.setStyleSheet("""
            QPushButton {
                background-color: #0a6;
                color: white;
                font-size: 16px;
                font-weight: bold;
                border-radius: 8px;
            }
            QPushButton:hover { background-color: #0c8; }
            QPushButton:disabled { background-color: #444; color: #888; }
        """)
        self.run_btn.clicked.connect(self._run_enhance)
        layout.addWidget(self.run_btn)

        # === 进度区 ===
        self.progress_panel = ProgressPanel()
        layout.addWidget(self.progress_panel)

        layout.addStretch()

    # ------------------------------------------------------------------
    # 事件处理
    # ------------------------------------------------------------------

    def _on_file_selected(self, path: str) -> None:
        self._input_path = path
        self.path_edit.setText(path)
        self.drop_zone.set_text(f"已选择:\n{os.path.basename(path)}")

        # 自动生成输出路径
        base, ext = os.path.splitext(path)
        default_out = f"{base}_enhanced{ext}"
        self.output_edit.setText(default_out)

        # 显示视频信息
        try:
            info = get_video_info(path)
            self.info_label.setText(
                f"分辨率: {info['width']}×{info['height']} | "
                f"帧率: {info['fps']:.2f} fps | "
                f"帧数: {info['frame_count']} | "
                f"时长: {info['duration']:.1f}s"
            )
        except Exception as e:
            self.info_label.setText(f"无法读取视频信息: {e}")

    def _browse_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择视频文件", "",
            "视频文件 (*.mp4 *.avi *.mkv *.mov *.webm);;所有文件 (*.*)"
        )
        if path:
            self._on_file_selected(path)

    def _browse_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "保存增强后的视频", "output/enhanced.mp4",
            "MP4 视频 (*.mp4);;所有文件 (*.*)"
        )
        if path:
            self.output_edit.setText(path)

    # ------------------------------------------------------------------
    # 增强执行
    # ------------------------------------------------------------------

    def _run_enhance(self) -> None:
        if self._running:
            return

        input_path = self._input_path
        if not input_path or not os.path.isfile(input_path):
            QMessageBox.warning(self, "错误", "请先选择输入视频文件")
            return

        output_path = self.output_edit.text().strip()
        if not output_path:
            output_path = os.path.splitext(input_path)[0] + "_enhanced.mp4"

        model = self.model_combo.currentData()
        outscale = self.scale_spin.value()
        encoder = self.encoder_combo.currentData()
        crf = self.crf_spin.value()
        keep_audio = self.keep_audio_cb.isChecked()
        fp32 = self.fp32_cb.isChecked()
        tile = self.tile_spin.value()

        self._running = True
        self.run_btn.setEnabled(False)
        self.run_btn.setText("处理中...")
        self.progress_panel.reset()

        # 后台线程执行
        def worker():
            try:
                result = enhance_video(
                    input_path=input_path,
                    output_path=output_path,
                    model_name=model,
                    outscale=outscale,
                    encoder=encoder,
                    crf=crf,
                    keep_audio=keep_audio,
                    fp32=fp32,
                    tile_size=tile,
                    progress_callback=lambda c, t, s: self.progress_signal.emit(c, t, s),
                )
                self.done_signal.emit(result)
            except Exception as e:
                self.done_signal.emit({"error": str(e)})

        threading.Thread(target=worker, daemon=True).start()

    def _on_progress(self, current: int, total: int, status: str) -> None:
        self.progress_panel.update_progress(current, total, status)

    def _on_done(self, result: dict) -> None:
        self._running = False
        self.run_btn.setEnabled(True)
        self.run_btn.setText("▶  开始增强")

        if "error" in result:
            QMessageBox.critical(self, "增强失败", result["error"])
            self.progress_panel.update_progress(0, 100, f"失败: {result['error']}")
        else:
            elapsed = result.get("time_seconds", 0)
            frames = result.get("total_frames", 0)
            self.progress_panel.update_progress(
                100, 100,
                f"✅ 完成！输出: {result['output']} | {frames} 帧 | 耗时 {elapsed:.1f}s"
            )
            QMessageBox.information(
                self, "增强完成",
                f"视频增强完成！\n\n"
                f"输出: {result['output']}\n"
                f"帧数: {frames}\n"
                f"分辨率: {result.get('output_width', '?')}×{result.get('output_height', '?')}\n"
                f"耗时: {elapsed:.1f} 秒"
            )
