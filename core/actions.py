# -*- coding: utf-8 -*-
"""动作执行器：根据配置对窗口/进程执行触发动作，并支持人走后的自动恢复。"""
import threading
from typing import List, Optional

import ctypes
import psutil
import win32con
import win32gui
import win32process
import win32api

from .config import (ActionItem, ACT_CLOSE_PROCESS, ACT_MINIMIZE,
                     ACT_BOTTOM, ACT_FRONT, ACT_COMMAND, ACTION_LABELS)

import logging
log = logging.getLogger("sentinel")


# ---------------- 窗口枚举 ----------------

class WindowInfo:
    __slots__ = ("hwnd", "title", "process")

    def __init__(self, hwnd, title, process):
        self.hwnd = hwnd
        self.title = title
        self.process = process


def list_windows() -> List[WindowInfo]:
    """枚举所有可见、有标题的顶层窗口。"""
    result: List[WindowInfo] = []

    def _cb(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd)
        if not title:
            return
        exstyle = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        if exstyle & win32con.WS_EX_TOOLWINDOW:
            return
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            proc = psutil.Process(pid).name()
        except Exception:
            proc = ""
        result.append(WindowInfo(hwnd, title, proc))

    win32gui.EnumWindows(_cb, None)
    return result


def find_windows_by_title(keyword: str) -> List[WindowInfo]:
    """按标题模糊（包含）匹配，忽略大小写。"""
    kw = keyword.strip().lower()
    if not kw:
        return []
    return [w for w in list_windows() if kw in w.title.lower()]


# ---------------- 前台切换（Windows 对后台进程抢前台有限制，需附加线程输入） ----------------

def force_set_foreground(hwnd: int) -> None:
    try:
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        fg = win32gui.GetForegroundWindow()
        fg_tid, _ = win32process.GetWindowThreadProcessId(fg) if fg else (0, 0)
        cur_tid = win32api.GetCurrentThreadId()
        this_pid = win32api.GetCurrentProcessId()
        target_tid, _ = win32process.GetWindowThreadProcessId(hwnd)
        attached = False
        if fg_tid and fg_tid != cur_tid:
            win32process.AttachThreadInput(cur_tid, fg_tid, True)
            attached = True
        try:
            win32process.AttachThreadInput(cur_tid, target_tid, True)
            try:
                win32gui.SetForegroundWindow(hwnd)
                win32gui.BringWindowToTop(hwnd)
            finally:
                win32process.AttachThreadInput(cur_tid, target_tid, False)
        finally:
            if attached:
                win32process.AttachThreadInput(cur_tid, fg_tid, False)
    except Exception as e:
        log.warning("置前窗口失败: %s", e)


# ---------------- 执行器 ----------------

