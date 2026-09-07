# -*- coding: utf-8 -*-
"""窗口选择对话框：列出当前可见窗口，点选后返回窗口标题。"""
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QLabel, QLineEdit,
                             QListWidget, QListWidgetItem, QDialogButtonBox,
                             QPushButton)

from core.actions import list_windows


class WindowPickerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择窗口")
        self.resize(560, 480)
        self.chosen_title = ""

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("选择一个窗口（目标将按标题模糊匹配，可在设置里手动改短）："))

        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("输入关键词过滤标题或进程名…")
        self.filter_edit.textChanged.connect(self._refresh)
        lay.addWidget(self.filter_edit)

        self.listw = QListWidget()
        self.listw.doubleClicked.connect(self.accept)
        lay.addWidget(self.listw, 1)

        refresh_btn = QPushButton("刷新列表")
        refresh_btn.clicked.connect(self._refresh)
        lay.addWidget(refresh_btn)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

        self._refresh()

    def _refresh(self):
        kw = self.filter_edit.text().strip().lower()
        self.listw.clear()
        for w in list_windows():
            text = f"{w.title}    ——  [{w.process}]"
            if kw and kw not in w.title.lower() and kw not in w.process.lower():
                continue
            item = QListWidgetItem(text)
            item.setData(0x0100, w.title)  # Qt.UserRole
            self.listw.addItem(item)

    def accept(self):
        item = self.listw.currentItem()
        if item is not None:
            self.chosen_title = item.data(0x0100)
        super().accept()

    @staticmethod
    def pick(parent=None):
        dlg = WindowPickerDialog(parent)
        if dlg.exec_() and dlg.chosen_title:
            return dlg.chosen_title
        return None
