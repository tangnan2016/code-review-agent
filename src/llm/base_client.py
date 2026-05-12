"""LLM 客户端基类"""
from abc import ABC, abstractmethod
from typing import Optional


class BaseLLMClient(ABC):
    """LLM 客户端抽象基类"""

    def __init__(self, config: dict):
        self.api_key = config.get("api_key", "")
        self.base_url = config.get("base_url", "")
        self.model = config.get("model", "")
        self.max_tokens = config.get("max_tokens", 4096)
        self.temperature = config.get("temperature", 0.1)
        self.provider_name = "base"

    @abstractmethod
    async def chat(self, system_prompt: str, user_prompt: str) -> str:
        """
        发送对话请求

        Args:
            system_prompt: 系统提示
            user_prompt: 用户提示

        Returns:
            LLM 响应文本
        """
        pass

    @abstractmethod
    async def close(self):
        """关闭客户端连接"""
        pass