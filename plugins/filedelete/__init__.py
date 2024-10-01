import datetime
import threading
from pathlib import Path
from typing import List, Dict, Any
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from app.core.config import settings
from app.log import logger
from app.plugins import _PluginBase
from app.utils.system import SystemUtils

class FileDelete(_PluginBase):
    # 插件名称
    plugin_name = "文件删除"
    plugin_desc = "自定义文件类型从源目录删除。"
    plugin_icon = "https://raw.githubusercontent.com/thsrite/MoviePilot-Plugins/main/icons/delete_files.png"
    plugin_version = "1.1"
    plugin_author = "guyue2005"
    author_url = "https://github.com/guyue2005"
    plugin_config_prefix = "filedelete_"
    plugin_order = 30
    auth_level = 1

    _scheduler = None
    _enabled = False
    _onlyonce = False
    _cron = None
    _monitor_dirs = ""
    _rmt_mediaext = None
    _keywords = None

    def init_plugin(self, config: dict = None):
        self._dirconf = {}

        if config:
            self._enabled = config.get("enabled")
            self._onlyonce = config.get("onlyonce")
            self._monitor_dirs = config.get("monitor_dirs") or ""
            self._cron = config.get("cron")
            self._rmt_mediaext = config.get("rmt_mediaext") or ".nfo, .jpg"
            self._keywords = config.get("keywords") or ""

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
                                            name=f"文件删除 {mon_path}")

            if self._onlyonce:
                logger.info("文件删除服务启动，立即运行一次")
                self._scheduler.add_job(name="文件删除", func=self.delete_files, trigger='date',
                                        run_date=datetime.datetime.now(tz=pytz.timezone(settings.TZ)) + datetime.timedelta(seconds=3))
                self._onlyonce = False

            if self._scheduler.get_jobs():
                self._scheduler.start()

    def delete_files(self):
        logger.info("开始全量删除监控目录 ...")
        keywords = [kw.strip() for kw in self._keywords.split(",") if kw.strip()]

        for mon_path in self._dirconf.keys():
            files = SystemUtils.list_files(Path(mon_path), [ext.strip() for ext in self._rmt_mediaext.split(",")])
            
            for file in files:
                logger.info(f"开始处理本地文件：{file}")
                if any(keyword in str(file) for keyword in keywords):
                    logger.info(f"准备删除文件：{file}")
                    try:
                        state, error = SystemUtils.delete(file)
                        if state == 0:
                            logger.info(f"{file} 删除成功")
                        else:
                            logger.error(f"{file} 删除失败，错误信息：{error}")
                    except Exception as e:
                        logger.error(f"删除文件 {file} 时发生异常：{e}")
                else:
                    logger.info(f"文件 {file} 不符合关键词（{', '.join(keywords)}），跳过")

        logger.info("全量删除监控目录完成！")

    def stop_service(self):
        if self._scheduler:
            self._scheduler.remove_all_jobs()
            if self._scheduler.running:
                self._scheduler.shutdown()
            self._scheduler = None
