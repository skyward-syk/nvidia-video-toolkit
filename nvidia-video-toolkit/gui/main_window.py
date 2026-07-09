"""
主窗口 — Tab 容器 + 菜单 + 状态栏
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QMenuBar, QStatusBar,
    QWidget, QVBoxLayout, QLabel,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction

from gui.enhance_tab import EnhanceTab
from gui.img2video_tab import Img2VideoTab
from gui.settings_tab import SettingsTab
from core.gpu_utils import SystemInfo


class MainWindow(QMainWindow):
    """NVIDIA AI 视频工具套件主窗口"""

    def __init__(self, gpu_info: SystemInfo, logger, parent=None):
        super().__init__(parent)
        self.gpu_info = gpu_info
        self.logger = logger

        self.setWindowTitle("NVIDIA AI 视频工具套件")
        self.setMinimumSize(900, 700)
        self.resize(1000, 750)

        self._setup_ui()
        self._setup_menu()
        self._setup_statusbar()

        # 应用暗色主题
        self._apply_dark_theme()

    # ------------------------------------------------------------------
    # UI 布局
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(6, 6, 6, 6)

        # Tab 容器
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #444;
                border-radius: 6px;
                background-color: #1e1e1e;
            }
            QTabBar::tab {
                padding: 8px 20px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            QTabBar::tab:selected {
                background-color: #2d2d2d;
                color: #fff;
                font-weight: bold;
            }
            QTabBar::tab:!selected {
                background-color: #252525;
                color: #999;
            }
        """)

        # 添加各 Tab
        self.enhance_tab = EnhanceTab(gpu_info=self.gpu_info, logger=self.logger)
        self.img2video_tab = Img2VideoTab(gpu_info=self.gpu_info, logger=self.logger)
        self.settings_tab = SettingsTab(gpu_info=self.gpu_info, logger=self.logger)

        self.tabs.addTab(self.enhance_tab, "🎥 视频画质增强")
        self.tabs.addTab(self.img2video_tab, "🖼️ 图片生视频")
        self.tabs.addTab(self.settings_tab, "⚙️ 设置")

        layout.addWidget(self.tabs)

    # ------------------------------------------------------------------
    # 菜单
    # ------------------------------------------------------------------

    def _setup_menu(self) -> None:
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件(&F)")

        open_action = QAction("打开视频...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._on_open_file)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        exit_action = QAction("退出(&X)", self)
        exit_action.setShortcut("Alt+F4")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助(&H)")

        about_action = QAction("关于...", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

    def _on_open_file(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, "打开视频文件", "",
            "视频文件 (*.mp4 *.avi *.mkv *.mov *.webm);;所有文件 (*.*)"
        )
        if path:
            self.tabs.setCurrentIndex(0)  # 切换到增强 Tab
            self.enhance_tab._on_file_selected(path)

    def _on_about(self) -> None:
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.about(
            self, "关于 NVIDIA AI 视频工具套件",
            "<h2>NVIDIA AI 视频工具套件</h2>"
            "<p>版本 1.0.0</p>"
            "<p>功能:</p>"
            "<ul>"
            "<li>视频画质增强（Real-ESRGAN 超分辨率）</li>"
            "<li>单图生成动态视频（Stable Video Diffusion）</li>"
            "<li>图片序列合成视频</li>"
            "</ul>"
            "<p>需要 NVIDIA RTX 显卡 + CUDA 环境</p>"
        )

    # ------------------------------------------------------------------
    # 状态栏
    # ------------------------------------------------------------------

    def _setup_statusbar(self) -> None:
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)

        best = self.gpu_info.best_gpu
        if best:
            gpu_text = f"GPU: {best.name} ({best.vram_gb:.1f} GB)"
        else:
            gpu_text = "GPU: 未检测到"

        cuda_text = "CUDA: ✓" if self.gpu_info.cuda_available else "CUDA: ✗"
        nvenc_text = "NVENC: ✓" if self.gpu_info.nvenc_available else "NVENC: ✗"

        self.statusbar.showMessage(f"{gpu_text}  |  {cuda_text}  |  {nvenc_text}  |  就绪")

    # ------------------------------------------------------------------
    # 主题
    # ------------------------------------------------------------------

    def _apply_dark_theme(self) -> None:
        """应用暗色主题样式"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1a1a1a;
            }
            QWidget {
                background-color: #1e1e1e;
                color: #ddd;
                font-size: 13px;
            }
            QGroupBox {
                border: 1px solid #444;
                border-radius: 8px;
                margin-top: 14px;
                padding-top: 14px;
                font-weight: bold;
                color: #ccc;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }
            QPushButton {
                background-color: #3a3a3a;
                border: 1px solid #555;
                border-radius: 5px;
                padding: 6px 16px;
                color: #ddd;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
                border-color: #777;
            }
            QPushButton:pressed {
                background-color: #2a2a2a;
            }
            QLineEdit {
                background-color: #252525;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 4px 8px;
                color: #eee;
            }
            QComboBox {
                background-color: #252525;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 4px 8px;
                color: #eee;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #2a2a2a;
                color: #ddd;
                selection-background-color: #4a9eff;
            }
            QSpinBox, QDoubleSpinBox {
                background-color: #252525;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 4px;
                color: #eee;
            }
            QCheckBox {
                color: #ccc;
            }
            QLabel {
                color: #ccc;
                background: transparent;
            }
            QMenuBar {
                background-color: #252525;
                color: #ccc;
            }
            QMenuBar::item:selected {
                background-color: #3a3a3a;
            }
            QMenu {
                background-color: #2a2a2a;
                color: #ddd;
                border: 1px solid #555;
            }
            QMenu::item:selected {
                background-color: #4a9eff;
            }
            QStatusBar {
                background-color: #151515;
                color: #888;
            }
        """)
