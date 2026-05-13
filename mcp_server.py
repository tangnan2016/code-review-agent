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
import json
import os
import sys
from pathlib import Path

# 把项目根目录加入 sys.path，使 src.* 可以正常导入
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response

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

# HTML 报告通过 HTTP 提供访问时的 URL 前缀路径
_REPORT_URL_PREFIX = "/reports"

# SSE 模式下报告可访问的 base URL（由 main() 启动时写入）
_SERVER_BASE_URL: str = ""


# ------------------------------------------------------------------ #
#  静态报告路由（SSE 模式下通过 HTTP 直接访问 HTML 报告）             #
# ------------------------------------------------------------------ #

@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> Response:
    """Lightweight liveness probe — does NOT open an SSE stream."""
    return JSONResponse({"status": "ok"})


@mcp.custom_route(_REPORT_URL_PREFIX + "/{filename:path}", methods=["GET"])
async def serve_report(request: Request) -> Response:
    """Serve generated HTML/JSON reports over HTTP."""
    filename = request.path_params["filename"]

    # 安全：阻止路径穿越，确保只能访问 output 目录内的文件
    output_root = Path(_OUTPUT_DIR).resolve()
    file_path = (output_root / filename).resolve()
    if not str(file_path).startswith(str(output_root)):
        return Response("Forbidden", status_code=403)

    if not file_path.exists() or not file_path.is_file():
        return Response("Not Found", status_code=404)

    return FileResponse(str(file_path))

# 支持的 provider 配置表
# 内置 provider 元数据表（仅用于感知环境变量名和内置默认值，不代表"已配置"）
# api_key_env:  对应的 API Key 环境变量名（None = 本地服务无需 Key）
# model_env:    对应的模型名称环境变量名
# default_model: 无任何环境变量时的兜底模型名
_PROVIDERS: dict[str, dict] = {
    "deepseek": {"api_key_env": "DEEPSEEK_API_KEY",  "model_env": "DEEPSEEK_MODEL",  "default_model": "deepseek-chat"},
    "openai":   {"api_key_env": "OPENAI_API_KEY",    "model_env": "OPENAI_MODEL",    "default_model": "gpt-4o"},
    "claude":   {"api_key_env": "ANTHROPIC_API_KEY", "model_env": "CLAUDE_MODEL",    "default_model": "claude-3-5-sonnet-20241022"},
    "ollama":   {"api_key_env": None,                "model_env": "OLLAMA_MODEL",    "default_model": "llama3"},
}


def _detect_configured_providers() -> dict[str, dict]:
    """
    扫描当前环境变量，返回实际已配置的 provider 及其 model。

    检测规则：
      - 内置 provider（deepseek/openai/claude）：对应 API Key 环境变量已设置 → 已配置
      - ollama：无需 Key，始终视为已配置（本地服务）
      - 通用自定义 provider（LM_PROVIDER + LM_API_KEY）：同时设置 → 已配置

    Returns:
        {provider_name: {"model": str, "source": str}}
    """
    result: dict[str, dict] = {}

    # 检测内置 provider
    for name, meta in _PROVIDERS.items():
        api_key_env = meta["api_key_env"]
        model_env   = meta["model_env"]
        default_model = meta["default_model"]

        if api_key_env is None or os.environ.get(api_key_env):
            model = os.environ.get(model_env, "") or default_model
            result[name] = {"model": model, "source": "built-in"}

    # 检测通用自定义 provider（LM_PROVIDER + LM_API_KEY）
    lm_provider  = os.environ.get("LM_PROVIDER", "").strip()
    lm_api_key   = os.environ.get("LM_API_KEY", "").strip()
    lm_model     = os.environ.get("LLM_MODEL", "").strip()
    lm_base_url  = os.environ.get("LM_BASE_URL", "").strip()

    if lm_provider and lm_api_key:
        # 自定义 provider 的 model：LLM_MODEL > 已有内置配置的 model > 空
        model = lm_model or result.get(lm_provider, {}).get("model", "（请设置 LLM_MODEL）")
        entry: dict = {"model": model, "source": "generic env vars (LM_*)"}
        if lm_base_url:
            entry["base_url"] = lm_base_url
        result[lm_provider] = entry   # 覆盖同名内置 provider

    return result


