# -*- coding: utf-8 -*-
"""摸鱼哨兵 - 入口。

用法: python main.py
"""
import ctypes
import logging
import os
import sys
import traceback

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

from core.config import app_root, load_config
from ui.main_window import MainWindow


def _setup_logging():
    if getattr(sys, "frozen", False):
        # 打包模式下无控制台：日志/未捕获异常写到 exe 旁边的 sentinel.log
        log_path = os.path.join(app_root(), "sentinel.log")
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            filename=log_path, encoding="utf-8")

        def _hook(t, v, tb):
            logging.getLogger("sentinel.crash").error(
                "未捕获异常", exc_info=(t, v, tb))
            traceback.print_exception(t, v, tb, file=sys.stderr)

        sys.excepthook = _hook
    else:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def main():
    _setup_logging()
    if getattr(sys, "frozen", False):
        # 让任务栏用自带图标而不是通用 python 图标
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "moyu.sentinel")
        except Exception:
            pass
    if hasattr(Qt, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # 关闭主窗口只是隐藏到托盘

    cfg = load_config()
    win = MainWindow(cfg)
    win.show()
    # 窗口句柄可用后再注册全局热键
    win.register_hotkeys()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
