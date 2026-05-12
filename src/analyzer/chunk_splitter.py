"""代码分割器：将大文件按逻辑边界拆分为可审查的片段chunk_splitter.py"""
import re
from typing import List, Dict
from dataclasses import dataclass


@dataclass
class CodeChunk:
    """代码片段"""
    content: str
    start_line: int
    end_line: int
    file_path: str
    language: str
    chunk_index: int
    total_chunks: int


def split_code(file_info: Dict, max_lines: int = 150) -> List[CodeChunk]:
    """
    将文件内容分割为多个代码片段

    策略:
    1. 小文件直接返回
    2. 大文件按函数/类边界分割
    3. 如果找不到边界，按行数均匀分割

    Args:
        file_info: {"path": str, "content": str, "language": str}
        max_lines: 每个片段最大行数

    Returns:
        CodeChunk 列表
    """
    content = file_info["content"]
    file_path = file_info["path"]
    language = file_info["language"]
    lines = content.split("\n")
    total_lines = len(lines)

    # 小文件直接返回
    if total_lines <= max_lines:
        return [CodeChunk(
            content=content,
            start_line=1,
            end_line=total_lines,
            file_path=file_path,
            language=language,
            chunk_index=0,
            total_chunks=1,
        )]

    # 尝试按逻辑边界分割
    boundaries = _find_boundaries(lines, language)

    if boundaries:
        chunks = _split_by_boundaries(lines, boundaries, max_lines)
    else:
        chunks = _split_by_lines(lines, max_lines)

    total_chunks = len(chunks)
    result = []
    for i, (start, end) in enumerate(chunks):
        chunk_lines = lines[start:end]
        chunk_content = "\n".join(chunk_lines)
        if chunk_content.strip():
            result.append(CodeChunk(
                content=chunk_content,
                start_line=start + 1,
                end_line=end,
                file_path=file_path,
                language=language,
                chunk_index=i,
                total_chunks=total_chunks,
            ))

    return result


def _find_boundaries(lines: List[str], language: str) -> List[int]:
    """
    查找代码的逻辑边界（函数/类定义的起始行）

    Returns:
        边界行号列表（0-indexed）
    """
    patterns = {
        "python": r"^(class\s+\w|def\s+\w|async\s+def\s+\w)",
        "javascript": r"^(function\s+\w|class\s+\w|const\s+\w+\s*=\s*(async\s+)?\(|export\s+(default\s+)?function|export\s+(default\s+)?class)",
        "typescript": r"^(function\s+\w|class\s+\w|const\s+\w+\s*=\s*(async\s+)?\(|export\s+(default\s+)?function|export\s+(default\s+)?class|interface\s+\w|type\s+\w)",
        "java": r"^(\s*(public|private|protected)\s+.*\{|\s*class\s+\w)",
        "go": r"^(func\s+|type\s+\w+\s+struct)",
        "rust": r"^(fn\s+|pub\s+fn\s+|impl\s+|struct\s+|enum\s+)",
        "cpp": r"^(\w+.*\{|class\s+\w|namespace\s+\w)",
        "c": r"^(\w+\s+\w+\s*\(|struct\s+\w)",
        "ruby": r"^(def\s+\w|class\s+\w|module\s+\w)",
        "php": r"^(\s*(public|private|protected)?\s*function\s+\w|class\s+\w)",
    }

    pattern_str = patterns.get(language)
    if not pattern_str:
        # 通用模式：空行后跟非空行
        pattern_str = None

    boundaries = [0]

    if pattern_str:
        pattern = re.compile(pattern_str)
        for i, line in enumerate(lines):
            if i > 0 and pattern.match(line.strip() if language == "python" else line):
                boundaries.append(i)
    else:
        # 通用策略：连续空行作为边界
        for i, line in enumerate(lines):
            if i > 0 and i < len(lines) - 1:
                if not line.strip() and lines[i - 1].strip() and i + 1 < len(lines) and lines[i + 1].strip():
                    boundaries.append(i + 1)

    return boundaries


def _split_by_boundaries(lines: List[str], boundaries: List[int], max_lines: int) -> List[tuple]:
    """按边界分割，合并过小的片段"""
    boundaries = sorted(set(boundaries))
    total = len(lines)
    chunks = []
    current_start = 0

    for i in range(1, len(boundaries)):
        boundary = boundaries[i]
        current_size = boundary - current_start

        if current_size >= max_lines:
            # 当前块已经够大，切割
            chunks.append((current_start, boundary))
            current_start = boundary

    # 最后一块
    if current_start < total:
        chunks.append((current_start, total))

    # 如果某个块太大，进一步按行数分割
    result = []
    for start, end in chunks:
        size = end - start
        if size > max_lines * 2:
            sub_chunks = _split_by_lines(lines[start:end], max_lines)
            for s, e in sub_chunks:
                result.append((start + s, start + e))
        else:
            result.append((start, end))

    return result


def _split_by_lines(lines: List[str], max_lines: int) -> List[tuple]:
    """按固定行数分割"""
    total = len(lines)
    chunks = []
    for i in range(0, total, max_lines):
        end = min(i + max_lines, total)
        chunks.append((i, end))
    return chunks