# -*- coding: utf-8 -*-
"""监控线程：读摄像头 -> 人脸检测 -> 触发状态机。

触发条件：连续 N 帧检测人数 >= 阈值（防单帧误报）；
触发后进入冷却，人数回落保持 M 帧后发出恢复信号。
"""
import time
from typing import Callable

import cv2
from PyQt5.QtCore import QThread, pyqtSignal

from .config import AppConfig
from .detector import FaceDetector

CAMERA_W, CAMERA_H = 640, 480
PREVIEW_INTERVAL = 0.1  # 预览帧发射间隔（秒），避免淹没 GUI 线程
CAMERA_REOPEN_DELAY = 2.0


class MonitorWorker(QThread):
    frame_ready = pyqtSignal(object)        # 带标注的 BGR 帧（预览用）
    face_count_changed = pyqtSignal(int)    # 当前检测人数
    triggered = pyqtSignal(str)             # 触发原因（"face_count"）
    recovered = pyqtSignal()                # 人数回落，可执行恢复动作
    status_message = pyqtSignal(str)        # 日志
    failed = pyqtSignal(str)                # 致命错误（弹窗提示并停止）

    def __init__(self, get_config: Callable[[], AppConfig], parent=None):
        super().__init__(parent)
        self._get_config = get_config
        self._stop = False
        self._detector = FaceDetector()
        self._last_count = -1

    # ---------- 生命周期 ----------
    def stop(self) -> None:
        self._stop = True

    def run(self):
        cfg = self._get_config()
        try:
            if not self._open_camera(cfg.camera_index):
                return
            self._loop()
        except Exception as e:
            self.failed.emit(f"监测线程异常: {e}")
        finally:
            self._release_camera()

    # ---------- 摄像头 ----------
    def _open_camera(self, index: int) -> bool:
        self._cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)  # Windows 上 DSHOW 打开更快
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_W)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_H)
        # 等待第一帧确认摄像头真正可用
        for _ in range(30):
            if self._stop:
                return False
            ok, _ = self._cap.read()
            if ok:
                self.status_message.emit(f"摄像头 {index} 已打开")
                return True
            time.sleep(0.1)
        self.failed.emit(
            f"摄像头 {index} 打不开或无画面\n\n"
            "请依次检查：\n"
            "1. 是否被其他程序占用（微信视频/腾讯会议/直播软件）\n"
            "2. Windows 设置 → 隐私和安全性 → 摄像头 → "
            "允许桌面应用访问摄像头\n"
            "3. 设置里点“测试摄像头”换一个可用编号\n"
            "4. 笔记本的 Fn 摄像头开关或物理滑盖")
        self._release_camera()
        return False

    def _release_camera(self) -> None:
        if getattr(self, "_cap", None) is not None:
            self._cap.release()
            self._cap = None

    # ---------- 主循环 ----------
    def _loop(self):
        hit_streak = 0        # 连续满足人数条件的帧数
        clear_streak = 0      # 连续不满足的帧数
        last_trigger_ts = 0.0
        is_triggered = False
        last_preview_ts = 0.0
        cam_error_streak = 0
        self._last_count = -1

        while not self._stop:
            cfg = self._get_config()
            self._detector.set_params(cfg.score_threshold, cfg.min_face_size)

            ok, frame = self._cap.read()
            if not ok or frame is None:
                cam_error_streak += 1
                if cam_error_streak == 20:
                    self.status_message.emit("摄像头读取异常，尝试重连...")
                    self._release_camera()
                    time.sleep(CAMERA_REOPEN_DELAY)
                    if not self._stop and not self._open_camera(cfg.camera_index):
                        break  # 打开失败已发 failed 信号，结束线程
                else:
                    time.sleep(0.05)
                continue
            cam_error_streak = 0

            faces = self._detector.detect(frame)
            count = len(faces)
            now = time.monotonic()

            if count != self._last_count:
                self._last_count = count
                self.face_count_changed.emit(count)

            # 触发状态机
            if count >= cfg.face_threshold:
                hit_streak += 1
                clear_streak = 0
            else:
                hit_streak = 0
                clear_streak += 1

            if (hit_streak >= cfg.consecutive_frames
                    and not is_triggered
                    and now - last_trigger_ts >= cfg.cooldown_seconds):
                is_triggered = True
                last_trigger_ts = now
                self.triggered.emit("face_count")

            if (is_triggered and cfg.auto_recover
                    and clear_streak >= cfg.recover_frames):
                is_triggered = False
                self.recovered.emit()

            # 节流发送预览帧
            if now - last_preview_ts >= PREVIEW_INTERVAL:
                last_preview_ts = now
                self.frame_ready.emit(self._detector.annotate(frame, faces))
