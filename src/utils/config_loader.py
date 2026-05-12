"""配置加载器 config_loader.py"""

import os
import re
from pathlib import Path
from typing import Any, Dict

import yaml

from src.utils.logger import logger


# ---------------------------------------------------------------------------
# ${VAR} / ${VAR:-default} 展开
# ---------------------------------------------------------------------------

def _expand_env_vars(content: str) -> str:
    """展开 YAML 文本中的 ${VAR_NAME} 和 ${VAR_NAME:-default} 占位符。

    - ${VAR_NAME}          → os.environ["VAR_NAME"]，未设置时替换为空字符串
    - ${VAR_NAME:-default} → os.environ["VAR_NAME"]，未设置时使用 default
    """
    def _replace(m: re.Match) -> str:
        expr = m.group(1)
        if ":-" in expr:
            var_name, default = expr.split(":-", 1)
            return os.environ.get(var_name.strip(), default)
        return os.environ.get(expr.strip(), "")

    return re.sub(r"\$\{([^}]+)\}", _replace, content)


# ---------------------------------------------------------------------------
# 类型转换辅助
# ---------------------------------------------------------------------------

_INT_KEYS   = frozenset({"concurrency", "max_tokens", "max_chunk_lines", "timeout"})
_FLOAT_KEYS = frozenset({"temperature"})


def _set_typed(d: Dict[str, Any], key: str, raw: str, env_var: str = "") -> None:
    """将字符串 raw 按 key 的语义转换为合适类型后写入 d。

    - timeout / concurrency / max_tokens / max_chunk_lines → int
    - temperature                                          → float
    - 其余                                                 → str

    转换失败时记录 warning 并跳过（保留原配置文件中的值）。
    """
    label = f"环境变量 {env_var}={raw!r}" if env_var else f"{key}={raw!r}"
    if key in _INT_KEYS:
        try:
            d[key] = int(raw)
        except ValueError:
            logger.warning(f"{label} 无法转为 int，跳过")
    elif key in _FLOAT_KEYS:
        try:
            d[key] = float(raw)
        except ValueError:
            logger.warning(f"{label} 无法转为 float，跳过")
    else:
        d[key] = raw


# ---------------------------------------------------------------------------
# base_url 规范化
# ---------------------------------------------------------------------------

# OpenAI SDK 会自动在 base_url 后追加这些路径，用户设置时常误带上，需截断
_BASE_URL_STRIP_SUFFIXES = ("/chat/completions", "/completions")


def _normalize_base_url(url: str) -> str:
    """去除 base_url 末尾被 OpenAI SDK 自动追加的 API 路径。

    常见错误：base_url = "https://api.example.com/v1/chat/completions"
    正确写法：base_url = "https://api.example.com/v1"
    """
    url = url.rstrip("/")
    for suffix in _BASE_URL_STRIP_SUFFIXES:
        if url.endswith(suffix):
            url = url[: -len(suffix)]
            logger.warning(
                "base_url 末尾含 API 路径 %r，已自动截断。"
                "请将 base_url 设置为根路径（如 https://api.example.com/v1）",
                suffix,
            )
            break
    return url




# 各 provider 专属环境变量：{provider_name: {config_key: ENV_VAR}}
_PROVIDER_ENV_MAP: Dict[str, Dict[str, str]] = {
    "openai": {
        "api_key":  "OPENAI_API_KEY",
        "model":    "OPENAI_MODEL",
        "base_url": "OPENAI_BASE_URL",
    },
    "claude": {
        "api_key":  "ANTHROPIC_API_KEY",
        "model":    "CLAUDE_MODEL",
        "base_url": "CLAUDE_BASE_URL",
    },
    "deepseek": {
        "api_key":  "DEEPSEEK_API_KEY",
        "model":    "DEEPSEEK_MODEL",
        "base_url": "DEEPSEEK_BASE_URL",
    },
    "ollama": {
        # ollama 本地服务，无需 api_key
        "model":    "OLLAMA_MODEL",
        "base_url": "OLLAMA_BASE_URL",
    },
}

# 通用字段：作用于当前激活 provider（由 llm.default_provider / LM_PROVIDER 决定）
# 优先级低于专属变量，适合统一覆盖场景
_GENERIC_PROVIDER_ENV_MAP: Dict[str, str] = {
    "LM_API_KEY":      "api_key",
    "LM_BASE_URL":     "base_url",
    "LLM_MODEL":       "model",
    "LLM_TEMPERATURE": "temperature",
    "LLM_MAX_TOKENS":  "max_tokens",
    "LLM_TIMEOUT":     "timeout",
}

# analyzer 字段
_ANALYZER_ENV_MAP: Dict[str, str] = {
    "ANALYZER_CONCURRENCY":     "concurrency",
    "ANALYZER_MAX_CHUNK_LINES": "max_chunk_lines",
}


# ---------------------------------------------------------------------------
# ConfigLoader
# ---------------------------------------------------------------------------