class ActionExecutor:
    """执行/恢复动作。触发时记录可逆动作影响的窗口，恢复时还原。"""

    def __init__(self):
        self._minimized: List[int] = []   # 被最小化的 hwnd
        self._bottomed: List[int] = []    # 被压底的 hwnd
        self._lock = threading.Lock()

    # ---------- 触发 ----------
    def execute(self, actions: List[ActionItem], source: str = "auto") -> List[str]:
        """执行全部启用动作，返回日志行列表。

        多次触发会累积恢复记录（去重），人走后统一恢复。
        """
        logs = []
        for act in actions:
            if not act.enabled or not act.target.strip():
                continue
            try:
                if act.type == ACT_MINIMIZE:
                    msg = self._do_minimize_window(act.target.strip(), act.recoverable)
                elif act.type == ACT_BOTTOM:
                    msg = self._do_bottom_window(act.target.strip(), act.recoverable)
                elif act.type == ACT_FRONT:
                    msg = self._do_front_window(act.target.strip())
                elif act.type == ACT_CLOSE_PROCESS:
                    msg = self._do_close_process(act.target.strip())
                elif act.type == ACT_COMMAND:
                    msg = self._do_run_command(act.target.strip())
                else:
                    msg = f"[跳过] 未知动作类型: {act.type}"
            except Exception as e:
                msg = f"[失败] {ACTION_LABELS.get(act.type, act.type)}({act.target}): {e}"
            logs.append(msg)
        return logs

    # ---------- 恢复 ----------
    def recover(self) -> List[str]:
        logs = []
        with self._lock:
            minimized, bottomed = self._minimized[:], self._bottomed[:]
            self._minimized.clear()
            self._bottomed.clear()
        for hwnd in minimized:
            try:
                if win32gui.IsWindow(hwnd):
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    logs.append(f"已还原最小化窗口: {win32gui.GetWindowText(hwnd)}")
            except Exception as e:
                logs.append(f"[失败] 还原窗口: {e}")
        for hwnd in bottomed:
            try:
                if win32gui.IsWindow(hwnd):
                    win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, 0, 0, 0, 0,
                                          win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
                    logs.append(f"已提回压底窗口: {win32gui.GetWindowText(hwnd)}")
            except Exception as e:
                logs.append(f"[失败] 提回窗口: {e}")
        return logs

    # ---------- 各动作实现 ----------
    def _do_close_process(self, proc_name: str) -> str:
        name = proc_name.lower()
        if not name.endswith(".exe"):
            name += ".exe"
        pids = []
        for p in psutil.process_iter(["pid", "name"]):
            try:
                if (p.info["name"] or "").lower() == name:
                    pids.append(p.info["pid"])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        if not pids:
            return f"[跳过] 未找到进程 {proc_name}"
        # 先对它的窗口发 WM_CLOSE 优雅关闭
        closed_windows = 0
        for w in list_windows():
            try:
                _, pid = win32process.GetWindowThreadProcessId(w.hwnd)
                if pid in pids:
                    win32gui.PostMessage(w.hwnd, win32con.WM_CLOSE, 0, 0)
                    closed_windows += 1
            except Exception:
                pass
        # 无窗口进程直接结束；有窗口的 2 秒后仍存活再强杀
        timer = threading.Timer(2.0, self._kill_if_alive, args=(pids, proc_name))
        timer.daemon = True
        timer.start()
        return f"正在关闭 {proc_name}（{len(pids)} 个进程，{closed_windows} 个窗口）"

    def _kill_if_alive(self, pids: List[int], name: str) -> None:
        for pid in pids:
            try:
                p = psutil.Process(pid)
                p.terminate()
            except psutil.NoSuchProcess:
                pass
            except Exception as e:
                log.warning("结束进程 %s(%s) 失败: %s", name, pid, e)

    def _do_minimize_window(self, keyword: str, recoverable: bool = True) -> str:
        wins = find_windows_by_title(keyword)
        if not wins:
            return f"[跳过] 未找到标题含“{keyword}”的窗口"
        with self._lock:
            for w in wins:
                try:
                    if not win32gui.IsIconic(w.hwnd):
                        win32gui.ShowWindow(w.hwnd, win32con.SW_MINIMIZE)
                        if recoverable and w.hwnd not in self._minimized:
                            self._minimized.append(w.hwnd)
                except Exception:
                    pass
        return f"已最小化 {len(wins)} 个“{keyword}”窗口"

    def _do_bottom_window(self, keyword: str, recoverable: bool = True) -> str:
        wins = find_windows_by_title(keyword)
        if not wins:
            return f"[跳过] 未找到标题含“{keyword}”的窗口"
        with self._lock:
            for w in wins:
                try:
                    win32gui.SetWindowPos(w.hwnd, win32con.HWND_BOTTOM, 0, 0, 0, 0,
                                          win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
                    if recoverable and w.hwnd not in self._bottomed:
                        self._bottomed.append(w.hwnd)
                except Exception:
                    pass
        # 沉底不自动移交焦点，把前台交给 z 序最高的其他窗口
        hwnds = {w.hwnd for w in wins}
        others = [w for w in list_windows() if w.hwnd not in hwnds]
        if others:
            force_set_foreground(others[0].hwnd)
        return f"已压底 {len(wins)} 个“{keyword}”窗口"

    def _do_front_window(self, keyword: str) -> str:
        wins = find_windows_by_title(keyword)
        if not wins:
            return f"[跳过] 未找到标题含“{keyword}”的窗口"
        # 优先匹配度最高的（标题最短的）
        best = min(wins, key=lambda w: len(w.title))
        force_set_foreground(best.hwnd)
        return f"已置前窗口: {best.title}"

    def _do_run_command(self, command: str) -> str:
        import subprocess
        subprocess.Popen(command, shell=True)
        return f"已执行命令: {command}"
