"""
图片生视频 Tab
- 子页 A: 单图生成动态视频 (SVD)
- 子页 B: 图片序列合成视频
"""

from __future__ import annotations

import os
import threading
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QPushButton, QComboBox, QSpinBox,
    QDoubleSpinBox, QCheckBox, QFileDialog,
    QLineEdit, QTabWidget, QMessageBox,
)
from PySide6.QtCore import Qt, Signal

from gui.widgets.progress import ProgressPanel
from gui.widgets.drop_zone import DropZone, DropZoneFolder
from gui.widgets.preview import PreviewLabel
from core.img2video_svd import MODEL_VARIANTS, ImageToVideoGenerator
from core.sequence import images_to_video
from core.gpu_utils import SystemInfo


class Img2VideoTab(QWidget):
    """图片生视频 Tab — 含 SVD 和序列合成两个子页"""

    progress_signal = Signal(int, int, str)
    done_signal = Signal(dict)

    def __init__(self, gpu_info: SystemInfo, logger, parent=None):
        super().__init__(parent)
        self.gpu_info = gpu_info
        self.logger = logger
        self._running = False

        self._setup_ui()

        self.progress_signal.connect(self._on_progress)
        self.done_signal.connect(self._on_done)

    # ------------------------------------------------------------------
    # UI 主结构
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # 子页切换
        self.sub_tabs = QTabWidget()
        self.sub_tabs.addTab(self._build_svd_page(), "🎬 单图生成视频 (AI)")
        self.sub_tabs.addTab(self._build_sequence_page(), "📁 图片序列合成")
        layout.addWidget(self.sub_tabs)

        # 执行按钮
        self.run_btn = QPushButton("▶  开始生成")
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
        self.run_btn.clicked.connect(self._run)
        layout.addWidget(self.run_btn)

        # 进度
        self.progress_panel = ProgressPanel()
        layout.addWidget(self.progress_panel)

        layout.addStretch()

    # ==================================================================
    # 子页 A: SVD 单图生视频
    # ==================================================================

    def _build_svd_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(10)

        # 输入图
        in_group = QGroupBox("输入图片")
        in_layout = QVBoxLayout(in_group)

        self.svd_drop = DropZone("拖放图片到此处\n或点击选择")
        self.svd_drop.file_dropped.connect(self._on_svd_image)
        in_layout.addWidget(self.svd_drop)

        row = QHBoxLayout()
        self.svd_path = QLineEdit()
        self.svd_path.setReadOnly(True)
        self.svd_path.setPlaceholderText("未选择图片...")
        row.addWidget(self.svd_path)
        browse = QPushButton("浏览...")
        browse.clicked.connect(self._browse_svd_image)
        row.addWidget(browse)
        in_layout.addLayout(row)
        layout.addWidget(in_group)

        # SVD 参数
        param_group = QGroupBox("生成参数")
        param_layout = QVBoxLayout(param_group)

        r1 = QHBoxLayout()
        r1.addWidget(QLabel("模型:"))
        self.svd_model_combo = QComboBox()
        for key, cfg in MODEL_VARIANTS.items():
            self.svd_model_combo.addItem(f"{cfg['desc']}", key)
        self.svd_model_combo.setCurrentIndex(1)  # svd_xt
        r1.addWidget(self.svd_model_combo, 1)
        param_layout.addLayout(r1)

        r2 = QHBoxLayout()
        r2.addWidget(QLabel("生成帧数:"))
        self.svd_frames = QSpinBox()
        self.svd_frames.setRange(1, 30)
        self.svd_frames.setValue(25)
        r2.addWidget(self.svd_frames)

        r2.addSpacing(20)
        r2.addWidget(QLabel("输出帧率:"))
        self.svd_fps = QSpinBox()
        self.svd_fps.setRange(1, 60)
        self.svd_fps.setValue(7)
        r2.addWidget(self.svd_fps)
        param_layout.addLayout(r2)

        r3 = QHBoxLayout()
        r3.addWidget(QLabel("动态幅度:"))
        self.svd_motion = QSpinBox()
        self.svd_motion.setRange(1, 255)
        self.svd_motion.setValue(127)
        self.svd_motion.setToolTip("1=几乎静止, 255=剧烈运动")
        r3.addWidget(self.svd_motion)

        r3.addSpacing(20)
        r3.addWidget(QLabel("噪声强度:"))
        self.svd_noise = QDoubleSpinBox()
        self.svd_noise.setRange(0.0, 1.0)
        self.svd_noise.setValue(0.02)
        self.svd_noise.setSingleStep(0.01)
        r3.addWidget(self.svd_noise)
        param_layout.addLayout(r3)

        r4 = QHBoxLayout()
        r4.addWidget(QLabel("随机种子:"))
        self.svd_seed = QSpinBox()
        self.svd_seed.setRange(0, 999999)
        self.svd_seed.setValue(42)
        r4.addWidget(self.svd_seed)
        r4.addStretch()
        param_layout.addLayout(r4)

        layout.addWidget(param_group)

        # 输出
        out_group = QGroupBox("输出")
        out_layout = QHBoxLayout(out_group)
        self.svd_output = QLineEdit()
        self.svd_output.setPlaceholderText("output/svd_output.mp4")
        out_layout.addWidget(self.svd_output)
        ob = QPushButton("选择...")
        ob.clicked.connect(lambda: self._browse_output(self.svd_output))
        out_layout.addWidget(ob)
        layout.addWidget(out_group)

        return page

    # ==================================================================
    # 子页 B: 图片序列合成
    # ==================================================================

    def _build_sequence_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(10)

        in_group = QGroupBox("图片来源")
        in_layout = QVBoxLayout(in_group)

        self.seq_drop = DropZoneFolder("拖放图片文件夹到此处\n或点击选择")
        self.seq_drop.folder_dropped.connect(self._on_seq_folder)
        in_layout.addWidget(self.seq_drop)

        row = QHBoxLayout()
        self.seq_path = QLineEdit()
        self.seq_path.setReadOnly(True)
        self.seq_path.setPlaceholderText("未选择文件夹...")
        row.addWidget(self.seq_path)
        browse = QPushButton("浏览...")
        browse.clicked.connect(self._browse_seq_folder)
        row.addWidget(browse)
        in_layout.addLayout(row)

        self.seq_info = QLabel("")
        self.seq_info.setStyleSheet("color: #888; font-size: 12px;")
        in_layout.addWidget(self.seq_info)
        layout.addWidget(in_group)

        param_group = QGroupBox("合成参数")
        param_layout = QVBoxLayout(param_group)

        r1 = QHBoxLayout()
        r1.addWidget(QLabel("输出帧率:"))
        self.seq_fps = QDoubleSpinBox()
        self.seq_fps.setRange(1, 120)
        self.seq_fps.setValue(30)
        r1.addWidget(self.seq_fps)
        r1.addStretch()
        param_layout.addLayout(r1)

        r2 = QHBoxLayout()
        r2.addWidget(QLabel("输出宽度:"))
        self.seq_width = QSpinBox()
        self.seq_width.setRange(1, 7680)
        self.seq_width.setValue(1920)
        r2.addWidget(self.seq_width)
        r2.addWidget(QLabel("高度:"))
        self.seq_height = QSpinBox()
        self.seq_height.setRange(1, 4320)
        self.seq_height.setValue(1080)
        r2.addWidget(self.seq_height)
        r2.addStretch()
        param_layout.addLayout(r2)

        layout.addWidget(param_group)

        out_group = QGroupBox("输出")
        out_layout = QHBoxLayout(out_group)
        self.seq_output = QLineEdit()
        self.seq_output.setPlaceholderText("output/sequence.mp4")
        out_layout.addWidget(self.seq_output)
        ob = QPushButton("选择...")
        ob.clicked.connect(lambda: self._browse_output(self.seq_output))
        out_layout.addWidget(ob)
        layout.addWidget(out_group)

        return page

    # ------------------------------------------------------------------
    # 事件处理
    # ------------------------------------------------------------------

    def _on_svd_image(self, path: str) -> None:
        self.svd_path.setText(path)
        self.svd_drop.set_text(f"已选择:\n{os.path.basename(path)}")
        default_out = os.path.join("output", f"svd_{os.path.splitext(os.path.basename(path))[0]}.mp4")
        self.svd_output.setText(default_out)

    def _browse_svd_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择图片", "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.webp);;所有文件 (*.*)"
        )
        if path:
            self._on_svd_image(path)

    def _on_seq_folder(self, path: str) -> None:
        self.seq_path.setText(path)
        self.seq_drop.set_text(f"已选择:\n{os.path.basename(path)}")

        # 统计图片数量
        from core.sequence import discover_images
        try:
            images = discover_images(path)
            self.seq_info.setText(f"发现 {len(images)} 张图片")
        except Exception:
            self.seq_info.setText("")

        default_out = os.path.join("output", f"{os.path.basename(path)}.mp4")
        self.seq_output.setText(default_out)

    def _browse_seq_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择图片文件夹")
        if path:
            self._on_seq_folder(path)

    def _browse_output(self, edit: QLineEdit) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "保存视频", edit.text() or "output/output.mp4",
            "MP4 视频 (*.mp4);;所有文件 (*.*)"
        )
        if path:
            edit.setText(path)

    # ------------------------------------------------------------------
    # 执行
    # ------------------------------------------------------------------

    def _run(self) -> None:
        if self._running:
            return

        idx = self.sub_tabs.currentIndex()
        if idx == 0:
            self._run_svd()
        else:
            self._run_sequence()

    def _run_svd(self) -> None:
        image_path = self.svd_path.text().strip()
        if not image_path or not os.path.isfile(image_path):
            QMessageBox.warning(self, "错误", "请先选择输入图片")
            return

        output_path = self.svd_output.text().strip() or "output/svd_output.mp4"
        model_id = self.svd_model_combo.currentData()
        num_frames = self.svd_frames.value()
        fps = self.svd_fps.value()
        motion = self.svd_motion.value()
        noise = self.svd_noise.value()
        seed = self.svd_seed.value()

        self._running = True
        self.run_btn.setEnabled(False)
        self.run_btn.setText("生成中...")
        self.progress_panel.reset()

        def worker():
            try:
                gen = ImageToVideoGenerator(model_id=model_id, device="cuda")
                result = gen.generate(
                    image_path=image_path,
                    output_path=output_path,
                    num_frames=num_frames,
                    fps=fps,
                    motion_bucket_id=motion,
                    noise_aug_strength=noise,
                    seed=seed,
                    progress_callback=lambda c, t, s: self.progress_signal.emit(c, t, s),
                )
                gen.unload()
                self.done_signal.emit(result)
            except Exception as e:
                self.done_signal.emit({"error": str(e)})

        threading.Thread(target=worker, daemon=True).start()

    def _run_sequence(self) -> None:
        folder = self.seq_path.text().strip()
        if not folder or not os.path.isdir(folder):
            QMessageBox.warning(self, "错误", "请先选择包含图片的文件夹")
            return

        output_path = self.seq_output.text().strip() or "output/sequence.mp4"
        fps = self.seq_fps.value()
        width = self.seq_width.value()
        height = self.seq_height.value()

        self._running = True
        self.run_btn.setEnabled(False)
        self.run_btn.setText("合成中...")
        self.progress_panel.reset()

        def worker():
            try:
                result = images_to_video(
                    source=folder,
                    output_path=output_path,
                    fps=fps,
                    width=width,
                    height=height,
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
        self.run_btn.setText("▶  开始生成")

        if "error" in result:
            QMessageBox.critical(self, "生成失败", result["error"])
            self.progress_panel.update_progress(0, 100, f"失败: {result['error']}")
        else:
            self.progress_panel.update_progress(100, 100, f"✅ 完成！输出: {result['output']}")
            QMessageBox.information(self, "生成完成", f"视频已生成:\n{result['output']}")
