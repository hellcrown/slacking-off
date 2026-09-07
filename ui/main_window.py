# -*- coding: utf-8 -*-
"""主窗口：预览 / 状态 / 日志 / 托盘 / 全局热键。"""
import ctypes
import ctypes.wintypes
import time

import win32con
import win32gui
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QImage, QPixmap, QPainter, QColor, QIcon
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QSystemTrayIcon, QMenu, QAction,
)

from core.config import AppConfig, save_config
from core.actions import ActionExecutor
from core.monitor import MonitorWorker

WM_HOTKEY = 0x0312
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN = 0x1, 0x2, 0x4, 0x8
MOD_NOREPEAT = 0x4000
HK_TOGGLE, HK_TRIGGER = 1, 2

STATE_COLOR = {"idle": "#9e9e9e", "running": "#43a047", "triggered": "#e53935"}


def make_tray_icon(color: str) -> QIcon:
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(color))
    p.setPen(Qt.NoPen)
    p.drawEllipse(6, 6, 52, 52)
    p.end()
    return QIcon(pm)


def parse_hotkey(text: str):
    """'Ctrl+Alt+M' -> (mods, vk)；无修饰键或无法识别返回 None。"""
    if not text:
        return None
    mods = 0
    key = None
    for token in text.split("+"):
        t = token.strip().lower()
        if t in ("ctrl", "control"):
            mods |= MOD_CONTROL
        elif t == "alt":
            mods |= MOD_ALT
        elif t == "shift":
            mods |= MOD_SHIFT
        elif t in ("win", "meta"):
            mods |= MOD_WIN
        elif t and key is None:
            key = token.strip()
    if not mods or not key:
        return None
    if len(key) == 1:
        ch = key.upper()
        if ch.isdigit() or ch.isalpha():
            return mods, ord(ch)
        return None
    if key.upper().startswith("F") and key[1:].isdigit():
        n = int(key[1:])
        if 1 <= n <= 24:
            return mods, 0x70 + n - 1
    return None


