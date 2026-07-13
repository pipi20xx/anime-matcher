import os
import sqlite3
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QGroupBox, QFormLayout, 
                             QLineEdit, QComboBox, QPlainTextEdit, QPushButton, 
                             QLabel, QMessageBox, QHBoxLayout, QCheckBox, 
                             QScrollArea, QFrame)
from PyQt6.QtCore import Qt
from src.utils.config import config
from src.utils.paths import CORE_DB_PATH


class SettingsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.main_layout = QVBoxLayout(self)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content_widget = QWidget()
        self.layout = QVBoxLayout(content_widget)
        
        self.init_ui()
        self.load_settings()
        
        scroll.setWidget(content_widget)
        self.main_layout.addWidget(scroll)

    def init_ui(self):
        # 1. 格式设置
        format_group = QGroupBox("重命名与目录格式设置")
        format_layout = QFormLayout()
        
        # --- 剧集部分 ---
        self.rename_format_combo = QComboBox()
        self.rename_format_combo.addItems([
            "[{team}] {title} - S{season_02}E{episode_02} [{resolution}][{video_encode}][{subtitle}]",
            "S{season_02}E{episode_02} - {filename}",
            "{title} - S{season_02}E{episode_02} - {filename}"
        ])
        self.rename_format_combo.setEditable(True)
        format_layout.addRow("剧集文件名格式:", self.rename_format_combo)
        
        self.folder_format_input = QLineEdit()
        format_layout.addRow("剧集主文件夹:", self.folder_format_input)
        
        self.season_format_input = QLineEdit()
        format_layout.addRow("剧集季文件夹:", self.season_format_input)

        format_layout.addRow(QFrame()) # 分割线

        # --- 电影部分 ---
        self.movie_format_combo = QComboBox()
        self.movie_format_combo.addItems([
            "{title} ({year}) [{resolution}][{video_encode}][{source}]",
            "{title}.{year}.{resolution}.{video_encode}-{team}"
        ])
        self.movie_format_combo.setEditable(True)
        format_layout.addRow("电影文件名格式:", self.movie_format_combo)
        
        self.movie_folder_input = QLineEdit()
        format_layout.addRow("电影文件夹格式:", self.movie_folder_input)
        
        format_group.setLayout(format_layout)
        self.layout.addWidget(format_group)

        # 2. 联网匹配
        net_group = QGroupBox("联网匹配设置 (TMDB / Bangumi)")
        net_layout = QFormLayout()
        self.with_cloud_cb = QCheckBox("云端联动")
        self.with_cloud_cb.setChecked(True)
        net_layout.addRow(self.with_cloud_cb)
        self.tmdb_api_key_input = QLineEdit()
        net_layout.addRow("TMDB API Key:", self.tmdb_api_key_input)
        self.tmdb_proxy_input = QLineEdit()
        net_layout.addRow("TMDB 代理:", self.tmdb_proxy_input)
        self.bangumi_token_input = QLineEdit()
        net_layout.addRow("Bangumi Token:", self.bangumi_token_input)
        self.bangumi_proxy_input = QLineEdit()
        net_layout.addRow("Bangumi 代理:", self.bangumi_proxy_input)
        
        self.use_storage_cb = QCheckBox("智能记忆与本地缓存")
        self.use_storage_cb.setChecked(True)
        net_layout.addRow(self.use_storage_cb)
        
        strat_layout = QHBoxLayout()
        self.anime_priority_cb = QCheckBox("动画优先级加权")
        self.bangumi_priority_cb = QCheckBox("Bangumi 优先")
        self.bangumi_failover_cb = QCheckBox("Bangumi 故障转移")
        strat_layout.addWidget(self.anime_priority_cb)
        strat_layout.addWidget(self.bangumi_priority_cb)
        strat_layout.addWidget(self.bangumi_failover_cb)
        net_layout.addRow("策略:", strat_layout)
        
        self.batch_enhancement_cb = QCheckBox("合集增强")
        net_layout.addRow(self.batch_enhancement_cb)
        
        net_group.setLayout(net_layout)
        self.layout.addWidget(net_group)

        # 3. 数据库管理
        db_group = QGroupBox("数据库管理")
        db_layout = QHBoxLayout()
        self.clear_cache_btn = QPushButton("清理元数据缓存")
        self.clear_cache_btn.clicked.connect(lambda: self.clear_core_db_table("metadata_cache"))
        self.clear_memory_btn = QPushButton("清理标题记忆")
        self.clear_memory_btn.clicked.connect(lambda: self.clear_core_db_table("recognition_memory"))
        self.clear_fingerprint_btn = QPushButton("清理指纹缓存")
        self.clear_fingerprint_btn.clicked.connect(lambda: self.clear_core_db_table("fingerprint_cache"))
        db_layout.addWidget(self.clear_cache_btn)
        db_layout.addWidget(self.clear_memory_btn)
        db_layout.addWidget(self.clear_fingerprint_btn)
        db_group.setLayout(db_layout)
        self.layout.addWidget(db_group)

        # 4. 内核状态 (内置，无需下载)
        algo_group = QGroupBox("识别内核")
        algo_layout = QVBoxLayout()
        self.algo_status_label = QLabel("内核状态: 内置 (recognition_service Pipeline)")
        self.algo_status_label.setStyleSheet(
            "color: white; background-color: green; font-weight: bold; "
            "border-radius: 3px; padding: 4px;"
        )
        algo_layout.addWidget(self.algo_status_label)
        
        help_btn = QPushButton("💡 占位符帮助文档")
        help_btn.clicked.connect(self.show_placeholder_help)
        algo_layout.addWidget(help_btn)
        
        algo_group.setLayout(algo_layout)
        self.layout.addWidget(algo_group)

        # 5. 噪声清洗
        self.regex_rules_edit = QPlainTextEdit()
        self.regex_rules_edit.setPlaceholderText("(?i) unwanted => replacement")
        regex_group = QGroupBox("重命名后正则替换")
        r_layout = QVBoxLayout()
        r_layout.addWidget(self.regex_rules_edit)
        regex_group.setLayout(r_layout)
        self.layout.addWidget(regex_group)

        # 6. 保存按钮
        self.save_btn = QPushButton("保存配置并生效")
        self.save_btn.setFixedHeight(45)
        self.save_btn.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold;")
        self.save_btn.clicked.connect(self.save_settings)
        self.layout.addWidget(self.save_btn)

    def show_placeholder_help(self):
        msg = (
            "重命名格式支持以下占位符 (用花括号包裹):\n\n"
            "── 最终结论字段 (final_result) ──\n"
            "{title}            - 最终采信标题\n"
            "{tmdb_id}          - TMDB 唯一识别码\n"
            "{category}         - 媒体分类 (剧集/电影)\n"
            "{processed_name}   - 渲染后标题 (按专家规则重命名后)\n"
            "{season}           - 季号 (不补零)\n"
            "{season_02}        - 季号补零 (如 01)\n"
            "{episode}          - 集号或范围 (如 13 或 01-12)\n"
            "{episode_02}       - 集号补零 (如 05)\n"
            "{team}             - 制作小组\n"
            "{resolution}       - 分辨率\n"
            "{video_encode}     - 视频编码\n"
            "{video_effect}     - 视频特效 (如 HDR, Dolby Vision)\n"
            "{audio_encode}     - 音频编码\n"
            "{subtitle}         - 字幕语言\n"
            "{source}           - 资源来源\n"
            "{platform}         - 发布平台\n"
            "{origin_country}   - 制片国家\n"
            "{vote_average}     - 媒体评分\n"
            "{year}             - 最终年份\n"
            "{release_date}     - 正式上映日期\n"
            "{poster_path}      - 云端海报图片路径\n"
            "{duration}         - 识别耗时\n"
            "{filename}         - 原始文件名 (无后缀)\n"
            "{path}             - 原始完整路径"
        )
        QMessageBox.information(self, "占位符指南", msg)

    def clear_core_db_table(self, table_name):
        if not os.path.exists(CORE_DB_PATH):
            QMessageBox.warning(self, "提示", "数据库尚未创建。")
            return
        if QMessageBox.question(self, '确认', f"确定清理 {table_name}？") == QMessageBox.StandardButton.Yes:
            try:
                conn = sqlite3.connect(CORE_DB_PATH)
                cursor = conn.cursor()
                cursor.execute(f"DELETE FROM {table_name}")
                conn.commit()
                conn.close()
                QMessageBox.information(self, "成功", f"已清理 {table_name}。")
            except Exception as e:
                QMessageBox.warning(self, "错误", str(e))

    def load_settings(self):
        # 剧集
        self.rename_format_combo.setCurrentText(
            config.get_value("rename_format", "S{season_02}E{episode_02} - {filename}")
        )
        self.folder_format_input.setText(
            config.get_value("folder_format", "({year}){title}[tmdbid={tmdb_id}]")
        )
        self.season_format_input.setText(
            config.get_value("season_format", "Season {season}")
        )
        
        # 电影
        self.movie_format_combo.setCurrentText(
            config.get_value("movie_format", "{title} ({year}) [{resolution}][{video_encode}]")
        )
        self.movie_folder_input.setText(
            config.get_value("movie_folder_format", "({year}){title}[tmdbid={tmdb_id}]")
        )
        
        self.regex_rules_edit.setPlainText(config.get_value("regex_rules", ""))
        self.with_cloud_cb.setChecked(config.get_value("with_cloud", True, type=bool))
        self.tmdb_api_key_input.setText(config.get_value("tmdb_api_key", ""))
        self.tmdb_proxy_input.setText(config.get_value("tmdb_proxy", ""))
        self.bangumi_token_input.setText(config.get_value("bangumi_token", ""))
        self.bangumi_proxy_input.setText(config.get_value("bangumi_proxy", ""))
        self.use_storage_cb.setChecked(config.get_value("use_storage", True, type=bool))
        self.anime_priority_cb.setChecked(config.get_value("anime_priority", True, type=bool))
        self.bangumi_priority_cb.setChecked(config.get_value("bangumi_priority", False, type=bool))
        self.bangumi_failover_cb.setChecked(config.get_value("bangumi_failover", True, type=bool))
        self.batch_enhancement_cb.setChecked(config.get_value("batch_enhancement", False, type=bool))

    def save_settings(self):
        config.set_value("rename_format", self.rename_format_combo.currentText())
        config.set_value("folder_format", self.folder_format_input.text())
        config.set_value("season_format", self.season_format_input.text())
        
        config.set_value("movie_format", self.movie_format_combo.currentText())
        config.set_value("movie_folder_format", self.movie_folder_input.text())
        
        config.set_value("regex_rules", self.regex_rules_edit.toPlainText())
        config.set_value("with_cloud", self.with_cloud_cb.isChecked())
        config.set_value("tmdb_api_key", self.tmdb_api_key_input.text().strip())
        config.set_value("tmdb_proxy", self.tmdb_proxy_input.text().strip())
        config.set_value("bangumi_token", self.bangumi_token_input.text().strip())
        config.set_value("bangumi_proxy", self.bangumi_proxy_input.text().strip())
        config.set_value("use_storage", self.use_storage_cb.isChecked())
        config.set_value("anime_priority", self.anime_priority_cb.isChecked())
        config.set_value("bangumi_priority", self.bangumi_priority_cb.isChecked())
        config.set_value("bangumi_failover", self.bangumi_failover_cb.isChecked())
        config.set_value("batch_enhancement", self.batch_enhancement_cb.isChecked())
        QMessageBox.information(self, "成功", "设置已保存。")

    def get_config_data(self):
        return {
            'rename_format': self.rename_format_combo.currentText(),
            'folder_format': self.folder_format_input.text(),
            'season_format': self.season_format_input.text(),
            'movie_format': self.movie_format_combo.currentText(),
            'movie_folder_format': self.movie_folder_input.text(),
            'regex_rules': self.parse_regex_rules(),
            'with_cloud': self.with_cloud_cb.isChecked(),
            'tmdb_api_key': self.tmdb_api_key_input.text().strip(),
            'tmdb_proxy': self.tmdb_proxy_input.text().strip(),
            'bangumi_token': self.bangumi_token_input.text().strip(),
            'bangumi_proxy': self.bangumi_proxy_input.text().strip(),
            'use_storage': self.use_storage_cb.isChecked(),
            'anime_priority': self.anime_priority_cb.isChecked(),
            'bangumi_priority': self.bangumi_priority_cb.isChecked(),
            'bangumi_failover': self.bangumi_failover_cb.isChecked(),
            'batch_enhancement': self.batch_enhancement_cb.isChecked(),
        }

    def parse_regex_rules(self):
        rules = []
        for line in self.regex_rules_edit.toPlainText().splitlines():
            if '=>' in line:
                p, r = line.split('=>', 1)
                rules.append((p.strip(), r.strip()))
        return rules
