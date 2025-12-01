import os
from pathlib import Path
from typing import List, Dict, Any, Tuple
from app.plugins import _PluginV2Base  # v2 基类
from app.core.config import settings
import asyncio

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
        self._monitor_dirs = []
        self._keywords = []
        self._delete_files_enabled = True
        self._delete_empty_dirs = False
        self._delete_small_dirs = False
        self._small_dir_size_threshold = 10
        self._cron = ""

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

        if self._onlyonce:
            await self.run_enabled_deletion_methods()
            self._onlyonce = False
            self.update_config({"onlyonce": False})

        if self._enabled and self._cron:
            # v2 使用异步调度
            asyncio.create_task(self._cron_job())

    async def _cron_job(self):
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        scheduler = AsyncIOScheduler(timezone=settings.TZ)
        hour, minute, day, month, day_of_week = self._cron.split()[1:6]
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

    def get_form(self) -> Tuple[List[dict], dict]:
        # v2 表单结构，保持原逻辑
        return [
            {
                "component": "VForm",
                "content": [
                    # ...表单字段保持原样...
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
            "small_dir_size_threshold": 10
        }
