import os
import sys
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QTabWidget, QApplication
from PyQt6.QtCore import Qt
from src.gui.tabs.main_tab import MainTab
from src.gui.tabs.settings_tab import SettingsTab
from src.gui.rule_manager import RuleManagerWidget

class VideoRenamerGUI(QMainWindow):
    """
    主窗口 Shell。
    负责：页签组装、全局拖拽分发、窗口基础设置。
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Anime-Matcher PC - 视频重命名工具")
        self.setGeometry(100, 100, 1400, 900)
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        
        # 1. 初始化 Tab 容器
        self.tab_widget = QTabWidget()
        self.main_layout.addWidget(self.tab_widget)
        
        # 2. 实例化各个解耦后的组件
        self.main_tab = MainTab(self)
        self.rule_tab = RuleManagerWidget()
        self.settings_tab = SettingsTab(self)
        
        # 3. 添加页签
        self.tab_widget.addTab(self.main_tab, "主界面")
        self.tab_widget.addTab(self.rule_tab, "识别规则管理")
        self.tab_widget.addTab(self.settings_tab, "设置")
        
        # 4. 开启全局拖拽接受
        self.setAcceptDrops(True)
        
        # 5. 恢复窗口上次关闭时的尺寸和位置
        self.restore_window_state()

    def restore_window_state(self):
        """从配置中恢复窗口几何状态"""
        from src.utils.config import config
        geometry = config.get_value("window_geometry")
        if geometry:
            self.restoreGeometry(geometry)
        if config.get_value("window_maximized", False, type=bool):
            self.showMaximized()

    def closeEvent(self, event):
        """窗口关闭时记录位置和尺寸"""
        from src.utils.config import config
        # 保存主窗口几何信息
        config.set_value("window_geometry", self.saveGeometry())
        config.set_value("window_maximized", self.isMaximized())
        # 保存主界面 Tab 的内部组件状态 (如分割条)
        self.main_tab.save_ui_states()
        super().closeEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            urls = [u.toString() for u in event.mimeData().urls()]
            # 自动分发给主界面组件处理
            self.main_tab.add_paths_to_list(urls)
            # 自动跳转到主界面 Tab
            self.tab_widget.setCurrentIndex(0)
            event.acceptProposedAction()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = VideoRenamerGUI()
    window.show()
    sys.exit(app.exec())
