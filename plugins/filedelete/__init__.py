import datetime
import random
import threading
import os
from pathlib import Path
from typing import List, Tuple, Dict, Any

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.log import logger
from app.plugins import _PluginBase

lock = threading.Lock()

class FileDelete(_PluginBase):
    # 插件名称
    plugin_name = "云盘无用文件删除"
    # 插件描述
    plugin_desc = "自定义文件类型从源目录删除，包括可选的空文件夹。"
    # 插件图标
    plugin_icon = "https://raw.githubusercontent.com/guyue2005/MoviePilot-Plugins/main/icons/delete_files.png"
    # 插件版本
    plugin_version = "1.4"
    # 插件作者
    plugin_author = "guyue2005"
    # 作者主页
    author_url = "https://github.com/guyue2005"
    # 插件配置项ID前缀
    plugin_config_prefix = "filedelete_"
    # 加载顺序
    plugin_order = 30
    # 可使用的用户级别
    auth_level = 1

    _scheduler = None
    _enabled = False
    _onlyonce = False
    _cron = None
    _delay = None
    _monitor_dirs = ""
    _rmt_mediaext = None
    _keywords = None
    _delete_empty_folders = False  # 是否删除空文件夹的开关

    _event = threading.Event()

    def init_plugin(self, config: dict = None):
        self._dirconf = {}

        if config:
            self._enabled = config.get("enabled")
            self._onlyonce = config.get("onlyonce")
            self._monitor_dirs = config.get("monitor_dirs") or ""
            self._cron = config.get("cron")
            self._delay = config.get("delay")
            self._rmt_mediaext = config.get("rmt_mediaext") or ".nfo, .jpg"
            self._keywords = config.get("keywords") or ""
            self._delete_empty_folders = config.get("delete_empty_folders", False)  # 加载空文件夹删除开关

        self.stop_service()

        if self._enabled or self._onlyonce:
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)
            monitor_dirs = self._monitor_dirs.split("\n")
            for mon_path in monitor_dirs:
                if mon_path:
                    self._dirconf[mon_path] = None

                if self._enabled:
                    self._scheduler.add_job(func=self.delete_files, trigger='date',
                                            run_date=datetime.datetime.now(
                                                tz=pytz.timezone(settings.TZ)) + datetime.timedelta(seconds=3),
                                            name=f"文件删除 {mon_path}")

            if self._onlyonce:
                logger.info("文件删除服务启动，立即运行一次")
                self._scheduler.add_job(name="文件删除", func=self.delete_files, trigger='date',
                                        run_date=datetime.datetime.now(
                                            tz=pytz.timezone(settings.TZ)) + datetime.timedelta(seconds=3)
                                        )
                self._onlyonce = False
                self.__update_config()

            if self._scheduler.get_jobs():
                self._scheduler.print_jobs()
                self._scheduler.start()

    def delete_files(self):
        """
        定时任务，删除文件和空文件夹（如果开关开启）
        """
        logger.info("开始全量删除监控目录 ...")
        keywords = [kw.strip() for kw in self._keywords.split(",") if kw.strip()]

        for mon_path in self._dirconf.keys():
            files = SystemUtils.list_files(Path(mon_path), [ext.strip() for ext in self._rmt_mediaext.split(",")])
            
            for file in files:
                logger.info(f"开始处理本地文件：{file}")
                if any(keyword in str(file) for keyword in keywords):
                    logger.info(f"删除文件：{file}")
                    try:
                        os.remove(file)  # 使用 os.remove 删除文件
                        logger.info(f"{file} 删除成功")
                    except Exception as e:
                        logger.error(f"删除文件 {file} 时出错: {e}")
                else:
                    logger.info(f"文件 {file} 不符合关键词，跳过")

            # 如果开关开启，删除空文件夹
            if self._delete_empty_folders:
                self.delete_empty_folders(Path(mon_path))

        logger.info("全量删除监控目录完成！")

    def delete_empty_folders(self, path: Path):
        """删除空文件夹"""
        for root, dirs, files in os.walk(path, topdown=False):
            for dir_name in dirs:
                dir_path = os.path.join(root, dir_name)
                if not os.listdir(dir_path):  # 如果文件夹为空
                    try:
                        os.rmdir(dir_path)
                        logger.info(f"删除空文件夹：{dir_path}")
                    except OSError:
                        logger.error(f"无法删除空文件夹 {dir_path}: 文件夹可能不为空或其他问题。")
                else:
                    logger.info(f"文件夹 {dir_path} 不为空，无法删除。")

    def __update_config(self):
        self.update_config({
            "enabled": self._enabled,
            "onlyonce": self._onlyonce,
            "monitor_dirs": self._monitor_dirs,
            "cron": self._cron,
            "delay": self._delay,
            "rmt_mediaext": self._rmt_mediaext,
            "keywords": self._keywords,
            "delete_empty_folders": self._delete_empty_folders  # 更新空文件夹删除开关状态
        })

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        pass

    def get_service(self) -> List[Dict[str, Any]]:
        if self._enabled and self._cron:
            return [{
                "id": "FileDelete",
                "name": "云盘无用文件删除",
                "trigger": CronTrigger.from_crontab(self._cron),
                "func": self.delete_files,
                "kwargs": {}
            }]
        return []

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
                            },
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
                                            'model': 'onlyonce',
                                            'label': '立即运行一次',
                                        }
                                    }
                                ]
                            },
                        ]
                    },
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
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'cron',
                                            'label': '定时删除周期',
                                            'placeholder': '5位cron表达式，留空关闭'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'delay',
                                            'label': '随机延时',
                                            'placeholder': '20,1-10  处理10个文件后随机延迟1-10秒'
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
                                    'cols': 12
                                },
                                'content': [
                                    {
                                        'component': 'VTextarea',
                                        'props': {
                                            'model': 'monitor_dirs',
                                            'label': '监控目录',
                                            'rows': 5,
                                            'placeholder': '每行一个监控目录'
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
                                    'cols': 12
                                },
                                'content': [
                                    {
                                        'component': 'VTextarea',
                                        'props': {
                                            'model': 'rmt_mediaext',
                                            'label': '文件格式',
                                            'rows': 2,
                                            'placeholder': ".nfo, .jpg, .mp4, .mkv, .png, .jpg, .pdf, .docx"
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
                                    'cols': 12
                                },
                                'content': [
                                    {
                                        'component': 'VTextarea',
                                        'props': {
                                            'model': 'keywords',
                                            'label': '删除关键词',
                                            'rows': 2,
                                            'placeholder': "关键词1, 关键词2"
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
                                    'cols': 12
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'delete_empty_folders',
                                            'label': '删除空文件夹',
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                ]
            }
        ], {
            "enabled": False,
            "onlyonce": False,
            "monitor_dirs": "",
            "cron": "",
            "delay": "20,1-10",
            "rmt_mediaext": ".nfo, .jpg, .mp4, .mkv, .png, .jpg, .pdf, .docx",
            "keywords": "",
            "delete_empty_folders": False
        }

    def get_page(self) -> List[dict]:
        pass

    def stop_service(self):
        if self._scheduler:
            self._scheduler.remove_all_jobs()
            if self._scheduler.running:
                self._event.set()
                self._scheduler.shutdown()
                self._event.clear()
            self._scheduler = None
