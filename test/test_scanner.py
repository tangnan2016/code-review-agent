"""文件扫描器测试"""
import pytest
import tempfile
from pathlib import Path

from src.scanner.file_scanner import FileScanner


@pytest.fixture
def sample_project(tmp_path):
    """创建示例项目结构"""
    # Python 文件
    (tmp_path / "main.py").write_text("print('hello')\n" * 10)
    (tmp_path / "utils.py").write_text("def helper(): pass\n" * 5)

    # JS 文件
    js_dir = tmp_path / "src"
    js_dir.mkdir()
    (js_dir / "app.js").write_text("const x = 1;\n" * 20)

    # 应该被排除的文件
    node_modules = tmp_path / "node_modules"
    node_modules.mkdir()
    (node_modules / "lib.js").write_text("module.exports = {}")

    # 大文件（超过限制）
    (tmp_path / "big.py").write_text("x = 1\n" * 100000)

    # 非代码文件
    (tmp_path / "readme.md").write_text("# README")
    (tmp_path / "data.json").write_text("{}")

    return tmp_path


class TestFileScanner:
    def test_scan_basic(self, sample_project):
        scanner = FileScanner(max_file_size_kb=500)
        files = scanner.scan(str(sample_project))

        # 应该找到 main.py, utils.py, app.js
        paths = [f.relative_path for f in files]
        assert "main.py" in paths
        assert "utils.py" in paths
        assert any("app.js" in p for p in paths)

    def test_exclude_dirs(self, sample_project):
        scanner = FileScanner(exclude_dirs=["node_modules"])
        files = scanner.scan(str(sample_project))

        paths = [f.relative_path for f in files]
        assert not any("node_modules" in p for p in paths)

    def test_exclude_large_files(self, sample_project):
        scanner = FileScanner(max_file_size_kb=10)
        files = scanner.scan(str(sample_project))

        paths = [f.relative_path for f in files]
        assert "big.py" not in paths

    def test_include_extensions(self, sample_project):
        scanner = FileScanner(include_extensions=[".py"])
        files = scanner.scan(str(sample_project))

        for f in files:
            assert f.relative_path.endswith(".py")

    def test_empty_directory(self, tmp_path):
        scanner = FileScanner()
        files = scanner.scan(str(tmp_path))
        assert len(files) == 0