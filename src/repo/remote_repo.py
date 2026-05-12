"""远程 Git 仓库处理"""
import shutil
import tempfile
from pathlib import Path
from typing import List, Dict, Optional

from src.utils.logger import logger


def clone_and_scan(url: str, config: dict, branch: Optional[str] = None) -> List[Dict]:
    """
    克隆远程仓库并扫描文件

    Args:
        url: Git 仓库 URL
        config: scanner 配置
        branch: 分支名（可选）

    Returns:
        文件信息列表
    """
    try:
        import git
    except ImportError:
        raise ImportError("需要安装 gitpython: pip install gitpython")

    # 创建临时目录
    temp_dir = Path(tempfile.mkdtemp(prefix="code_review_"))
    logger.info(f"克隆仓库: {url} -> {temp_dir}")

    try:
        # 克隆
        clone_kwargs = {"depth": 1}
        if branch:
            clone_kwargs["branch"] = branch

        git.Repo.clone_from(url, str(temp_dir), **clone_kwargs)
        logger.info("克隆完成")

        # 扫描
        from src.repo.local_repo import scan_local_repo
        files = scan_local_repo(str(temp_dir), config)

        return files
    finally:
        # 清理临时目录
        try:
            shutil.rmtree(temp_dir)
            logger.info("临时目录已清理")
        except OSError as e:
            logger.warning(f"清理临时目录失败: {e}")


def is_git_url(source: str) -> bool:
    """判断是否为 Git URL"""
    git_patterns = [
        "https://github.com/",
        "https://gitlab.com/",
        "https://bitbucket.org/",
        "git@",
        "git://",
    ]
    source_lower = source.lower()
    if source_lower.endswith(".git"):
        return True
    for pattern in git_patterns:
        if source_lower.startswith(pattern):
            return True
    return False