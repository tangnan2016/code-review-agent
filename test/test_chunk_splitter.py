"""代码分割器测试"""
import pytest
from src.scanner.file_scanner import ScannedFile
from src.analyzer.chunk_splitter import ChunkSplitter


@pytest.fixture
def python_file():
    """创建一个示例 Python 文件"""
    content = "\n".join([f"line_{i} = {i}" for i in range(1, 301)])
    return ScannedFile(
        absolute_path="/tmp/test.py",
        relative_path="test.py",
        content=content,
        language="python",
        size_bytes=len(content.encode())
    )


class TestChunkSplitter:
    def test_small_file_single_chunk(self):
        """小文件不需要分割"""
        content = "x = 1\ny = 2\nz = 3"
        file = ScannedFile(
            absolute_path="/tmp/small.py",
            relative_path="small.py",
            content=content,
            language="python",
            size_bytes=len(content.encode())
        )
        splitter = ChunkSplitter(max_lines=100)
        chunks = splitter.split_file(file)

        assert len(chunks) == 1
        assert chunks[0].content == content
        assert chunks[0].start_line == 1

    def test_large_file_multiple_chunks(self, python_file):
        """大文件应该被分割为多个片段"""
        splitter = ChunkSplitter(max_lines=100, overlap=10)
        chunks = splitter.split_file(python_file)

        assert len(chunks) > 1
        # 每个片段不超过 max_lines
        for chunk in chunks:
            lines = chunk.content.split("\n")
            assert len(lines) <= 110  # max_lines + overlap 容差

    def test_overlap(self, python_file):
        """测试片段重叠"""
        splitter = ChunkSplitter(max_lines=100, overlap=10)
        chunks = splitter.split_file(python_file)

        if len(chunks) >= 2:
            # 第二个片段的起始行应该在第一个片段结束之前
            assert chunks[1].start_line < chunks[0].end_line + 1

    def test_split_files_batch(self, python_file):
        """测试批量分割"""
        splitter = ChunkSplitter(max_lines=100)
        chunks = splitter.split_files([python_file, python_file])

        # 两个文件的片段总数应该是单个文件的两倍
        single_chunks = splitter.split_file(python_file)
        assert len(chunks) == len(single_chunks) * 2