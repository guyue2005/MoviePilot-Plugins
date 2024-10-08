import datetime
import threading
from pathlib import Path
from typing import List, Dict, Any, Tuple
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from app.core.config import settings
from app.log import logger
from app.plugins import _PluginBase
import os

class FileDelete(_PluginBase):
    # 插件名称
    plugin_name = "云盘无用文件删除"
    # 插件描述
    plugin_desc = "自定义文件类型从源目录删除，包括可选的空目录。"
    # 插件图标
    plugin_icon = "https://raw.githubusercontent.com/guyue2005/MoviePilot-Plugins/main/icons/delete.png"
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
    _monitor_dirs = ""
    _format = None
    _keywords = None
    _delete_files_enabled = True  # 默认为启用文件删除
    
    
    def __init__(self):
        super().__init__()
        self._delete_empty_dirs = False
        self._delete_english_dirs = False
        self._delete_small_dirs = False
        self._small_dir_size_threshold = 10
    

    def init_plugin(self, config: dict = None):
        self._dirconf = {}
        
        if config:
            self._enabled = config.get("enabled", False)
            self._onlyonce = config.get("onlyonce", False)
            self._monitor_dirs = config.get("monitor_dirs", "")
            self._keywords = config.get("keywords", "")
            self._delete_empty_dirs = config.get("delete_empty_dirs", False)
            self._delete_english_dirs = config.get("delete_english_dirs", False)
            self._delete_small_dirs = config.get("delete_small_dirs", False)
            self._small_dir_size_threshold = int(config.get("small_dir_size_threshold", 10))
            self._delete_files_enabled = config.get("delete_files_enabled", False)  # 默认关闭

        logger.info(f"插件初始化状态: enabled={self._enabled}, onlyonce={self._onlyonce}, "
                    f"delete_empty_dirs={self._delete_empty_dirs}, delete_english_dirs={self._delete_english_dirs}, "
                    f"delete_small_dirs={self._delete_small_dirs}, delete_files_enabled={self._delete_files_enabled}")

        self.stop_service()

        if self._enabled or self._onlyonce:
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)
            monitor_dirs = [line.strip() for line in self._monitor_dirs.splitlines() if line.strip()]

            logger.info(f"监控目录: {monitor_dirs}")

            if not monitor_dirs:
                return
            for mon_path in monitor_dirs:
                self._dirconf[mon_path] = None

            if self._onlyonce:
                logger.info("文件删除服务启动，立即运行一次")
                # 只调用启用的功能
                self.delete_files_if_enabled()
                self.delete_empty_dirs_if_enabled()
                self.delete_english_dirs_if_enabled()
                self.delete_small_dirs_if_enabled()
                self._onlyonce = False
                self.__update_config()

            if self._scheduler.get_jobs():
                self._scheduler.print_jobs()
                self._scheduler.start()

    def delete_files_if_enabled(self):
        if self._delete_files_enabled:
            self.delete_files()
        else:
            logger.info("文件删除功能未启用，跳过删除文件操作")

    def delete_empty_dirs_if_enabled(self):
        if self._delete_empty_dirs:
            self.delete_empty_dirs()
        else:
            logger.info("空目录删除功能未启用，跳过删除空目录操作")

    def delete_english_dirs_if_enabled(self):
        if self._delete_english_dirs:
            self.delete_english_dirs()
        else:
            logger.info("英文目录删除功能未启用，跳过删除英文目录操作")

    def delete_small_dirs_if_enabled(self):
        if self._delete_small_dirs:
            self.delete_small_dirs()
        else:
            logger.info("小目录删除功能未启用，跳过删除小目录操作")

    def delete_files(self):
        logger.info("开始全量删除文件 ...")
        exclude_keywords = [kw.strip() for kw in self._keywords.split(",") if kw.strip()]

        for mon_path in self._dirconf.keys():
            logger.info(f"当前监控路径: {mon_path}")

            if not Path(mon_path).exists():
                logger.error(f"监控路径不存在: {mon_path}")
                continue

            try:
                logger.info(f"准备在路径 {mon_path} 中查找文件 ...")
                files = self.list_files(Path(mon_path))
            except Exception as e:
                logger.error(f"调用 list_files 方法时发生异常: {e}", exc_info=True)
                continue

            if not files:
                logger.info("未找到任何文件，跳过删除操作")
                continue

            for file in files:
                if file.is_file():
                    if any(exclude_kw in str(file) for exclude_kw in exclude_keywords):
                        logger.info(f"文件 {file} 被排除，跳过删除。")
                        continue
                    logger.info(f"找到文件：{file}")
                    try:
                        os.remove(file)
                        logger.info(f"成功删除文件: {file}")
                    except Exception as e:
                        logger.error(f"删除文件 {file} 失败：{e}")

    def delete_empty_dirs(self):
        logger.info("开始删除空目录 ...")
        for mon_path in self._dirconf.keys():
            for root, dirs, _ in os.walk(mon_path, topdown=False):
                for dir_name in dirs:
                    dir_path = os.path.join(root, dir_name)
                    if not os.listdir(dir_path):
                        try:
                            os.rmdir(dir_path)
                            logger.info(f"成功删除空目录：{dir_path}")
                        except Exception as e:
                            logger.error(f"删除空目录 {dir_path} 失败：{e}")

    def delete_english_dirs(self):
        logger.info("开始删除英文目录 ...")
        for mon_path in self._dirconf.keys():
            for root, dirs, _ in os.walk(mon_path):
                for dir_name in dirs:
                    if all(c.isalnum() or c in ['.', '_', '-'] for c in dir_name):
                        dir_path = os.path.join(root, dir_name)
                        try:
                            os.rmdir(dir_path)
                            logger.info(f"成功删除英文目录：{dir_path}")
                        except Exception as e:
                            logger.error(f"删除英文目录 {dir_path} 失败：{e}")

    def delete_small_dirs(self):
        logger.info("开始删除小目录 ...")
        size_threshold = int(self._small_dir_size_threshold) * 1024 * 1024
        for mon_path in self._dirconf.keys():
            for root, dirs, _ in os.walk(mon_path, topdown=False):
                for dir_name in dirs:
                    dir_path = os.path.join(root, dir_name)
                    dir_size = sum(os.path.getsize(os.path.join(dir_path, f)) for f in os.listdir(dir_path) if os.path.isfile(os.path.join(dir_path, f)))
                    
                    if dir_size < size_threshold:
                        if not os.listdir(dir_path):
                            try:
                                os.rmdir(dir_path)
                                logger.info(f"成功删除目录：{dir_path}")
                            except Exception as e:
                                logger.error(f"删除目录 {dir_path} 失败：{e}")

        
        
    def __update_config(self):
        self.update_config({
            "enabled": self._enabled,
            "onlyonce": self._onlyonce,
            "monitor_dirs": self._monitor_dirs,
            "keywords": self._keywords,
            "delete_empty_dirs": self._delete_empty_dirs,
            "delete_english_dirs": self._delete_english_dirs,
            "delete_small_dirs": self._delete_small_dirs,
            "small_dir_size_threshold": self._small_dir_size_threshold,
            "delete_files_enabled": self._delete_files_enabled  # 更新文件删除开关状态
        })

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        pass

    def get_service(self) -> List[Dict[str, Any]]:
        if self._enabled:
            return [{
                "id": "FileDelete",
                "name": "云盘无用文件删除",
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
                                            'model': 'delete_empty_dirs',
                                            'label': '删除空目录',
                                            'disabled': self._delete_small_dirs  # 根据小目录状态禁用
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
                                            'model': 'delete_english_dirs',
                                            'label': '删除英文目录',
                                            'disabled': self._delete_small_dirs  # 根据小目录状态禁用
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
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'onlyonce',
                                            'label': '立即运行一次',
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
                                            'model': 'delete_small_dirs',
                                            'label': '启用删除目录',
                                            'disabled': self._delete_empty_dirs or self._delete_english_dirs or self._delete_files_enabled  # 根据空和英文目录状态禁用
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
                                            'model': 'small_dir_size_threshold',
                                            'label': '删除多大目录 (MB)',
                                            'placeholder': '设置小于此值的目录将被删除'
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
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'delete_files_enabled',
                                            'label': '启用删除文件',
                                            'disabled': self._delete_small_dirs # 根据小目录状态禁用 
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
                                            'model': 'keywords',
                                            'label': '排除关键词',
                                            'rows': 2,
                                            'placeholder': "关键词1,关键词2"
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
                                        'component': 'VAlert',
                                        'props': {
                                            'type': 'info',
                                            'variant': 'tonal',
                                            'text': '注意：开启功能的顺序：1.开启删除目录后。不能启用其他选项。2.删除空目录必须目录中没有任何文件，才会被执行，3.可以删除文件，在开启空目录和英文目录'
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
                                        'component': 'VAlert',
                                        'props': {
                                            'type': 'info',
                                            'variant': 'tonal',
                                            'text': '使用方法：1.删除目录。只能独立开启。2.删除文件+删除空目录，3.删除空文件+删除英文目录'
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
            "cron": "",
            "delay": "20,1-10",
            "keywords": "",
            "delete_files_enabled": False  # 添加这一行
        }

    def get_page(self) -> List[dict]:
        pass

    def stop_service(self):
        if self._scheduler:
            self._scheduler.remove_all_jobs()
            if self._scheduler.running:
                self._scheduler.shutdown()
            self._scheduler = None
