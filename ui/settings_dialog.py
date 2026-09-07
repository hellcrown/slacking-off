# -*- coding: utf-8 -*-
"""设置对话框：检测参数 / 动作列表 / 热键。保存时写回传入的 AppConfig。"""
from typing import List

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox, QLabel,
    QSpinBox, QDoubleSpinBox, QCheckBox, QComboBox, QLineEdit,
    QDialogButtonBox, QTableWidget, QTableWidgetItem, QPushButton,
    QHeaderView, QAbstractItemView, QMessageBox, QKeySequenceEdit,
)
from PyQt5.QtCore import Qt

from core.config import (AppConfig, ActionItem, ACTION_LABELS,
                         ACTION_TARGET_HINTS, ACTION_REVERSIBLE,
                         ACT_CLOSE_PROCESS, ACT_MINIMIZE, ACT_BOTTOM,
                         ACT_FRONT, ACT_COMMAND)
from .window_picker import WindowPickerDialog


class SettingsDialog(QDialog):
    def __init__(self, cfg: AppConfig, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.resize(720, 640)
        self.cfg = cfg
        self._action_rows: List[ActionItem] = []

        root = QVBoxLayout(self)

        # ---------- 检测设置 ----------
        g1 = QGroupBox("检测设置")
        f1 = QFormLayout(g1)
        self.camera_index = QSpinBox()
        self.camera_index.setRange(0, 9)
        self.camera_index.setValue(cfg.camera_index)
        f1.addRow("摄像头编号", self.camera_index)

        self.face_threshold = QSpinBox()
        self.face_threshold.setRange(1, 5)
        self.face_threshold.setToolTip("检测到该人数即触发。2=出现第二张脸；1=任何人出现（摄像头对门口模式）")
        self.face_threshold.setValue(cfg.face_threshold)
        f1.addRow("触发人数阈值", self.face_threshold)

        self.consecutive_frames = QSpinBox()
        self.consecutive_frames.setRange(1, 60)
        self.consecutive_frames.setToolTip("连续满足条件的帧数，越大越不容易误触发")
        self.consecutive_frames.setValue(cfg.consecutive_frames)
        f1.addRow("连续确认帧数", self.consecutive_frames)

        self.score_threshold = QDoubleSpinBox()
        self.score_threshold.setRange(0.1, 0.95)
        self.score_threshold.setSingleStep(0.05)
        self.score_threshold.setToolTip("人脸置信度阈值：越低越灵敏（0.5 敏感 / 0.9 严格）")
        self.score_threshold.setValue(cfg.score_threshold)
        f1.addRow("检测灵敏度阈值", self.score_threshold)

        self.min_face_size = QSpinBox()
        self.min_face_size.setRange(16, 500)
        self.min_face_size.setValue(cfg.min_face_size)
        f1.addRow("最小人脸尺寸(像素)", self.min_face_size)

        self.cooldown_seconds = QDoubleSpinBox()
        self.cooldown_seconds.setRange(1.0, 600.0)
        self.cooldown_seconds.setValue(cfg.cooldown_seconds)
        f1.addRow("触发冷却(秒)", self.cooldown_seconds)

        self.recover_frames = QSpinBox()
        self.recover_frames.setRange(1, 300)
        self.recover_frames.setValue(cfg.recover_frames)
        f1.addRow("恢复确认帧数", self.recover_frames)

        self.auto_recover = QCheckBox("人离开后自动恢复窗口（还原最小化/压底）")
        self.auto_recover.setChecked(cfg.auto_recover)
        f1.addRow("", self.auto_recover)

        self.monitor_on_start = QCheckBox("启动软件即开始监测")
        self.monitor_on_start.setChecked(cfg.monitor_on_start)
        f1.addRow("", self.monitor_on_start)

        self.show_preview = QCheckBox("主窗口显示摄像头预览")
        self.show_preview.setChecked(cfg.show_preview)
        f1.addRow("", self.show_preview)
        root.addWidget(g1)

        # ---------- 动作列表 ----------
        g2 = QGroupBox("触发动作（从上到下依次执行）")
        v2 = QVBoxLayout(g2)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["启用", "类型", "目标", "人走后恢复"])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        v2.addWidget(self.table)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("添加动作")
        add_btn.clicked.connect(self._add_row)
        pick_btn = QPushButton("从当前窗口选择目标…")
        pick_btn.clicked.connect(self._pick_target)
        del_btn = QPushButton("删除选中")
        del_btn.clicked.connect(self._del_row)
        up_btn = QPushButton("上移")
        up_btn.clicked.connect(lambda: self._move_row(-1))
        down_btn = QPushButton("下移")
        down_btn.clicked.connect(lambda: self._move_row(1))
        for b in (add_btn, pick_btn, del_btn, up_btn, down_btn):
            btn_row.addWidget(b)
        btn_row.addStretch(1)
        v2.addLayout(btn_row)

        self.hint = QLabel("")
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet("color: gray;")
        v2.addWidget(self.hint)
        self.table.currentCellChanged.connect(self._update_hint)
        root.addWidget(g2, 1)

        # ---------- 热键 ----------
        g3 = QGroupBox("全局热键")
        f3 = QFormLayout(g3)
        self.hk_toggle = QKeySequenceEdit()
        self.hk_toggle.setKeySequence(cfg.hotkeys.toggle_monitor)
        f3.addRow("开始/停止监测", self.hk_toggle)
        self.hk_trigger = QKeySequenceEdit()
        self.hk_trigger.setKeySequence(cfg.hotkeys.trigger_now)
        f3.addRow("立即执行动作（老板键）", self.hk_trigger)
        hk_note = QLabel("热键需含 Ctrl/Alt/Shift 至少一个修饰键；删除请点击输入框后按 Esc。")
        hk_note.setStyleSheet("color: gray;")
        f3.addRow("", hk_note)
        root.addWidget(g3)

        # ---------- 按钮 ----------
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._on_save)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

        for act in cfg.actions:
            self._add_row(act)

    # ---------- 动作表格 ----------
    def _add_row(self, act: ActionItem = None):
        if act is None:
            act = ActionItem(type=ACT_MINIMIZE, target="")
        row = self.table.rowCount()
        self.table.insertRow(row)

        cb_enable = QCheckBox()
        cb_enable.setChecked(act.enabled)
        self.table.setCellWidget(row, 0, cb_enable)

        combo = QComboBox()
        for t, label in ACTION_LABELS.items():
            combo.addItem(label, t)
        combo.setCurrentIndex(combo.findData(act.type))
        combo.currentIndexChanged.connect(self._update_hint)
        self.table.setCellWidget(row, 1, combo)

        edit = QLineEdit(act.target)
        edit.setPlaceholderText("目标")
        self.table.setCellWidget(row, 2, edit)

        cb_recover = QCheckBox()
        reversible = ACTION_REVERSIBLE.get(act.type, False)
        cb_recover.setChecked(act.recoverable and reversible)
        cb_recover.setEnabled(reversible)
        self.table.setCellWidget(row, 3, cb_recover)

        self._action_rows.append(None)  # 占位，保存时统一读取
        combo.currentIndexChanged.connect(
            lambda _, r=row, c=combo, cb=cb_recover:
            self._on_type_changed(r, c, cb))

    def _on_type_changed(self, row, combo, cb_recover):
        reversible = ACTION_REVERSIBLE.get(combo.currentData(), False)
        cb_recover.setEnabled(reversible)
        if not reversible:
            cb_recover.setChecked(False)
        edit = self.table.cellWidget(row, 2)
        if edit is not None:
            edit.setPlaceholderText(ACTION_TARGET_HINTS.get(combo.currentData(), ""))
        self._update_hint()

    def _update_hint(self, *args):
        row = self.table.currentRow()
        if row < 0:
            self.hint.setText("")
            return
        combo = self.table.cellWidget(row, 1)
        edit = self.table.cellWidget(row, 2)
        if combo is None:
            return
        t = combo.currentData()
        hint = ACTION_TARGET_HINTS.get(t, "")
        cur = edit.text() if edit else ""
        self.hint.setText(f"目标说明：{hint}" + (f"　当前：{cur}" if cur else ""))

    def _pick_target(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先选中一行动作")
            return
        title = WindowPickerDialog.pick(self)
        if title:
            edit = self.table.cellWidget(row, 2)
            edit.setText(title)

    def _del_row(self):
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)

    def _move_row(self, delta: int):
        row = self.table.currentRow()
        if row < 0:
            return
        target = row + delta
        if 0 <= target < self.table.rowCount():
            # 简单起见：读取全部行数据后重建
            rows = self._read_rows()
            rows[row], rows[target] = rows[target], rows[row]
            self.table.setRowCount(0)
            for act in rows:
                self._add_row(act)
            self.table.setCurrentCell(target, 0)

    def _read_rows(self) -> List[ActionItem]:
        acts = []
        for r in range(self.table.rowCount()):
            enable = self.table.cellWidget(r, 0)
            combo = self.table.cellWidget(r, 1)
            edit = self.table.cellWidget(r, 2)
            recover = self.table.cellWidget(r, 3)
            if not (enable and combo and edit):
                continue
            acts.append(ActionItem(
                type=combo.currentData(),
                target=edit.text().strip(),
                enabled=enable.isChecked(),
                recoverable=bool(recover and recover.isChecked()),
            ))
        return acts

    # ---------- 保存 ----------
    def _seq_text(self, widget: QKeySequenceEdit) -> str:
        seq = widget.keySequence()
        s = seq.toString().split(",")[0].strip()
        return s

    def _on_save(self):
        acts = self._read_rows()
        enabled_empty = [a for a in acts if a.enabled and not a.target]
        if enabled_empty:
            QMessageBox.warning(self, "提示", "有已启用但目标为空的动作，请填写目标或取消启用。")
            return
        hk_t = self._seq_text(self.hk_toggle)
        hk_f = self._seq_text(self.hk_trigger)
        if hk_t and "+" not in hk_t:
            QMessageBox.warning(self, "提示", f"热键“{hk_t}”缺少修饰键（Ctrl/Alt/Shift），请重新设置。")
            return
        if hk_f and "+" not in hk_f:
            QMessageBox.warning(self, "提示", f"热键“{hk_f}”缺少修饰键（Ctrl/Alt/Shift），请重新设置。")
            return

        c = self.cfg
        c.camera_index = self.camera_index.value()
        c.face_threshold = self.face_threshold.value()
        c.consecutive_frames = self.consecutive_frames.value()
        c.score_threshold = self.score_threshold.value()
        c.min_face_size = self.min_face_size.value()
        c.cooldown_seconds = self.cooldown_seconds.value()
        c.recover_frames = self.recover_frames.value()
        c.auto_recover = self.auto_recover.isChecked()
        c.monitor_on_start = self.monitor_on_start.isChecked()
        c.show_preview = self.show_preview.isChecked()
        if hk_t:
            c.hotkeys.toggle_monitor = hk_t
        if hk_f:
            c.hotkeys.trigger_now = hk_f
        c.actions = acts
        self.accept()
