import logging
import yaml
from typing import Dict

class LoggingUtils:
    """
    日志工具类：根据配置文件动态配置日志。
    """
    @staticmethod
    def load_config(config_file: str) -> Dict:
        with open(config_file, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
        return config

    @staticmethod
    def setup_logging(logging_config: Dict):
        log_level = logging_config.get("level", "INFO").upper()
        log_file = logging_config.get("file", "./logs/runtime.log")

        logging.basicConfig(
            level=getattr(logging, log_level, logging.INFO),
            format="%(asctime)s[%(levelname)s][%(filename)s:%(funcName)s:%(lineno)d] - %(message)s",
            handlers=[
                logging.FileHandler(log_file, encoding="utf-8")
            ]
        )

        logging.info(f"日志系统已初始化，日志等级: {log_level}, 输出文件: {log_file}")
