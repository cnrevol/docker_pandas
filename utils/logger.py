import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime
import json
from fastapi import Request
import traceback
import os

class BpodLogger:
    def __init__(self, log_file_path='log'):
        self.log_file_path = log_file_path
        # 确保日志目录存在
        os.makedirs(self.log_file_path, exist_ok=True)
        self.setup_logging()

    def setup_logging(self):
        # 创建主logger
        self.logger = logging.getLogger('bpod_api')
        self.logger.setLevel(logging.DEBUG)
        # 防止重复添加handler与向上冒泡
        if getattr(self.logger, "_bpod_configured", False):
            return

        # 创建格式化器
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        # API请求日志
        api_handler = TimedRotatingFileHandler(
            f"{self.log_file_path}/api.log",
            when="midnight",
            interval=1,
            backupCount=10,
            encoding='utf-8'
        )
        api_handler.setLevel(logging.INFO)
        api_handler.setFormatter(formatter)
        self.logger.addHandler(api_handler)

        # 业务逻辑日志
        business_handler = TimedRotatingFileHandler(
            f"{self.log_file_path}/business.log",
            when="midnight",
            interval=1,
            backupCount=10,
            encoding='utf-8'
        )
        business_handler.setLevel(logging.DEBUG)
        business_handler.setFormatter(formatter)
        self.logger.addHandler(business_handler)

        # 错误日志
        error_handler = TimedRotatingFileHandler(
            f"{self.log_file_path}/error.log",
            when="midnight",
            interval=1,
            backupCount=10,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        self.logger.addHandler(error_handler)
        # 标记已配置，避免重复添加；并禁止向root传播
        self.logger.propagate = False
        setattr(self.logger, "_bpod_configured", True)

    def log_request(self, request: Request, response_time: float = None):
        """记录API请求信息"""
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "method": request.method,
            "url": str(request.url),
            "client_host": request.client.host
        }
        if response_time is not None:
            log_data["response_time"] = f"{response_time:.3f}s"
        
        self.info(f"API Request: {json.dumps(log_data)}")

    def log_error(self, error: Exception, request: Request = None):
        """记录错误信息"""
        error_data = {
            "timestamp": datetime.now().isoformat(),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "stack_trace": traceback.format_exc()
        }
        if request:
            error_data.update({
                "method": request.method,
                "url": str(request.url),
                "client_host": request.client.host
            })
        self.error(f"Error: {json.dumps(error_data)}")

    # 保持原有的日志方法
    def info(self, message):
        self.logger.info(message)

    def warning(self, message):
        self.logger.warning(message)

    def debug(self, message):
        self.logger.debug(message)

    def error(self, message):
        self.logger.error(message)
