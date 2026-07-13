import os
import urllib.parse
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
                             QGroupBox, QTextEdit, QPushButton, QTableWidget,
                             QTableWidgetItem, QHeaderView,
                             QMessageBox, QFormLayout, QCheckBox, QLineEdit,
                             QComboBox, QFileDialog)
from PyQt6.QtCore import Qt
from src.gui.worker import RenameWorker

VIDEO_EXTENSIONS = ['.mkv', '.mp4', '.avi', '.mov', '.wmv', '.ts', '.flv', '.webm', '.mpg', '.mpeg']

class MainTab(QWidget):
    """
    程序主页页签。
    负责：文件列表、自定义覆盖参数、预览表格、重命名任务调度。
    """
    def __init__(self, parent_window=None):
        super().__init__(parent_window)
        self.parent_window = parent_window
        self.layout = QVBoxLayout(self)
        self.init_ui()
        self.worker = None

    def init_ui(self):
        # --- 1. 上部：文件选择与自定义选项 ---
        self.top_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 1.1 左侧：文件列表
        file_group = QGroupBox("文件/文件夹选择")
        file_layout = QVBoxLayout()
        self.file_list = QTextEdit()
        self.file_list.setPlaceholderText("拖放文件/文件夹到此...")
        self.file_list.setAcceptDrops(False) # 禁用默认拖拽，由容器处理
        
        btn_layout = QHBoxLayout()
        self.browse_files_btn = QPushButton("浏览文件")
        self.browse_files_btn.clicked.connect(self.browse_files)
        self.browse_folder_btn = QPushButton("浏览文件夹")
        self.browse_folder_btn.clicked.connect(self.browse_folder)
        self.clear_btn = QPushButton("清空列表")
        self.clear_btn.clicked.connect(self.clear_file_list)
        btn_layout.addWidget(self.browse_files_btn)
        btn_layout.addWidget(self.browse_folder_btn)
        btn_layout.addWidget(self.clear_btn)
        
        file_layout.addWidget(self.file_list)
        file_layout.addLayout(btn_layout)
        file_group.setLayout(file_layout)
        self.top_splitter.addWidget(file_group)

        # 1.2 右侧：自定义覆盖参数
        custom_group = QGroupBox("识别参数覆盖")
        custom_layout = QFormLayout()
        
        self.custom_season_checkbox = QCheckBox("自定义季度")
        self.custom_season_input = QLineEdit()
        self.custom_season_input.setPlaceholderText("例如: 1")
        self.custom_season_input.setEnabled(False)
        self.custom_season_checkbox.toggled.connect(self.custom_season_input.setEnabled)
        custom_layout.addRow(self.custom_season_checkbox, self.custom_season_input)

        self.custom_episode_offset_checkbox = QCheckBox("自定义集数偏移")
        self.custom_episode_offset_input = QLineEdit()
        self.custom_episode_offset_input.setPlaceholderText("例如: 12 或 -12")
        self.custom_episode_offset_input.setEnabled(False)
        self.custom_episode_offset_checkbox.toggled.connect(self.custom_episode_offset_input.setEnabled)
        custom_layout.addRow(self.custom_episode_offset_checkbox, self.custom_episode_offset_input)

        self.custom_tmdbid_checkbox = QCheckBox("自定义TMDBID")
        tmdb_layout = QHBoxLayout()
        self.custom_tmdbid_input = QLineEdit()
        self.custom_tmdbid_input.setEnabled(False)
        self.custom_tmdb_media_combo = QComboBox()
        self.custom_tmdb_media_combo.addItems(["tv", "movie"])
        self.custom_tmdb_media_combo.setEnabled(False)
        tmdb_layout.addWidget(self.custom_tmdbid_input, 2)
        tmdb_layout.addWidget(self.custom_tmdb_media_combo, 1)
        custom_layout.addRow(self.custom_tmdbid_checkbox, tmdb_layout)
        
        self.custom_tmdbid_checkbox.toggled.connect(self.custom_tmdbid_input.setEnabled)
        self.custom_tmdbid_checkbox.toggled.connect(self.custom_tmdb_media_combo.setEnabled)
        
        custom_group.setLayout(custom_layout)
        self.top_splitter.addWidget(custom_group)
        self.layout.addWidget(self.top_splitter, 2)

        # --- 2. 中部：预览表格 ---
        preview_group = QGroupBox("预览/结果")
        preview_layout = QVBoxLayout()
        self.preview_table = QTableWidget(0, 4)
        self.preview_table.setHorizontalHeaderLabels(["原文件名", "新文件名", "目标主文件夹", "目标季文件夹"])
        self.preview_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        preview_layout.addWidget(self.preview_table)
        preview_group.setLayout(preview_layout)
        self.layout.addWidget(preview_group, 3)

        # --- 3. 下部：操作按钮 ---
        action_layout = QHBoxLayout()
        self.preview_btn = QPushButton("预览重命名")
        self.preview_btn.clicked.connect(lambda: self.start_processing(preview_only=True))
        self.execute_btn = QPushButton("执行重命名")
        self.execute_btn.clicked.connect(lambda: self.start_processing(preview_only=False))
        self.execute_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.cancel_processing)
        self.cancel_btn.setEnabled(False)
        action_layout.addWidget(self.preview_btn)
        action_layout.addWidget(self.execute_btn)
        action_layout.addWidget(self.cancel_btn)
        self.layout.addLayout(action_layout)
        
        # 恢复分割条状态
        self.restore_splitter_state()

    def restore_splitter_state(self):
        from src.utils.config import config
        state = config.get_value("main_splitter_state")
        if state:
            self.top_splitter.restoreState(state)

    def save_ui_states(self):
        """保存内部组件状态，供主窗口关闭时调用"""
        from src.utils.config import config
        config.set_value("main_splitter_state", self.top_splitter.saveState())

    def browse_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "选择视频文件", "", "视频文件 (*.mkv *.mp4 *.avi *.ts);;所有文件 (*.*)")
        if files: self.add_paths_to_list(files)

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if folder:
            video_files = []
            for root, _, files in os.walk(folder):
                for f in files:
                    if os.path.splitext(f)[1].lower() in VIDEO_EXTENSIONS:
                        video_files.append(os.path.join(root, f))
            self.add_paths_to_list(video_files)

    def add_paths_to_list(self, paths):
        current_text = self.file_list.toPlainText()
        existing = set(current_text.splitlines())
        
        processed = []
        for p in paths:
            # 1. URL 解码
            p = urllib.parse.unquote(p)
            
            # 2. 智能剥离协议头并处理 UNC 路径
            if p.startswith('file:///'): 
                # 本地路径格式 file:///D:/path
                p = p[8:]
            elif p.startswith('file://'):
                # 网络 UNC 路径格式 file://192.168.1.1/share
                # 剥离后需补回 // 以前缀表示这是网络路径
                p = '//' + p[7:]
            
            # 3. 针对 Windows 本地盘符的修正 (如 /D:/ -> D:/)
            if os.name == 'nt' and len(p) > 2 and p[0] == '/' and p[2] == ':':
                p = p[1:]
            
            # 4. 标准化路径 (会自动将 // 转为 \\\\)
            p = os.path.normpath(p)
            
            if p not in existing:
                processed.append(p)
                existing.add(p)
        if processed:
            prefix = "\n" if current_text.strip() else ""
            self.file_list.append(prefix + "\n".join(processed))

    def clear_file_list(self):
        self.file_list.clear()
        self.preview_table.setRowCount(0)
        # 通过主窗口访问日志 Tab 重置进度
        if hasattr(self.parent_window, 'log_tab'):
            self.parent_window.log_tab.reset()

    def start_processing(self, preview_only=False):
        file_text = self.file_list.toPlainText()
        file_paths = [p.strip() for p in file_text.splitlines() if p.strip()]
        if not file_paths:
            QMessageBox.warning(self, "警告", "请先添加文件！")
            return

        # 获取 SettingsTab 的最新全量配置 (包含联网参数)
        config_data = self.parent_window.settings_tab.get_config_data()
        
        # 注入 MainTab 特有的覆盖参数
        config_data['custom_settings'] = {
            'custom_season_enabled': self.custom_season_checkbox.isChecked(),
            'custom_season_value': self.custom_season_input.text(),
            'custom_episode_offset_enabled': self.custom_episode_offset_checkbox.isChecked(),
            'custom_episode_offset_value': self.custom_episode_offset_input.text(),
            'tmdb_id_override': self.custom_tmdbid_input.text() if self.custom_tmdbid_checkbox.isChecked() else None,
            'media_type_override': self.custom_tmdb_media_combo.currentText()
        }

        self.preview_table.setRowCount(0)
        self.set_ui_enabled(False)

        # 获取日志 Tab 并重置
        log_tab = self.parent_window.log_tab
        log_tab.reset()

        self.worker = RenameWorker(file_paths, config_data, preview_only)
        self.worker.log_signal.connect(log_tab.append)
        self.worker.progress_signal.connect(log_tab.set_progress)
        self.worker.preview_signal.connect(self.update_preview_table)
        self.worker.finished_signal.connect(self.processing_finished)
        self.worker.start()

        # 自动切换到日志 Tab
        self.parent_window.tab_widget.setCurrentWidget(log_tab)

    def update_preview_table(self, old, new, main, season):
        row = self.preview_table.rowCount()
        self.preview_table.insertRow(row)
        self.preview_table.setItem(row, 0, QTableWidgetItem(old))
        self.preview_table.setItem(row, 1, QTableWidgetItem(new))
        self.preview_table.setItem(row, 2, QTableWidgetItem(main))
        self.preview_table.setItem(row, 3, QTableWidgetItem(season))
        self.preview_table.scrollToBottom()

    def set_ui_enabled(self, enabled):
        self.browse_files_btn.setEnabled(enabled)
        self.browse_folder_btn.setEnabled(enabled)
        self.preview_btn.setEnabled(enabled)
        self.execute_btn.setEnabled(enabled)
        self.clear_btn.setEnabled(enabled)
        self.cancel_btn.setEnabled(not enabled)

    def cancel_processing(self):
        if self.worker: self.worker.requestInterruption()

    def processing_finished(self, results):
        self.set_ui_enabled(True)
        QMessageBox.information(self, "完成", f"任务结束！共处理 {len(results)} 个文件。")
