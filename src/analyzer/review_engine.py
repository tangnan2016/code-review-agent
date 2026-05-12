"""审查引擎：调度 LLM 进行代码审查review_engine.py"""
import asyncio
import json
import re
from typing import List, Dict, Optional

from src.analyzer.chunk_splitter import CodeChunk, split_code
from src.llm.llm_factory import create_llm_client
from src.llm.base_client import BaseLLMClient
from src.utils.logger import logger

SYSTEM_PROMPT = """你是一位资深代码审查专家，拥有15年软件工程经验。
请对以下代码进行审查，关注以下方面：
1. **安全性(Security)**: SQL注入、XSS、硬编码密钥、路径遍历等
2. **正确性(Logic)**: 空指针、边界条件、资源泄漏、竞态条件等
3. **性能(Performance)**: N+1查询、不必要的内存分配、算法复杂度等
4. **代码规范(Style)**: 命名、魔法数字、代码重复等
5. **最佳实践(BestPractice)**: 设计模式、错误处理、日志等
6. **可维护性(Maintainability)**: 复杂度、耦合度、可读性等

## 输出格式
严格输出 JSON，不要添加任何其他文字：
```json
{
  "issues": [
    {
      "line_start": 10,
      "line_end": 12,
      "severity": "warning",
      "category": "Security",
      "title": "硬编码密钥",
      "description": "代码中包含硬编码的API密钥，可能导致安全风险",
      "suggestion": "使用环境变量或配置文件管理密钥"
    }
  ]
}
```

## 规则
- severity 取值: critical, error, warning, info
- category 取值: Security, Logic, Performance, Style, BestPractice, Maintainability
- 如果没有问题，返回 {"issues": []}
- 只报告真正有价值的问题，不要制造噪音
- line_start 和 line_end 必须在给定的行范围内
"""

# 重试配置
_MAX_RETRIES = 5
_RETRY_BASE_DELAY = 2.0   # 首次重试等待秒数，指数递增


async def review_code(files: List[Dict], config: dict) -> List[Dict]:
    """
    审查代码文件列表

    Args:
        files: 文件信息列表 [{"path", "content", "language"}]
        config: 完整配置

    Returns:
        问题列表 [{"file", "line_start", "line_end", "severity", ...}]
    """
    analyzer_config = config.get("analyzer", {})
    llm_config = config.get("llm", {})
    concurrency = analyzer_config.get("concurrency", 5)           # 并发请求数，建议 2-3（DeepSeek 限流）
    max_lines = analyzer_config.get("max_chunk_lines", 150)        # 与 config.yaml 的 key 对齐

    # 分割代码
    all_chunks: List[CodeChunk] = []
    for file_info in files:
        chunks = split_code(file_info, max_lines)
        all_chunks.extend(chunks)

    logger.info(f"共 {len(files)} 个文件，分割为 {len(all_chunks)} 个代码片段")

    if not all_chunks:
        return []

    # 创建 LLM 客户端
    client = create_llm_client(llm_config)
    logger.info(f"使用 LLM: {client.provider_name} / {client.model}")

    # 并发审查
    semaphore = asyncio.Semaphore(concurrency)

    async def review_chunk(chunk: CodeChunk) -> List[Dict]:
        async with semaphore:
            return await _review_with_retry(client, chunk)

    tasks = [review_chunk(chunk) for chunk in all_chunks]
    completed = 0
    total = len(tasks)
    all_issues = []

    for coro in asyncio.as_completed(tasks):
        result = await coro
        all_issues.extend(result)
        completed += 1
        if completed % 5 == 0 or completed == total:
            logger.info(f"审查进度: {completed}/{total}")

    await client.close()

    # 按严重程度排序
    severity_order = {"critical": 0, "error": 1, "warning": 2, "info": 3}
    all_issues.sort(key=lambda x: severity_order.get(x.get("severity", "info"), 9))

    logger.info(f"审查完成，共发现 {len(all_issues)} 个问题")
    return all_issues


