import os
import datetime
from peewee import *
from src.utils.paths import DB_PATH

# 确保使用的是绝对路径
db = SqliteDatabase(os.path.abspath(DB_PATH))

class BaseModel(Model):
    class Meta:
        database = db

class LocalRule(BaseModel):
    category = CharField(index=True, unique=True)
    content = TextField(default="")
    enabled = BooleanField(default=True)
    updated_at = DateTimeField(default=datetime.datetime.now)

class RemoteSubscription(BaseModel):
    name = CharField()
    url = CharField()
    category = CharField()
    enabled = BooleanField(default=True)
    last_updated = DateTimeField(null=True)

class SubscriptionCache(BaseModel):
    subscription = ForeignKeyField(RemoteSubscription, backref='caches', on_delete='CASCADE')
    content = TextField(default="")
    updated_at = DateTimeField(default=datetime.datetime.now)

def init_db():
    try:
        db.connect(reuse_if_open=True)
        db.create_tables([LocalRule, RemoteSubscription, SubscriptionCache])
        
        # --- 自动迁移逻辑：检查并补全缺失的列 ---
        existing_columns = [c.name for c in db.get_columns('localrule')]
        if 'updated_at' not in existing_columns:
            db.execute_sql('ALTER TABLE localrule ADD COLUMN updated_at DATETIME')
            print("[DEBUG] 自动迁移：已补全 localrule.updated_at 列")

        existing_cache_columns = [c.name for c in db.get_columns('subscriptioncache')]
        if 'updated_at' not in existing_cache_columns:
            db.execute_sql('ALTER TABLE subscriptioncache ADD COLUMN updated_at DATETIME')
            print("[DEBUG] 自动迁移：已补全 subscriptioncache.updated_at 列")

        print(f"[DEBUG] 数据库初始化成功: {os.path.abspath(DB_PATH)}")
    except Exception as e:
        print(f"[ERROR] 数据库初始化或迁移失败: {e}")

init_db()
