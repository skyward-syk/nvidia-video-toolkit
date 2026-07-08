"""
拖拽区域组件 — 支持拖放文件到指定区域
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent


class DropZone(QFrame):
    """文件拖放区域，拖入文件时发出 file_dropped 信号"""

    file_dropped = Signal(str)   # 拖入的单个文件路径
    files_dropped = Signal(list)  # 拖入的多个文件路径

    def __init__(self, placeholder: str = "拖放文件到此处\n或点击选择", parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Sunken)
        self.setMinimumHeight(140)
        self.setStyleSheet(self._style())

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        self._label = QLabel(placeholder)
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setWordWrap(True)
        self._label.setStyleSheet("color: #888; font-size: 14px;")
        layout.addWidget(self._label)

        self._placeholder = placeholder

    def set_text(self, text: str) -> None:
        self._label.setText(text)

    def reset(self) -> None:
        self._label.setText(self._placeholder)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet(self._style(hover=True))

    def dragLeaveEvent(self, event) -> None:
        self.setStyleSheet(self._style(hover=False))

    def dropEvent(self, event: QDropEvent) -> None:
        self.setStyleSheet(self._style(hover=False))
        urls = event.mimeData().urls()
        paths = [url.toLocalFile() for url in urls]

        if len(paths) == 1:
            self.file_dropped.emit(paths[0])
        if len(paths) > 1:
            self.files_dropped.emit(paths)

    def mousePressEvent(self, event) -> None:
        """点击时弹出文件选择对话框"""
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, "选择文件", "",
            "所有支持格式 (*.mp4 *.avi *.mkv *.mov *.png *.jpg *.jpeg *.bmp *.webp);;"
            "视频文件 (*.mp4 *.avi *.mkv *.mov);;"
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.webp);;"
            "所有文件 (*.*)"
        )
        if path:
            self.file_dropped.emit(path)

    @staticmethod
    def _style(hover: bool = False) -> str:
        border_color = "#4a9eff" if hover else "#555"
        bg = "#2a2a2a" if hover else "#1e1e1e"
        return f"""
            DropZone {{
                border: 2px dashed {border_color};
                border-radius: 12px;
                background-color: {bg};
            }}
        """


class DropZoneFolder(QFrame):
    """文件夹拖放区域（用于序列合成）"""

    folder_dropped = Signal(str)

    def __init__(self, placeholder: str = "拖放文件夹到此处\n或点击选择", parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Sunken)
        self.setMinimumHeight(120)
        self.setStyleSheet(DropZone._style())

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        self._label = QLabel(placeholder)
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setWordWrap(True)
        self._label.setStyleSheet("color: #888; font-size: 14px;")
        layout.addWidget(self._label)

        self._placeholder = placeholder

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet(DropZone._style(hover=True))

    def dragLeaveEvent(self, event) -> None:
        self.setStyleSheet(DropZone._style(hover=False))

    def dropEvent(self, event: QDropEvent) -> None:
        self.setStyleSheet(DropZone._style(hover=False))
        urls = event.mimeData().urls()
        for url in urls:
            path = url.toLocalFile()
            if os.path.isdir(path):
                self.folder_dropped.emit(path)
                return
        # 如果拖入的不是文件夹，取第一个文件的父目录
        if urls:
            parent_dir = os.path.dirname(urls[0].toLocalFile())
            if os.path.isdir(parent_dir):
                self.folder_dropped.emit(parent_dir)

    def mousePressEvent(self, event) -> None:
        from PySide6.QtWidgets import QFileDialog
        path = QFileDialog.getExistingDirectory(self, "选择图片文件夹")
        if path:
            self.folder_dropped.emit(path)

    def set_text(self, text: str) -> None:
        self._label.setText(text)

    def reset(self) -> None:
        self._label.setText(self._placeholder)


import os