async def _review_with_retry(client: BaseLLMClient, chunk: CodeChunk) -> List[Dict]:
    """带重试的单 chunk 审查，指数退避；超时错误等待更长时间再重试"""
    tag = f"[{chunk.file_path}:{chunk.start_line}]"

    for attempt in range(_MAX_RETRIES + 1):
        try:
            return await _review_single_chunk(client, chunk)
        except Exception as e:
            exc_info = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
            if attempt < _MAX_RETRIES:
                # 超时说明服务端繁忙，等更长时间；普通错误快速重试
                is_timeout = (
                    isinstance(e, (asyncio.TimeoutError, TimeoutError))
                    or "timeout" in type(e).__name__.lower()
                    or "timeout" in str(e).lower()
                )
                base = 30.0 if is_timeout else _RETRY_BASE_DELAY
                delay = base * (2 ** attempt)
                logger.debug(f"审查暂时失败 {tag}（第{attempt + 1}次），{delay:.0f}s 后重试 | {exc_info}")
                await asyncio.sleep(delay)
            else:
                logger.warning(f"审查失败 {tag}（已重试{_MAX_RETRIES}次）| {exc_info}")

    return []


async def _review_single_chunk(client: BaseLLMClient, chunk: CodeChunk) -> List[Dict]:
    """审查单个代码片段（不含重试）"""
    user_prompt = _build_user_prompt(chunk)
    response = await client.chat(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )
    return _parse_response(response, chunk)


def _build_user_prompt(chunk: CodeChunk) -> str:
    """构建用户提示"""
    context = ""
    if chunk.total_chunks > 1:
        context = f"（第 {chunk.chunk_index + 1}/{chunk.total_chunks} 个片段）"

    header = (
        f"请审查以下代码：\n\n"
        f"文件: {chunk.file_path} {context}\n"
        f"语言: {chunk.language}\n"
        f"行范围: {chunk.start_line} - {chunk.end_line}\n\n"
    )
    return header + f"```{chunk.language}\n{chunk.content}\n```"


def _parse_response(response: str, chunk: CodeChunk) -> List[Dict]:
    """解析 LLM 响应为问题列表"""
    json_str = _extract_json(response)
    if not json_str:
        logger.debug(f"未提取到 JSON [{chunk.file_path}:{chunk.start_line}]: {response[:200]!r}")
        return []

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.debug(f"JSON 解析失败 [{chunk.file_path}:{chunk.start_line}]: {e} | 原文: {json_str[:200]!r}")
        return []

    issues_raw = data.get("issues", [])
    if not isinstance(issues_raw, list):
        return []

    issues = []
    required = {"line_start", "line_end", "severity", "category", "title", "description"}
    valid_severities = {"critical", "error", "warning", "info"}

    for item in issues_raw:
        if not isinstance(item, dict):
            continue
        if not required.issubset(item.keys()):
            continue

        line_start = item["line_start"]
        line_end = item["line_end"]
        if not isinstance(line_start, int) or not isinstance(line_end, int):
            continue

        severity = item["severity"] if item["severity"] in valid_severities else "info"

        issues.append({
            "file": chunk.file_path,
            "line_start": line_start,
            "line_end": line_end,
            "severity": severity,
            "category": item["category"],
            "title": item["title"],
            "description": item["description"],
            "suggestion": item.get("suggestion", ""),
        })

    return issues


def _extract_json(text: str) -> Optional[str]:
    """
    从 LLM 返回文本中提取 JSON 字符串。

    按优先级尝试：
    1. ```json ... ``` 代码块
    2. ``` ... ``` 代码块
    3. 裸 JSON 对象（大括号匹配）
    """
    # 1. 带语言标注的代码块
    m = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # 2. 无语言标注的代码块
    m = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        candidate = m.group(1).strip()
        if candidate.startswith("{"):
            return candidate

    # 3. 裸 JSON：找到第一个 { 然后做括号匹配
    brace_start = text.find("{")
    if brace_start == -1:
        return None

    depth = 0
    in_string = False
    escape_next = False

    for i in range(brace_start, len(text)):
        ch = text[i]
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[brace_start: i + 1]

    return None