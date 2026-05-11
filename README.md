# 🔍 AI Code Review Agent

基于大语言模型的智能代码走查工具，支持多种 LLM 提供商，自动扫描代码仓库并生成专业的审查报告。

## ✨ 功能特性

- 🤖 **多 LLM 支持**: OpenAI / DeepSeek / Claude / Ollama (本地)
- 📂 **多种输入**: 本地目录、Git 仓库 URL
- 🔍 **智能分析**: 安全漏洞、逻辑错误、性能问题、代码规范
- 📊 **多格式报告**: HTML (可视化) / Markdown / JSON
- ⚡ **异步并发**: 高效并行审查多个代码片段
- 🎯 **智能分割**: 按函数/类边界分割代码，保留上下文
- 🔧 **灵活配置**: YAML 配置 + 环境变量 + 命令行参数

## 🚀 快速开始

### 安装

```bash
# 克隆项目
git clone https://github.com/yourname/code-review-agent.git
cd code-review-agent

# 安装依赖
pip install -e .

# 或使用开发模式
pip install -e ".[dev]"

# 配置 API Key
# 方式1: 环境变量 (推荐)
export DEEPSEEK_API_KEY="your-api-key"
export OPENAI_API_KEY="your-api-key"
export ANTHROPIC_API_KEY="your-api-key"

# 方式2: 编辑 config.yaml
cp config.yaml config.local.yaml
# 编辑 config.local.yaml 填入 api_key


# 使用
# 审查本地项目
code-review ./my-project

# 审查 Git 仓库
code-review https://github.com/user/repo.git

# 指定 LLM 和输出格式
code-review ./src --provider deepseek --format markdown

# 使用本地 Ollama
code-review ./src --provider ollama

# 指定配置文件
code-review ./src --config ./config.local.yaml

# 调整并发数
code-review ./src --concurrency 10