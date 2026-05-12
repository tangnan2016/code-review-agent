"""本地仓库文件扫描 local_repo.py"""
import os
from pathlib import Path
from typing import List, Dict
from src.utils.logger import logger

# 默认排除目录：虚拟环境 / 缓存 / 构建产物 / IDE / 依赖包等
_DEFAULT_IGNORE_DIRS: frozenset = frozenset({
    # Python 虚拟环境
    ".venv", "venv", "env",
    # Python 缓存 & 构建产物
    "__pycache__", ".mypy_cache", ".pytest_cache", ".tox",
    "dist", "build", ".eggs",
    # 版本控制
    ".git", ".svn", ".hg",
    # 前端依赖
    "node_modules", "vendor", "bower_components",
    # IDE / 编辑器
    ".idea", ".vscode", ".vs",
    # 测试覆盖率产物
    "htmlcov",
    # 其他常见构建输出
    "target", "out", "bin", "obj",
    ".cache",
})


def scan_local_repo(path: str, config: dict) -> List[Dict]:
    """
    扫描本地目录，返回符合条件的文件列表

    Args:
        path: 本地目录路径
        config: scanner 配置

    Returns:
        文件信息列表 [{"path": str, "content": str, "language": str}]
    """
    root = Path(path).resolve()

    if not root.exists():
        raise FileNotFoundError(f"路径不存在: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"不是目录: {root}")

    extensions = set(config.get("extensions", [".py"]))
    # 合并内置默认忽略目录 + config 里的自定义忽略目录
    ignore_dirs = _DEFAULT_IGNORE_DIRS | set(config.get("ignore_dirs", []))
    max_size_kb = config.get("max_file_size_kb", 500)

    files = []
    scanned = 0
    skipped = 0

    for dirpath, dirnames, filenames in os.walk(root):
        # 原地过滤：精确名称命中 OR 以 "." 开头的隐藏目录
        dirnames[:] = [
            d for d in dirnames
            if d not in ignore_dirs and not d.startswith(".")
        ]

        for filename in filenames:
            filepath = Path(dirpath) / filename
            ext = filepath.suffix.lower()

            if ext not in extensions:
                continue

            # 检查文件大小
            try:
                size_kb = filepath.stat().st_size / 1024
                if size_kb > max_size_kb:
                    logger.debug(f"跳过大文件: {filepath} ({size_kb:.1f} KB)")
                    skipped += 1
                    continue
            except OSError:
                continue

            # 读取文件内容
            try:
                content = filepath.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                skipped += 1
                continue

            # 跳过空文件
            if not content.strip():
                continue

            rel_path = str(filepath.relative_to(root))
            language = _detect_language(ext)

            files.append({
                "path": rel_path,
                "content": content,
                "language": language,
            })
            scanned += 1

    logger.info(f"扫描完成: {scanned} 个文件, 跳过 {skipped} 个")
    return files


def _detect_language(ext: str) -> str:
    """根据扩展名检测语言"""
    mapping = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".java": "java",
        ".go": "go",
        ".rs": "rust",
        ".cpp": "cpp",
        ".c": "c",
        ".cs": "csharp",
        ".rb": "ruby",
        ".php": "php",
        ".swift": "swift",
        ".kt": "kotlin",
        ".scala": "scala",
        ".vue": "vue",
        ".sh": "bash",
    }
    return mapping.get(ext, "unknown")