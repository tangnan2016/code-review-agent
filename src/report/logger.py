"""控制台报告输出"""
from typing import List, Dict

from src.report.helpers import (
    count_by_severity,
    group_by_file,
    severity_emoji,
    severity_label,
)


def print_console_report(issues: List[Dict]):
    """在控制台打印审查结果摘要"""
    if not issues:
        print("\n" + "=" * 60)
        print("🎉 审查完成：未发现问题！代码质量优秀！")
        print("=" * 60)
        return

    counts = count_by_severity(issues)
    groups = group_by_file(issues)

    print("\n" + "=" * 60)
    print("📋 代码审查结果摘要")
    print("=" * 60)

    # 统计
    print(f"\n📊 问题统计:")
    print(f"   🔴 严重: {counts['critical']}")
    print(f"   🟠 错误: {counts['error']}")
    print(f"   🟡 警告: {counts['warning']}")
    print(f"   🔵 建议: {counts['info']}")
    print(f"   📝 总计: {sum(counts.values())}")

    # 按文件展示
    print(f"\n📂 涉及文件: {len(groups)} 个")
    print("-" * 60)

    for file_path, file_issues in groups.items():
        print(f"\n📄 {file_path} ({len(file_issues)} 个问题)")
        for issue in file_issues:
            emoji = severity_emoji(issue["severity"])
            label = severity_label(issue["severity"])
            line_info = f"L{issue['line_start']}-{issue['line_end']}"
            print(f"   {emoji} [{label}] {line_info}: {issue['title']}")
            if issue.get("description"):
                desc = issue["description"][:80]
                print(f"      └─ {desc}")

    print("\n" + "=" * 60)