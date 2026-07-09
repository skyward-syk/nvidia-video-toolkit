"""
预览组件 — 用于预览输入图片/视频帧
"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QSizePolicy
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap


class PreviewLabel(QLabel):
    """可缩放预览标签，保持宽高比"""

    def __init__(self, placeholder: str = "预览区域", parent=None):
        super().__init__(parent)
        self.setText(placeholder)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(200)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet("""
            QLabel {
                border: 1px solid #444;
                border-radius: 8px;
                background-color: #1a1a1a;
                color: #666;
                font-size: 14px;
            }
        """)
        self._original_pixmap: QPixmap | None = None

    def set_pixmap(self, pixmap: QPixmap) -> None:
        """设置图片并缩放适配"""
        self._original_pixmap = pixmap
        self._update_display()

    def load_image(self, path: str) -> None:
        """从文件加载图片预览"""
        pixmap = QPixmap(path)
        if pixmap.isNull():
            self.setText(f"无法加载: {path}")
            return
        self.set_pixmap(pixmap)

    def clear(self) -> None:
        """清除预览"""
        self._original_pixmap = None
        self.setText("预览区域")

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_display()

    def _update_display(self) -> None:
        """按当前窗口大小缩放显示"""
        if self._original_pixmap is None:
            return
        scaled = self._original_pixmap.scaled(
            self.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.setPixmap(scaled)