class MainWindow(QMainWindow):
    def __init__(self, cfg: AppConfig):
        super().__init__()
        self.cfg = cfg
        self.executor = ActionExecutor()
        self.worker = None
        self._state = "idle"
        self._hotkey_ids = []
        self._last_camera_index = None

        self.setWindowTitle("摸鱼哨兵")
        self.resize(760, 720)
        self.setWindowIcon(make_tray_icon(STATE_COLOR["idle"]))

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # ---------- 状态行 ----------
        row = QHBoxLayout()
        self.face_label = QLabel("人脸数: -")
        self.face_label.setStyleSheet("font-size: 20pt; font-weight: bold;")
        self.status_label = QLabel("未监测")
        self.status_label.setStyleSheet(
            "font-size: 14pt; font-weight: bold; color: %s;" % STATE_COLOR["idle"])
        row.addWidget(self.face_label)
        row.addStretch(1)
        row.addWidget(self.status_label)
        root.addLayout(row)

        # ---------- 预览 ----------
        self.preview = QLabel("摄像头预览")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(640, 480)
        self.preview.setStyleSheet(
            "background: #111; color: #888; border: 1px solid #333;")
        root.addWidget(self.preview, 1)

        # ---------- 按钮行 ----------
        btns = QHBoxLayout()
        self.toggle_btn = QPushButton("开始监测")
        self.toggle_btn.clicked.connect(self.toggle_monitoring)
        self.toggle_btn.setStyleSheet("font-weight: bold;")
        self.trigger_btn = QPushButton("立即执行动作（老板键）")
        self.trigger_btn.clicked.connect(lambda: self.run_actions("manual"))
        self.settings_btn = QPushButton("设置")
        btns.addWidget(self.toggle_btn)
        btns.addWidget(self.trigger_btn)
        btns.addStretch(1)
        btns.addWidget(self.settings_btn)
        root.addLayout(btns)

        # ---------- 日志 ----------
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(300)
        self.log.setStyleSheet("font-family: Consolas, 'Microsoft YaHei';")
        root.addWidget(self.log)

        # ---------- 冷却计时 ----------
        self.cooldown_timer = QTimer(self)
        self.cooldown_timer.setSingleShot(True)
        self.cooldown_timer.timeout.connect(self._cooldown_over)

        # ---------- 托盘 ----------
        self._icons = {k: make_tray_icon(v) for k, v in STATE_COLOR.items()}
        self.tray = QSystemTrayIcon(self._icons["idle"], self)
        self.tray.setToolTip("摸鱼哨兵 - 未监测")
        menu = QMenu()
        self.tray_toggle_action = QAction("开始监测", self)
        self.tray_toggle_action.triggered.connect(self.toggle_monitoring)
        a_trigger = QAction("立即执行动作", self)
        a_trigger.triggered.connect(lambda: self.run_actions("manual"))
        a_show = QAction("显示主窗口", self)
        a_show.triggered.connect(self.show_and_raise)
        a_quit = QAction("退出", self)
        a_quit.triggered.connect(self._quit)
        menu.addAction(self.tray_toggle_action)
        menu.addAction(a_trigger)
        menu.addSeparator()
        menu.addAction(a_show)
        menu.addAction(a_quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda reason: self.show_and_raise()
            if reason == QSystemTrayIcon.DoubleClick else None)
        self.tray.show()

        self.settings_btn.clicked.connect(self.open_settings)

        self.append_log("摸鱼哨兵已启动。热键：%s（开关监测） / %s（老板键）"
                        % (cfg.hotkeys.toggle_monitor, cfg.hotkeys.trigger_now))
        if cfg.monitor_on_start:
            self.start_monitoring()

    # ================= 日志与状态 =================
    def append_log(self, text: str):
        self.log.appendPlainText(time.strftime("[%H:%M:%S] ") + text)

    def _set_state(self, state: str):
        self._state = state
        color = STATE_COLOR[state]
        text = {"idle": "未监测", "running": "监测中", "triggered": "已触发！"}[state]
        self.status_label.setText(text)
        self.status_label.setStyleSheet(
            "font-size: 14pt; font-weight: bold; color: %s;" % color)
        self.tray.setIcon(self._icons[state])
        self.tray.setToolTip(f"摸鱼哨兵 - {text}")

    # ================= 监测控制 =================
    def get_config(self) -> AppConfig:
        return self.cfg

    def start_monitoring(self):
        if self.worker is not None and self.worker.isRunning():
            # 摄像头变更需要重启
            if self._last_camera_index == self.cfg.camera_index:
                return
            self.stop_monitoring()
        self._last_camera_index = self.cfg.camera_index
        self.worker = MonitorWorker(self.get_config)
        self.worker.frame_ready.connect(self.on_frame)
        self.worker.face_count_changed.connect(self.on_face_count)
        self.worker.triggered.connect(self.run_actions)
        self.worker.recovered.connect(self.on_recovered)
        self.worker.status_message.connect(self.append_log)
        self.worker.start()
        self._set_state("running")
        self.toggle_btn.setText("停止监测")
        self.tray_toggle_action.setText("停止监测")
        self.append_log("监测已开始（摄像头 %d，阈值 %d 人）"
                        % (self.cfg.camera_index, self.cfg.face_threshold))

    def stop_monitoring(self):
        if self.worker is not None:
            self.worker.stop()
            self.worker.wait(3000)
            self.worker = None
        self._set_state("idle")
        self.toggle_btn.setText("开始监测")
        self.tray_toggle_action.setText("开始监测")
        self.face_label.setText("人脸数: -")
        self.append_log("监测已停止")

    def toggle_monitoring(self):
        if self._state == "idle":
            self.start_monitoring()
        else:
            self.stop_monitoring()

    # ================= 信号处理 =================
    def on_frame(self, frame):
        if not self.cfg.show_preview:
            return
        h, w, ch = frame.shape
        img = QImage(frame.data.tobytes(), w, h, w * 3, QImage.Format_BGR888)
        pm = QPixmap.fromImage(img).scaled(
            self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.preview.setPixmap(pm)

    def on_face_count(self, n: int):
        color = "#e53935" if n >= self.cfg.face_threshold else "#43a047"
        self.face_label.setText(f"人脸数: {n}")
        self.face_label.setStyleSheet(
            "font-size: 20pt; font-weight: bold; color: %s;" % color)

    def run_actions(self, reason: str = "face_count"):
        label = "检测到目标人数" if reason == "face_count" else "手动触发"
        self.append_log(f">>> 触发动作（{label}）")
        for line in self.executor.execute(self.cfg.actions, reason):
            self.append_log("    " + line)
        self._set_state("triggered")
        self.cooldown_timer.start(int(self.cfg.cooldown_seconds * 1000))

    def _cooldown_over(self):
        if self._state == "triggered":
            self._set_state("running" if self.worker else "idle")

    def on_recovered(self):
        self.append_log("<<< 人数已回落，执行恢复")
        for line in self.executor.recover():
            self.append_log("    " + line)

    # ================= 设置 =================
    def open_settings(self):
        from .settings_dialog import SettingsDialog
        old_camera = self.cfg.camera_index
        dlg = SettingsDialog(self.cfg, self)
        if dlg.exec_():
            save_config(self.cfg)
            self.append_log("设置已保存")
            self.register_hotkeys()
            if self.worker and self.cfg.camera_index != old_camera:
                self.stop_monitoring()
                self.start_monitoring()

    # ================= 全局热键 =================
    def register_hotkeys(self):
        user32 = ctypes.windll.user32
        hwnd = int(self.winId())
        for hid in self._hotkey_ids:
            user32.UnregisterHotKey(hwnd, hid)
        self._hotkey_ids = []
        for hid, text in ((HK_TOGGLE, self.cfg.hotkeys.toggle_monitor),
                          (HK_TRIGGER, self.cfg.hotkeys.trigger_now)):
            parsed = parse_hotkey(text)
            if not parsed:
                if text:
                    self.append_log(f"[警告] 热键 {text} 无法注册（需含修饰键）")
                continue
            mods, vk = parsed
            if user32.RegisterHotKey(hwnd, hid, mods | MOD_NOREPEAT, vk):
                self._hotkey_ids.append(hid)
            else:
                self.append_log(f"[警告] 热键 {text} 注册失败（可能被其他程序占用）")
        if self._hotkey_ids:
            self.append_log("热键生效：%s（开关监测） / %s（老板键）"
                            % (self.cfg.hotkeys.toggle_monitor,
                               self.cfg.hotkeys.trigger_now))

    def nativeEvent(self, eventType, message):
        try:
            msg = ctypes.wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY:
                if msg.wParam == HK_TOGGLE:
                    self.toggle_monitoring()
                elif msg.wParam == HK_TRIGGER:
                    self.run_actions("manual")
        except Exception:
            pass
        return super().nativeEvent(eventType, message)

    # ================= 窗口行为 =================
    def show_and_raise(self):
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        # 关闭按钮 = 最小化到托盘，真正退出走托盘菜单
        if self.tray.isVisible():
            event.ignore()
            self.hide()
            self.tray.showMessage("摸鱼哨兵", "程序已最小化到托盘，右键托盘图标可退出。",
                                  QSystemTrayIcon.Information, 2000)

    def _quit(self):
        self.stop_monitoring()
        user32 = ctypes.windll.user32
        hwnd = int(self.winId())
        for hid in self._hotkey_ids:
            user32.UnregisterHotKey(hwnd, hid)
        self.tray.hide()
        from PyQt5.QtWidgets import QApplication
        QApplication.quit()