def _resolve_provider(provider: str) -> str:
    """
    解析最终使用的 provider。优先级：
      1. 调用方显式传入的 provider 参数
      2. LM_PROVIDER 环境变量
      3. 已配置的第一个非 ollama provider
      4. ollama（如已配置）
      5. 兜底返回空字符串（由 _check_provider 报错）
    """
    if provider:
        return provider
    lm_provider = os.environ.get("LM_PROVIDER", "").strip()
    if lm_provider:
        return lm_provider
    configured = _detect_configured_providers()
    for p in configured:
        if p != "ollama":
            return p
    return next(iter(configured), "")


# ------------------------------------------------------------------ #
#  工具定义                                                            #
# ------------------------------------------------------------------ #

@mcp.tool()
async def review_local_code(
    path: str,
    provider: str = "",
    model: str = "",
    output_format: str = "html",
) -> str:
    """
    对本地代码目录进行 AI 代码审查。

    Args:
        path:          要审查的本地目录绝对路径（如 /Users/xxx/my-project）
        provider:      LLM 提供者。留空时自动使用已配置的 provider（优先 LM_PROVIDER 环境变量）。
                       内置选项：deepseek / openai / claude / ollama
                       自定义：任意名称（需配合 LM_API_KEY + LM_BASE_URL + LLM_MODEL 使用）
        model:         模型名称；留空时使用该 provider 的已配置默认值
        output_format: 报告格式，html（生成可视化报告）或 json（返回结构化问题列表）

    Returns:
        JSON 格式的审查摘要，包含问题列表和报告文件路径
    """
    effective_provider = _resolve_provider(provider)
    err = _check_provider(effective_provider, requested_model=model or None)
    if err:
        return err
    return await _do_review(path, effective_provider, model or None, output_format)


