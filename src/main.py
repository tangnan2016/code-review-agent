"""主流程编排main.py"""
import asyncio
import time
from typing import List, Dict

from src.utils.config_loader import ConfigLoader
from src.utils.logger import logger, setup_logger
from src.repo.local_repo import scan_local_repo
from src.repo.remote_repo import clone_and_scan, is_git_url
from src.analyzer.review_engine import review_code
from src.report.report_generator import ReportGenerator


async def run_review(
    source: str,
    provider: str = None,
    model: str = None,
    output_dir: str = None,
    output_format: str = None,
    language: str = None,
    config_path: str = "config/config.yaml",
    verbose: bool = False,
):
    """
    执行代码审查主流程

    Args:
        source: 代码来源（本地路径或远程 Git URL）
        provider: LLM 提供者
        model: 模型名称
        output_dir: 输出目录
        output_format: 输出格式 (html/markdown/json)
        language: 报告语言
        config_path: 配置文件路径
        verbose: 是否显示详细日志
    """
    # 1. 加载配置
    config = ConfigLoader.load(config_path)

    # 应用命令行参数覆盖
    if provider:
        config.setdefault("llm", {})["provider"] = provider
    if model:
        config.setdefault("llm", {})["model"] = model
    if output_dir:
        config.setdefault("output", {})["dir"] = output_dir
    if output_format:
        config.setdefault("output", {})["format"] = output_format
    if language:
        config.setdefault("output", {})["language"] = language

    # 设置日志级别
    log_level = "DEBUG" if verbose else config.get("log_level", "INFO")
    setup_logger(log_level)

    logger.info("=" * 60)
    logger.info("Code Review Agent 启动")
    logger.info("=" * 60)
    start_time = time.time()

    # 2. 获取代码文件
    files = _load_files(source, config)
    if not files:
        logger.warning("未找到可审查的代码文件")
        return None

    logger.info(f"扫描到 {len(files)} 个代码文件")

    # 3. 执行审查
    issues = await review_code(files, config)

    # 4. 生成报告
    output_config = config.get("output", {})
    report_format = output_config.get("format", "html")
    report_dir = output_config.get("dir", "output")
    report_language = output_config.get("language", "zh")

    generator = ReportGenerator(
        output_dir=report_dir,
        output_format=report_format,
        language=report_language,
    )

    report_path = generator.generate(
        issues=issues,
        files=files,
        source=source,
        config=config,
    )

    # 5. 输出结果摘要
    elapsed = time.time() - start_time
    _print_summary(issues, files, report_path, elapsed)

    return report_path


def _load_files(source: str, config: dict) -> List[Dict]:
    scanner_config = config.get("scanner", {})

    if is_git_url(source):
        branch = scanner_config.get("branch")
        files = clone_and_scan(source, scanner_config, branch=branch)
    else:
        files = scan_local_repo(source, scanner_config)

    return files


def _print_summary(issues: List[Dict], files: List[Dict], report_path: str, elapsed: float):
    """打印审查结果摘要"""
    logger.info("=" * 60)
    logger.info("审查完成")
    logger.info("=" * 60)
    logger.info(f"文件数: {len(files)}")
    logger.info(f"问题数: {len(issues)}")

    # 按严重程度统计
    severity_counts = {}
    for issue in issues:
        sev = issue.get("severity", "info")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    for sev in ["critical", "error", "warning", "info"]:
        count = severity_counts.get(sev, 0)
        if count > 0:
            logger.info(f"  {sev}: {count}")

    logger.info(f"耗时: {elapsed:.1f}s")
    logger.info(f"报告: {report_path}")