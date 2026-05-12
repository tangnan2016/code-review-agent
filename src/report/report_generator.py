"""报告生成器：生成 HTML/JSON 格式的审查报告"""
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict

from src.report.helpers import (
    count_by_severity,
    group_by_file,
    escape_html,
    severity_label,
)
from src.utils.logger import logger

# HTML 模板文件路径（与本文件同目录）
_TEMPLATE_FILE = Path(__file__).parent / "report_template.html"


def _render_template(**kwargs) -> str:
    """读取 report_template.html 并替换 ${var} 占位符"""
    template = _TEMPLATE_FILE.read_text(encoding="utf-8")

    def _replace(m: re.Match) -> str:
        return str(kwargs.get(m.group(1), m.group(0)))

    return re.sub(r'\$\{(\w+)\}', _replace, template)


class ReportGenerator:
    """报告生成器"""

    def __init__(
        self,
        output_dir: str = "./reports",
        output_format: str = "html",
        language: str = "zh",
    ):
        self.output_dir = output_dir
        self.output_format = output_format
        self.language = language

    def generate(
        self,
        issues: List[Dict],
        files: List[Dict],
        source: str,
        config: dict,
    ) -> str:
        """
        生成审查报告

        Args:
            issues: 问题列表
            files: 文件列表
            source: 审查源（路径或URL）
            config: 完整配置

        Returns:
            报告文件路径
        """
        files_count = len(files)
        chunks_count = sum(f.get("chunks", 1) for f in files)
        elapsed = config.get("_elapsed", 0)

        Path(self.output_dir).mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"review_{timestamp}.{self.output_format}"
        filepath = os.path.join(self.output_dir, filename)

        if self.output_format == "json":
            self._generate_json_report(filepath, issues, source, elapsed, files_count, chunks_count)
        else:
            self._generate_html_report(filepath, issues, source, elapsed, files_count, chunks_count)

        logger.info(f"报告已生成: {filepath}")
        return filepath

    # ------------------------------------------------------------------ #
    #  JSON                                                                #
    # ------------------------------------------------------------------ #

    def _generate_json_report(
        self,
        filepath: str,
        issues: List[Dict],
        source: str,
        elapsed: float,
        files_count: int,
        chunks_count: int,
    ):
        counts = count_by_severity(issues)
        report = {
            "meta": {
                "source": source,
                "generated_at": datetime.now().isoformat(),
                "elapsed_seconds": round(elapsed, 2),
                "files_count": files_count,
                "chunks_count": chunks_count,
            },
            "summary": {"total": len(issues), **counts},
            "issues": issues,
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------ #
    #  HTML                                                                #
    # ------------------------------------------------------------------ #

    def _generate_html_report(
        self,
        filepath: str,
        issues: List[Dict],
        source: str,
        elapsed: float,
        files_count: int,
        chunks_count: int,
    ):
        counts = count_by_severity(issues)
        groups = group_by_file(issues)

        if not issues:
            file_sections = self._no_issues_section()
        else:
            file_sections = "".join(
                self._build_file_section(fp, fi) for fp, fi in groups.items()
            )

        html_content = _render_template(
            repo_source=escape_html(source),
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            elapsed=round(elapsed, 2),
            total_issues=len(issues),
            critical_count=counts["critical"],
            error_count=counts["error"],
            warning_count=counts["warning"],
            info_count=counts["info"],
            total_files=files_count,
            total_chunks=chunks_count,
            file_sections=file_sections,
        )

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_content)

    # ------------------------------------------------------------------ #
    #  片段构建（私有）                                                     #
    # ------------------------------------------------------------------ #

    def _build_file_section(self, file_path: str, issues: List[Dict]) -> str:
        """构建单个文件的折叠区块（file-issues 是 file-header 的兄弟节点）"""
        file_counts = count_by_severity(issues)

        badges = "".join(
            f'<span class="badge {sev}">{file_counts[sev]} {severity_label(sev)}</span>'
            for sev in ("critical", "error", "warning", "info")
            if file_counts[sev] > 0
        )

        issue_cards = "".join(self._build_issue_card(issue) for issue in issues)

        # 有 critical/error 的文件默认展开
        open_class = "open" if file_counts["critical"] > 0 or file_counts["error"] > 0 else ""

        return (
            f'<div class="file-section {open_class}">'
            f'  <div class="file-header">'
            f'    <span class="file-name">'
            f'      <span class="toggle-icon">&#9654;</span>'
            f'      {escape_html(file_path)}'
            f'    </span>'
            f'    <div class="badge-group">{badges}</div>'
            f'  </div>'
            f'  <div class="file-issues">'
            f'    <div class="issue-list">{issue_cards}</div>'
            f'  </div>'
            f'</div>'
        )

    @staticmethod
    def _build_issue_card(issue: Dict) -> str:
        """构建单个问题卡片，使用 .get() 兜底，避免 KeyError"""
        sev = issue.get("severity", "info")
        title = escape_html(issue.get("title", "（无标题）"))
        description = escape_html(issue.get("description", ""))
        category = escape_html(issue.get("category", ""))
        line_start = issue.get("line_start", "-")
        line_end = issue.get("line_end", "-")
        suggestion = issue.get("suggestion", "")

        suggestion_html = (
            f'<div class="issue-suggestion">{escape_html(suggestion)}</div>'
            if suggestion
            else ""
        )
        category_html = (
            f'<span class="badge category">{category}</span>'
            if category
            else ""
        )

        return (
            f'<div class="issue-card {sev}">'
            f'  <div class="issue-title">'
            f'    <span class="severity-dot {sev}"></span>'
            f'    <h4>{title}</h4>'
            f'    <span class="badge {sev}">{severity_label(sev)}</span>'
            f'    {category_html}'
            f'  </div>'
            f'  <div class="issue-meta">&#128205; 行 {line_start} – {line_end}</div>'
            f'  <div class="issue-description">{description}</div>'
            f'  {suggestion_html}'
            f'</div>'
        )

    @staticmethod
    def _no_issues_section() -> str:
        return (
            '<div class="no-issues">'
            '  <div class="emoji">&#127881;</div>'
            '  <h2>代码质量优秀！</h2>'
            '  <p>未发现明显问题，继续保持！</p>'
            '</div>'
        )