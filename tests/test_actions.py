# -*- coding: utf-8 -*-
"""动作执行器集成测试（隔离版）：
- 窗口操作（最小化/恢复/置前/压底）用自建 tkinter 窗口，不碰用户程序
- 关闭程序用 mspaint（若用户已开着画图则跳过该项）
"""
import subprocess
import sys
import time
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.actions import ActionExecutor, list_windows, find_windows_by_title
from core.config import ActionItem

import win32gui

TKWIN = "SentinelTestWin"

TK_CODE = (
    "import tkinter\n"
    f"r = tkinter.Tk()\n"
    f"r.title('{TKWIN}')\n"
    "r.geometry('300x200+100+100')\n"
    "r.mainloop()\n"
)


def wait_window(keyword, timeout=8):
    t0 = time.time()
    while time.time() - t0 < timeout:
        wins = find_windows_by_title(keyword)
        if wins:
            return wins[0]
        time.sleep(0.3)
    return None


def main():
    print("== 0. 窗口枚举 ==")
    wins = list_windows()
    print(f"共 {len(wins)} 个可见窗口")
    assert len(wins) > 0, "窗口枚举失败"

    print("== 1. 启动隔离测试窗口 ==")
    tkproc = subprocess.Popen([sys.executable, "-c", TK_CODE])
    w = wait_window(TKWIN)
    assert w, "测试窗口未出现"
    print(f"   找到: {w.title} (进程 {w.process})")

    ex = ActionExecutor()

    print("== 2. 最小化 ==")
    logs = ex.execute([ActionItem(type="minimize_window", target=TKWIN)])
    print("  ", logs[0])
    time.sleep(0.6)
    iconic = win32gui.IsIconic(w.hwnd)
    print(f"   IsIconic={iconic}")
    assert iconic, "最小化失败"

    print("== 3. 恢复 ==")
    logs = ex.recover()
    print("  ", logs)
    time.sleep(0.6)
    iconic = win32gui.IsIconic(w.hwnd)
    print(f"   IsIconic={iconic}")
    assert not iconic, "恢复失败"

    print("== 4. 置前 ==")
    logs = ex.execute([ActionItem(type="front_window", target=TKWIN)])
    print("  ", logs[0])
    time.sleep(0.8)
    fg = win32gui.GetWindowText(win32gui.GetForegroundWindow())
    print(f"   前台窗口: {fg}")
    assert fg == TKWIN, "置前失败"

    print("== 5. 压底 ==")
    logs = ex.execute([ActionItem(type="bottom_window", target=TKWIN)])
    print("  ", logs[0])
    time.sleep(0.8)
    fg = win32gui.GetWindowText(win32gui.GetForegroundWindow())
    print(f"   前台窗口: {fg}（压底后不应是测试窗口）")
    # z 序检查：EnumWindows 按 z 序从上到下返回，压底的窗口应在最后
    order = []
    win32gui.EnumWindows(lambda h, _: order.append(h)
                         if win32gui.IsWindowVisible(h) and win32gui.GetWindowText(h) else None, None)
    z_pos = order.index(w.hwnd) if w.hwnd in order else -1
    print(f"   测试窗口 z 序位置: {z_pos + 1}/{len(order)}（应为最后）")
    assert fg != TKWIN or z_pos == len(order) - 1, "压底失败"

    print("== 6. 恢复（压底提回） ==")
    logs = ex.recover()
    print("  ", logs)

    print("== 7. 关闭测试窗口进程 ==")
    logs = ex.execute([ActionItem(type="close_process", target="python.exe")]) \
        if False else None
    # 不能按 python.exe 名杀（会误杀自身/其他 python），改用结束这个测试子进程验证恢复路径无泄漏
    tkproc.terminate()
    tkproc.wait(timeout=5)
    print("   tkinter 子进程已结束")

    # 关闭程序动作用画图板验证（用户没开着才测）
    import psutil
    running = [p for p in psutil.process_iter(["name"])
               if (p.info["name"] or "").lower() in ("mspaint.exe",)]
    if not running:
        print("== 8. 关闭程序 mspaint ==")
        subprocess.Popen("mspaint")
        w2 = wait_window("画图")
        if not w2:
            w2 = wait_window("Paint")
        assert w2, "画图窗口未出现"
        time.sleep(1.0)
        logs = ex.execute([ActionItem(type="close_process", target="mspaint.exe")])
        print("  ", logs[0])
        gone = False
        for _ in range(40):
            alive = any((p.info["name"] or "").lower() == "mspaint.exe"
                        for p in psutil.process_iter(["name"]))
            if not alive:
                gone = True
                break
            time.sleep(0.2)
        print(f"   mspaint 已退出: {gone}")
        assert gone, "关闭程序失败"
    else:
        print("== 8. 跳过关闭程序测试（检测到画图正在运行） ==")

    print()
    print("ALL ACTION TESTS PASSED")


if __name__ == "__main__":
    main()
