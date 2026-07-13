import os
import sys

_FROZEN = getattr(sys, 'frozen', False)


def get_app_root():
    """获取 PC 客户端根目录 (EXE 所在目录或 main.py 所在目录)"""
    if _FROZEN:
        # 打包后的 EXE 环境 (PyInstaller --onedir)
        path = os.path.dirname(os.path.abspath(sys.executable))
    else:
        # 开发环境下，相对于 main.py
        import __main__
        if hasattr(__main__, "__file__"):
            path = os.path.dirname(os.path.abspath(__main__.__file__))
        else:
            path = os.path.dirname(os.path.abspath(sys.argv[0]))
    return os.path.normpath(path)


def get_project_root():
    """获取主项目根目录 (anime-matcher-pc 的父目录)

    开发模式下: anime-matcher-pc/.. → anime-matcher/
    打包模式下: 返回 EXE 所在目录 (无上级项目)
    """
    if _FROZEN:
        return get_app_root()
    return os.path.normpath(os.path.join(get_app_root(), ".."))


def get_resource_path(relative_path):
    """获取内置只读资源路径"""
    if _FROZEN:
        base_path = getattr(sys, '_MEIPASS', get_app_root())
        return os.path.normpath(os.path.join(base_path, relative_path))
    return os.path.normpath(os.path.join(get_app_root(), relative_path))


# --- 核心路径变量 ---
APP_ROOT = get_app_root()
PROJECT_ROOT = get_project_root()

# 打包模式下，data 目录放在 EXE 同级；开发模式下放在主项目根目录
if _FROZEN:
    DATA_DIR = os.path.join(APP_ROOT, "data")
else:
    DATA_DIR = os.path.join(PROJECT_ROOT, "data")

CONFIG_INI = os.path.join(APP_ROOT, "VideoRenamer_Qt6.ini")
DB_PATH = os.path.join(APP_ROOT, "VideoRenamer.db")
CORE_DB_PATH = os.path.join(DATA_DIR, "matcher_storage.db")

# --- 设置环境变量，让 recognition_service 使用正确的数据库路径 ---
os.environ.setdefault("AM_DATABASE_PATH", CORE_DB_PATH)

# --- 将主项目的 src/ 目录加入 sys.path (仅开发模式) ---
# 打包模式下，PyInstaller 已将 recognition_engine / recognition_service / anitopy
# 打入 _internal/ 目录，无需手动添加 sys.path
if not _FROZEN:
    _CORE_SRC = os.path.join(PROJECT_ROOT, "src")
    if _CORE_SRC not in sys.path:
        sys.path.insert(0, _CORE_SRC)
