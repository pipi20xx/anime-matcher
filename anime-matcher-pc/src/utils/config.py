import os
from PyQt6.QtCore import QSettings
from src.utils.paths import CONFIG_INI

class ConfigManager:
    def __init__(self, path=CONFIG_INI):
        self.config_path = path
        # 确保目录存在
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        self.settings = QSettings(self.config_path, QSettings.Format.IniFormat)

    def get_value(self, key, default=None, type=None):
        if type: return self.settings.value(key, default, type=type)
        return self.settings.value(key, default)

    def set_value(self, key, value):
        self.settings.setValue(key, value)
        self.settings.sync()

# Global instance
config = ConfigManager()
