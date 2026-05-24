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

    def call_model(model: str) -> str:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
        )
        return (response.choices[0].message.content or "").strip()

    answer = call_model(config.deepseek_model)
    if answer and not _looks_like_broken_chinese(answer):
        return answer

    if config.case_extract_model and config.case_extract_model != config.deepseek_model:
        fallback_answer = call_model(config.case_extract_model)
        if fallback_answer:
            return fallback_answer

    return ""


def _looks_like_broken_chinese(text: str) -> bool:
    if not text:
        return True
    if "???" in text:
        return True
    cjk_count = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")
    question_count = text.count("?")
    return question_count >= 8 and cjk_count < 10
