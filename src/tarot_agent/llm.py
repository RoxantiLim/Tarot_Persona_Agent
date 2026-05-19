from __future__ import annotations

from .config import AppConfig


def deepseek_chat(config: AppConfig, messages: list[dict[str, str]], temperature: float = 0.3) -> str:
    if not config.deepseek_api_key:
        return "未配置 DEEPSEEK_API_KEY。请复制 `.env.example` 为 `.env` 并填写密钥。"
    try:
        from openai import OpenAI
    except ImportError:
        return "缺少 openai 依赖。请先安装 requirements.txt。"
    client = OpenAI(api_key=config.deepseek_api_key, base_url=config.deepseek_base_url)
    response = client.chat.completions.create(
        model=config.deepseek_model,
        messages=messages,
        temperature=temperature,
    )
    return response.choices[0].message.content or ""
