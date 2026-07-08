"""
进度展示组件
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QProgressBar, QLabel, QTextEdit,
)
from PySide6.QtCore import Qt, Signal


class ProgressPanel(QWidget):
    """进度面板：进度条 + 状态文本 + 日志输出"""

    log_signal = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 状态标签
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: #aaa; font-size: 13px;")
        layout.addWidget(self.status_label)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%  |  %v / %m")
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #555;
                border-radius: 6px;
                background: #1e1e1e;
                text-align: center;
                color: #ccc;
                height: 28px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #0a6, stop:1 #4af);
                border-radius: 5px;
            }
        """)
        layout.addWidget(self.progress_bar)

        # 日志输出
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(120)
        self.log_output.setStyleSheet("""
            QTextEdit {
                background-color: #111;
                color: #8a8;
                border: 1px solid #444;
                border-radius: 4px;
                font-family: Consolas, monospace;
                font-size: 12px;
            }
        """)
        layout.addWidget(self.log_output)

        # 连接信号
        self.log_signal.connect(self._append_log)

    def update_progress(self, current: int, total: int, status: str = "") -> None:
        """更新进度"""
        if total > 0:
            pct = int(current / total * 100)
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(current)
        else:
            self.progress_bar.setRange(0, 0)

        if status:
            self.status_label.setText(status)
            self.append_log(status)

    def append_log(self, text: str) -> None:
        """追加日志"""
        self.log_output.append(text)
        # 自动滚到底部
        scrollbar = self.log_output.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _append_log(self, text: str) -> None:
        self.append_log(text)

    def reset(self) -> None:
        """重置进度"""
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.status_label.setText("就绪")
        self.log_output.clear()
