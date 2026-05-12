"""配置加载器 config_loader.py"""
import os
from pathlib import Path
from typing import Any, Dict

import yaml
from src.utils.logger import logger


class ConfigLoader:
    """加载和合并配置"""

    @staticmethod
    def load(config_path: str = "config.yml") -> Dict[str, Any]:
        """加载配置文件，并用环境变量覆盖敏感字段

        Args:
            config_path: 配置文件路径，默认 config.yml

        Returns:
            合并后的配置字典
        """
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")

        with open(path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        config = ConfigLoader._apply_env_overrides(config)
        ConfigLoader._validate(config)
        return config

    @staticmethod
    def _apply_env_overrides(config: Dict[str, Any]) -> Dict[str, Any]:
        """用环境变量覆盖配置

        新 config.yml 结构：llm.providers.<provider>.api_key
        支持三类覆盖：
          1. 各 provider 专属 Key（OPENAI_API_KEY / ANTHROPIC_API_KEY / DEEPSEEK_API_KEY）
          2. 通用字段（LM_API_KEY / LM_BASE_URL / LLM_MODEL）→ 作用于当前激活 provider
          3. 切换 provider（LM_PROVIDER）→ 覆盖 llm.default_provider
        """
        llm = config.setdefault("llm", {})
        providers = llm.setdefault("providers", {})

        # 1. 各 provider 专属 api_key 环境变量
        provider_key_envs = {
            "openai": "OPENAI_API_KEY",
            "claude": "ANTHROPIC_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
        }
        for provider_name, env_var in provider_key_envs.items():
            value = os.environ.get(env_var)
            if value:
                providers.setdefault(provider_name, {})["api_key"] = value
                logger.debug(
                    f"环境变量 {env_var} 已覆盖 llm.providers.{provider_name}.api_key"
                )

        # 2. 通用字段：覆盖当前激活 provider 的对应键
        active_provider = llm.get("default_provider", "")
        if active_provider and active_provider in providers:
            provider_cfg = providers[active_provider]
            generic_mappings = {
                "LM_API_KEY": "api_key",
                "LM_BASE_URL": "base_url",
                "LLM_MODEL": "model",
            }
            for env_var, key in generic_mappings.items():
                value = os.environ.get(env_var)
                if value:
                    provider_cfg[key] = value
                    logger.debug(
                        f"环境变量 {env_var} 已覆盖 llm.providers.{active_provider}.{key}"
                    )

        # 3. 切换 default_provider
        lm_provider = os.environ.get("LM_PROVIDER")
        if lm_provider:
            llm["default_provider"] = lm_provider
            logger.debug(f"环境变量 LM_PROVIDER 已覆盖 llm.default_provider → {lm_provider}")

        return config

    @staticmethod
    def _validate(config: Dict[str, Any]) -> None:
        """验证配置完整性"""
        llm_config = config.get("llm", {})

        # 验证 default_provider 存在
        provider = llm_config.get("default_provider", "")
        if not provider:
            raise ValueError("llm.default_provider 未配置")

        # 验证 provider 在 providers 列表中
        providers = llm_config.get("providers", {})
        if provider not in providers:
            available = list(providers.keys())
            raise ValueError(
                f"llm.default_provider '{provider}' 不在 providers 中，"
                f"可用: {available}"
            )

        # 验证 api_key（ollama 本地部署跳过）
        if provider != "ollama":
            api_key = providers[provider].get("api_key", "")
            if not api_key:
                env_hints = {
                    "openai": "OPENAI_API_KEY",
                    "deepseek": "DEEPSEEK_API_KEY",
                    "claude": "ANTHROPIC_API_KEY",
                }
                env_hint = env_hints.get(provider, "LM_API_KEY")
                raise ValueError(
                    f"提供者 '{provider}' 的 api_key 未配置。\n"
                    f"请在 config.yml 的 llm.providers.{provider}.api_key 中填写，"
                    f"或设置环境变量 {env_hint}。"
                )