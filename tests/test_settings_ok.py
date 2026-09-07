# -*- coding: utf-8 -*-
"""回归测试：设置对话框保存路径（曾因 NameError 在点 OK 后崩溃）。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer

app = QApplication(sys.argv)

from core.config import load_config, save_config, ACT_MINIMIZE, ACT_CLOSE_PROCESS
from ui.main_window import MainWindow
from ui.settings_dialog import SettingsDialog

cfg = load_config()
w = MainWindow(cfg)
w.show()
app.processEvents()
w.register_hotkeys()
assert w._hotkey_ids, "热键注册失败"

# 场景1：不做任何修改直接点 OK（曾触发 NameError 崩溃）
d = SettingsDialog(w.cfg, w)
d._on_save()
assert d.result() == 1, "场景1 OK 失败"
print("场景1 默认配置直接保存: OK")

# 场景2：添加两行动作再保存
d2 = SettingsDialog(w.cfg, w)
d2._add_row()
d2.table.cellWidget(0, 2).setText("微信")           # 默认占位行 -> 最小化 微信
cb = d2.table.cellWidget(1, 1)                       # 新行类型改为 关闭程序
idx = [i for i in range(cb.count()) if cb.itemData(i) == ACT_CLOSE_PROCESS][0]
cb.setCurrentIndex(idx)
d2.table.cellWidget(1, 2).setText("chrome.exe")
d2._on_save()
assert d2.result() == 1, "场景2 OK 失败"
types = [a.type for a in w.cfg.actions]
targets = [a.target for a in w.cfg.actions]
assert ACT_MINIMIZE in types and ACT_CLOSE_PROCESS in types, types
assert "微信" in targets and "chrome.exe" in targets, targets
print("场景2 添加动作后保存: OK ->", targets)

# 场景3：保存到磁盘 + 重新读取
save_config(w.cfg)
cfg2 = load_config()
assert [a.target for a in cfg2.actions] == targets
print("场景3 配置落盘/读回: OK")

# 清理：退出应用，删除测试配置
def cleanup():
    w._quit()

QTimer.singleShot(200, cleanup)
app.exec_()
os.remove(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json"))
print()
print("SETTINGS OK REGRESSION PASSED")
