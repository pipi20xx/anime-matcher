from datetime import datetime
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                             QTextEdit, QPushButton, QProgressBar, QCheckBox,
                             QFileDialog, QMessageBox, QLabel, QComboBox)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QTextCursor, QColor


class LogTab(QWidget):
    """
    操作日志页签。
    负责：展示运行日志、进度条、日志导出、自动滚动、级别筛选。
    """
    # 外部可连接此信号来追加日志
    append_log = pyqtSignal(str)
    # 外部可连接此信号来更新进度
    update_progress = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self._auto_scroll = True
        self._log_history: list[str] = []
        self._current_filter = "全部"
        self.init_ui()

    def init_ui(self):
        # --- 1. 顶部工具栏 ---
        toolbar_layout = QHBoxLayout()

        # 左侧：进度条 + 百分比
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(22)
        self.progress_bar.setValue(0)
        self.progress_label = QLabel("就绪")
        self.progress_label.setFixedWidth(60)
        toolbar_layout.addWidget(QLabel("进度:"))
        toolbar_layout.addWidget(self.progress_bar, 1)
        toolbar_layout.addWidget(self.progress_label)

        # 分隔
        toolbar_layout.addSpacing(16)

        # 右侧：日志操作按钮
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["全部", "✅ 信息", "⚠️ 警告", "❌ 错误", "📂 文件"])
        self.filter_combo.setFixedWidth(120)
        self.filter_combo.currentTextChanged.connect(self._apply_filter)

        self.auto_scroll_cb = QCheckBox("自动滚动")
        self.auto_scroll_cb.setChecked(True)
        self.auto_scroll_cb.toggled.connect(self._toggle_auto_scroll)

        self.clear_btn = QPushButton("清空日志")
        self.clear_btn.clicked.connect(self.clear_logs)

        self.export_btn = QPushButton("导出日志")
        self.export_btn.clicked.connect(self.export_logs)

        toolbar_layout.addWidget(QLabel("筛选:"))
        toolbar_layout.addWidget(self.filter_combo)
        toolbar_layout.addWidget(self.auto_scroll_cb)
        toolbar_layout.addWidget(self.clear_btn)
        toolbar_layout.addWidget(self.export_btn)

        self.layout.addLayout(toolbar_layout)

        # --- 2. 日志文本区 ---
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFont(QFont("Consolas", 10))
        self.log_output.setPlaceholderText("操作日志将在此显示...")
        self.layout.addWidget(self.log_output, 1)

        # --- 3. 底部状态栏 ---
        status_layout = QHBoxLayout()
        self.status_label = QLabel("共 0 条日志")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        self.layout.addLayout(status_layout)

        # 连接内部信号
        self.append_log.connect(self._append_text)
        self.update_progress.connect(self._set_progress)

    # ========== 公开方法（供 MainTab 调用） ==========

    def append(self, text: str):
        """追加一条日志（线程安全，通过信号传递）"""
        self.append_log.emit(text)

    def set_progress(self, value: int):
        """设置进度条（线程安全）"""
        self.update_progress.emit(value)

    def reset(self):
        """重置日志和进度"""
        self._log_history.clear()
        self.log_output.clear()
        self.progress_bar.setValue(0)
        self.progress_label.setText("就绪")
        self._update_status()

    # ========== 内部方法 ==========

    def _append_text(self, text: str):
        """实际追加日志文本到界面（主线程执行）"""
        self._log_history.append(text)
        # 如果当前筛选不匹配则不显示，但仍保存到历史
        if self._matches_filter(text):
            self._display_line(text)
        self._update_status()

    def _display_line(self, text: str):
        """显示一行日志，带颜色标记"""
        # 根据日志内容着色（深色，适配白色背景）
        if "❌" in text or "💥" in text:
            color = QColor("#C62828")  # 深红 - 错误
        elif "⚠️" in text:
            color = QColor("#E65100")  # 深橙 - 警告
        elif "✅" in text:
            color = QColor("#2E7D32")  # 深绿 - 成功
        elif "┏" in text or "┗" in text:
            color = QColor("#1565C0")  # 深蓝 - 边界
        elif "📂" in text or "📁" in text:
            color = QColor("#6A1B9A")  # 深紫 - 文件
        else:
            color = QColor("#333333")  # 默认深灰

        self.log_output.setTextColor(color)
        self.log_output.append(text)
        self.log_output.setTextColor(QColor("#333333"))  # 恢复默认色

        if self._auto_scroll:
            self.log_output.moveCursor(QTextCursor.MoveOperation.End)

    def _set_progress(self, value: int):
        self.progress_bar.setValue(value)
        if value == 0:
            self.progress_label.setText("就绪")
        elif value >= 100:
            self.progress_label.setText("完成")
        else:
            self.progress_label.setText(f"{value}%")

    def _matches_filter(self, text: str) -> bool:
        if self._current_filter == "全部":
            return True
        elif self._current_filter == "✅ 信息":
            return "✅" in text
        elif self._current_filter == "⚠️ 警告":
            return "⚠️" in text
        elif self._current_filter == "❌ 错误":
            return "❌" in text or "💥" in text
        elif self._current_filter == "📂 文件":
            return "📂" in text or "📁" in text
        return True

    def _apply_filter(self, filter_text: str):
        """重新按筛选条件渲染日志"""
        self._current_filter = filter_text
        self.log_output.clear()
        for line in self._log_history:
            if self._matches_filter(line):
                self._display_line(line)

    def _toggle_auto_scroll(self, checked: bool):
        self._auto_scroll = checked
        if checked:
            self.log_output.moveCursor(QTextCursor.MoveOperation.End)

    def _update_status(self):
        total = len(self._log_history)
        shown = sum(1 for l in self._log_history if self._matches_filter(l))
        if total == shown:
            self.status_label.setText(f"共 {total} 条日志")
        else:
            self.status_label.setText(f"显示 {shown}/{total} 条日志")

    def clear_logs(self):
        reply = QMessageBox.question(
            self, "确认", "确定要清空所有日志吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.reset()

    def export_logs(self):
        if not self._log_history:
            QMessageBox.information(self, "提示", "当前没有日志可导出。")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"AnimeProRenamer_Log_{timestamp}.txt"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出日志", default_name, "文本文件 (*.txt);;所有文件 (*.*)"
        )
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(f"# AnimeProRenamer 操作日志\n")
                    f.write(f"# 导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"# 日志条数: {len(self._log_history)}\n")
                    f.write("=" * 60 + "\n\n")
                    for line in self._log_history:
                        f.write(line + "\n")
                QMessageBox.information(self, "成功", f"日志已导出到:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出失败: {e}")
