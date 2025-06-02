from app.plugins import _PluginBase
from apscheduler.triggers.cron import CronTrigger
from app.core.config import settings
from app.log import logger
from app.helper.meta import MetaHelper
from app.helper.message import MessageHelper
import os
import shutil
from typing import List, Dict, Any, Tuple

class MoveCompletedSeries(_PluginBase):
    plugin_name = "完结剧集搬运"
    plugin_desc = "定时检测剧集是否完结，并将其移动到归档目录"
    plugin_version = "1.1.0"
    # 插件作者
    plugin_author = "guyue2005"
    # 作者主页
    author_url = "https://github.com/guyue2005"
    plugin_icon = "mdi-movie-check"
    plugin_config_prefix = "movecompleted_"
    plugin_order = 5
    auth_level = 1

    def __init__(self):
        super().__init__()
        self._cache = {}
        self._enabled = False
        self._source_dir = "/media/TVShows"
        self._dest_dir = "/media/CompletedTVShows"
        self._cron = "0 3 * * *"
        self._enable_telegram_notify = False
        # 初始化元数据助手
        self.meta_helper = MetaHelper()
        # 初始化消息助手
        self.message_helper = MessageHelper()

    def init_plugin(self, config: dict = None):
        if not config:
            return
        self._enabled = config.get("enabled", False)
        self._source_dir = config.get("source_dir", "/media/TVShows")
        self._dest_dir = config.get("dest_dir", "/media/CompletedTVShows")
        self._cron = config.get("cron", "0 3 * * *")
        self._enable_telegram_notify = config.get("enable_telegram_notify", False)

        self.stop_service()

        if self._enabled:
            self.add_job(
                self.scan_and_move,
                CronTrigger.from_crontab(self._cron),
                id="move_completed_series",
                replace_existing=True
            )
            logger.info("完结剧集搬运插件启动成功")

    def scan_and_move(self):
        if not os.path.exists(self._dest_dir):
            try:
                os.makedirs(self._dest_dir)
                logger.info(f"归档目录 {self._dest_dir} 不存在，已自动创建")
            except Exception as e:
                logger.error(f"创建归档目录失败: {e}")
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
                    if self._enable_telegram_notify:
                        self.message_helper.send_message(
                            title="完结剧集搬运",
                            text=f"剧集《{series_name}》已完结，已移动到归档目录。"
                        )
            except Exception as e:
                logger.error(f"处理剧集 {series_name} 时出错: {e}")

    def is_series_completed(self, series_name: str) -> bool:
        if series_name in self._cache:
            return self._cache[series_name]

        try:
            # 使用系统自带的TMDB功能查询剧集信息
            tmdb_info = self.meta_helper.get_tmdb_info(title=series_name, mtype="tv")
            if not tmdb_info:
                logger.warning(f"未找到剧集：{series_name}")
                self._cache[series_name] = False
                return False
            
            # 检查剧集是否已完结
            status = tmdb_info.get("status")
            if status and status.lower() in ["ended", "canceled"]:
                logger.info(f"剧集 {series_name} 已完结，状态: {status}")
                self._cache[series_name] = True
                return True
            else:
                logger.info(f"剧集 {series_name} 未完结，状态: {status}")
                self._cache[series_name] = False
                return False
        except Exception as e:
            logger.error(f"检查剧集 {series_name} 状态时出错: {e}")
            return False

    def stop_service(self):
        """
        停止插件服务
        """
        try:
            self.remove_job("move_completed_series")
            logger.info("完结剧集搬运插件停止成功")
        except:
            pass

    def get_state(self) -> bool:
        return self._enabled

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        return [
            {
                'component': 'VForm',
                'content': [
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'enabled',
                                            'label': '启用插件',
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
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'source_dir',
                                            'label': '源目录',
                                            'placeholder': '/media/TVShows'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'dest_dir',
                                            'label': '归档目录',
                                            'placeholder': '/media/CompletedTVShows'
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
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'cron',
                                            'label': '执行周期',
                                            'placeholder': '0 3 * * *'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'enable_telegram_notify',
                                            'label': '启用通知',
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ], {
            'enabled': False,
            'source_dir': '/media/TVShows',
            'dest_dir': '/media/CompletedTVShows',
            'cron': '0 3 * * *',
            'enable_telegram_notify': False
        }
    
    def get_api(self) -> List[Dict[str, Any]]:
        """
        返回插件API接口
        """
        return []
    
    def get_page(self) -> List[Dict[str, Any]]:
        """
        返回插件页面
        """
        return [] 
