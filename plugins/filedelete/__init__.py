import datetime
import logging
import shutil
import threading
import os
from pathlib import Path
from typing import List, Dict, Any
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from app.core.config import settings
from app.plugins import _PluginBase

class SystemUtils:
    @staticmethod
    def delete(file_path: str):
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                return 0, "删除成功"
            else:
                return 1, "文件不存在"
        except Exception as e:
            logging.error(f"删除文件时发生错误: {e}")
            return 2, str(e)

    @staticmethod
    def empty_folder(folder_path: str):
        try:
            for item in Path(folder_path).iterdir():
                if item.is_file():
                    item.unlink()  # 删除文件
                elif item.is_dir():
                    shutil.rmtree(str(item))  # 删除文件夹及其内容
            logging.info(f'已清空文件夹: {folder_path}')
        except Exception as e:
            logging.error(f"处理文件夹 {folder_path} 时发生错误: {e}")

class FileDelete(_PluginBase):
    # 插件名称
    plugin_name = "云盘无用文件删除"
    # 插件描述
    plugin_desc = "自定义文件类型从源目录删除。"
    # 插件图标
    plugin_icon = "https://raw.githubusercontent.com/thsrite/MoviePilot-Plugins/main/icons/delete_files.png"
    # 插件版本
    plugin_version = "1.2"
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
    _monitor_dirs = ""
    _rmt_mediaext = None
    _keywords = None

    _event = threading.Event()

    def init_plugin(self, config: dict = None):
        self._dirconf = {}
        
        if config:
            self._enabled = config.get("enabled", False)
            self._onlyonce = config.get("onlyonce", False)
            self._monitor_dirs = config.get("monitor_dirs", "")
            self._rmt_mediaext = config.get("rmt_mediaext", ".nfo, .jpg")
            self._keywords = config.get("keywords", "")

        self.stop_service()

        if self._enabled or self._onlyonce:
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)
            monitor_dirs = self._monitor_dirs.split("\n")
            for mon_path in monitor_dirs:
                if mon_path:
                    self._dirconf[mon_path] = None

            if self._enabled:
                self._scheduler.add_job(func=self.delete_files, trigger='date',
                                        run_date=datetime.datetime.now(tz=pytz.timezone(settings.TZ)) + datetime.timedelta(seconds=3),
                                        name="文件删除任务")

            if self._onlyonce:
                logger.info("文件删除服务启动，立即运行一次")
                self._scheduler.add_job(name="文件删除", func=self.delete_files, trigger='date',
                                        run_date=datetime.datetime.now(tz=pytz.timezone(settings.TZ)) + datetime.timedelta(seconds=3))
                self._onlyonce = False
                self.__update_config()

            if self._scheduler.get_jobs():
                self._scheduler.start()

    def delete_files(self):
        logger.info("开始全量删除监控目录 ...")
        keywords = [kw.strip() for kw in self._keywords.split(",") if kw.strip()]

        for mon_path in self._dirconf.keys():
            self.empty_folder(mon_path)

        logger.info("全量删除监控目录完成！")

    def empty_folder(self, folder_path: str):
        try:
            for item in Path(folder_path).iterdir():
                if item.is_file():
                    if any(keyword in str(item) for keyword in self._keywords.split(",")):
                        logger.info(f"删除文件：{item}")
                        state, error = SystemUtils.delete(str(item))
                        logger.info(f"{item} 删除 {'成功' if state == 0 else '失败'} {error}")
                    else:
                        logger.info(f"文件 {item} 不符合关键词，跳过")
                elif item.is_dir():
                    logger.info(f"删除文件夹及其内容：{item}")
                    SystemUtils.empty_folder(str(item))

            logger.info(f'已清空文件夹: {folder_path}')
        except Exception as e:
            logger.error(f"处理文件夹 {folder_path} 时发生错误: {e}")

    def __update_config(self):
        self.update_config({
            "enabled": self._enabled,
            "onlyonce": self._onlyonce,
            "monitor_dirs": self._monitor_dirs,
            "rmt_mediaext": self._rmt_mediaext,
            "keywords": self._keywords
        })

    def stop_service(self):
        if self._scheduler:
            self._scheduler.remove_all_jobs()
            if self._scheduler.running:
                self._event.set()
                self._scheduler.shutdown()
                self._event.clear()
            self._scheduler = None

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
                                            'model': 'monitor_dirs',
                                            'label': '监控目录',
                                            'rows': 5,
                                            'placeholder': '每行一个监控目录'
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
                                            'model': 'rmt_mediaext',
                                            'label': '文件格式',
                                            'placeholder': ".nfo, .jpg, .mp4, .mkv"
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
                    }
                ]
            }
        ], {
            "enabled": False,
            "onlyonce": False,
            "monitor_dirs": "",
            "rmt_mediaext": ".nfo, .jpg",
            "keywords": ""
        }

    def get_page(self) -> List[dict]:
        pass  # 如果需要实现，可以在这里添加
