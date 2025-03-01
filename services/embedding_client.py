import time
import httpx
import logging
import threading
from openai import OpenAI
from typing import Dict, List
from abc import ABC, abstractmethod
from collections import deque

import os
from httpx_socks import SyncProxyTransport


class EmbeddingService(ABC):
    """
    抽象类：定义通用的 Embedding 服务接口和请求到达率控制。
    """
    
    def __init__(self, config: Dict):
        self.name = config["name"]
        self.base_url = config["api_base"]
        self.api_key = config["api_key"]
        self.rpm = config["rpm"]
        self.pool_size = config["embedding_pool_size"]
        self.tpm = config.get("tpm")
        self.dim = config.get("dim")
        
        
        self.lock = threading.Lock()
        self.last_request_time = 0
        self.min_interval = 60 / self.rpm
        
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
        
        self.cache = {}
        self.order = deque()  # 用于记录缓存的顺序
    
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
    def get_embeddings(self, text: List[str]) -> List[List[float]]:
        """
        获取文本的 Embedding。
        :param text: 文本列表
        :return: 返回嵌入向量的列表
        """
        pass


class OpenAIEmbeddingService(EmbeddingService):
    """
    OpenAI Embedding 服务的具体实现。
    """

    def __init__(self, config: Dict):
        super().__init__(config)
        self.tokens_used = 0  # 当前已使用的 token 数量
        self.last_reset_time = time.time()  # 上次重置 token 使用记录的时间
        
    def _check_and_reset_token_usage(self):
        """
        检查 token 使用情况，如果已到达新的时间窗口则重置 token 计数器。
        """
        current_time = time.time()
        elapsed_time = current_time - self.last_reset_time

        # 如果已经过了一分钟，则重置计数器
        if elapsed_time >= 60:
            self.tokens_used = 0
            self.last_reset_time = current_time
            self.logger.debug(f"Token usage counter reset. New cycle started.")
            
        

    def get_embeddings(self, text: List[str]) -> List[List[float]]:
        self.logger.debug(f"Getting embeddings for text: {text}")
        
        cached_embeddings = self._get_cached_embeddings(text)
        if cached_embeddings:
            return cached_embeddings
        
        for attempt in range(self.retries):
            self._rate_limit()
            self._check_and_reset_token_usage()
            try:
                embeddings_response = self.client.embeddings.create(
                    model=self.name,
                    input=text,
                    timeout=self.request_timeout,
                    encoding_format='float',
                    dimensions=self.dim
                )
                # 获取返回的 token 使用量
                total_tokens = dict(embeddings_response.usage)['total_tokens']
                self.tokens_used += total_tokens  # 更新已使用的 token 数量
                if self.tokens_used > self.tpm:
                    wait_time = 60 - (time.time() - self.last_reset_time)
                    if wait_time > 0:
                        self.logger.info(f"Token usage exceeded TPM limit. Waiting for {wait_time:.2f} seconds.")
                        time.sleep(wait_time)  # 等待直到下一个周期

                    # 重置 token 使用计数
                    self.tokens_used = total_tokens
                    self.last_reset_time = time.time()
                    
                embeddings = embeddings_response.data
                
                embeddings_list = [dict(embedding)['embedding'] for embedding in embeddings]
                self.logger.debug(f"Received embeddings from model '{self.name}': {embeddings_list}")
                
                # 将新获取的嵌入存入缓存
                self._cache_embeddings(text, embeddings_list)
                return embeddings_list
            
            except Exception as e:
                self.logger.error(f"Attempt {attempt + 1} - Error getting embeddings from model {self.name}: {e}")
        
        return []  # Return an empty list if all attempts fail
    
    def _get_cached_embeddings(self, text: List[str]) -> List[List[float]]:
        """检查缓存中是否有已请求过的文本嵌入"""
        embeddings = []
        for t in text:
            if t in self.cache:
                self.logger.info(f"Cache hit for: {t}")
                embeddings.append(self.cache[t])
            else:
                embeddings.append(None)  # 如果缓存中没有该文本的嵌入，则返回 None
        return [emb for emb in embeddings if emb is not None]  # 返回已缓存的嵌入列表
    
    def _cache_embeddings(self, text: List[str], embeddings_list: List[List[float]]):
        """将新获取的嵌入存入缓存池"""
        for t, emb in zip(text, embeddings_list):
            if len(self.cache) >= self.pool_size:
                # 缓存已满，移除最久未使用的条目
                oldest_text = self.order.popleft()
                del self.cache[oldest_text]
                self.logger.debug(f"Cache full. Removed: {oldest_text}")

            self.cache[t] = emb
            self.order.append(t)  # 将新添加的条目放到队列末尾


class EmbeddingServiceFactory:
    """
    工厂类：根据配置动态创建 Embedding 服务实例。
    """
    
    @staticmethod
    def create_service(model_config: Dict, global_config: Dict) -> EmbeddingService:
        # 在这里添加全局配置的信息，但传递给服务的构造函数需要的是合并后的配置
        model_config["request_timeout"] = global_config.get("request_timeout", 10)
        model_config["retries"] = global_config.get("retries", 3)
        model_config["embedding_pool_size"] = global_config.get("embedding_pool_size", 5)

        if model_config.get("type", "embedding") == "embedding":
            logging.info(f"Creating OpenAI embedding service with model name: {model_config['name']}")
            return OpenAIEmbeddingService(model_config)
        else:
            logging.error(f"Unsupported type: {model_config.get('type')}")
            raise ValueError(f"Unsupported type: {model_config.get('type')}")


