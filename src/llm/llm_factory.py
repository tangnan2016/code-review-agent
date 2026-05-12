"""LLM 客户端工厂"""
from src.llm.base_client import BaseLLMClient
from src.llm.openai_client import OpenAIClient
from src.llm.claude_client import ClaudeClient


def create_llm_client(llm_config: dict) -> BaseLLMClient:
    """
    根据配置创建 LLM 客户端

    Args:
        llm_config: llm 配置段

    Returns:
        LLM 客户端实例
    """
    provider = llm_config.get("default_provider", "deepseek")
    providers = llm_config.get("providers", {})

    if provider not in providers:
        available = list(providers.keys())
        raise ValueError(
            f"未知的 LLM 提供者: '{provider}', 可用: {available}"
        )

    provider_config = providers[provider].copy()
    provider_config["_provider_name"] = provider

    # 验证 API Key
    api_key = provider_config.get("api_key", "")
    if not api_key and provider != "ollama":
        raise ValueError(
            f"提供者 '{provider}' 的 api_key 未配置。"
            f"请设置环境变量或在 config.yaml 中配置。"
        )

    # Claude 使用专用客户端
    if provider == "claude":
        return ClaudeClient(provider_config)

    # 其他都使用 OpenAI 兼容客户端
    return OpenAIClient(provider_config)