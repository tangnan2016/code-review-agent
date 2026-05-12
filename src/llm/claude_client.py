"""Anthropic Claude API 客户端"""
import asyncio
from typing import Optional

import aiohttp

from src.llm.base_client import BaseLLMClient
from src.utils.logger import logger


class ClaudeClient(BaseLLMClient):
    """Claude API 客户端"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.provider_name = "claude"
        self._session: Optional[aiohttp.ClientSession] = None

    def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建 HTTP session"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=120)
            headers = {
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            }
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                headers=headers,
            )
        return self._session

    async def chat(self, system_prompt: str, user_prompt: str) -> str:
        """发送对话请求"""
        session = self._get_session()

        url = f"{self.base_url.rstrip('/')}/v1/messages"

        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_prompt},
            ],
        }

        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with session.post(url, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        content = data.get("content", [])
                        if content and len(content) > 0:
                            return content[0].get("text", "")
                        return ""

                    elif resp.status == 429:
                        retry_after = int(resp.headers.get("Retry-After", 10))
                        logger.warning(f"Claude 速率限制，等待 {retry_after}s...")
                        await asyncio.sleep(retry_after)
                        continue

                    else:
                        body = await resp.text()
                        logger.error(f"Claude API 错误 [{resp.status}]: {body[:300]}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        raise RuntimeError(f"Claude API 请求失败: {resp.status}")

            except aiohttp.ClientError as e:
                logger.warning(f"网络错误 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise

        return ""

    async def close(self):
        """关闭连接"""
        if self._session and not self._session.closed:
            await self._session.close()