@mcp.tool()
async def review_git_repo(
    url: str,
    branch: str = "main",
    provider: str = "",
    model: str = "",
    output_format: str = "html",
) -> str:
    """
    对远程 Git 仓库进行 AI 代码审查（自动 clone 后审查）。

    Args:
        url:           Git 仓库地址（https:// 或 git@ 格式）
        branch:        分支名称（默认 main）
        provider:      LLM 提供者。留空时自动使用已配置的 provider（优先 LM_PROVIDER 环境变量）。
                       内置选项：deepseek / openai / claude / ollama
                       自定义：任意名称（需配合 LM_API_KEY + LM_BASE_URL + LLM_MODEL 使用）
        model:         模型名称；留空时使用该 provider 的已配置默认值
        output_format: 报告格式，html（生成可视化报告）或 json（返回结构化问题列表）

    Returns:
        JSON 格式的审查摘要
    """
    effective_provider = _resolve_provider(provider)
    err = _check_provider(effective_provider, requested_model=model or None)
    if err:
        return err
    return await _do_review(url, effective_provider, model or None, output_format, branch=branch)


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
        entry: dict = {
            "path": str(r),
            "name": r.name,
            "format": r.suffix.lstrip("."),
            "size_kb": round(stat.st_size / 1024, 1),
            "created_at": stat.st_mtime,
        }
        if _SERVER_BASE_URL and r.suffix == ".html":
            entry["report_url"] = f"{_SERVER_BASE_URL}{_REPORT_URL_PREFIX}/{r.name}"
        result.append(entry)

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
    列出当前实际已配置的 LLM provider 及其状态。

    Returns:
        JSON，包含：已配置的 provider 列表、每个 provider 的 model、配置来源；
        以及未配置但支持的内置 provider 列表（说明需要设置哪些环境变量）
    """
    configured = _detect_configured_providers()

    configured_list = []
    for name, info in configured.items():
        entry = {
            "provider":  name,
            "model":     info["model"],
            "source":    info["source"],
            "status":    "configured",
        }
        if "base_url" in info:
            entry["base_url"] = info["base_url"]
        configured_list.append(entry)

    # 列出未配置的内置 provider，告知需要哪些环境变量
    not_configured = []
    for name, meta in _PROVIDERS.items():
        if name not in configured:
            api_key_env = meta["api_key_env"]
            not_configured.append({
                "provider":       name,
                "status":         "not configured",
                "requires_env":   api_key_env or "（无需 Key，本地服务）",
                "optional_model_env": meta["model_env"],
                "default_model":  meta["default_model"],
            })

    return json.dumps(
        {
            "configured": configured_list,
            "not_configured": not_configured,
            "tip": "留空 provider 参数时，自动使用第一个已配置的 provider",
        },
        ensure_ascii=False,
        indent=2,
    )


# ------------------------------------------------------------------ #
#  内部实现                                                            #
# ------------------------------------------------------------------ #

def _check_provider(provider: str, requested_model: str | None = None) -> str | None:
    """
    校验 provider 和 model 是否在当前配置中。
    - provider 不在已配置列表 → 报错，列出已配置的 provider 和 model
    - requested_model 非空且与配置 model 不符 → 警告（允许继续，model 由调用方控制）
    """
    if not provider:
        return json.dumps(
            {"error": "未能解析 provider，请检查 LM_PROVIDER 环境变量或显式传入 provider 参数"},
            ensure_ascii=False,
        )

    configured = _detect_configured_providers()

    if not configured:
        return json.dumps(
            {
                "error": "当前没有配置任何 LLM provider",
                "how_to_configure": {
                    "built-in": "设置 DEEPSEEK_API_KEY / OPENAI_API_KEY / ANTHROPIC_API_KEY 等",
                    "custom":   "同时设置 LM_PROVIDER=<name> + LM_API_KEY=<key> + LM_BASE_URL=<url> + LLM_MODEL=<model>",
                },
            },
            ensure_ascii=False,
        )

    if provider not in configured:
        available = [
            {"provider": p, "model": info["model"], "source": info["source"]}
            for p, info in configured.items()
        ]
        return json.dumps(
            {
                "error": f"provider '{provider}' 未配置或不支持",
                "available_providers": available,
                "tip": f"如需使用 '{provider}'，请在 .env 中设置对应 API Key 或设置 LM_PROVIDER={provider} + LM_API_KEY=<key>",
            },
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

    # 若调用方未指定 model，从已配置 provider 中读取
    if not model:
        configured = _detect_configured_providers()
        model = configured.get(provider, {}).get("model") or None

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

    # JSON 报告直接返回内容；HTML 报告返回路径 + 可访问 URL
    if output_format == "json":
        try:
            content = Path(report_path).read_text(encoding="utf-8")
            data = json.loads(content)
            return json.dumps(data, ensure_ascii=False, indent=2)
        except Exception:
            pass

    report_filename = Path(report_path).name
    result: dict = {"report_path": report_path}

    if _SERVER_BASE_URL:
        # SSE 服务模式：拼接出可直接在浏览器打开的 URL
        report_url = f"{_SERVER_BASE_URL.rstrip('/')}{_REPORT_URL_PREFIX}/{report_filename}"
        result["report_url"] = report_url
        result["message"] = f"报告已生成，点击链接在浏览器中查看: {report_url}"
    else:
        result["message"] = f"报告已生成，请打开文件查看: {report_path}"

    return json.dumps(result, ensure_ascii=False)


# ------------------------------------------------------------------ #
#  入口                                                                #
# ------------------------------------------------------------------ #

def main():
    global _SERVER_BASE_URL

    parser = argparse.ArgumentParser(description="Code Review Agent MCP Server")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio",
                        help="传输方式：stdio（默认，本地集成）或 sse（HTTP 服务）")
    parser.add_argument("--host", default="0.0.0.0", help="SSE 模式监听地址")
    parser.add_argument("--port", type=int, default=8080, help="SSE 模式监听端口")
    parser.add_argument("--base-url", default="", dest="base_url",
                        help="对外可访问的 base URL（用于生成报告链接，如 http://127.0.0.1:8080）"
                             "。缺省时自动根据 host/port 推断。")
    args = parser.parse_args()

    if args.transport == "sse":
        host = mcp.settings.host
        port = mcp.settings.port

        # 推断对外可访问的 base URL
        # 优先级：--base-url CLI 参数 > REVIEW_BASE_URL 环境变量 > 自动推断
        if args.base_url:
            _SERVER_BASE_URL = args.base_url.rstrip("/")
        elif os.environ.get("REVIEW_BASE_URL"):
            _SERVER_BASE_URL = os.environ["REVIEW_BASE_URL"].rstrip("/")
        else:
            display_host = "127.0.0.1" if host in ("0.0.0.0", "::") else host
            _SERVER_BASE_URL = f"http://{display_host}:{port}"

        # 确保报告输出目录存在
        output_dir = Path(_OUTPUT_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)

        print(
            f"Starting MCP SSE server on {host}:{port}\n"
            f"  MCP endpoint  : {_SERVER_BASE_URL}/sse\n"
            f"  Reports served: {_SERVER_BASE_URL}{_REPORT_URL_PREFIX}/<filename>",
            flush=True,
        )
        mcp.run(transport="sse")
    else:
        mcp.run()  # stdio，用于 Claude Desktop 等本地客户端



if __name__ == "__main__":
    main()