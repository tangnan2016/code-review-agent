"""报告生成辅助函数"""
import html
from typing import List, Dict


def count_by_severity(issues: List[Dict]) -> Dict[str, int]:
    """按严重程度统计问题数"""
    counts = {"critical": 0, "error": 0, "warning": 0, "info": 0}
    for issue in issues:
        severity = issue.get("severity", "info")
        if severity in counts:
            counts[severity] += 1
    return counts


def group_by_file(issues: List[Dict]) -> Dict[str, List[Dict]]:
    """按文件分组"""
    groups = {}
    for issue in issues:
        file_path = issue.get("file", "unknown")
        if file_path not in groups:
            groups[file_path] = []
        groups[file_path].append(issue)
    return groups


def escape_html(text: str) -> str:
    """HTML 转义"""
    return html.escape(text)


def severity_label(severity: str) -> str:
    """获取严重程度的中文标签"""
    labels = {
        "critical": "严重",
        "error": "错误",
        "warning": "警告",
        "info": "建议",
    }
    return labels.get(severity, severity)


def severity_emoji(severity: str) -> str:
    """获取严重程度的 emoji"""
    emojis = {
        "critical": "🔴",
        "error": "🟠",
        "warning": "🟡",
        "info": "🔵",
    }
    return emojis.get(severity, "⚪")