class ConfigLoader:
    """加载和合并配置。

    config.yml 结构：
        llm:
          default_provider: deepseek
          providers:
            deepseek:
              api_key: ...
              model: ...
              base_url: ...
              temperature: 0.2
              max_tokens: 4096
              timeout: 300
            openai: ...
            claude: ...
            ollama: ...
        analyzer:
          concurrency: 2
          max_chunk_lines: 150

    环境变量覆盖优先级（高 → 低）：
      1. 专属 provider 变量   DEEPSEEK_API_KEY / DEEPSEEK_MODEL / DEEPSEEK_BASE_URL …
      2. 通用字段             LM_API_KEY / LM_BASE_URL / LLM_MODEL /
                             LLM_TEMPERATURE / LLM_MAX_TOKENS / LLM_TIMEOUT
                             → 均作用于当前激活 provider
      3. 切换 provider        LM_PROVIDER → llm.default_provider
      4. analyzer 字段        ANALYZER_CONCURRENCY / ANALYZER_MAX_CHUNK_LINES
      5. config.yml 文件值    （兜底）
    """

    @staticmethod
    def load(config_path: str = "config.yml") -> Dict[str, Any]:
        """加载配置文件，并用环境变量覆盖字段。

        加载顺序：
          1. 自动寻找并加载 .env 文件（不覆盖 shell 中已有的同名变量）
          2. 展开 config.yaml 中的 ${VAR} / ${VAR:-default} 占位符
          3. 用环境变量覆盖对应字段

        Args:
            config_path: 配置文件路径，默认 config.yml

        Returns:
            合并后的配置字典
        """
        # 加载 .env（override=False：shell 里已有的变量优先，.env 只做补充）
        try:
            from dotenv import load_dotenv
            load_dotenv(override=False)
        except ImportError:
            logger.debug("python-dotenv 未安装，跳过 .env 加载（pip install python-dotenv）")

        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")

        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()

        config = yaml.safe_load(_expand_env_vars(raw)) or {}

        config = ConfigLoader._apply_env_overrides(config)
        ConfigLoader._validate(config)
        return config

    @staticmethod
    def _apply_env_overrides(config: Dict[str, Any]) -> Dict[str, Any]:
        llm = config.setdefault("llm", {})
        providers = llm.setdefault("providers", {})

        # Step 0: 切换 default_provider（最先处理，后续通用字段依赖它）
        lm_provider = os.environ.get("LM_PROVIDER")
        if lm_provider:
            llm["default_provider"] = lm_provider
            logger.debug(f"LM_PROVIDER → llm.default_provider = {lm_provider}")

        # Step 1: 通用字段 → 作用于当前激活 provider（低优先级，先写）
        # 必须在专属变量之前写入，确保专属变量（Step 2）可以覆盖它
        # 支持自定义 provider（如 qwen）：setdefault 自动创建 provider 条目
        active_provider = llm.get("default_provider", "")
        if active_provider:
            provider_cfg = providers.setdefault(active_provider, {})
            for env_var, config_key in _GENERIC_PROVIDER_ENV_MAP.items():
                raw = os.environ.get(env_var)
                if raw:
                    _set_typed(provider_cfg, config_key, raw, env_var)
                    logger.debug(
                        f"{env_var} → llm.providers.{active_provider}.{config_key}"
                    )

        # Step 2: 各 provider 专属环境变量（高优先级，后写覆盖通用变量）
        # DEEPSEEK_API_KEY / OPENAI_API_KEY 等只对固定 provider 生效
        for provider_name, field_map in _PROVIDER_ENV_MAP.items():
            for config_key, env_var in field_map.items():
                raw = os.environ.get(env_var)
                if raw:
                    cfg = providers.setdefault(provider_name, {})
                    _set_typed(cfg, config_key, raw, env_var)
                    logger.debug(
                        f"{env_var} → llm.providers.{provider_name}.{config_key}"
                    )

        # Step 3: analyzer 字段
        analyzer = config.setdefault("analyzer", {})
        for env_var, config_key in _ANALYZER_ENV_MAP.items():
            raw = os.environ.get(env_var)
            if raw:
                _set_typed(analyzer, config_key, raw, env_var)
                logger.debug(f"{env_var} → analyzer.{config_key}")

        # Step 4: 规范化所有 provider 的 base_url（截断误带的 /chat/completions 等）
        for prov_cfg in providers.values():
            if "base_url" in prov_cfg and prov_cfg["base_url"]:
                prov_cfg["base_url"] = _normalize_base_url(prov_cfg["base_url"])

        return config

    @staticmethod
    def _validate(config: Dict[str, Any]) -> None:
        """验证配置完整性"""
        llm_config = config.get("llm", {})

        provider = llm_config.get("default_provider", "")
        if not provider:
            raise ValueError("llm.default_provider 未配置")

        providers = llm_config.get("providers", {})
        if provider not in providers:
            raise ValueError(
                f"llm.default_provider '{provider}' 不在 providers 中，"
                f"可用: {list(providers.keys())}"
            )

        # ollama 本地服务不需要 api_key
        if provider != "ollama":
            api_key = providers[provider].get("api_key", "")
            if not api_key:
                env_hints = {
                    "openai":   "OPENAI_API_KEY",
                    "deepseek": "DEEPSEEK_API_KEY",
                    "claude":   "ANTHROPIC_API_KEY",
                }
                env_hint = env_hints.get(provider, "LM_API_KEY")
                raise ValueError(
                    f"提供者 '{provider}' 的 api_key 未配置。\n"
                    f"请在 config.yml 的 llm.providers.{provider}.api_key 中填写，"
                    f"或设置环境变量 {env_hint}。"
                )