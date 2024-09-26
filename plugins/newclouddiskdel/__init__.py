import json
import os
import shutil
import time
from pathlib import Path
from tkinter import Tk
from tkinter.filedialog import askdirectory

from app.core.config import settings
from app.core.event import eventmanager, Event
from app.log import logger
from app.plugins import _PluginBase
from typing import Any, List, Dict, Tuple

class NewCloudDiskDel(_PluginBase):
    plugin_name = "新云盘关键词文件删除"
    plugin_desc = "根据关键词删除无用云盘资源文件。"
    plugin_icon = "clouddisk.png"
    plugin_version = "1.0.0"
    plugin_author = "guyue2005"
    author_url = "https://github.com/guyue2005"
    plugin_config_prefix = "newclouddiskdel_"
    plugin_order = 26
    auth_level = 1

    _enabled = False
    _paths = {}
    _keywords = []

    def init_plugin(self, config: dict = None):
        if config:
            self._enabled = config.get("enabled")
            self._keywords = config.get("keywords", "").split(",")
            for path in str(config.get("path")).split("\n"):
                paths = path.split(":")
                self._paths[paths[0]] = paths[1]

    @eventmanager.register(EventType.PluginAction)
    def newclouddisk_del(self, event: Event):
        if not self._enabled or not event:
            return

        event_data = event.event_data
        if not event_data or event_data.get("action") != "networkdisk_del":
            return

        logger.info(f"获取到云盘删除请求 {event_data}")

        media_path = event_data.get("media_path")
        if not media_path:
            logger.error("未获取到删除路径")
            return

        cloud_file_flag = False

        for library_path in list(self._paths.keys()):
            if str(media_path).startswith(library_path):
                cloud_file_flag = True
                media_path = str(media_path).replace(library_path, self._paths.get(library_path))
                logger.info(f"获取到moviepilot本地云盘挂载路径 {media_path}")
                path = Path(media_path)

                for keyword in self._keywords:
                    if keyword in media_path:
                        self.__remove_files(path)
                        break
                break

    def __remove_files(self, path):
        if path.is_file() or path.suffix == ".strm":
            logger.info(f"删除文件 {path}")
            path.unlink()
        elif path.is_dir():
            logger.warn(f"删除目录 {path}")
            shutil.rmtree(path)

    def select_path(self) -> str:
        """ 手动选择路径 """
        Tk().withdraw()  # 隐藏主窗口
        selected_path = askdirectory(title="选择云盘路径")
        return selected_path if selected_path else None

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
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 8
                                },
                                'content': [
                                    {
                                        'component': 'VTextarea',
                                        'props': {
                                            'model': 'keywords',
                                            'rows': '2',
                                            'label': '删除关键词',
                                            'placeholder': '用逗号分隔的关键词'
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
                                },
                                'content': [
                                    {
                                        'component': 'VBtn',
                                        'props': {
                                            'label': '选择路径',
                                            'click': self.select_path
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
            "keywords": "",
            "path": "",
        }

    def stop_service(self):
        pass
