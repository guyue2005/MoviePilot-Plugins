from app.plugins import _PluginBase
from apscheduler.triggers.cron import CronTrigger
# 修正导入路径
from app.scheduler.scheduler import Scheduler
from app.utils.commons import singleton
from app.log import logger
import os
import shutil
import requests
import time

@singleton
class MoveCompletedSeries(_PluginBase):
    plugin_name = "完结剧集搬运"
    plugin_desc = "定时检测剧集是否完结，并将其移动到归档目录"
    plugin_version = "1.0.0"
    # 插件作者
    plugin_author = "guyue2005"
    # 作者主页
    author_url = "https://github.com/guyue2005"
    plugin_icon = "mdi-movie-check"
    plugin_config_prefix = "movecompleted_"
    plugin_order = 5
    auth_level = 1

    # 获取调度器实例
    scheduler = Scheduler()

    def __init__(self):
        self._cache = {}
        self._enabled = False
        self._source_dir = "/media/TVShows"
        self._dest_dir = "/media/CompletedTVShows"
        self._tmdb_api_key = ""
        self._cron = "0 3 * * *"
        self._enable_telegram_notify = False
        self._telegram_bot_token = ""
        self._telegram_chat_id = ""

    def init_plugin(self, config: dict = None):
        if not config:
            return
        
        self._enabled = config.get("enabled", False)
        self._source_dir = config.get("source_dir", "/media/TVShows")
        self._dest_dir = config.get("dest_dir", "/media/CompletedTVShows")
        self._tmdb_api_key = config.get("tmdb_api_key", "")
        self._cron = config.get("cron", "0 3 * * *")

        self._enable_telegram_notify = config.get("enable_telegram_notify", False)
        self._telegram_bot_token = config.get("telegram_bot_token", "")
        self._telegram_chat_id = config.get("telegram_chat_id", "")

        self.stop_service()

        if self._enabled:
            self.scheduler.add_job(
                "move_completed_series",
                self.scan_and_move,
                CronTrigger.from_crontab(self._cron),
                replace_existing=True
            )
            logger.info("完结剧集搬运插件启动成功")

    def scan_and_move(self):
        if not self._tmdb_api_key:
            logger.error("未配置TMDb API Key，无法检查剧集状态")
            return
            
        if not os.path.exists(self._dest_dir):
            try:
                os.makedirs(self._dest_dir)
                logger.info(f"归档目录 {self._dest_dir} 不存在，已自动创建")
            except Exception as e:
                logger.error(f"创建归档目录失败: {e}")
                return
                
        if not os.path.exists(self._source_dir):
            logger.error(f"源目录 {self._source_dir} 不存在")
            return

        for series_name in os.listdir(self._source_dir):
            path = os.path.join(self._source_dir, series_name)
            if not os.path.isdir(path):
                continue
            try:
                if self.is_series_completed(series_name):
                    target_path = os.path.join(self._dest_dir, series_name)
                    logger.info(f"{series_name} 已完结，移动中...")
                    shutil.move(path, target_path)
                    self.send_telegram_message(f"剧集《{series_name}》已完结，已移动到归档目录。")
            except Exception as e:
                logger.error(f"处理剧集 {series_name} 时出错: {e}")

    def is_series_completed(self, series_name: str) -> bool:
        if not self._tmdb_api_key:
            return False
            
        # 添加缓存过期检查，缓存保留24小时
        cache_key = f"series_status_{series_name}"
        if cache_key in self._cache:
            cache_time, is_completed = self._cache[cache_key]
            # 缓存24小时有效
            if (time.time() - cache_time) < 86400:
                return is_completed

        try:
            url = "https://api.themoviedb.org/3/search/tv"
            r = requests.get(url, params={"api_key": self._tmdb_api_key, "query": series_name}, timeout=10)
            results = r.json().get("results", [])
            if not results:
                logger.warning(f"未找到剧集：{series_name}")
                self._cache[cache_key] = (time.time(), False)
                return False
            series_id = results[0]["id"]
            
            # 添加重试机制
            max_retries = 3
            retry_count = 0
            while retry_count < max_retries:
                try:
                    details = requests.get(
                        f"https://api.themoviedb.org/3/tv/{series_id}",
                        params={"api_key": self._tmdb_api_key},
                        timeout=10
                    ).json()
                    completed = details.get("status") == "Ended"
                    self._cache[cache_key] = (time.time(), completed)
                    return completed
                except requests.exceptions.RequestException:
                    retry_count += 1
                    if retry_count >= max_retries:
                        raise
                    time.sleep(2)  # 重试前等待2秒
        except Exception as e:
            logger.error(f"查询剧集状态失败：{series_name} - {e}")
            return False

    def send_telegram_message(self, message: str):
        if not self._enabled or not self._enable_telegram_notify:
            return
        if not self._telegram_bot_token or not self._telegram_chat_id:
            logger.warning("Telegram通知启用但缺少 Bot Token 或 Chat ID")
            return
        url = f"https://api.telegram.org/bot{self._telegram_bot_token}/sendMessage"
        try:
            # 添加重试机制
            max_retries = 3
            retry_count = 0
            while retry_count < max_retries:
                try:
                    requests.post(url, data={"chat_id": self._telegram_chat_id, "text": message}, timeout=10)
                    return
                except requests.exceptions.RequestException:
                    retry_count += 1
                    if retry_count >= max_retries:
                        raise
                    time.sleep(2)  # 重试前等待2秒
        except Exception as e:
            logger.error(f"发送 Telegram 通知失败: {e}")

    def get_form(self):
        return [
            {
                'component': 'VForm',
                'content': [
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {'cols': 12, 'md': 6},
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'enabled',
                                            'label': '启用插件'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {'cols': 12, 'md': 6},
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'tmdb_api_key',
                                            'label': 'TMDb API Key'
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {'cols': 12, 'md': 6},
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'source_dir',
                                            'label': '剧集目录'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {'cols': 12, 'md': 6},
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'dest_dir',
                                            'label': '归档目录'
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {'cols': 12, 'md': 6},
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'cron',
                                            'label': 'Cron 表达式（定时检测）',
                                            'placeholder': '0 3 * * *'
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {'cols': 12, 'md': 4},
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'enable_telegram_notify',
                                            'label': '启用搬运通知（Telegram）'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {'cols': 12, 'md': 4},
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'telegram_bot_token',
                                            'label': 'Telegram Bot Token'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {'cols': 12, 'md': 4},
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'telegram_chat_id',
                                            'label': 'Telegram Chat ID'
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ], {
            "enabled": False,
            "tmdb_api_key": "",
            "source_dir": "/media/TVShows",
            "dest_dir": "/media/CompletedTVShows",
            "cron": "0 3 * * *",
            "enable_telegram_notify": False,
            "telegram_bot_token": "",
            "telegram_chat_id": ""
        }

    def stop_service(self):
        try:
            self.scheduler.remove_job("move_completed_series")
            logger.info("完结剧集搬运任务已停止")
        except Exception:
            logger.debug("完结剧集搬运任务不存在或已停止")

    def get_state(self):
        return self._enabled 
