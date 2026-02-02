"""
进度输出工具 - 适用于 Celery worker 和普通 Python 环境
"""
import logging
import sys
from typing import Optional

logger = logging.getLogger(__name__)


class ProgressReporter:
    """进度报告器 - 输出到日志和控制台"""
    
    def __init__(self, total: int, description: str = "处理中", version_id: Optional[int] = None):
        """
        Args:
            total: 总步骤数
            description: 描述信息
            version_id: 版本ID（可选）
        """
        self.total = total
        self.current = 0
        self.description = description
        self.version_id = version_id
        self._log_prefix = f"[版本 {version_id}] " if version_id else ""
    
    def update(self, n: int = 1, message: str = ""):
        """更新进度"""
        self.current += n
        percentage = int((self.current / self.total) * 100) if self.total > 0 else 0
        status_msg = f"{self._log_prefix}{self.description}: {self.current}/{self.total} ({percentage}%)"
        if message:
            status_msg += f" - {message}"
        logger.info(status_msg)
        # 同时输出到 stderr（确保在 Celery worker 中可见）
        print(status_msg, file=sys.stderr, flush=True)
    
    def set_message(self, message: str):
        """设置当前步骤的消息"""
        percentage = int((self.current / self.total) * 100) if self.total > 0 else 0
        status_msg = f"{self._log_prefix}{self.description}: {self.current}/{self.total} ({percentage}%) - {message}"
        logger.info(status_msg)
        print(status_msg, file=sys.stderr, flush=True)
    
    def finish(self, message: str = "完成"):
        """完成进度"""
        status_msg = f"{self._log_prefix}{self.description}: {message}"
        logger.info(status_msg)
        print(status_msg, file=sys.stderr, flush=True)


def log_step(version_id: Optional[int], step_name: str, message: str = ""):
    """记录单个步骤"""
    prefix = f"[版本 {version_id}] " if version_id else ""
    status_msg = f"{prefix}步骤: {step_name}"
    if message:
        status_msg += f" - {message}"
    logger.info(status_msg)
    print(status_msg, file=sys.stderr, flush=True)
