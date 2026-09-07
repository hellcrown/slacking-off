# -*- coding: utf-8 -*-
"""端到端联调：真实摄像头 + YuNet + 触发状态机 + 动作执行 + 恢复。

自动化方案：阈值设 1（镜头前有人即触发，触发后最小化测试窗口）；
触发后把阈值改回 2（人数回落）→ 状态机走恢复路径 → 窗口还原。
"""
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer

from core.config import AppConfig, ActionItem, ACT_MINIMIZE, ACT_FRONT
from core.monitor import MonitorWorker
from core.actions import ActionExecutor

import win32gui

TKWIN = "SentinelITWin"
TK_CODE = (
    "import tkinter\n"
    f"r = tkinter.Tk()\n"
    f"r.title('{TKWIN}')\n"
    "r.geometry('280x180+80+80')\n"
    "r.mainloop()\n"
)

TIMEOUT = 60


def wait_cond(cond, timeout=TIMEOUT, what=""):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if cond():
            return True
        app.processEvents()
        time.sleep(0.1)
    print(f"[TIMEOUT] {what}")
    return False


def find_hwnd():
    from core.actions import find_windows_by_title
    wins = find_windows_by_title(TKWIN)
    return wins[0].hwnd if wins else 0


if __name__ == "__main__":
    app = QApplication(sys.argv)

    print("== 启动隔离测试窗口 ==")
    tkproc = subprocess.Popen([sys.executable, "-c", TK_CODE])
    hwnd = 0
    for _ in range(30):
        hwnd = find_hwnd()
        if hwnd:
            break
        time.sleep(0.3)
    assert hwnd, "测试窗口未出现"
    print("   OK")

    cfg = AppConfig()
    cfg.camera_index = 0
    cfg.face_threshold = 1          # 镜头前有人即触发
    cfg.consecutive_frames = 3
    cfg.recover_frames = 10
    cfg.cooldown_seconds = 5.0
    cfg.auto_recover = True
    cfg.actions = [
        ActionItem(type=ACT_MINIMIZE, target=TKWIN, enabled=True, recoverable=True),
        ActionItem(type=ACT_FRONT, target=TKWIN, enabled=True, recoverable=False),
    ]

    executor = ActionExecutor()
    events = {"triggered": [], "recovered": [], "faces": []}

    worker = MonitorWorker(lambda: cfg)
    worker.triggered.connect(lambda r: (
        events["triggered"].append(time.time()),
        [print("   action:", l) for l in executor.execute(cfg.actions, r)]))
    worker.recovered.connect(lambda: (
        events["recovered"].append(time.time()),
        [print("   recover:", l) for l in executor.recover()]))
    worker.face_count_changed.connect(lambda n: (
        events["faces"].append(n),
        print(f"   faces -> {n}") if len(events["faces"]) < 6 else None))
    worker.status_message.connect(lambda m: print("   [monitor]", m))

    print("== 启动监测（请保持在镜头前） ==")
    worker.start()

    ok1 = wait_cond(lambda: len(events["triggered"]) >= 1, what="等待触发")
    if ok1:
        time.sleep(0.5); app.processEvents()
        iconic = win32gui.IsIconic(hwnd)
        print(f"   触发成功，测试窗口已最小化: IsIconic={iconic}")
        assert iconic, "触发后窗口未最小化"
    else:
        worker.stop(); worker.wait(3000); sys.exit(1)

    print("== 模拟人离开：阈值改回 2 ==")
    cfg.face_threshold = 2
    ok2 = wait_cond(lambda: len(events["recovered"]) >= 1, what="等待恢复")
    time.sleep(0.5); app.processEvents()
    if ok2:
        iconic = win32gui.IsIconic(hwnd)
        print(f"   恢复成功，测试窗口已还原: IsIconic={iconic}")
        assert not iconic, "恢复后窗口仍最小化"
    else:
        worker.stop(); worker.wait(3000); sys.exit(1)

    worker.stop()
    worker.wait(3000)
    tkproc.terminate()
    tkproc.wait(timeout=5)

    dt = events["recovered"][0] - events["triggered"][0] if ok1 and ok2 else -1
    print(f"   触发->恢复 用时 {dt:.1f}s")
    print()
    print("INTEGRATION TEST PASSED" if (ok1 and ok2) else "INTEGRATION TEST FAILED")
