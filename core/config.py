# -*- coding: utf-8 -*-
"""配置管理：dataclass 定义 + JSON 持久化。"""
import json
import os
import sys
from dataclasses import dataclass, field, asdict
from typing import List

# 动作类型常量
ACT_CLOSE_PROCESS = "close_process"      # 关闭程序（按进程名）
ACT_MINIMIZE = "minimize_window"         # 最小化窗口（按标题模糊匹配）
ACT_BOTTOM = "bottom_window"             # 窗口压底
ACT_FRONT = "front_window"               # 指定窗口置前
ACT_COMMAND = "run_command"              # 执行自定义命令

ACTION_LABELS = {
    ACT_CLOSE_PROCESS: "关闭程序",
    ACT_MINIMIZE: "最小化窗口",
    ACT_BOTTOM: "窗口压底",
    ACT_FRONT: "窗口置前",
    ACT_COMMAND: "执行命令",
}

ACTION_TARGET_HINTS = {
    ACT_CLOSE_PROCESS: "进程名，如 chrome.exe",
    ACT_MINIMIZE: "窗口标题关键词，如 微信",
    ACT_BOTTOM: "窗口标题关键词，如 网易云音乐",
    ACT_FRONT: "窗口标题关键词，如 工作周报",
    ACT_COMMAND: "命令行，如 notepad",
}

# 各动作类型是否可逆（能否参与自动恢复）：
# 最小化->还原、压底->提回；置前/关程序/命令不可逆也不应撤销
ACTION_REVERSIBLE = {
    ACT_CLOSE_PROCESS: False,
    ACT_MINIMIZE: True,
    ACT_BOTTOM: True,
    ACT_FRONT: False,
    ACT_COMMAND: False,
}


@dataclass
class ActionItem:
    type: str = ACT_MINIMIZE
    target: str = ""
    enabled: bool = True
    recoverable: bool = True   # 人走后是否自动恢复（仅可逆动作生效）


@dataclass
class Hotkeys:
    toggle_monitor: str = "Ctrl+Alt+S"   # 切换监测开关（Ctrl+Alt+M 常被其他软件占用）
    trigger_now: str = "Ctrl+Alt+H"      # 老板键：立即执行全部动作


@dataclass
class AppConfig:
    camera_index: int = 0
    face_threshold: int = 2        # 检测到 >= 该人数则触发（2=出现第二张脸）
    consecutive_frames: int = 8    # 连续 N 帧满足条件才触发（防误报）
    recover_frames: int = 25       # 人数回落保持 N 帧后执行恢复
    score_threshold: float = 0.6   # YuNet 置信度阈值：越低越灵敏（0.9 严格 / 0.5 敏感）
    min_face_size: int = 80        # 最小人脸像素（宽/高），过滤远处小误检
    cooldown_seconds: float = 10.0 # 触发后的冷却时间
    auto_recover: bool = True      # 人走后自动恢复窗口
    monitor_on_start: bool = False # 启动软件即开始监测
    show_preview: bool = True      # 主窗口显示摄像头预览
    hotkeys: Hotkeys = field(default_factory=Hotkeys)
    actions: List[ActionItem] = field(default_factory=lambda: [
        ActionItem(type=ACT_MINIMIZE, target="", enabled=False),
    ])


def app_root() -> str:
    """程序根目录：脚本模式 = main.py 所在目录；打包后 = exe 所在目录。

    打包后 __file__ 指向临时解压目录，配置必须写到 exe 旁边才能持久保存。
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _config_path() -> str:
    return os.path.join(app_root(), "config.json")


def load_config() -> AppConfig:
    cfg = AppConfig()
    path = _config_path()
    if not os.path.exists(path):
        return cfg
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        hk = data.pop("hotkeys", {}) or {}
        acts = data.pop("actions", []) or []
        for k, v in data.items():
            if hasattr(cfg, k) and not k.startswith("_"):
                setattr(cfg, k, v)
        if isinstance(hk, dict):
            for k, v in hk.items():
                if hasattr(cfg.hotkeys, k):
                    setattr(cfg.hotkeys, k, v)
        items = []
        for a in acts:
            if isinstance(a, dict) and "type" in a:
                items.append(ActionItem(
                    type=a.get("type", ACT_MINIMIZE),
                    target=a.get("target", ""),
                    enabled=bool(a.get("enabled", True)),
                    recoverable=bool(a.get("recoverable", True)),
                ))
        if items:
            cfg.actions = items
    except Exception:
        # 配置损坏则回退默认
        return AppConfig()
    return cfg


def save_config(cfg: AppConfig) -> None:
    data = asdict(cfg)
    with open(_config_path(), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
