"""审查引擎测试"""
import pytest
import json
import asyncio
from unittest.mock import AsyncMock, MagicMock

from src.analyzer.review_engine import ReviewEngine, Severity, ReviewIssue
from src.analyzer.chunk_splitter import CodeChunk
from src.llm.base_client import BaseLLMClient


class MockLLMClient(BaseLLMClient):
    """模拟 LLM 客户端"""

    def __init__(self, response: str = None):
        super().__init__("http://mock", "key", "mock-model")
        self._response = response or json.dumps({
            "issues": [
                {
                    "line_start": 5,
                    "line_end": 5,
                    "severity": "warning",
                    "category": "Style",
                    "title": "魔法数字",
                    "description": "代码中使用了硬编码的数字",
                    "suggestion": "使用常量代替"
                }
            ]
        })

    async def chat(self, system_prompt: str, user_prompt: str) -> str:
        await asyncio.sleep(0.01)  # 模拟网络延迟
        return self._response

    async def health_check(self) -> bool:
        return True


@pytest.fixture
def sample_chunk():
    return CodeChunk(
        file_path="test.py",
        content="x = 1\ny = 2\nz = x + y\nprint(z)\nresult = 42\n",
        start_line=1,
        end_line=5,
        language="python",
        chunk_index=0,
        total_chunks=1
    )


class TestReviewEngine:
    @pytest.mark.asyncio
    async def test_review_single_chunk(self, sample_chunk):
        """测试单个片段审查"""
        client = MockLLMClient()
        engine = ReviewEngine(client, concurrency=2)
        result = await engine.review_all([sample_chunk])

        assert result.total_chunks == 1
        assert result.total_issues == 1
        assert result.issues[0].severity == Severity.WARNING
        assert result.issues[0].title == "魔法数字"

    @pytest.mark.asyncio
    async def test_review_empty_response(self, sample_chunk):
        """测试空响应"""
        client = MockLLMClient(response='{"issues": []}')
        engine = ReviewEngine(client, concurrency=2)
        result = await engine.review_all([sample_chunk])

        assert result.total_issues == 0

    @pytest.mark.asyncio
    async def test_review_invalid_json(self, sample_chunk):
        """测试无效 JSON 响应"""
        client = MockLLMClient(response="这不是有效的 JSON")
        engine = ReviewEngine(client, concurrency=2)
        result = await engine.review_all([sample_chunk])

        assert result.total_issues == 0  # 应该优雅处理

    @pytest.mark.asyncio
    async def test_review_concurrent(self, sample_chunk):
        """测试并发审查"""
        client = MockLLMClient()
        engine = ReviewEngine(client, concurrency=3)

        chunks = [sample_chunk] * 10
        result = await engine.review_all(chunks)

        assert result.total_chunks == 10
        assert result.total_issues == 10

    @pytest.mark.asyncio
    async def test_line_number_adjustment(self, sample_chunk):
        """测试行号调整"""
        # 片段从第 50 行开始
        chunk = CodeChunk(
            file_path="test.py",
            content="x = 1\n",
            start_line=50,
            end_line=50,
            language="python",
            chunk_index=1,
            total_chunks=2
        )
        client = MockLLMClient()
        engine = ReviewEngine(client, concurrency=1)
        result = await engine.review_all([chunk])

        # LLM 返回的 line_start=5，加上偏移 50-1=49，最终应该是 54
        assert result.issues[0].line_start == 54