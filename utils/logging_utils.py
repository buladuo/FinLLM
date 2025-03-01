import logging
import os
import glob
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
    def _get_log_file(log_file_path: str, file_name: str) -> str:
        # 确保路径以'/'结尾并组合成完整的日志文件路径
        if not log_file_path.endswith('/'):
            log_file_path += '/'
        return os.path.join(log_file_path, file_name)
    
    @staticmethod
    def clear_log_folder(log_file_path: str):
        # 清理日志文件夹，删除其中的所有日志文件
        if os.path.exists(log_file_path):
            for log_file in glob.glob(os.path.join(log_file_path, '*.log')):
                try:
                    os.remove(log_file)
                    logging.info(f"已删除日志文件: {log_file}")
                except Exception as e:
                    logging.error(f"删除日志文件 {log_file} 时发生错误: {e}")
        else:
            logging.warning(f"日志目录不存在: {log_file_path}")

    @staticmethod
    def setup_logging(logging_config: Dict):
        log_level = logging_config.get("level", "INFO").upper()
        log_file_path = logging_config.get("file", "./logs/")

        # 清空日志文件夹
        # LoggingUtils.clear_log_folder(log_file_path)

        # 创建日志文件
        log_file = LoggingUtils._get_log_file(log_file_path, 'init.log')

        # 清除现有的日志处理器
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)

        # 设置新的日志配置
        logging.basicConfig(
            level=getattr(logging, log_level, logging.INFO),
            format="[%(levelname)s][%(filename)s:%(funcName)s:%(lineno)d] - %(message)s",
            handlers=[
                logging.FileHandler(log_file, encoding="utf-8")
            ]
        )

        logging.info(f"日志系统已初始化，日志等级: {log_level}, 输出文件: {log_file}")
    @staticmethod
    def update_logging_file(logging_config: Dict, id):
        log_level = logging_config.get("level", "INFO").upper()
        log_file = LoggingUtils._get_log_file(logging_config.get("file", "./logs/"), f'{id + 1}.log')

        # 更新日志文件的路径
        for handler in logging.root.handlers[:]:
            handler.close()
            logging.root.removeHandler(handler)

        # 创建新的 FileHandler 并添加到 logger
        try:
            new_handler = logging.FileHandler(log_file, encoding="utf-8")

            # 设置日志格式
            formatter = logging.Formatter("[%(levelname)s][%(filename)s:%(funcName)s:%(lineno)d] - %(message)s")
            new_handler.setFormatter(formatter)

            # 设置日志级别
            logging.getLogger().setLevel(getattr(logging, log_level, logging.INFO))

            # 添加新的处理器到 logger
            logging.getLogger().addHandler(new_handler)
            logging.info(f"日志文件已更新: {log_file}")
        except Exception as e:
            logging.error(f"更新日志文件时发生错误: {e}")

# 示例用法
if __name__ == "__main__":
    config = LoggingUtils.load_config("log_config.yaml")
    LoggingUtils.setup_logging(config)

    # 在程序中循环或需要更新日志文件的地方调用
    for i in range(3):
        LoggingUtils.update_logging_file(config, i)
        logging.info(f"这是循环第 {i + 1} 次的日志。")
