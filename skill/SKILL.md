# Code Review Agent SKILL

## 功能描述

对本地代码目录或 Git 仓库进行 **AI 多维度代码审查**，分析安全性、逻辑正确性、性能、代码规范、最佳实践、可维护性六个维度，生成 HTML 可视化报告或 JSON 结构化结果。

## 触发场景

- "帮我做代码审查 /path/to/project"
- "review my code at /path/to/project"
- "检查这个项目的代码质量"
- "审查这个仓库：https://github.com/xxx/yyy"
- "代码哪里有问题"、"检查代码安全性"、"生成代码审查报告"

## 调用方式

本 Skill 支持两种调用路径，按实际部署情况选择：

### 路径一：本地 CLI（直接运行，无需部署）

```bash
# 基础用法
cd /path/to/code-review-agent
python run.py <源码路径或 Git URL>

# 完整参数
python run.py <source> \
  --provider deepseek \   # LLM 提供者：deepseek / openai / claude
  --format html           # 报告格式：html / json
```

### 路径二：MCP HTTP 服务（已通过 Docker 部署后）

服务地址：`http://<部署机器IP>:8080`

可用 MCP 工具：

| 工具名 | 说明 | 必填参数 |
|--------|------|---------|
| `review_local_code` | 审查容器内可访问的本地路径 | `path` |
| `review_git_repo` | Clone 并审查 Git 仓库 | `url` |
| `list_reports` | 列出已生成的报告 | 无 |
| `get_report_content` | 读取 JSON 报告内容 | `report_path` |

## 执行步骤

1. 从用户消息中识别**代码来源**（本地路径 or Git URL）
2. 确认 **LLM provider**（默认 deepseek）和**报告格式**（默认 html）
3. 执行审查（CLI 或 MCP 工具）
4. 解析结果，按严重程度（critical / error / warning / info）分级呈现问题摘要
5. 提供报告路径，引导用户查看详细 HTML 报告

## 输出示例

```
审查完成，共发现 12 个问题：

🔴 严重(1)：src/utils/config.py:23 - 硬编码 API 密钥，存在泄露风险
🟠 错误(2)：src/api/handler.py:45 - 未处理 None 返回值可能导致空指针
🟡 警告(7)：命名不规范、魔法数字、代码重复等
🔵 建议(2)：可使用上下文管理器优化资源释放

📄 完整报告：output/review_20260512_103000.html
```

## 注意事项

- 大型项目（>200 文件）建议在 `config.yaml` 中设置 `concurrency: 2`
- 首次使用需在 `config.yaml` 配置 LLM provider 和 API Key（或通过 `.env` 注入）