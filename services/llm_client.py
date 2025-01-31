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
    
    def __init__(self, name: str, base_url: str, api_key: str, rpm: int,request_timeout:int,retries:int):
        self.name = name
        self.base_url = base_url
        self.api_key = api_key
        self.rpm = rpm
        self.lock = threading.Lock()
        self.last_request_time = 0
        self.min_interval = 60 / rpm
        
        self.request_timeout = request_timeout
        self.retries = retries
        
        self.logger = logging.getLogger(self.__class__.__name__)

        # 初始化 OpenAI 客户端
        # http_client = httpx.Client()
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
    
    @abstractmethod
    def query(self, prompt: str, question: str) -> str:
        """
        发送查询请求。
        :param prompt: 查询内容
        :return: 模型回复
        """
        pass
    

class OpenAIService(LLMService):
    """
    OpenAI 模型服务的具体实现。
    """
    def query(self, prompt: str, question: str = None) -> str:
        if question is None:
            return self._retry_query_with_prompt(prompt)
        else:
            return self._retry_query_with_prompt_and_question(prompt, question)
    
    
    def _retry_query_with_prompt_and_question(self, prompt: str, question: str) -> str:
        question = str(question)

        self.logger.debug(f"Querying model '{self.name}' with system prompt: {prompt} and question: {question}")
        
        for attempt in range(self.retries):
            self._rate_limit()
            try:
                messages = [
                    {"role": "system", "content": str(prompt)},
                    {"role": "user", "content": str(question)}
                ]
                completion = self.client.chat.completions.create(
                    model=self.name,
                    messages=messages,
                    timeout=self.request_timeout
                )
                self.logger.info(f"Received response from model '{self.name}'.")
                return completion.choices[0].message.content
            except Exception as e:
                self.logger.error(f"Attempt {attempt + 1} - Error querying model {self.name}: {e}"
                                  f"Your input is{messages}")
        
        return "Error: Failed to retrieve response after multiple attempts."

    def _retry_query_with_prompt(self, prompt: str) -> str:
        
        self.logger.debug(f"Querying model '{self.name}' with prompt: {prompt}")
        for attempt in range(self.retries):
            self._rate_limit()
            try:
                completion = self.client.chat.completions.create(
                    model=self.name,
                    messages=[{"role": "user", "content": prompt}],
                    timeout=self.request_timeout
                )
                self.logger.info(f"Received response from model '{self.name}'.")
                return completion.choices[0].message.content
            except Exception as e:
                self.logger.error(f"Attempt {attempt + 1} - Error querying model {self.name}: {e}")
        return "Error: Failed to retrieve response after multiple attempts."

class LLMServiceFactory:
    """
    工厂类：根据配置动态创建 LLM 服务实例。
    """

    @staticmethod
    def create_service(model_config: Dict,global_config:Dict) -> LLMService:
        model_type = model_config.get("type", "openai")
        name = model_config["name"]
        api_base = model_config["api_base"]
        api_key = model_config["api_key"]
        rpm = model_config["rpm"]
        
        request_timeout = global_config.get("request_timeout",10)
        retries = global_config.get("retries",3)

        if model_type == "openai":
            logging.info(f"Creating OpenAI service with model name: {name}")
            return OpenAIService(name, api_base, api_key, rpm, request_timeout,retries)
        else:
            logging.error(f"Unsupported model type: {model_type}")
            raise ValueError(f"Unsupported model type: {model_type}")

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
