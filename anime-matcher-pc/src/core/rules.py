import requests
import datetime
import traceback
from src.utils.database import LocalRule, RemoteSubscription, SubscriptionCache

class RuleManager:
    """管理规则的同步与合并逻辑"""
    @staticmethod
    def sync_subscription(sub_id):
        try:
            sub = RemoteSubscription.get_by_id(sub_id)
            headers = {'User-Agent': 'Mozilla/5.0 (AnimeMatcher-PC)'}
            response = requests.get(sub.url, headers=headers, timeout=15)
            response.raise_for_status()
            content = response.text
            
            cache, created = SubscriptionCache.get_or_create(
                subscription=sub,
                defaults={'content': content}
            )
            if not created:
                cache.content = content
                cache.updated_at = datetime.datetime.now()
                cache.save()
            
            sub.last_updated = datetime.datetime.now()
            sub.save()
            return True, "同步成功"
        except Exception as e:
            return False, str(e)

    @staticmethod
    def get_merged_rules(category: str):
        """
        根据分类加载合并后的规则列表。
        使用更稳健的 Peewee 查询语法。
        """
        rules = []
        
        # 1. 加载本地规则 (使用关键字参数查询)
        local_rule = LocalRule.get_or_none(category=category, enabled=True)
        if local_rule and local_rule.content:
            lines = [line.strip() for line in local_rule.content.splitlines() if line.strip()]
            rules.extend(lines)
            
        # 2. 加载该分类下所有远程缓存内容
        subs = RemoteSubscription.select().where(RemoteSubscription.category == category, RemoteSubscription.enabled == True)
        for sub in subs:
            cache = SubscriptionCache.get_or_none(subscription=sub)
            if cache and cache.content:
                lines = [line.strip() for line in cache.content.splitlines() if line.strip()]
                rules.extend(lines)
        
        # 去重
        return sorted(list(set(rules)))
