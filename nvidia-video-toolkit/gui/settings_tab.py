"""
设置 Tab
"""

from __future__ import annotations

import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QPushButton, QComboBox, QLineEdit,
    QFileDialog, QTextEdit,
)
from PySide6.QtCore import Qt

from core.gpu_utils import SystemInfo, gpu_summary


class SettingsTab(QWidget):
    """设置页面"""

    def __init__(self, gpu_info: SystemInfo, logger, parent=None):
        super().__init__(parent)
        self.gpu_info = gpu_info
        self.logger = logger

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # === GPU 信息 ===
        gpu_group = QGroupBox("GPU 状态")
        gpu_layout = QVBoxLayout(gpu_group)

        self.gpu_text = QTextEdit()
        self.gpu_text.setReadOnly(True)
        self.gpu_text.setMaximumHeight(200)
        self.gpu_text.setStyleSheet("""
            QTextEdit {
                background-color: #111;
                color: #8c8;
                border: 1px solid #444;
                border-radius: 4px;
                font-family: Consolas, monospace;
                font-size: 12px;
            }
        """)
        self.gpu_text.setPlainText(gpu_summary(self.gpu_info))

        refresh_btn = QPushButton("🔄 刷新 GPU 信息")
        refresh_btn.clicked.connect(self._refresh_gpu)
        gpu_layout.addWidget(self.gpu_text)
        gpu_layout.addWidget(refresh_btn)
        layout.addWidget(gpu_group)

        # === 路径设置 ===
        path_group = QGroupBox("路径设置")
        path_layout = QVBoxLayout(path_group)

        # 模型目录
        r1 = QHBoxLayout()
        r1.addWidget(QLabel("模型目录:"))
        self.model_dir_edit = QLineEdit()
        default_models = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "models"
        )
        self.model_dir_edit.setText(default_models)
        r1.addWidget(self.model_dir_edit)
        mb = QPushButton("浏览...")
        mb.clicked.connect(lambda: self._browse_dir(self.model_dir_edit))
        r1.addWidget(mb)
        path_layout.addLayout(r1)

        # 输出目录
        r2 = QHBoxLayout()
        r2.addWidget(QLabel("默认输出目录:"))
        self.output_dir_edit = QLineEdit()
        default_output = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "output"
        )
        self.output_dir_edit.setText(default_output)
        r2.addWidget(self.output_dir_edit)
        ob = QPushButton("浏览...")
        ob.clicked.connect(lambda: self._browse_dir(self.output_dir_edit))
        r2.addWidget(ob)
        path_layout.addLayout(r2)

        # FFmpeg 路径
        r3 = QHBoxLayout()
        r3.addWidget(QLabel("FFmpeg 路径:"))
        self.ffmpeg_edit = QLineEdit()
        self.ffmpeg_edit.setText("ffmpeg")
        self.ffmpeg_edit.setPlaceholderText("ffmpeg 或完整路径")
        r3.addWidget(self.ffmpeg_edit)
        fb = QPushButton("浏览...")
        fb.clicked.connect(self._browse_ffmpeg)
        r3.addWidget(fb)
        path_layout.addLayout(r3)

        layout.addWidget(path_group)

        # === 推理设置 ===
        infer_group = QGroupBox("推理设置")
        infer_layout = QVBoxLayout(infer_group)

        r4 = QHBoxLayout()
        r4.addWidget(QLabel("默认 GPU:"))
        self.gpu_combo = QComboBox()
        for g in self.gpu_info.gpus:
            self.gpu_combo.addItem(f"GPU #{g.index}: {g.name} ({g.vram_gb:.1f} GB)", g.index)
        if self.gpu_combo.count() == 0:
            self.gpu_combo.addItem("无可用 GPU", -1)
        infer_layout.addWidget(self.gpu_combo)
        infer_layout.addStretch()

        r5 = QHBoxLayout()
        r5.addWidget(QLabel("默认精度:"))
        self.precision_combo = QComboBox()
        self.precision_combo.addItem("自动（根据 VRAM）", "auto")
        self.precision_combo.addItem("FP16（推荐）", "fp16")
        self.precision_combo.addItem("FP32", "fp32")
        infer_layout.addWidget(self.precision_combo)
        infer_layout.addStretch()

        layout.addWidget(infer_group)

        layout.addStretch()

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    def _refresh_gpu(self) -> None:
        from core.gpu_utils import detect_gpu_info
        self.gpu_info = detect_gpu_info()
        self.gpu_text.setPlainText(gpu_summary(self.gpu_info))

        # 更新 GPU 下拉框
        self.gpu_combo.clear()
        for g in self.gpu_info.gpus:
            self.gpu_combo.addItem(f"GPU #{g.index}: {g.name} ({g.vram_gb:.1f} GB)", g.index)
        if self.gpu_combo.count() == 0:
            self.gpu_combo.addItem("无可用 GPU", -1)

    def _browse_dir(self, edit: QLineEdit) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择目录")
        if path:
            edit.setText(path)

    def _browse_ffmpeg(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 FFmpeg 可执行文件", "",
            "可执行文件 (*.exe);;所有文件 (*.*)"
        )
        if path:
            self.ffmpeg_edit.setText(path)

    # ------------------------------------------------------------------
    # 获取当前设置
    # ------------------------------------------------------------------

    def get_model_dir(self) -> str:
        return self.model_dir_edit.text().strip()

    def get_output_dir(self) -> str:
        return self.output_dir_edit.text().strip()

    def get_ffmpeg_path(self) -> str:
        return self.ffmpeg_edit.text().strip()

    def get_gpu_id(self) -> int:
        return self.gpu_combo.currentData() or 0

    def get_precision(self) -> str:
        return self.precision_combo.currentData()
