import os
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Tuple
from app.plugins import _PluginV2Base
from app.core.config import settings
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import random

class FileDeleteV2(_PluginV2Base):
    plugin_name = "云盘无用文件删除"
    plugin_desc = "自定义文件类型从源目录删除，包括可选的空目录。"
    plugin_icon = "https://raw.githubusercontent.com/guyue2005/MoviePilot-Plugins/main/icons/delete.png"
    plugin_version = "2.0"
    plugin_author = "guyue2005"
    author_url = "https://github.com/guyue2005"
    plugin_order = 30
    auth_level = 1

    def __init__(self):
        super().__init__()
        self._scheduler = None
        self._enabled = False
        self._onlyonce = False
        self._monitor_dirs: List[str] = []
        self._keywords: List[str] = []
        self._delete_files_enabled = True
        self._delete_empty_dirs = False
        self._delete_small_dirs = False
        self._small_dir_size_threshold = 10
        self._cron = ""
        self._delay = "20,1-10"

    async def init_plugin(self, config: dict = None):
        if config:
            self._enabled = config.get("enabled", False)
            self._onlyonce = config.get("onlyonce", False)
            self._monitor_dirs = [line.strip() for line in config.get("monitor_dirs", "").splitlines() if line.strip()]
            self._keywords = [kw.strip() for kw in config.get("keywords", "").split(",") if kw.strip()]
            self._delete_files_enabled = config.get("delete_files_enabled", False)
            self._delete_empty_dirs = config.get("delete_empty_dirs", False)
            self._delete_small_dirs = config.get("delete_small_dirs", False)
            self._small_dir_size_threshold = int(config.get("small_dir_size_threshold", 10))
            self._cron = config.get("cron", "")
            self._delay = config.get("delay", "20,1-10")

        if self._onlyonce:
            await self.run_enabled_deletion_methods()
            self._onlyonce = False
            self.update_config({"onlyonce": False})

        if self._enabled and self._cron:
            asyncio.create_task(self._cron_job())

    async def _cron_job(self):
        if not self._cron:
            return
        scheduler = AsyncIOScheduler(timezone=settings.TZ)
        cron_parts = self._cron.split()
        if len(cron_parts) != 5:
            self.logger.error(f"Cron 表达式格式不正确: {self._cron}")
            return
        minute, hour, day, month, day_of_week = cron_parts
        scheduler.add_job(
            self.run_enabled_deletion_methods,
            trigger='cron',
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            day_of_week=day_of_week
        )
        scheduler.start()
        self._scheduler = scheduler

    async def run_enabled_deletion_methods(self):
        if self._delete_files_enabled:
            await self.delete_files()
        if self._delete_empty_dirs:
            await self.delete_empty_dirs()
        if self._delete_small_dirs:
            await self.delete_small_dirs()

    async def delete_files(self):
        self.logger.info("开始删除文件 ...")
        size_threshold = self._small_dir_size_threshold * 1024 * 1024
        for mon_path in self._monitor_dirs:
            p = Path(mon_path)
            if not p.exists():
                self.logger.error(f"监控目录不存在: {mon_path}")
                continue
            for file in p.rglob("*"):
                if file.is_file():
                    if any(kw in str(file) for kw in self._keywords):
                        continue
                    if file.stat().st_size > size_threshold:
                        continue
                    try:
                        file.unlink()
                        self.logger.info(f"删除文件: {file}")
                        await asyncio.sleep(self._get_delay())
                    except Exception as e:
                        self.logger.error(f"删除失败: {file}, {e}")

    async def delete_empty_dirs(self):
        self.logger.info("开始删除空目录 ...")
        for mon_path in self._monitor_dirs:
            for root, dirs, _ in os.walk(mon_path, topdown=False):
                for dir_name in dirs:
                    dir_path = os.path.join(root, dir_name)
                    if any(kw in dir_path for kw in self._keywords):
                        continue
                    if os.path.isdir(dir_path) and not os.listdir(dir_path):
                        try:
                            os.rmdir(dir_path)
                            self.logger.info(f"删除空目录: {dir_path}")
                        except Exception as e:
                            self.logger.error(f"删除失败: {dir_path}, {e}")

    async def delete_small_dirs(self):
        self.logger.info("开始删除小目录 ...")
        threshold = self._small_dir_size_threshold * 1024 * 1024
        for mon_path in self._monitor_dirs:
            for root, dirs, _ in os.walk(mon_path, topdown=False):
                for dir_name in dirs:
                    dir_path = os.path.join(root, dir_name)
                    if any(kw in dir_path for kw in self._keywords):
                        continue
                    size = sum(f.stat().st_size for f in Path(dir_path).glob("*") if f.is_file())
                    if size < threshold:
                        try:
                            os.rmdir(dir_path)
                            self.logger.info(f"删除小目录: {dir_path}")
                        except Exception as e:
                            self.logger.error(f"删除失败: {dir_path}, {e}")

    def _get_delay(self) -> float:
        """解析随机延时，例如 '20,1-10' 表示处理20个文件后随机延时1-10秒"""
        try:
            parts = self._delay.split(',')
            if len(parts) == 2 and '-' in parts[1]:
                min_sec, max_sec = map(int, parts[1].split('-'))
                return random.randint(min_sec, max_sec)
        except Exception:
            pass
        return 0

    def get_form(self) -> Tuple[List[dict], dict]:
        return [
            {
                "component": "VForm",
                "content": [
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [{"component": "VSwitch", "props": {"model": "enabled", "label": "启用插件"}}]
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [{"component": "VSwitch", "props": {"model": "delete_files_enabled", "label": "启用删除文件"}}]
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [{"component": "VSwitch", "props": {"model": "delete_empty_dirs", "label": "删除空目录"}}]
                            }
                        ]
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [{"component": "VSwitch", "props": {"model": "onlyonce", "label": "立即运行一次"}}]
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [{"component": "VSwitch", "props": {"model": "delete_small_dirs", "label": "启用删除全部目录"}}]
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [{"component": "VTextField", "props": {"model": "small_dir_size_threshold", "label": "删除多大文件/目录 (MB)"}}]
                            }
                        ]
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [{"component": "VTextarea", "props": {"model": "monitor_dirs", "label": "监控目录", "rows": 5, "placeholder": "每行一个监控目录"}}]
                            }
                        ]
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [{"component": "VTextarea", "props": {"model": "keywords", "label": "排除关键词", "rows": 2, "placeholder": "关键词1,关键词2"}}]
                            }
                        ]
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [{"component": "VTextField", "props": {"model": "cron", "label": "定时删除周期", "placeholder": "5位cron表达式，留空关闭"}}]
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [{"component": "VTextField", "props": {"model": "delay", "label": "随机延时", "placeholder": "20,1-10"}}]
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
            "keywords": "",
            "delete_files_enabled": False,
            "delete_empty_dirs": False,
            "delete_small_dirs": False,
            "small_dir_size_threshold": 10,
            "delay": "20,1-10"
        }

    async def stop_service(self):
        if self._scheduler:
            self._scheduler.remove_all_jobs()
            if self._scheduler.running:
                self._scheduler.shutdown()
            self._scheduler = None
