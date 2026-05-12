"""OpenAI 兼容 API 客户端（支持 OpenAI、DeepSeek、Ollama 等）openai_client.py"""
import asyncio
from typing import Optional

import aiohttp

from src.llm.base_client import BaseLLMClient
from src.utils.logger import logger


class OpenAIClient(BaseLLMClient):
    """OpenAI 兼容 API 客户端"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.provider_name = config.get("_provider_name", "openai")
        self._session: Optional[aiohttp.ClientSession] = None

    def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建 HTTP session（损坏后自动重建）"""
        if self._session is None or self._session.closed:
            self._session = self._create_session()
        return self._session

    def _create_session(self) -> aiohttp.ClientSession:
        timeout = aiohttp.ClientTimeout(
            total=120,
            connect=10,      # 连接超时单独控制，避免无限等待
            sock_read=90,
        )
        headers = {"Content-Type": "application/json"}
        if self.api_key and self.api_key != "ollama":
            headers["Authorization"] = f"Bearer {self.api_key}"
        return aiohttp.ClientSession(timeout=timeout, headers=headers)

    def _invalidate_session(self):
        """标记 session 失效，下次请求时重建"""
        if self._session and not self._session.closed:
            asyncio.ensure_future(self._session.close())
        self._session = None

    async def chat(self, system_prompt: str, user_prompt: str) -> str:
        """
        发送对话请求。

        - 仅处理低层问题：429 限流（读取 Retry-After）、网络抖动（最多 1 次重建 session）
        - 空响应 / API 错误均抛出异常，由上层（review_engine）决定是否重试
        """
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }

        # 429 最多重试 3 次，网络错误最多重建 1 次 session
        for rate_attempt in range(4):
            try:
                return await self._do_request(url, payload)
            except _RateLimitError as e:
                if rate_attempt >= 3:
                    raise RuntimeError(f"速率限制重试耗尽（{rate_attempt + 1}次）") from e
                delay = e.retry_after
                logger.warning(f"速率限制，等待 {delay}s 后重试（第{rate_attempt + 1}次）...")
                await asyncio.sleep(delay)
            except aiohttp.ClientError as e:
                # 网络层错误：重建 session 后重试一次
                logger.warning(f"网络错误，重建 session 后重试: {type(e).__name__}: {e}")
                self._invalidate_session()
                try:
                    return await self._do_request(url, payload)
                except Exception as retry_exc:
                    raise RuntimeError(f"网络错误重试仍失败: {type(retry_exc).__name__}: {retry_exc}") from retry_exc

        # 逻辑上不可达，保险起见
        raise RuntimeError("请求异常退出")

    async def _do_request(self, url: str, payload: dict) -> str:
        """执行单次 HTTP 请求，返回内容字符串或抛出具体异常"""
        session = self._get_session()
        async with session.post(url, json=payload) as resp:
            if resp.status == 429:
                retry_after = int(resp.headers.get("Retry-After", 5))
                raise _RateLimitError(retry_after)

            if resp.status != 200:
                body = await resp.text()
                raise RuntimeError(f"API 错误 [{resp.status}]: {body[:300]}")

            data = await resp.json()
            choices = data.get("choices") or []
            if not choices:
                raise RuntimeError(f"API 返回空 choices，原始响应: {str(data)[:200]}")

            content: str = choices[0].get("message", {}).get("content", "")
            if not content.strip():
                raise RuntimeError("API 返回内容为空字符串")

            return content

    async def close(self):
        """关闭连接"""
        if self._session and not self._session.closed:
            await self._session.close()


class _RateLimitError(Exception):
    """429 速率限制专用异常（内部使用）"""
    def __init__(self, retry_after: int):
        super().__init__(f"rate limit, retry after {retry_after}s")
        self.retry_after = retry_after