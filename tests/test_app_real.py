# -*- coding: utf-8 -*-
"""真实应用验证：启动 main.py（真实 GUI+托盘），
监测触发后自动最小化测试窗口；关闭按钮应隐藏到托盘而非退出。"""
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RTWIN = "SentinelRTWin"

TK_CODE = (
    "import tkinter\n"
    f"r = tkinter.Tk()\n"
    f"r.title('{RTWIN}')\n"
    "r.geometry('260x160+120+120')\n"
    "r.mainloop()\n"
)


def find_hwnd():
    from core.actions import find_windows_by_title
    wins = find_windows_by_title(RTWIN)
    return wins[0].hwnd if wins else 0


def find_app_hwnd():
    from core.actions import find_windows_by_title
    wins = find_windows_by_title("摸鱼哨兵")
    return wins[0].hwnd if wins else 0


if __name__ == "__main__":
    import win32gui, win32con

    # 1. 写入测试配置：启动即监测、阈值1（镜头前有人立即触发）、最小化测试窗口
    cfg = {
        "camera_index": 0,
        "face_threshold": 1,
        "consecutive_frames": 3,
        "score_threshold": 0.6,
        "min_face_size": 60,
        "cooldown_seconds": 10.0,
        "recover_frames": 25,
        "auto_recover": True,
        "monitor_on_start": True,
        "show_preview": True,
        "hotkeys": {"toggle_monitor": "Ctrl+Alt+M", "trigger_now": "Ctrl+Alt+H"},
        "actions": [{"type": "minimize_window", "target": RTWIN,
                     "enabled": True, "recoverable": False}],
    }
    with open(os.path.join(ROOT, "config.json"), "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

    # 2. 测试窗口
    tkproc = subprocess.Popen([sys.executable, "-c", TK_CODE])
    hwnd = 0
    for _ in range(30):
        hwnd = find_hwnd()
        if hwnd:
            break
        time.sleep(0.3)
    assert hwnd, "测试窗口未出现"

    # 3. 启动真实应用（stderr 落盘）
    err = open(os.path.join(ROOT, "tests", "_app_err.txt"), "w", encoding="utf-8")
    app = subprocess.Popen([sys.executable, os.path.join(ROOT, "main.py")],
                           stdout=err, stderr=err, cwd=ROOT)

    # 4. 等主窗口出现
    app_hwnd = 0
    for _ in range(30):
        app_hwnd = find_app_hwnd()
        if app_hwnd:
            break
        time.sleep(0.3)
    print("主窗口出现:", bool(app_hwnd))

    # 5. 等触发（镜头前有人 -> 最小化测试窗口）
    ok = False
    t0 = time.time()
    while time.time() - t0 < 15:
        if win32gui.IsIconic(hwnd):
            ok = True
            break
        time.sleep(0.3)
    print("监测触发并最小化测试窗口:", ok, f"({time.time()-t0:.1f}s)")

    # 6. 点关闭 -> 应隐藏而非退出（进程仍存活）
    win32gui.PostMessage(app_hwnd, win32con.WM_CLOSE, 0, 0)
    time.sleep(1.5)
    alive = app.poll() is None
    hidden = not win32gui.IsWindowVisible(app_hwnd)
    print("关闭按钮 -> 隐藏到托盘:", alive and hidden)

    # 7. 清理
    app.terminate()
    app.wait(timeout=5)
    tkproc.terminate()
    tkproc.wait(timeout=5)
    err.close()
    os.remove(os.path.join(ROOT, "config.json"))

    errtxt = open(os.path.join(ROOT, "tests", "_app_err.txt"), encoding="utf-8").read()
    crash = ("Traceback" in errtxt)
    print("stderr 有异常:", crash)
    if crash:
        print(errtxt[:2000])

    passed = ok and alive and hidden and not crash and bool(app_hwnd)
    print()
    print("REAL APP TEST " + ("PASSED" if passed else "FAILED"))
    sys.exit(0 if passed else 1)
