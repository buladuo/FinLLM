import time
import httpx
import logging
import threading
from openai import OpenAI
from typing import Dict
from abc import ABC, abstractmethod
from utils.logging_utils import LoggingUtils

import os
from httpx_socks import SyncProxyTransport


class LLMService(ABC):
    """
    抽象类：定义通用的大模型服务接口和请求到达率控制。
    """
    
    def __init__(self, config: Dict):
        self.name = config["name"]
        self.base_url = config["api_base"]
        self.api_key = config["api_key"]
        self.rpm = config["rpm"]
        self.lock = threading.Lock()
        self.last_request_time = 0
        self.min_interval = 60 / self.rpm
        self.model_type = config.get("mode_type","chat")
        
        self.request_timeout = config.get("request_timeout", 10)  # 可以设置默认值
        self.retries = config.get("retries", 3)  # 可以设置默认值
        
        self.logger = logging.getLogger(self.__class__.__name__)

        # 初始化 OpenAI 客户端
        http_client = self._get_proxy()
        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            http_client=http_client
        )
    
    def _get_proxy(self) -> httpx.Client:
        """获取并配置代理客户端"""
        proxy_url = os.getenv("ALL_PROXY") or os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY")

        if proxy_url:
            if proxy_url.startswith("socks://"):
                # 更新代理 URL 为 socks5
                proxy_url = proxy_url.replace("socks://", "socks5://", 1)
                self.logger.info(f"Updated proxy URL to use socks5: {proxy_url}")

            # 配置 HTTPX 客户端
            if proxy_url.startswith("socks5://"):
                self.logger.info(f"Detected SOCKS5 proxy: {proxy_url}")
                transport = SyncProxyTransport.from_url(proxy_url)
                httpx_client = httpx.Client(transport=transport)
            else:
                # HTTP/HTTPS 代理
                self.logger.info(f"Detected HTTP/HTTPS proxy: {proxy_url}")
                httpx_client = httpx.Client(proxies=proxy_url)
        else:
            self.logger.info("No proxy detected, using direct connection")
            httpx_client = httpx.Client()  # 默认使用直接连接
        
        return httpx_client

    def _rate_limit(self):
        """
        控制请求到达率。
        """
        with self.lock:
            current_time = time.time()
            elapsed_time = current_time - self.last_request_time
            if elapsed_time < self.min_interval:
                sleep_time = self.min_interval - elapsed_time
                self.logger.info(f"Rate limit reached. Sleeping for {sleep_time:.2f} seconds.")
                time.sleep(sleep_time)
            self.last_request_time = time.time()
            
    def _is_compliant(self, response: str) -> bool:
        """
        检查返回内容是否合规的函数。
        :param response: 模型返回的文本
        :return: 是否合规的布尔值
        """
        # 示例合规性检查：你可以根据需求调整检查逻辑
        forbidden_keywords = ["服务器繁忙，请稍候再试", "[内容由于不合规被停止生成，我们换个话题吧]","服务暂时不可用，第三方响应错误"]  # 添加你的不合规关键字
        
        for keyword in forbidden_keywords:
            if keyword in response:
                self.logger.warning(f"Response contains forbidden keyword: {keyword}")
                return False
        
        return True
    
    def _trim_response_based_on_thinking(self, response: str) -> str:
        """
        根据模型思考部分的提示裁剪响应文本。
        :param response: 模型返回的文本
        :return: 裁剪后的文本
        """
        # 示例检查：根据某些关键词裁剪文本
        thinking_indicators = [
            "[思考结束]"
        ]

        for indicator in thinking_indicators:
            if indicator in response:
                # 找到指示词的位置并裁剪
                index = response.find(indicator)
                trimmed_response = response[index:].strip()  # 裁剪到指示词之前
                self.logger.info(f"Response trimmed based on thinking indicator '{indicator}'.")
                return trimmed_response

        return response  # 如果没有发现，返回原始响应
    
    @abstractmethod
    def query(self, messages: list) -> str:
        """
        发送查询请求。
        :param message: 请求内容
        :return: 模型回复
        """
        pass
    

class OpenAIService(LLMService):
    """
    OpenAI 模型服务的具体实现。
    """

    def query(self, messages: list) -> str:
        self.logger.debug(f"Querying model '{self.name}' with message: {messages}")
        for message in messages:
            if not isinstance(message['content'], str):
                message['content'] = str(message['content'])
        for attempt in range(self.retries):
            self._rate_limit()
            try:
                completion = self.client.chat.completions.create(
                    model=self.name,
                    messages=messages,
                    timeout=self.request_timeout
                )
                response_text = completion.choices[0].message.content
                self.logger.debug(f"Received response from model '{self.name}': {response_text}")
                
                # 后处理检查返回内容的合规性
                if not self._is_compliant(response_text):
                    self.logger.warning(f"Response not compliant, attempting retry {attempt + 1}.")
                    continue  # 不合规，继续重试
                
                if self.model_type == "think":
                    response_text = self._trim_response_based_on_thinking(response_text)
                
                return response_text
            
            except Exception as e:
                self.logger.error(f"Attempt {attempt + 1} - Error querying model {self.name}: {e}")
        
        return "Error: Failed to retrieve a compliant response after multiple attempts."



class LLMServiceFactory:
    """
    工厂类：根据配置动态创建 LLM 服务实例。
    """
    
    @staticmethod
    def create_service(model_config: Dict, global_config: Dict) -> LLMService:
        # 在这里添加全局配置的信息，但传递给服务的构造函数需要的是合并后的配置
        model_config["request_timeout"] = global_config.get("request_timeout", 10)
        model_config["retries"] = global_config.get("retries", 3)

        if model_config.get("type", "openai") == "openai":
            logging.info(f"Creating OpenAI service with model name: {model_config['name']}")
            return OpenAIService(model_config)
        else:
            logging.error(f"Unsupported type: {model_config.get('type')}")
            raise ValueError(f"Unsupported type: {model_config.get('type')}")


# 测试脚本
if __name__ == "__main__":
    import yaml

    # 加载配置
    config_path = "../configs/config.yaml"
    with open(config_path, "r") as file:
        config = yaml.safe_load(file)
    
    logging_config = config.get("logging", {})
    LoggingUtils.setup_logging(logging_config)
    

    models_config = config["models"]
    global_config = config["global"]

    # 测试每个模型
    for model_name, model_config in models_config.items():
        print(f"\n测试模型: {model_name}")
        service = LLMServiceFactory.create_service(model_config,global_config)
        response = service.query("Hello! Can you explain what RPM is?")
        print(f"模型回复: {response}")
