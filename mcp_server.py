"""
Code Review Agent - MCP Server

将代码审查能力暴露为 MCP 工具，供 Claude Desktop / Cursor / Claude Code 等客户端调用。

支持的 LLM Provider 及对应环境变量：
  Provider   API Key 环境变量         模型环境变量（可选）         默认模型
  deepseek   DEEPSEEK_API_KEY        DEEPSEEK_MODEL              deepseek-coder
  openai     OPENAI_API_KEY          OPENAI_MODEL                gpt-4o
  claude     ANTHROPIC_API_KEY       CLAUDE_MODEL                claude-3-5-sonnet-20241022
  ollama     （无需 Key，本地服务）   OLLAMA_MODEL                codellama

启动方式：
  stdio 模式（Claude Desktop / claude_desktop_config.json）：
    python mcp_server.py

  HTTP/SSE 模式（网络部署）：
    python mcp_server.py --transport sse --host 0.0.0.0 --port 8080

集成到 Claude Desktop（选择一种 provider 注入对应 Key 和 Model 即可）：
  ~/Library/Application Support/Claude/claude_desktop_config.json
  {
    "mcpServers": {
      "code-review": {
        "command": "python",
        "args": ["/absolute/path/to/code-review-agent/mcp_server.py"],
        "env": {
          "DEEPSEEK_API_KEY": "sk-xxx",
          "DEEPSEEK_MODEL": "deepseek-coder"
          // 或 OpenAI:   "OPENAI_API_KEY": "sk-xxx", "OPENAI_MODEL": "gpt-4o"
          // 或 Claude:   "ANTHROPIC_API_KEY": "sk-ant-xxx", "CLAUDE_MODEL": "claude-3-5-sonnet-20241022"
          // 或 Ollama:   "OLLAMA_MODEL": "codellama"（无需 Key）
        }
      }
    }
  }
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# 把项目根目录加入 sys.path，使 src.* 可以正常导入
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# FastMCP 的 Settings 在实例化时就读取 FASTMCP_HOST / FASTMCP_PORT 环境变量。
# 必须在 FastMCP() 之前把这两个值写入 os.environ，否则 main() 里再设就晚了。
# 优先级：--host/--port 命令行参数 > FASTMCP_HOST/FASTMCP_PORT 已有环境变量 > 默认值
# ---------------------------------------------------------------------------
def _pre_parse_server_settings() -> argparse.Namespace:
    """预解析 --transport / --host / --port，返回解析结果供模块级 FastMCP() 使用。"""
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--transport", default="stdio")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8080)
    args, _ = p.parse_known_args()
    return args


_server_args = _pre_parse_server_settings()   # 必须在 FastMCP() 前执行

# FastMCP 的 host/port 通过构造函数传入（在 __init__ 时就固定到 self.settings 中）。
# SSE 模式：绑定到 0.0.0.0:8080；stdio 模式：host/port 无实际意义，用默认值即可。
if _server_args.transport == "sse":
    mcp = FastMCP("code-review-agent", host=_server_args.host, port=_server_args.port)
else:
    mcp = FastMCP("code-review-agent")

_CONFIG_PATH = str(PROJECT_ROOT / "config" / "config.yaml")
_OUTPUT_DIR = str(PROJECT_ROOT / "output")

# 支持的 provider 配置表
# api_key_env: 所需 API Key 环境变量（None = 本地服务，无需 Key）
# model_env:   模型名称环境变量（优先级：调用参数 > 环境变量 > config.yaml > 内置默认值）
# default_model: 内置默认模型（当以上三级均未指定时使用）
_PROVIDERS: dict[str, dict] = {
    "deepseek": {"api_key_env": "DEEPSEEK_API_KEY",  "model_env": "DEEPSEEK_MODEL",  "default_model": "deepseek-coder"},
    "openai":   {"api_key_env": "OPENAI_API_KEY",    "model_env": "OPENAI_MODEL",    "default_model": "gpt-4o"},
    "claude":   {"api_key_env": "ANTHROPIC_API_KEY", "model_env": "CLAUDE_MODEL",    "default_model": "claude-3-5-sonnet-20241022"},
    "ollama":   {"api_key_env": None,                "model_env": "OLLAMA_MODEL",    "default_model": "codellama"},
}


# ------------------------------------------------------------------ #
#  工具定义                                                            #
# ------------------------------------------------------------------ #

@mcp.tool()
async def review_local_code(
    path: str,
    provider: str = "deepseek",
    model: str = "",
    output_format: str = "json",
) -> str:
    """
    对本地代码目录进行 AI 代码审查。

    Args:
        path:          要审查的本地目录绝对路径（如 /Users/xxx/my-project）
        provider:      LLM 提供者，可选 deepseek / openai / claude / ollama（默认 deepseek）
                       deepseek → 需环境变量 DEEPSEEK_API_KEY
                       openai   → 需环境变量 OPENAI_API_KEY
                       claude   → 需环境变量 ANTHROPIC_API_KEY
                       ollama   → 本地服务，无需 Key
        model:         模型名称；优先级：本参数 > 环境变量（如 DEEPSEEK_MODEL）> config.yaml > 内置默认值
        output_format: 报告格式，json（返回结构化问题列表）或 html（生成可视化报告）

    Returns:
        JSON 格式的审查摘要，包含问题列表和报告文件路径
    """
    err = _check_provider(provider)
    if err:
        return err
    return await _do_review(path, provider, model or None, output_format)


@mcp.tool()
async def review_git_repo(
    url: str,
    branch: str = "main",
    provider: str = "deepseek",
    model: str = "",
    output_format: str = "json",
) -> str:
    """
    对远程 Git 仓库进行 AI 代码审查（自动 clone 后审查）。

    Args:
        url:           Git 仓库地址（https:// 或 git@ 格式）
        branch:        分支名称（默认 main）
        provider:      LLM 提供者，可选 deepseek / openai / claude / ollama
                       deepseek → 需环境变量 DEEPSEEK_API_KEY
                       openai   → 需环境变量 OPENAI_API_KEY
                       claude   → 需环境变量 ANTHROPIC_API_KEY
                       ollama   → 本地服务，无需 Key
        model:         模型名称；优先级：本参数 > 环境变量（如 DEEPSEEK_MODEL）> config.yaml > 内置默认值
        output_format: 报告格式，json 或 html

    Returns:
        JSON 格式的审查摘要
    """
    err = _check_provider(provider)
    if err:
        return err
    return await _do_review(url, provider, model or None, output_format, branch=branch)


@mcp.tool()
def list_reports(limit: int = 10) -> str:
    """
    列出已生成的代码审查报告。

    Args:
        limit: 返回最近 N 份报告（默认 10）

    Returns:
        JSON 列表，包含报告路径、生成时间、文件大小
    """
    output_dir = Path(_OUTPUT_DIR)
    if not output_dir.exists():
        return json.dumps({"reports": [], "message": "暂无报告"}, ensure_ascii=False)

    reports = sorted(output_dir.glob("review_*.html"), key=lambda p: p.stat().st_mtime, reverse=True)
    reports += sorted(output_dir.glob("review_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    reports = sorted(reports, key=lambda p: p.stat().st_mtime, reverse=True)[:limit]

    result = []
    for r in reports:
        stat = r.stat()
        result.append({
            "path": str(r),
            "name": r.name,
            "format": r.suffix.lstrip("."),
            "size_kb": round(stat.st_size / 1024, 1),
            "created_at": stat.st_mtime,
        })

    return json.dumps({"reports": result}, ensure_ascii=False, indent=2)


@mcp.tool()
def get_report_content(report_path: str) -> str:
    """
    读取指定审查报告的内容（JSON 格式报告）。

    Args:
        report_path: 报告文件的绝对路径（仅支持 .json 格式）

    Returns:
        报告的 JSON 内容字符串
    """
    path = Path(report_path)
    if not path.exists():
        return json.dumps({"error": f"文件不存在: {report_path}"}, ensure_ascii=False)
    if path.suffix != ".json":
        return json.dumps({"error": "仅支持读取 .json 格式报告"}, ensure_ascii=False)

    return path.read_text(encoding="utf-8")


@mcp.tool()
def list_providers() -> str:
    """
    列出所有支持的 LLM Provider 及配置方式。

    Returns:
        JSON 列表，包含 provider 名称、API Key 环境变量、模型环境变量、内置默认模型及当前配置状态
    """
    result = []
    for name, cfg in _PROVIDERS.items():
        api_key_env = cfg["api_key_env"]
        model_env   = cfg["model_env"]
        result.append({
            "provider":      name,
            "api_key_env":   api_key_env or "（无需配置，本地服务）",
            "api_key_set":   True if api_key_env is None else bool(os.environ.get(api_key_env)),
            "model_env":     model_env,
            "model_set":     os.environ.get(model_env, ""),
            "default_model": cfg["default_model"],
        })
    return json.dumps({"providers": result}, ensure_ascii=False, indent=2)


# ------------------------------------------------------------------ #
#  内部实现                                                            #
# ------------------------------------------------------------------ #

def _check_provider(provider: str) -> str | None:
    """校验 provider 是否合法，以及对应 Key 是否已注入。返回错误 JSON 或 None。"""
    if provider not in _PROVIDERS:
        return json.dumps(
            {"error": f"不支持的 provider: {provider!r}，可选值: {list(_PROVIDERS)}"},
            ensure_ascii=False,
        )
    api_key_env = _PROVIDERS[provider]["api_key_env"]
    if api_key_env and not os.environ.get(api_key_env):
        return json.dumps(
            {"error": f"使用 {provider} 需要设置环境变量 {api_key_env}"},
            ensure_ascii=False,
        )
    return None


async def _do_review(
    source: str,
    provider: str,
    model: str | None,
    output_format: str,
    branch: str | None = None,
) -> str:
    """调用主流程并返回结构化结果。model 解析优先级：调用参数 > 环境变量 > config.yaml > 内置默认值"""
    from src.main import run_review

    # 若调用方未指定 model，尝试从环境变量读取
    if not model:
        cfg = _PROVIDERS.get(provider, {})
        model = os.environ.get(cfg.get("model_env", ""), "") or cfg.get("default_model") or None

    try:
        report_path = await run_review(
            source=source,
            provider=provider,
            model=model,
            output_dir=_OUTPUT_DIR,
            output_format=output_format,
            config_path=_CONFIG_PATH,
        )
    except Exception as e:
        return json.dumps(
            {"error": f"审查失败: {type(e).__name__}: {e}"},
            ensure_ascii=False,
        )

    if not report_path:
        return json.dumps({"error": "未找到可审查的代码文件"}, ensure_ascii=False)

    # JSON 报告直接返回内容；HTML 报告返回路径
    if output_format == "json":
        try:
            content = Path(report_path).read_text(encoding="utf-8")
            data = json.loads(content)
            return json.dumps(data, ensure_ascii=False, indent=2)
        except Exception:
            pass

    return json.dumps(
        {"report_path": report_path, "message": f"报告已生成，请打开查看: {report_path}"},
        ensure_ascii=False,
    )


# ------------------------------------------------------------------ #
#  入口                                                                #
# ------------------------------------------------------------------ #

def main():
    parser = argparse.ArgumentParser(description="Code Review Agent MCP Server")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio",
                        help="传输方式：stdio（默认，本地集成）或 sse（HTTP 服务）")
    parser.add_argument("--host", default="0.0.0.0", help="SSE 模式监听地址")
    parser.add_argument("--port", type=int, default=8080, help="SSE 模式监听端口")
    args = parser.parse_args()

    if args.transport == "sse":
        # host/port 已在模块级 FastMCP() 构造时通过 _server_args 传入，
        # 直接读取 mcp.settings 确认实际绑定值。
        print(f"Starting MCP SSE server on {mcp.settings.host}:{mcp.settings.port}", flush=True)
        mcp.run(transport="sse")
    else:
        mcp.run()  # stdio，用于 Claude Desktop 等本地客户端



if __name__ == "__main__":
    main()