import os

# 数据库文件路径 (存放在映射的 data 目录下)
DATABASE_PATH = os.environ.get("AM_DATABASE_PATH", "data/matcher_storage.db")

# 过期配置
CACHE_EXPIRY_DAYS = 14
MEMORY_EXPIRY_DAYS = 90
