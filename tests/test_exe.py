# -*- coding: utf-8 -*-
"""exe 端到端验收：启动打包后的 MoyuSentinel.exe，
验证主窗口出现、监测触发、动作执行、配置持久化、无崩溃。"""
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")
EXE = os.path.join(DIST, "MoyuSentinel.exe")
RTWIN = "SentinelExeWin"

TK_CODE = (
    "import tkinter\n"
    f"r = tkinter.Tk()\n"
    f"r.title('{RTWIN}')\n"
    "r.geometry('260x160+120+120')\n"
    "r.mainloop()\n"
)


def find_hwnd(title):
    from core.actions import find_windows_by_title
    wins = find_windows_by_title(title)
    return wins[0].hwnd if wins else 0


if __name__ == "__main__":
    import win32gui
    import psutil

    assert os.path.exists(EXE), "exe 不存在: " + EXE
    print("exe 大小: %.1f MB" % (os.path.getsize(EXE) / 1048576))

    # 清理现场
    for f in ("config.json", "sentinel.log"):
        p = os.path.join(DIST, f)
        if os.path.exists(p):
            os.remove(p)

    # 测试配置：启动即监测、阈值1、触发最小化测试窗口
    cfg = {
        "camera_index": 0, "face_threshold": 1, "consecutive_frames": 3,
        "score_threshold": 0.6, "min_face_size": 60, "cooldown_seconds": 10.0,
        "recover_frames": 25, "auto_recover": True, "monitor_on_start": True,
        "show_preview": True,
        "hotkeys": {"toggle_monitor": "Ctrl+Alt+S", "trigger_now": "Ctrl+Alt+H"},
        "actions": [{"type": "minimize_window", "target": RTWIN,
                     "enabled": True, "recoverable": False}],
    }
    with open(os.path.join(DIST, "config.json"), "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

    tkproc = subprocess.Popen([sys.executable, "-c", TK_CODE])
    hwnd = 0
    for _ in range(30):
        hwnd = find_hwnd(RTWIN)
        if hwnd:
            break
        time.sleep(0.3)
    assert hwnd, "测试窗口未出现"

    # 启动 exe，测启动耗时（进程创建 -> 主窗口可见）
    print("启动 exe ...")
    t0 = time.time()
    proc = subprocess.Popen([EXE])
    app_hwnd = 0
    while time.time() - t0 < 60:
        app_hwnd = find_hwnd("摸鱼哨兵")
        if app_hwnd and win32gui.IsWindowVisible(app_hwnd):
            break
        time.sleep(0.2)
    startup = time.time() - t0
    print("主窗口出现: %s  启动耗时 %.1fs" % (bool(app_hwnd), startup))

    # 等触发（镜头前有人 -> 最小化测试窗口）
    ok = False
    t1 = time.time()
    while time.time() - t1 < 20:
        if win32gui.IsIconic(hwnd):
            ok = True
            break
        time.sleep(0.3)
    print("监测触发并最小化测试窗口:", ok, "(%.1fs after window)" % (time.time() - t1))

    # 退出（taskkill；窗口×是隐藏到托盘）
    subprocess.run(["taskkill", "/IM", "MoyuSentinel.exe", "/F"],
                   capture_output=True)
    proc.wait(timeout=10)
    tkproc.terminate()
    tkproc.wait(timeout=5)

    # 检查崩溃日志与配置
    log = os.path.join(DIST, "sentinel.log")
    crash = ""
    if os.path.exists(log):
        content = open(log, encoding="utf-8", errors="replace").read()
        crash = "Traceback" in content
        if crash:
            print("--- sentinel.log ---")
            print(content[-3000:])
    config_kept = os.path.exists(os.path.join(DIST, "config.json"))
    print("配置文件仍在:", config_kept, "| 日志有崩溃:", crash)

    passed = bool(app_hwnd) and ok and config_kept and not crash
    print()
    print("EXE TEST " + ("PASSED" if passed else "FAILED"))
    sys.exit(0 if passed else 1)
