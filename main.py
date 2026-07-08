"""
NVIDIA AI 视频工具套件 — 主入口
功能:
  1. 视频画质增强（超分辨率）
  2. 单图生成动态视频
  3. 图片序列合成视频

用法:
  python main.py            # 启动 GUI
  python main.py --info     # 仅显示 GPU 状态信息
"""

from __future__ import annotations

import argparse
import logging
import sys
import os

# 确保项目根目录在 sys.path 中，并切换工作目录
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """配置日志：同时输出到控制台和文件"""
    logger = logging.getLogger("NvidiaVideoToolkit")
    logger.setLevel(level)

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(logging.Formatter(
        "[%(levelname)s] %(name)s: %(message)s"
    ))
    logger.addHandler(console)

    log_dir = os.path.join(PROJECT_ROOT, "output")
    os.makedirs(log_dir, exist_ok=True)
    file_handler = logging.FileHandler(
        os.path.join(log_dir, "app.log"), encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    ))
    logger.addHandler(file_handler)

    return logger


def main() -> None:
    parser = argparse.ArgumentParser(description="NVIDIA AI 视频工具套件")
    parser.add_argument("--info", action="store_true", help="仅显示 GPU 状态信息后退出")
    parser.add_argument("--debug", action="store_true", help="启用 DEBUG 级别日志")
    args = parser.parse_args()

    log_level = logging.DEBUG if args.debug else logging.INFO
    logger = setup_logging(log_level)
    logger.info("NVIDIA AI 视频工具套件 启动")

    from core.gpu_utils import detect_gpu_info, gpu_summary
    gpu_info = detect_gpu_info()
    summary = gpu_summary(gpu_info)
    logger.info("GPU 检测完成:\n%s", summary)

    if args.info:
        print(summary)
        return

    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
        from gui.main_window import MainWindow

        app = QApplication(sys.argv)
        app.setApplicationName("NVIDIA AI 视频工具套件")

        window = MainWindow(gpu_info=gpu_info, logger=logger)
        window.show()
        window.raise_()
        window.activateWindow()

        sys.exit(app.exec())

    except ImportError as e:
        logger.error("缺少依赖: %s", e)
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox
            app = QApplication(sys.argv)
            QMessageBox.critical(
                None, "启动失败",
                f"缺少必要的依赖库：\n\n{e}\n\n"
                "请运行 setup.bat 安装依赖。\n"
                "或手动执行: pip install -r requirements.txt"
            )
        except Exception:
            pass
        print(f"\n[错误] 缺少依赖: {e}")
        print("请运行 setup.bat 安装依赖")
        sys.exit(1)

    except Exception as e:
        logger.exception("应用启动失败")
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox
            app = QApplication(sys.argv)
            QMessageBox.critical(
                None, "启动失败",
                f"应用启动时发生错误：\n\n{type(e).__name__}: {e}\n\n"
                "请查看 output/app.log 获取详细日志。"
            )
        except Exception:
            pass
        print(f"\n[错误] 启动失败: {type(e).__name__}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
